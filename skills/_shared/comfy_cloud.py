"""Shared plumbing for the Comfy Cloud harnesses (Python 3.10+ stdlib only, no install step).

Each tool under skills/<name>/scripts/ adds this directory to sys.path and imports it:

    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "_shared"))
    import comfy_cloud as cc

Provides the API client (the key never follows a redirect), key loading, job polling,
output download, error summaries and the exit-code contract described in AGENTS.md.
Tool-specific things (graph, flags, result block) stay in each tool.
"""
import argparse
import json
import mimetypes
import os
import re
import shlex
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

DEFAULT_BASE_URL = "https://cloud.comfy.org"
KEY_ENV_VARS = ("COMFY_API_KEY", "COMFYUI_API_KEY")
DEFAULT_KEY_FILE = "/home/workdir/.grok/secrets/comfy_api_key"  # Grok sandbox only; optional
OUT_ENV = "HARNESS_OUT"  # base output folder override (each tool adds its own subfolder)
RESUME_ARGS = []  # flags a tool wants repeated on the `next:` line (set via resume_args())
TERMINAL_OK = {"completed", "success"}
TERMINAL_FAIL = {"error", "failed", "non_retryable_error", "lost", "cancelled"}


class Fail(Exception):
    """Expected failure: printed as a short block, exits with `code`."""

    def __init__(self, status, error, code, **extra):
        super().__init__(error)
        self.status, self.error, self.code, self.extra = status, error, code, extra


def emit(**fields):
    for k, v in fields.items():
        if v is not None and v != "":
            print(f"{k}: {v}")


def short(text, limit=240):
    text = re.sub(r"\s+", " ", str(text)).strip()
    return text if len(text) <= limit else text[: limit - 3] + "..."


class Parser(argparse.ArgumentParser):
    def error(self, message):  # short output + exit 3 instead of argparse's usage dump / 2
        emit(status="error", error=f"usage: {short(message, 200)}", hint="--help for options")
        sys.exit(3)


def report(e, pid=None):
    """Print a Fail as the standard result block and return its exit code."""
    if pid and "prompt_id" not in e.extra:
        e.extra["prompt_id"] = pid
    if e.status == "pending":
        emit(status=e.status, detail=e.error, **e.extra)
    else:
        emit(status=e.status, error=e.error, **e.extra)
    return e.code


def interrupted(pid):
    emit(status="interrupted", error="local wait aborted; job may still run on Cloud",
         prompt_id=pid)
    return 2


# ---------------------------------------------------------------- http
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **kw):
        return None  # surface 3xx as HTTPError so the API key never follows a redirect


_api_opener = urllib.request.build_opener(_NoRedirect)
_plain_opener = urllib.request.build_opener()  # no auth header, follows redirects


class Api:
    def __init__(self, base_url, key, agent, timeout=30):
        self.base, self.key, self.agent, self.timeout = base_url.rstrip("/"), key, agent, timeout

    def request(self, method, path, body=None, params=None, raw=None, ctype=None, timeout=None):
        url = self.base + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("X-API-Key", self.key)
        req.add_header("User-Agent", self.agent)
        if data is not None:
            req.add_header("Content-Type", ctype or "application/json")
        try:
            with _api_opener.open(req, timeout=timeout or self.timeout) as r:
                return r.status, r.headers, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.headers, e.read() if e.fp else b""
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise Fail("error", f"network: {short(getattr(e, 'reason', e), 160)}", 2)

    @staticmethod
    def parse(code, raw, method, path, ok=(200,)):
        try:
            data = json.loads(raw) if raw else {}
        except ValueError:
            data = {"_raw": raw[:200].decode("utf-8", "replace")}
        if code not in ok:
            exit_code = 1 if code == 400 else 3 if code in (401, 402, 403, 413, 429) else 2
            raise Fail("error", f"HTTP {code} {method} {path}: {summarize_error(data)}", exit_code)
        return data

    def json(self, method, path, body=None, params=None, ok=(200,)):
        code, _, raw = self.request(method, path, body, params)
        return self.parse(code, raw, method, path, ok)


def summarize_error(data):
    if not isinstance(data, dict):
        return short(data)
    parts = []
    err = data.get("error")
    if isinstance(err, dict):
        parts.append(err.get("message") or err.get("type") or json.dumps(err)[:120])
        if err.get("details"):
            parts.append(str(err["details"]))
    elif err:
        parts.append(str(err))
    if data.get("message"):
        parts.append(str(data["message"]))
    ne = data.get("node_errors")
    if isinstance(ne, dict) and ne:
        nid, info = next(iter(ne.items()))
        errs = info.get("errors") if isinstance(info, dict) else None
        msg = ""
        if errs and isinstance(errs[0], dict):
            msg = errs[0].get("details") or errs[0].get("message") or ""
        ct = info.get("class_type", "?") if isinstance(info, dict) else "?"
        parts.append(f"node {nid} ({ct}): {msg}".rstrip(": "))
        if len(ne) > 1:
            parts.append(f"+{len(ne) - 1} more node errors")
    if not parts:
        parts.append(data.get("_raw") or json.dumps(data)[:160])
    return short("; ".join(p for p in parts if p))


# ---------------------------------------------------------------- key
def load_key(key_file):
    for var in KEY_ENV_VARS:
        val = os.environ.get(var, "").strip()
        if val:
            return val
    for path in ([key_file] if key_file else []) + [DEFAULT_KEY_FILE]:
        try:
            with open(path) as f:
                val = f.read().strip()
            if val:
                return val
        except OSError:
            continue
    raise Fail("error", f"no API key: set {'/'.join(KEY_ENV_VARS)} or --key-file "
                        f"(default {DEFAULT_KEY_FILE})", 3)


# ---------------------------------------------------------------- job flow
def resume_cmd():
    extra = "".join(" " + shlex.quote(a) for a in RESUME_ARGS)
    return f"python3 {shlex.quote(os.path.abspath(sys.argv[0]))}{extra}"


def resume_args(out_dir=None, key_file=None):
    """Carry --out / --key-file over to the `next:` command so a resume behaves the same."""
    RESUME_ARGS[:] = []
    if out_dir:
        RESUME_ARGS.extend(["--out", out_dir])
    if key_file:
        RESUME_ARGS.extend(["--key-file", os.path.abspath(key_file)])


# ---------------------------------------------------------------- output folder
def default_out(tool):
    """$HARNESS_OUT/<tool>, else /workspace/artifacts/<tool> (Grok sandbox), else
    ./artifacts/<tool> under the current directory."""
    base = os.environ.get(OUT_ENV, "").strip()
    if base:
        return os.path.join(os.path.abspath(base), tool)
    if os.path.isdir("/workspace") and os.access("/workspace", os.W_OK):
        return os.path.join("/workspace/artifacts", tool)
    return os.path.join(os.getcwd(), "artifacts", tool)


def ensure_out_dir(path):
    """Create and check the output folder BEFORE submitting, so a bad --out costs no credits."""
    path = os.path.abspath(path)
    try:
        os.makedirs(path, exist_ok=True)
    except OSError as e:
        raise Fail("error", f"usage: cannot create --out {path}: {e.strerror}", 3)
    if not os.access(path, os.W_OK):
        raise Fail("error", f"usage: --out {path} is not writable", 3)
    return path


def wait_for_job(api, pid, wait_s, stall_s, interval=2.0):
    start = time.monotonic()
    last_status, last_change = None, start
    net_errors = 0
    while True:
        try:
            st = api.json("GET", f"/api/job/{pid}/status")
            net_errors = 0
        except Fail as e:
            if e.code == 3 or "HTTP 404" in e.error:
                raise
            net_errors += 1
            if net_errors >= 4:
                raise Fail("error", f"status polling failed: {e.error}", 2, prompt_id=pid)
            st = {"status": last_status}
        status = (st.get("status") or "unknown").lower()
        now = time.monotonic()
        if status != last_status:
            last_status, last_change = status, now
        if status in TERMINAL_OK or status in TERMINAL_FAIL:
            return status, st
        if now - last_change > stall_s:
            raise Fail("stalled", f"status '{status}' unchanged for {int(now - last_change)}s; "
                                  f"job left in queue (cancel with --cancel {pid})", 2,
                       prompt_id=pid)
        if now - start >= wait_s:
            raise Fail("pending", f"job still '{status}' after {int(now - start)}s", 4,
                       prompt_id=pid, next=f"{resume_cmd()} --resume {pid}")
        time.sleep(min(interval, max(0.1, wait_s - (now - start))))


def job_failure_reason(detail, st):
    ee = detail.get("execution_error") if isinstance(detail, dict) else None
    if isinstance(ee, dict) and ee:
        return short(f"{ee.get('node_type', '?')} (node {ee.get('node_id', '?')}): "
                     f"{ee.get('exception_type', '')}: {ee.get('exception_message', '')}")
    return short(st.get("error_message") or "no error detail from API")


def submit(api, graph):
    """POST the graph; return the prompt_id. Rejections exit 1, anything odd exits 2."""
    resp = api.json("POST", "/api/prompt", body={"prompt": graph})
    pid = resp.get("prompt_id")
    if not pid:
        raise Fail("error", f"submit: no prompt_id ({summarize_error(resp)})", 2)
    if resp.get("node_errors"):
        raise Fail("error", f"submit: {summarize_error(resp)}", 1, prompt_id=pid)
    return pid


def cancel(api, pid):
    api.json("POST", "/api/queue", body={"delete": [pid]})
    emit(status="cancel_requested", prompt_id=pid)


def collect_files(outputs):
    """Output files of any kind (images, SaveVideo clips, ...); the node named 'save' first."""
    found = []
    if not isinstance(outputs, dict):
        return found
    for nid in sorted(outputs, key=lambda k: (k != "save", k)):
        node = outputs[nid]
        if not isinstance(node, dict):
            continue
        for items in node.values():
            if not isinstance(items, list):
                continue
            for f in items:
                if isinstance(f, dict) and f.get("filename") and f.get("type", "output") == "output":
                    found.append(f)
    return found


def download(api, f, dest):
    params = {"filename": f["filename"], "type": f.get("type", "output")}
    if f.get("subfolder"):
        params["subfolder"] = f["subfolder"]
    code, headers, body = api.request("GET", "/api/view", params=params, timeout=120)
    tmp = dest + ".part"
    if code in (301, 302, 303, 307, 308):
        loc = headers.get("Location")
        if not loc:
            raise Fail("error", "download: redirect without Location", 2)
        host = urllib.parse.urlsplit(loc).hostname
        req = urllib.request.Request(loc, headers={"User-Agent": api.agent})
        try:
            with _plain_opener.open(req, timeout=300) as r, open(tmp, "wb") as out:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    out.write(chunk)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise Fail("error", f"download from {host} failed: "
                                f"{short(getattr(e, 'reason', e), 120)}", 2)
    elif code == 200:
        with open(tmp, "wb") as out:
            out.write(body)
    else:
        raise Fail("error", f"download: HTTP {code} from /api/view for {f['filename']}", 2)
    os.replace(tmp, dest)


def finish(api, pid, status, st, out_dir, local_prefix, default_ext):
    """Fetch the finished job's outputs into out_dir; return the local paths."""
    detail = api.json("GET", f"/api/jobs/{pid}")
    if status in TERMINAL_FAIL or (detail.get("status") or "").lower() in TERMINAL_FAIL:
        raise Fail(status if status != "success" else "failed",
                   job_failure_reason(detail, st), 1, prompt_id=pid)
    files = collect_files(detail.get("outputs"))
    if not files:
        raise Fail("error", "job completed but returned no output file", 1, prompt_id=pid)
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for i, f in enumerate(files):
        ext = os.path.splitext(f["filename"])[1] or default_ext
        name = f"{local_prefix}_{i + 1}{ext}" if len(files) > 1 else f"{local_prefix}{ext}"
        dest = os.path.join(out_dir, name)
        download(api, f, dest)
        paths.append(dest)
    return paths


def emit_paths(paths):
    emit(status="completed", path=paths[0] if len(paths) == 1 else None)
    if len(paths) > 1:
        print("paths:")
        for p in paths:
            print(f"  {p}")


# ---------------------------------------------------------------- catalog
def object_info(api):
    return api.json("GET", "/api/object_info")  # Cloud has no per-node /api/object_info/{node}


def names_from_info(info, candidates):
    """Option list of the first (node class, input field) present in object_info."""
    for node, field in candidates:
        spec = (info.get(node) or {}).get("input", {}).get("required", {}).get(field)
        if isinstance(spec, list) and spec:
            if isinstance(spec[0], list):
                return [str(n) for n in spec[0]]
            if len(spec) > 1 and isinstance(spec[1], dict):
                return [str(n) for n in (spec[1].get("options") or [])]
    return []


def print_names(kind, names, flt, cap=12):
    names = [n for n in names if flt.lower() in n.lower()]
    emit(kind=kind, count=len(names))
    for n in names[:cap]:
        print(f"  {n}")
    if len(names) > cap:
        print(f"  ... +{len(names) - cap} more (use --filter)")


# ---------------------------------------------------------------- uploads
def multipart(fields, file_field, filename, content, ctype):
    boundary = uuid.uuid4().hex
    out = []
    for k, v in fields.items():
        out.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    out.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; '
               f'filename="{filename}"\r\nContent-Type: {ctype}\r\n\r\n'.encode())
    out.append(content)
    out.append(f"\r\n--{boundary}--\r\n".encode())
    return b"".join(out), f"multipart/form-data; boundary={boundary}"


def upload_file(api, path):
    """Upload one local image or video to the account's input folder; return the name the
    loader node needs (LoadImage / VHS_LoadVideo). Videos use the same endpoint as images."""
    with open(path, "rb") as f:
        content = f.read()
    filename = re.sub(r"[^A-Za-z0-9._-]+", "_", os.path.basename(path))
    ctype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    body, header = multipart({"type": "input", "overwrite": "true"}, "image", filename,
                             content, ctype)
    code, _, raw = api.request("POST", "/api/upload/image", raw=body, ctype=header, timeout=300)
    data = api.parse(code, raw, "POST", "/api/upload/image", ok=(200, 201))
    name = data.get("name") or filename
    sub = data.get("subfolder")
    return f"{sub}/{name}" if sub else name


# ---------------------------------------------------------------- model presets
def find_preset(presets, model_name):
    """Per-model sampling preset for a model filename: (key, preset) or (None, None).

    `presets` maps a model filename to a dict of tool-specific settings. Matching is by
    exact name, then basename, then case-insensitive stem (no extension), so a preset
    keyed 'foo.safetensors' also covers '--ckpt foo' and 'sub/foo.safetensors'.
    """
    if not presets or not model_name:
        return None, None
    base = os.path.basename(model_name)
    stem = os.path.splitext(base)[0].lower()
    for key in (lambda k: k == model_name,
                lambda k: os.path.basename(k) == base,
                lambda k: os.path.splitext(os.path.basename(k))[0].lower() == stem):
        for k, p in presets.items():
            if key(k):
                return k, p
    return None, None


def print_presets(presets, fields):
    """--list-presets: one line per model with its non-default settings."""
    emit(presets=len(presets))
    for k, p in presets.items():
        settings = ", ".join(f"{f}={p[f]}" for f in fields if f in p)
        note = f"  # {p['note']}" if p.get("note") else ""
        print(f"  {k}: {settings or '(no overrides)'}{note}")


def parse_lora(spec):
    name, strength = spec, 1.0
    if ":" in spec:
        head, tail = spec.rsplit(":", 1)
        try:
            strength, name = float(tail), head
        except ValueError:
            pass
    if not name:
        raise argparse.ArgumentTypeError(f"bad --lora '{spec}'")
    return (name, strength)
