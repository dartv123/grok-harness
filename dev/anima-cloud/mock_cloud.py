import json, sys, threading, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs
API_PORT, STORE_PORT = int(sys.argv[1]), int(sys.argv[2])
MODE = sys.argv[3]  # ok | fail | slow | badnode
JOBS = {}; LEAKS = []
PNG = b"\x89PNG\r\n\x1a\n" + b"x" * 100
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
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path == "/api/prompt":
            if MODE == "badnode":
                return self.send(400, {"error": {"type": "prompt_outputs_failed_validation", "message": "Prompt outputs failed validation", "details": ""},
                    "node_errors": {"unet": {"errors": [{"type": "value_not_in_list", "message": "Value not in list", "details": "unet_name: 'divingAnima_v90.safetensors' not in [...]"}], "class_type": "UNETLoader"}}})
            pid = str(uuid.uuid4()); JOBS[pid] = {"t": time.time(), "batch": body["prompt"]["latent"]["inputs"]["batch_size"]}
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
            st = "pending" if age < 1 else "in_progress" if (age < 3 or MODE == "slow") else ("error" if MODE == "fail" else "completed")
            return self.send(200, {"id": pid, "status": st, "created_at": "x", "updated_at": "x", "error_message": "CUDA OOM" if st == "error" else None})
        if u.path.startswith("/api/jobs/"):
            pid = parts[3]; j = JOBS[pid]
            if MODE == "fail":
                return self.send(200, {"id": pid, "status": "failed", "create_time": 0, "update_time": 0,
                    "execution_error": {"node_id": "sampler", "node_type": "KSampler", "exception_type": "torch.OutOfMemoryError", "exception_message": "CUDA out of memory", "traceback": ["x"] * 50, "current_inputs": {}, "current_outputs": {}}})
            imgs = [{"filename": f"anima_base_{i:05}_.png", "subfolder": "", "type": "output"} for i in range(j["batch"])]
            return self.send(200, {"id": pid, "status": "completed", "create_time": 0, "update_time": 0, "workflow": {"big": "x" * 50000},
                "outputs": {"save": {"images": imgs}, "preview": {"images": [{"filename": "tmp.png", "type": "temp"}]}}})
        if u.path == "/api/view":
            return self.send(302, None, {"Location": f"http://127.0.0.1:{STORE_PORT}/bucket/{q['filename'][0]}?sig=abc"})
        if u.path.startswith("/api/object_info/"):
            return self.send(200, {"UNETLoader": {"input": {"required": {"unet_name": ["COMBO", {"options": [f"model_{i}.safetensors" for i in range(40)] + ["divingAnima_v90.safetensors"]}]}}}})
        self.send(404, {"code": "nf", "message": "nf"})
class Store(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        if self.headers.get("X-API-Key") or self.headers.get("Authorization"): LEAKS.append(self.path); print("LEAK!", file=sys.stderr)
        self.send_response(200); self.send_header("Content-Length", str(len(PNG))); self.end_headers(); self.wfile.write(PNG)
threading.Thread(target=ThreadingHTTPServer(("127.0.0.1", STORE_PORT), Store).serve_forever, daemon=True).start()
ThreadingHTTPServer(("127.0.0.1", API_PORT), Api).serve_forever()
