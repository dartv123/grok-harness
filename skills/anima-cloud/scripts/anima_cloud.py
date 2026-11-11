#!/usr/bin/env python3
"""anima_cloud - submit a baked Anima workflow to Comfy Cloud and fetch the result.

Single file, Python 3.10+ stdlib only. Prints a short `key: value` block.

Exit codes: 0 completed | 1 job failed/cancelled or workflow rejected (HTTP 400)
            2 network/server/stall error | 3 usage, key, credits or auth error
            4 still pending (use --resume <prompt_id>)
"""
import argparse
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

VERSION = "1.1.0"
DEFAULT_BASE_URL = "https://cloud.comfy.org"
DEFAULT_OUT = "/workspace/artifacts/anima"
KEY_ENV_VARS = ("COMFY_API_KEY", "COMFYUI_API_KEY")
DEFAULT_KEY_FILE = "/home/workdir/.grok/secrets/comfy_api_key"

# ---------------------------------------------------------------- baked config
# Shared model stack (from anima_api_workflow.json).
TEXT_ENCODER = "qwen_3_06b_base.safetensors"
VAE = "qwen_image_vae.safetensors"
HIRES_LORA = "anima-highres-aesthetic-boost.safetensors"
HIRES_LORA_MIN_PIXELS = 2 * 1024 * 1024  # original graph: enable LoRA at >= 2 MP

# Prepended to --prompt / used as default negative. Empty = same as the source graph.
QUALITY_PREFIX = ""
DEFAULT_NEGATIVE = ""

VARIANTS = {
    "base": {
        "unet": "divingAnima_v90.safetensors",
        "steps": 20,
        "cfg": 2.0,
        "sampler": "er_sde",
        "scheduler": "simple",
        "extra_loras": [],  # e.g. a turbo LoRA: [("anima_turbo.safetensors", 1.0)]
        "desc": "divingAnima v9.0, 20 steps, CFG 2, er_sde/simple",
    },
    # "turbo": {...}, "base+turbo": {...}  -> add when models are chosen
}
DEFAULT_VARIANT = "base"

TERMINAL_OK = {"completed", "success"}
TERMINAL_FAIL = {"error", "failed", "non_retryable_error", "lost", "cancelled"}

LIST_MODEL_KINDS = {
    "unet": ("UNETLoader", "unet_name"),
    "lora": ("LoraLoader", "lora_name"),
    "clip": ("CLIPLoader", "clip_name"),
    "vae": ("VAELoader", "vae_name"),
    "ckpt": ("CheckpointLoaderSimple", "ckpt_name"),
}
# `model` is not a loader kind: it lists both diffusion models (unet) and checkpoints (ckpt).
MODEL_KINDS = ("unet", "ckpt")
LIST_KINDS = {**LIST_MODEL_KINDS, "model": None}


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


# ---------------------------------------------------------------- graph
def build_graph(args):
    v = VARIANTS[args.variant]
    g = {}
    name = getattr(args, "model_name", None) or v["unet"]
    if getattr(args, "model_loader", "unet") == "ckpt":
        g["unet"] = {"class_type": "CheckpointLoaderSimple",
                     "inputs": {"ckpt_name": name}}
    else:
        g["unet"] = {"class_type": "UNETLoader",
                     "inputs": {"unet_name": name, "weight_dtype": "default"}}
    g["clip"] = {"class_type": "CLIPLoader",
                 "inputs": {"clip_name": TEXT_ENCODER, "type": "stable_diffusion",
                            "device": "default"}}
    g["vae"] = {"class_type": "VAELoader", "inputs": {"vae_name": VAE}}
    model, clip = ["unet", 0], ["clip", 0]

    if args.use_hires_lora:
        g["hires_lora"] = {"class_type": "LoraLoader",
                           "inputs": {"lora_name": HIRES_LORA, "strength_model": 1.0,
                                      "strength_clip": 1.0, "model": model, "clip": clip}}
        model, clip = ["hires_lora", 0], ["hires_lora", 1]

    for i, (name, strength) in enumerate(list(v["extra_loras"]) + args.loras):
        nid = f"lora_{i}"
        g[nid] = {"class_type": "LoraLoaderModelOnly",
                  "inputs": {"lora_name": name, "strength_model": strength, "model": model}}
        model = [nid, 0]

    g["pos"] = {"class_type": "CLIPTextEncode", "inputs": {"text": args.full_prompt, "clip": clip}}
    g["neg"] = {"class_type": "CLIPTextEncode", "inputs": {"text": args.negative, "clip": clip}}
    g["latent"] = {"class_type": "EmptyLatentImage",
                   "inputs": {"width": args.width, "height": args.height,
                              "batch_size": args.batch}}
    g["sampler"] = {"class_type": "KSampler",
                    "inputs": {"seed": args.seed,
                               "steps": args.steps if args.steps else v["steps"],
                               "cfg": args.cfg if args.cfg is not None else v["cfg"],
                               "sampler_name": v["sampler"], "scheduler": v["scheduler"],
                               "denoise": 1.0, "model": model, "positive": ["pos", 0],
                               "negative": ["neg", 0], "latent_image": ["latent", 0]}}
    g["decode"] = {"class_type": "VAEDecode",
                   "inputs": {"samples": ["sampler", 0], "vae": ["vae", 0]}}
    g["save"] = {"class_type": "SaveImage",
                 "inputs": {"filename_prefix": args.prefix, "images": ["decode", 0]}}
    return g


# ---------------------------------------------------------------- http
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **kw):
        return None  # surface 3xx as HTTPError so the API key never follows a redirect


_api_opener = urllib.request.build_opener(_NoRedirect)
_plain_opener = urllib.request.build_opener()  # no auth header, follows redirects


class Api:
    def __init__(self, base_url, key, timeout=30):
        self.base, self.key, self.timeout = base_url.rstrip("/"), key, timeout

    def request(self, method, path, body=None, params=None):
        url = self.base + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("X-API-Key", self.key)
        req.add_header("User-Agent", f"anima_cloud/{VERSION}")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with _api_opener.open(req, timeout=self.timeout) as r:
                return r.status, r.headers, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.headers, e.read() if e.fp else b""
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise Fail("error", f"network: {short(getattr(e, 'reason', e), 160)}", 2)

    def json(self, method, path, body=None, params=None, ok=(200,)):
        code, _, raw = self.request(method, path, body, params)
        try:
            data = json.loads(raw) if raw else {}
        except ValueError:
            data = {"_raw": raw[:200].decode("utf-8", "replace")}
        if code not in ok:
            exit_code = 1 if code == 400 else 3 if code in (401, 402, 403, 429) else 2
            raise Fail("error", f"HTTP {code} {method} {path}: {summarize_error(data)}", exit_code)
        return data


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


def resume_cmd():
    return f"python3 {os.path.abspath(sys.argv[0])}"


def job_failure_reason(detail, st):
    ee = detail.get("execution_error") if isinstance(detail, dict) else None
    if isinstance(ee, dict) and ee:
        return short(f"{ee.get('node_type', '?')} (node {ee.get('node_id', '?')}): "
                     f"{ee.get('exception_type', '')}: {ee.get('exception_message', '')}")
    return short(st.get("error_message") or "no error detail from API")


def collect_images(outputs):
    """Return image dicts, SaveImage node ('save') first, then any other 'output' images."""
    found = []
    if not isinstance(outputs, dict):
        return found
    keys = sorted(outputs, key=lambda k: (k != "save", k))
    for nid in keys:
        node = outputs[nid]
        for img in (node.get("images") or []) if isinstance(node, dict) else []:
            if isinstance(img, dict) and img.get("filename") and img.get("type", "output") == "output":
                found.append(img)
    return found


def download(api, img, dest):
    params = {"filename": img["filename"], "type": img.get("type", "output")}
    if img.get("subfolder"):
        params["subfolder"] = img["subfolder"]
    code, headers, body = api.request("GET", "/api/view", params=params)
    if code in (301, 302, 303, 307, 308):
        loc = headers.get("Location")
        if not loc:
            raise Fail("error", "download: redirect without Location", 2)
        host = urllib.parse.urlsplit(loc).hostname
        req = urllib.request.Request(loc, headers={"User-Agent": f"anima_cloud/{VERSION}"})
        try:
            with _plain_opener.open(req, timeout=120) as r:
                body = r.read()
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise Fail("error", f"download from {host} failed: "
                                f"{short(getattr(e, 'reason', e), 120)}", 2)
    elif code != 200:
        raise Fail("error", f"download: HTTP {code} from /api/view for {img['filename']}", 2)
    tmp = dest + ".part"
    with open(tmp, "wb") as f:
        f.write(body)
    os.replace(tmp, dest)
    return len(body)


def finish(api, pid, status, st, out_dir, local_prefix):
    detail = api.json("GET", f"/api/jobs/{pid}")
    if status in TERMINAL_FAIL or (detail.get("status") or "").lower() in TERMINAL_FAIL:
        raise Fail(status if status != "success" else "failed",
                   job_failure_reason(detail, st), 1, prompt_id=pid)
    images = collect_images(detail.get("outputs"))
    if not images:
        raise Fail("error", "job completed but returned no images", 1, prompt_id=pid)
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for i, img in enumerate(images):
        ext = os.path.splitext(img["filename"])[1] or ".png"
        name = f"{local_prefix}_{i + 1}{ext}" if len(images) > 1 else f"{local_prefix}{ext}"
        dest = os.path.join(out_dir, name)
        download(api, img, dest)
        paths.append(dest)
    return paths


# ---------------------------------------------------------------- cli
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


class _Parser(argparse.ArgumentParser):
    def error(self, message):  # short output + exit 3 instead of argparse's usage dump / 2
        emit(status="error", error=f"usage: {short(message, 200)}", hint="--help for options")
        sys.exit(3)


def build_parser():
    p = _Parser(prog="anima_cloud", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--prompt", help="positive prompt (tags)")
    p.add_argument("--negative", default=None, help="negative prompt (default: baked)")
    p.add_argument("--no-quality", action="store_true", help="skip the baked quality prefix")
    p.add_argument("--variant", default=DEFAULT_VARIANT, choices=sorted(VARIANTS))
    p.add_argument("--ckpt", "--model", dest="ckpt", metavar="NAME", default=None,
                   help="override the model file: any diffusion model / checkpoint on Cloud; "
                        "exact name or a unique substring")
    p.add_argument("--width", type=int, default=832)
    p.add_argument("--height", type=int, default=1216)
    p.add_argument("--seed", type=int, default=None, help="default: random")
    p.add_argument("--batch", type=int, default=1)
    p.add_argument("--steps", type=int, default=None, help="override variant steps")
    p.add_argument("--cfg", type=float, default=None, help="override variant CFG")
    p.add_argument("--lora", dest="loras", type=parse_lora, action="append", default=[],
                   metavar="NAME[:STRENGTH]", help="extra model-only LoRA (repeatable)")
    p.add_argument("--hires-lora", choices=("auto", "on", "off"), default="auto",
                   help="aesthetic boost LoRA; auto = on at >= 2 MP")
    p.add_argument("--out", default=DEFAULT_OUT)
    p.add_argument("--wait", type=float, default=25,
                   help="seconds to wait before returning 'pending' (default 25)")
    p.add_argument("--stall", type=float, default=900,
                   help="fail if status unchanged this long (default 900)")
    p.add_argument("--key-file", default=None)
    p.add_argument("--base-url", default=os.environ.get("COMFY_CLOUD_URL", DEFAULT_BASE_URL))
    g = p.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", help="print API JSON, submit nothing")
    g.add_argument("--resume", metavar="PROMPT_ID", help="wait for / download an existing job")
    g.add_argument("--cancel", metavar="PROMPT_ID", help="remove a job from the queue")
    g.add_argument("--list-variants", action="store_true")
    g.add_argument("--list-models", choices=sorted(LIST_KINDS), metavar="KIND",
                   help=f"list Cloud model files: {', '.join(sorted(LIST_KINDS))} "
                        f"('model' = diffusion models + checkpoints)")
    p.add_argument("--filter", default="", help="substring filter for --list-models")
    p.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return p


def validate(args, parser):
    if args.width % 16 or args.height % 16 or not (256 <= args.width <= 4096) \
            or not (256 <= args.height <= 4096):
        parser.error("--width/--height must be multiples of 16 within 256..4096")
    if not 1 <= args.batch <= 8:
        parser.error("--batch must be 1..8")
    if args.seed is None:
        args.seed = random.randint(0, 2**50)
    if args.seed < 0 or args.seed >= 2**64:
        parser.error("--seed must be 0..2^64-1")
    if not args.prompt:
        parser.error("--prompt is required")
    prefix = "" if args.no_quality or not QUALITY_PREFIX else QUALITY_PREFIX.rstrip(", ") + ", "
    args.full_prompt = prefix + args.prompt.strip()
    if args.negative is None:
        args.negative = DEFAULT_NEGATIVE
    pixels = args.width * args.height
    args.use_hires_lora = args.hires_lora == "on" or (
        args.hires_lora == "auto" and pixels >= HIRES_LORA_MIN_PIXELS)
    set_prefix(args)


def set_prefix(args):
    """Filename stem: variant + a short model tag (when --ckpt) + timestamp."""
    stamp = time.strftime("%y%m%d-%H%M%S")
    name = getattr(args, "model_name", None) or ""
    tag = re.sub(r"[^a-z0-9]+", "-",
                 os.path.splitext(os.path.basename(name))[0].lower()).strip("-")[:24]
    args.prefix = f"anima_{args.variant}{'_' + tag if tag else ''}_{stamp}"
    args.local_prefix = f"{args.prefix}_s{args.seed}"


def _object_info(api):
    return api.json("GET", "/api/object_info")  # Cloud has no per-node /api/object_info/{node}


def names_from_info(info, kind):
    node, field = LIST_MODEL_KINDS[kind]
    spec = (info.get(node) or {}).get("input", {}).get("required", {}).get(field)
    if isinstance(spec, list) and spec:
        if isinstance(spec[0], list):
            return [str(n) for n in spec[0]]
        if len(spec) > 1 and isinstance(spec[1], dict):
            return [str(n) for n in (spec[1].get("options") or [])]
    return []


def model_files(api):
    """All files --ckpt can point at: [(name, loader_kind)], unet before ckpt."""
    info = _object_info(api)
    pairs = []
    for kind in MODEL_KINDS:
        for n in names_from_info(info, kind):
            if all(n != existing for existing, _ in pairs):
                pairs.append((n, kind))
    return pairs


def resolve_model(api, want):
    """Map a full or partial model filename to (exact_name, loader_kind)."""
    pairs = model_files(api)
    if not pairs:  # no catalog: submit the name unchanged and let Cloud reject it
        return want.strip(), "unet"
    want = want.strip()
    base = os.path.basename(want)
    stem = os.path.splitext(base)[0].lower()
    for pred in (lambda n: n == want,
                 lambda n: os.path.basename(n) == base,
                 lambda n: os.path.splitext(os.path.basename(n))[0].lower() == stem):
        hits = [p for p in pairs if pred(p[0])]
        if hits:  # exact is exact: same file in both loaders -> diffusion model wins
            return hits[0]
    needle = want.lower()
    hits = [p for p in pairs if needle in p[0].lower()]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        raise Fail("error", f"model not on Cloud: {want}", 3,
                   hint="--list-models model --filter <text>")
    raise Fail("error", f"ambiguous model '{want}': "
                        + ", ".join(n for n, _ in hits[:4]) + (" ..." if len(hits) > 4 else ""), 3)


def list_models(api, kind, flt):
    if kind == "model":
        names = [n for n, _ in model_files(api)]
    else:
        names = names_from_info(_object_info(api), kind)
    names = [n for n in names if flt.lower() in n.lower()]
    cap = 12
    emit(kind=kind, count=len(names))
    for n in names[:cap]:
        print(f"  {n}")
    if len(names) > cap:
        print(f"  ... +{len(names) - cap} more (use --filter)")


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    pid = None
    try:
        if args.list_variants:
            for name, v in VARIANTS.items():
                print(f"{name}{' (default)' if name == DEFAULT_VARIANT else ''}: {v['desc']}")
            return 0

        api = None
        if not (args.resume or args.cancel or args.list_models):
            validate(args, parser)
            if args.ckpt:  # needs the catalog, so needs key + network even for --dry-run
                api = Api(args.base_url, load_key(args.key_file))
                args.model_name, args.model_loader = resolve_model(api, args.ckpt)
                set_prefix(args)
            graph = build_graph(args)
            if args.dry_run:
                print(json.dumps({"prompt": graph}, indent=1))
                return 0

        api = api or Api(args.base_url, load_key(args.key_file))

        if args.list_models:
            list_models(api, args.list_models, args.filter)
            return 0
        if args.cancel:
            api.json("POST", "/api/queue", body={"delete": [args.cancel]})
            emit(status="cancel_requested", prompt_id=args.cancel)
            return 0

        if args.resume:
            pid = args.resume
            local_prefix = f"anima_job_{pid[:8]}"
        else:
            resp = api.json("POST", "/api/prompt", body={"prompt": graph})
            pid = resp.get("prompt_id")
            if not pid:
                raise Fail("error", f"submit: no prompt_id ({summarize_error(resp)})", 2)
            if resp.get("node_errors"):
                raise Fail("error", f"submit: {summarize_error(resp)}", 1, prompt_id=pid)
            local_prefix = args.local_prefix

        status, st = wait_for_job(api, pid, args.wait, args.stall)
        paths = finish(api, pid, status, st, args.out, local_prefix)
        emit(status="completed", path=paths[0] if len(paths) == 1 else None)
        if len(paths) > 1:
            print("paths:")
            for pth in paths:
                print(f"  {pth}")
        if not args.resume:
            emit(variant=args.variant, size=f"{args.width}x{args.height}", seed=args.seed)
            emit(model=getattr(args, "model_name", None) or VARIANTS[args.variant]["unet"],
                 loader=getattr(args, "model_loader", "unet"))
        emit(prompt_id=pid)
        return 0
    except Fail as e:
        if pid and "prompt_id" not in e.extra:
            e.extra["prompt_id"] = pid
        if e.status == "pending":
            emit(status=e.status, detail=e.error, **e.extra)
        else:
            emit(status=e.status, error=e.error, **e.extra)
        return e.code
    except KeyboardInterrupt:
        emit(status="interrupted", error="local wait aborted; job may still run on Cloud",
             prompt_id=pid)
        return 2


if __name__ == "__main__":
    sys.exit(main())
