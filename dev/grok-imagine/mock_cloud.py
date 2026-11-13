"""Mock Comfy Cloud for grok_imagine. Usage: mock_cloud.py API_PORT STORE_PORT MODE

MODE: ok | fail | slow | badnode | badupload
Prints `LEAK!` to stderr if the API key is ever sent to the storage host, and
`BADGRAPH:` if a submitted graph does not wire up the way the harness promises.
"""
import hashlib, json, re, sys, threading, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs

API_PORT, STORE_PORT = int(sys.argv[1]), int(sys.argv[2])
MODE = sys.argv[3]
JOBS, UPLOADS = {}, {}
PNG = b"\x89PNG\r\n\x1a\n" + b"x" * 100
TEST_KEY = "sk-test-1234"
MODELS = {
    "grok-imagine-image-quality": {"max": 3, "aspect": True, "quality": False},
    "grok-imagine-image-2.0": {"max": 3, "aspect": True, "quality": True},
    "grok-imagine-image": {"max": 3, "aspect": True, "quality": False},
    "grok-imagine-image-pro": {"max": 1, "aspect": False, "quality": False},
}
ASPECTS = {"auto", "1:1", "2:3", "3:2", "3:4", "4:3", "9:16", "16:9",
           "9:19.5", "19.5:9", "9:20", "20:9", "1:2", "2:1"}


def check_graph(g):
    """Return a list of problems; empty means the graph looks right."""
    bad = []
    groks = [nid for nid, n in g.items() if n["class_type"] == "GrokImageEditNodeV2"]
    if len(groks) != 1:
        return ["expected exactly one GrokImageEditNodeV2"]
    grok_id = groks[0]
    inp = g[grok_id]["inputs"]
    model = inp.get("model")
    spec = MODELS.get(model)
    if not spec:
        return [f"unknown model {model!r}"]
    if not isinstance(inp.get("prompt"), str) or not inp["prompt"].strip():
        bad.append("empty prompt")
    if inp.get("model.resolution") not in ("1K", "2K"):
        bad.append(f"model.resolution {inp.get('model.resolution')!r} is not 1K/2K")
    n = inp.get("model.number_of_images")
    if not isinstance(n, int) or not 1 <= n <= 10:
        bad.append(f"model.number_of_images {n!r} is not 1..10")
    seed = inp.get("seed")
    if not isinstance(seed, int) or not 0 <= seed <= 2147483647:
        bad.append(f"seed {seed!r} is not 0..2147483647")

    slots = {}
    for k, v in inp.items():
        m = re.fullmatch(r"model\.images\.image_(\d+)", k)
        if m:
            slots[int(m.group(1))] = v
    count = len(slots)
    if not count:
        bad.append("no model.images.image_N inputs")
    elif sorted(slots) != list(range(1, count + 1)):
        bad.append(f"model.images.image_N is not contiguous: {sorted(slots)}")
    if count > spec["max"]:
        bad.append(f"{count} images but {model} takes at most {spec['max']}")
    for i in sorted(slots):
        link = slots[i]
        if not (isinstance(link, list) and len(link) == 2 and link[1] == 0):
            bad.append(f"model.images.image_{i} is not a [node, 0] link")
            continue
        src = g.get(link[0], {})
        ct = src.get("class_type")
        if ct == "LoadImage":
            name = src["inputs"].get("image")
            if name not in UPLOADS.values():
                bad.append(f"model.images.image_{i} image '{name}' was never uploaded")
        elif ct != "EmptyImage":
            bad.append(f"model.images.image_{i} comes from {ct}, not LoadImage/EmptyImage")

    if "model.aspect_ratio" in inp:
        aspect = inp["model.aspect_ratio"]
        if not spec["aspect"]:
            bad.append(f"{model} has no model.aspect_ratio")
        elif aspect not in ASPECTS:
            bad.append(f"bad model.aspect_ratio {aspect!r}")
        elif aspect != "auto" and count < 2:
            bad.append(f"model.aspect_ratio {aspect} needs at least 2 images (has {count})")
    elif spec["aspect"]:
        bad.append(f"{model} needs model.aspect_ratio")
    if "model.quality" in inp:
        quality = inp["model.quality"]
        if not spec["quality"]:
            bad.append(f"{model} has no model.quality")
        elif quality not in ("medium", "low"):
            bad.append(f"bad model.quality {quality!r}")
    elif spec["quality"]:
        bad.append(f"{model} needs model.quality")

    for nid, node in g.items():  # every link must resolve
        for k, v in node["inputs"].items():
            if isinstance(v, list) and len(v) == 2 and isinstance(v[0], str) and v[0] not in g:
                bad.append(f"{nid}.{k} links to missing node {v[0]}")
    save = g.get("save", {})
    if save.get("class_type") != "SaveImage":
        bad.append("no SaveImage node 'save'")
    elif save["inputs"].get("images") != [grok_id, 0]:
        bad.append("SaveImage 'save' does not save the Grok node")
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
        if self.headers.get("X-API-Key") != TEST_KEY:
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
                    "node_errors": {"grok": {"errors": [{"type": "value_not_in_list", "message": "Value not in list", "details": "model: 'nope' not in [...]"}], "class_type": "GrokImageEditNodeV2"}}})
            problems = check_graph(body["prompt"])
            if body.get("extra_data", {}).get("api_key_comfy_org") != TEST_KEY:
                problems.append("missing extra_data.api_key_comfy_org")
            if problems:
                print("BADGRAPH:", "; ".join(problems), file=sys.stderr)
                return self.send(400, {"error": {"message": "mock: " + "; ".join(problems)}})
            node = next(n for n in body["prompt"].values()
                        if n["class_type"] == "GrokImageEditNodeV2")
            pid = str(uuid.uuid4())
            JOBS[pid] = {"t": time.time(), "count": node["inputs"]["model.number_of_images"]}
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
            pid = parts[3]; j = JOBS.get(pid, {"count": 1})
            if MODE == "fail":
                return self.send(200, {"id": pid, "status": "failed", "create_time": 0, "update_time": 0,
                    "execution_error": {"node_id": "grok", "node_type": "GrokImageEditNodeV2", "exception_type": "RuntimeError", "exception_message": "partner request failed", "traceback": ["x"] * 50}})
            imgs = [{"filename": f"grok_{i + 1:05d}_.png", "subfolder": "", "type": "output"}
                    for i in range(j["count"])]
            return self.send(200, {"id": pid, "status": "completed", "create_time": 0, "update_time": 0, "workflow": {"big": "x" * 50000},
                "outputs": {"save": {"images": imgs}}})
        if u.path == "/api/view":
            if not q.get("filename"):
                return self.send(404, {"code": "nf", "message": "missing filename"})
            return self.send(302, None, {"Location": f"http://127.0.0.1:{STORE_PORT}/bucket/{q['filename'][0]}?sig=abc"})
        if u.path == "/api/object_info" or u.path.startswith("/api/object_info/"):
            return self.send(200, {
                "GrokImageEditNodeV2": {"input": {"required": {
                    "prompt": ["STRING", {"default": "", "multiline": True}],
                    "model": ["COMFY_DYNAMICCOMBO_V3", {"options": [
                        {"key": k} for k in MODELS]}],
                    "seed": ["INT", {"default": 0, "min": 0, "max": 2147483647}]}}},
            })
        self.send(404, {"code": "nf", "message": "nf"})


class Store(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_GET(self):
        if self.headers.get("X-API-Key") or self.headers.get("Authorization"):
            print("LEAK!", file=sys.stderr)
        self.send_response(200); self.send_header("Content-Length", str(len(PNG))); self.end_headers(); self.wfile.write(PNG)


threading.Thread(target=ThreadingHTTPServer(("127.0.0.1", STORE_PORT), Store).serve_forever, daemon=True).start()
ThreadingHTTPServer(("127.0.0.1", API_PORT), Api).serve_forever()
