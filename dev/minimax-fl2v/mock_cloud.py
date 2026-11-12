"""Mock Comfy Cloud for minimax_fl2v. Usage: mock_cloud.py API_PORT STORE_PORT MODE

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
    nodes = [n for n in g.values() if n["class_type"] == "MiniMaxH3ImageToVideo"]
    if len(nodes) != 1:
        return ["expected exactly one MiniMaxH3ImageToVideo"]
    inp = nodes[0]["inputs"]
    if not isinstance(inp.get("prompt"), str) or not inp["prompt"]:
        bad.append("empty prompt")
    if not isinstance(inp.get("length"), int) or inp["length"] % 17 != 5:
        bad.append(f"length {inp.get('length')} is not 5 mod 17")
    frames = [k for k in ("first_frame", "last_frame") if k in inp]
    if not frames:
        bad.append("no first_frame or last_frame")
    for k in frames:
        scaled = g.get(inp[k][0], {})
        if scaled.get("class_type") != "ImageScaleToTotalPixels":
            bad.append(f"{k} is not scaled with ImageScaleToTotalPixels"); continue
        if scaled["inputs"].get("resolution_steps") != 32:
            bad.append(f"{k} scale is not in steps of 32")
        load = g.get(scaled["inputs"]["image"][0], {})
        if load.get("class_type") != "LoadImage":
            bad.append(f"{k} does not come from a LoadImage")
        elif load["inputs"]["image"] not in UPLOADS.values():
            bad.append(f"{k} image '{load['inputs']['image']}' was never uploaded")
    for dim, slot in (("width", 0), ("height", 1)):
        src_node, s = inp.get(dim, [None, None])
        if g.get(src_node, {}).get("class_type") != "GetImageSize" or s != slot:
            bad.append(f"{dim} is not GetImageSize output {slot}")
    cv = [n for n in g.values() if n["class_type"] == "CreateVideo"]
    if len(cv) != 1 or g.get(cv[0]["inputs"]["audio"][0], {}).get("class_type") != "VAEDecodeAudio":
        bad.append("CreateVideo audio is not the generated track")
    for nid, n in g.items():  # every link must resolve
        for k, v in n["inputs"].items():
            if isinstance(v, list) and len(v) == 2 and isinstance(v[0], str) and v[0] not in g:
                bad.append(f"{nid}.{k} links to missing node {v[0]}")
    if g.get("save", {}).get("class_type") != "SaveVideo":
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
            vid = {"filename": "fl2v_00001_.mp4", "subfolder": "video", "type": "output"}
            return self.send(200, {"id": pid, "status": "completed", "create_time": 0, "update_time": 0, "workflow": {"big": "x" * 50000},
                "outputs": {"save": {"images": [vid], "animated": [True]}}})
        if u.path == "/api/view":
            if q.get("subfolder") != ["video"]:
                return self.send(404, {"code": "nf", "message": "wrong subfolder"})
            return self.send(302, None, {"Location": f"http://127.0.0.1:{STORE_PORT}/bucket/{q['filename'][0]}?sig=abc"})
        if u.path == "/api/object_info" or u.path.startswith("/api/object_info/"):
            return self.send(200, {
                "UNETLoader": {"input": {"required": {"unet_name": ["COMBO", {"options":
                    ["model_a.safetensors", "minimax_h3_fl2va_pruned_int8_convrot.safetensors"]}]}}},
                "LoraLoaderModelOnly": {"input": {"required": {"lora_name": ["COMBO", {"options":
                    ["example_style_a.safetensors", "minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors"]}]}}},
                "KSamplerSelect": {"input": {"required": {"sampler_name": ["COMBO", {"options": ["euler", "res_multistep"]}]}}},
                "BasicScheduler": {"input": {"required": {"scheduler": ["COMBO", {"options": ["simple", "beta"]}]}}},
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
