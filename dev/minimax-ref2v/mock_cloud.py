"""Mock Comfy Cloud for minimax_ref2v. Usage: mock_cloud.py API_PORT STORE_PORT MODE

MODE: ok | fail | slow | badnode | badupload
Prints `LEAK!` to stderr if the API key is ever sent to the storage host, and
`BADGRAPH:` if a submitted graph does not wire up the way the harness promises.
"""
import hashlib, json, sys, threading, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs

API_PORT, STORE_PORT = int(sys.argv[1]), int(sys.argv[2])
MODE = sys.argv[3]
JOBS, UPLOADS = {}, {}
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"v" * 4096


def check_graph(g):
    """Return a list of problems; empty means the graph looks right."""
    bad = []
    refs = [n for n in g.values() if n["class_type"] == "MiniMaxH3ReferenceToVideo"]
    if len(refs) != 1:
        return ["expected exactly one MiniMaxH3ReferenceToVideo"]
    inp = refs[0]["inputs"]
    if not isinstance(inp.get("prompt"), str) or not inp["prompt"]:
        bad.append("empty prompt")
    if not isinstance(inp.get("length"), int) or inp["length"] % 17 != 5:
        bad.append(f"length {inp.get('length')} is not 5 mod 17")
    slots = sorted(k for k in inp if k.startswith("ref_images.ref_image_"))
    if not slots and not any(k.startswith("ref_videos.") for k in inp):
        bad.append("no image or video references")
    for k in slots:
        node = g.get(inp[k][0])
        if not node or node["class_type"] != "LoadImage":
            bad.append(f"{k} does not point at a LoadImage")
        elif node["inputs"]["image"] not in UPLOADS.values() and not node["inputs"]["image"].endswith(".png"):
            bad.append(f"{k} image '{node['inputs']['image']}' was never uploaded")
    vids = sorted(k for k in inp if k.startswith("ref_videos.ref_video_"))
    for k in vids:
        src, slot = inp[k]
        node = g.get(src)
        if not node or node["class_type"] != "VHS_LoadVideo" or slot != 0:
            bad.append(f"{k} is not wired to a VHS_LoadVideo IMAGE output")
            continue
        if node["inputs"]["video"] not in UPLOADS.values():
            bad.append(f"{k} video '{node['inputs']['video']}' was never uploaded")
        for f in ("frame_load_cap", "skip_first_frames", "custom_width", "custom_height"):
            if not isinstance(node["inputs"].get(f), int) or node["inputs"][f] < 0:
                bad.append(f"{src} {f} is not a non-negative int")
        if not isinstance(node["inputs"].get("force_rate"), (int, float)) or not 0 <= node["inputs"]["force_rate"] <= 60:
            bad.append(f"{src} force_rate is not 0..60")
    if any(k.startswith("ref_audios.") for k in inp):
        bad.append("ref_audios is for standalone audio; a video's soundtrack goes to ref_video_audios")
    for k in sorted(k for k in inp if k.startswith("ref_video_audios.ref_video_audio_")):
        src, slot = inp[k]
        n = k.rsplit("_", 1)[1]
        if g.get(src, {}).get("class_type") != "VHS_LoadVideo" or slot != 2:
            bad.append(f"{k} is not wired to a VHS_LoadVideo AUDIO output")
        elif inp.get(f"ref_videos.ref_video_{n}", [None])[0] != src:
            bad.append(f"{k} is not the soundtrack of ref_video_{n}")
    cv = [n for n in g.values() if n["class_type"] == "CreateVideo"]
    if len(cv) != 1:
        bad.append("expected exactly one CreateVideo")
    else:
        src, slot = cv[0]["inputs"]["audio"]
        kind = g.get(src, {}).get("class_type")
        if not ((kind == "VAEDecodeAudio" and slot == 0) or (kind == "VHS_LoadVideo" and slot == 2)):
            bad.append("CreateVideo audio is neither the generated track nor a video soundtrack")
    for nid, n in g.items():  # every link must resolve
        for k, v in n["inputs"].items():
            if isinstance(v, list) and len(v) == 2 and isinstance(v[0], str) and v[0] not in g:
                bad.append(f"{nid}.{k} links to missing node {v[0]}")
    if g["save"]["class_type"] != "SaveVideo":
        bad.append("no SaveVideo node 'save'")
    return bad


def parse_multipart(ctype, raw):
    boundary = ctype.split("boundary=")[1].encode()
    fields, files = {}, {}
    for part in raw.split(b"--" + boundary):
        if b"\r\n\r\n" not in part:
            continue
        head, _, body = part.partition(b"\r\n\r\n")
        body = body[:-2] if body.endswith(b"\r\n") else body
        head = head.decode("utf-8", "replace")
        name = head.split('name="')[1].split('"')[0]
        if 'filename="' in head:
            files[name] = (head.split('filename="')[1].split('"')[0], body)
        else:
            fields[name] = body.decode()
    return fields, files


class Api(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def send(self, code, obj=None, headers=None):
        self.send_response(code)
        for k, v in (headers or {}).items(): self.send_header(k, v)
        body = json.dumps(obj).encode() if obj is not None else b""
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def auth(self):
        if self.headers.get("X-API-Key") != "sk-test-1234":
            self.send(401, {"code": "unauthorized", "message": "bad key"}); return False
        return True

    def do_POST(self):
        if not self.auth(): return
        raw = self.rfile.read(int(self.headers["Content-Length"]))
        if self.path == "/api/upload/image":
            if MODE == "badupload":
                return self.send(413, {"message": "file too large"})
            fields, files = parse_multipart(self.headers["Content-Type"], raw)
            if "image" not in files or fields.get("type") != "input":
                return self.send(400, {"message": "bad upload form"})
            fname, content = files["image"]
            name = hashlib.sha256(content).hexdigest() + "." + fname.rsplit(".", 1)[-1]
            UPLOADS[fname] = name
            return self.send(200, {"name": name, "subfolder": "", "type": "input"})
        body = json.loads(raw)
        if self.path == "/api/prompt":
            if MODE == "badnode":
                return self.send(400, {"error": {"type": "prompt_outputs_failed_validation", "message": "Prompt outputs failed validation", "details": ""},
                    "node_errors": {"unet": {"errors": [{"type": "value_not_in_list", "message": "Value not in list", "details": "unet_name: 'nope.safetensors' not in [...]"}], "class_type": "UNETLoader"}}})
            problems = check_graph(body["prompt"])
            if problems:
                print("BADGRAPH:", "; ".join(problems), file=sys.stderr)
                return self.send(400, {"error": {"message": "mock: " + "; ".join(problems)}})
            pid = str(uuid.uuid4()); JOBS[pid] = {"t": time.time()}
            return self.send(200, {"prompt_id": pid, "number": 1, "node_errors": {}})
        if self.path == "/api/queue":
            return self.send(200, {})
        self.send(404, {"code": "nf", "message": "nf"})

    def do_GET(self):
        if not self.auth(): return
        u = urlsplit(self.path); q = parse_qs(u.query); parts = u.path.split("/")
        if u.path.startswith("/api/job/") and u.path.endswith("/status"):
            pid = parts[3]; j = JOBS.get(pid)
            if not j: return self.send(404, {"code": "nf", "message": "job not found"})
            age = time.time() - j["t"]
            st = "pending" if age < 1 else "in_progress" if (age < 4 or MODE == "slow") else ("error" if MODE == "fail" else "completed")
            return self.send(200, {"id": pid, "status": st, "created_at": "x", "updated_at": "x", "error_message": "CUDA OOM" if st == "error" else None})
        if u.path.startswith("/api/jobs/"):
            pid = parts[3]
            if MODE == "fail":
                return self.send(200, {"id": pid, "status": "failed", "create_time": 0, "update_time": 0,
                    "execution_error": {"node_id": "sampler", "node_type": "SamplerCustomAdvanced", "exception_type": "torch.OutOfMemoryError", "exception_message": "CUDA out of memory", "traceback": ["x"] * 50}})
            vid = {"filename": "ref2v_00001_.mp4", "subfolder": "video", "type": "output"}
            return self.send(200, {"id": pid, "status": "completed", "create_time": 0, "update_time": 0, "workflow": {"big": "x" * 50000},
                "outputs": {"save": {"images": [vid], "animated": [True]}}})
        if u.path == "/api/view":
            if q.get("subfolder") != ["video"]:
                return self.send(404, {"code": "nf", "message": "wrong subfolder"})
            return self.send(302, None, {"Location": f"http://127.0.0.1:{STORE_PORT}/bucket/{q['filename'][0]}?sig=abc"})
        if u.path == "/api/object_info" or u.path.startswith("/api/object_info/"):
            return self.send(200, {
                "UNETLoader": {"input": {"required": {"unet_name": ["COMBO", {"options":
                    ["model_a.safetensors", "TenStrip__10Eros-Max__10Eros_Max_h3_8stepTURBO_beta6_int8.safetensors"]}]}}},
                "LoraLoaderModelOnly": {"input": {"required": {"lora_name": ["COMBO", {"options":
                    ["example_style_a.safetensors", "minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors"]}]}}},
                "ResolutionSelector": {"input": {"required": {"aspect_ratio": ["COMBO", {"options":
                    ["1:1 (Square)", "2:3 (Portrait Photo)", "3:2 (Photo)", "3:4 (Portrait Standard)", "4:3 (Standard)",
                     "9:16 (Portrait Widescreen)", "16:9 (Widescreen)", "21:9 (Ultrawide)"]}]}}},  # as on Cloud, 2026-11
            })
        self.send(404, {"code": "nf", "message": "nf"})


class Store(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_GET(self):
        if self.headers.get("X-API-Key") or self.headers.get("Authorization"):
            print("LEAK!", file=sys.stderr)
        self.send_response(200); self.send_header("Content-Length", str(len(MP4))); self.end_headers(); self.wfile.write(MP4)


threading.Thread(target=ThreadingHTTPServer(("127.0.0.1", STORE_PORT), Store).serve_forever, daemon=True).start()
ThreadingHTTPServer(("127.0.0.1", API_PORT), Api).serve_forever()
