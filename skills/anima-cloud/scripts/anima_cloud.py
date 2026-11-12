#!/usr/bin/env python3
"""anima_cloud - submit a baked Anima workflow to Comfy Cloud and fetch the result.

Python 3.10+ stdlib only (plus skills/_shared/comfy_cloud.py from this repo).
Prints a short `key: value` block.

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

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "_shared"))
import comfy_cloud as cc  # noqa: E402
from comfy_cloud import Fail, emit  # noqa: E402

VERSION = "1.2.1"
OUT_SUBDIR = "anima"  # default --out: see comfy_cloud.default_out()

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

# Per-model sampling presets. When the model in use (the variant's, or --ckpt) matches a
# key, its settings replace the variant's; explicit --steps/--cfg/--sampler/--scheduler
# still win, and --no-preset ignores the table. Keys are filenames; matching also accepts
# the name without extension. Any subset of: steps, cfg, sampler, scheduler, note.
MODEL_PRESETS = {
    # "someAnimaMix_v1.safetensors": {"sampler": "euler_ancestral", "scheduler": "beta",
    #                                 "steps": 28, "cfg": 4.0, "note": "author's recommended"},
}
PRESET_FIELDS = ("steps", "cfg", "sampler", "scheduler")

LIST_MODEL_KINDS = {
    "unet": ("UNETLoader", "unet_name"),
    "lora": ("LoraLoader", "lora_name"),
    "clip": ("CLIPLoader", "clip_name"),
    "vae": ("VAELoader", "vae_name"),
    "ckpt": ("CheckpointLoaderSimple", "ckpt_name"),
    "sampler": ("KSampler", "sampler_name"),
    "scheduler": ("KSampler", "scheduler"),
}
# `model` is not a loader kind: it lists both diffusion models (unet) and checkpoints (ckpt).
MODEL_KINDS = ("unet", "ckpt")
LIST_KINDS = {**LIST_MODEL_KINDS, "model": None}


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
                               "steps": args.sampling["steps"], "cfg": args.sampling["cfg"],
                               "sampler_name": args.sampling["sampler"],
                               "scheduler": args.sampling["scheduler"],
                               "denoise": 1.0, "model": model, "positive": ["pos", 0],
                               "negative": ["neg", 0], "latent_image": ["latent", 0]}}
    g["decode"] = {"class_type": "VAEDecode",
                   "inputs": {"samples": ["sampler", 0], "vae": ["vae", 0]}}
    g["save"] = {"class_type": "SaveImage",
                 "inputs": {"filename_prefix": args.prefix, "images": ["decode", 0]}}
    return g


# ---------------------------------------------------------------- cli
def build_parser():
    p = cc.Parser(prog="anima_cloud", description=__doc__,
                  formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--prompt", help="positive prompt (tags)")
    p.add_argument("--negative", default=None, help="negative prompt (default: baked)")
    p.add_argument("--no-quality", action="store_true", help="skip the baked quality prefix")
    p.add_argument("--variant", default=DEFAULT_VARIANT, choices=sorted(VARIANTS))
    p.add_argument("--ckpt", "--model", dest="ckpt", metavar="NAME", default=None,
                   help="override the model file: any diffusion model / checkpoint on Cloud; "
                        "exact name or a unique substring")
    p.add_argument("--loader", choices=("auto", "unet", "ckpt"), default="auto",
                   help="loader for --ckpt: auto = pick from the catalog, unet = UNETLoader, "
                        "ckpt = CheckpointLoaderSimple (default auto)")
    p.add_argument("--width", type=int, default=832)
    p.add_argument("--height", type=int, default=1216)
    p.add_argument("--seed", type=int, default=None, help="default: random")
    p.add_argument("--batch", type=int, default=1)
    p.add_argument("--steps", type=int, default=None, help="override steps")
    p.add_argument("--cfg", type=float, default=None, help="override CFG")
    p.add_argument("--sampler", default=None, help="override sampler_name (--list-models sampler)")
    p.add_argument("--scheduler", default=None, help="override scheduler (--list-models scheduler)")
    p.add_argument("--no-preset", action="store_true",
                   help="ignore the per-model preset; use the variant's sampling settings")
    p.add_argument("--lora", dest="loras", type=cc.parse_lora, action="append", default=[],
                   metavar="NAME[:STRENGTH]", help="extra model-only LoRA (repeatable)")
    p.add_argument("--hires-lora", choices=("auto", "on", "off"), default="auto",
                   help="aesthetic boost LoRA; auto = on at >= 2 MP")
    p.add_argument("--out", default=None,
                   help=f"output folder (default: $HARNESS_OUT/{OUT_SUBDIR}, else "
                        f"/workspace/artifacts/{OUT_SUBDIR} if /workspace exists, else "
                        f"./artifacts/{OUT_SUBDIR})")
    p.add_argument("--wait", type=float, default=25,
                   help="seconds to wait before returning 'pending' (default 25)")
    p.add_argument("--stall", type=float, default=900,
                   help="fail if status unchanged this long (default 900)")
    p.add_argument("--key-file", default=None)
    p.add_argument("--base-url", default=os.environ.get("COMFY_CLOUD_URL", cc.DEFAULT_BASE_URL))
    g = p.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", help="print API JSON, submit nothing")
    g.add_argument("--resume", metavar="PROMPT_ID", help="wait for / download an existing job")
    g.add_argument("--cancel", metavar="PROMPT_ID", help="remove a job from the queue")
    g.add_argument("--list-variants", action="store_true")
    g.add_argument("--list-presets", action="store_true", help="per-model sampling presets")
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
    if args.steps is not None and not 1 <= args.steps <= 150:
        parser.error("--steps must be 1..150")
    if args.cfg is not None and not 0 <= args.cfg <= 30:
        parser.error("--cfg must be 0..30")
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


def resolve_sampling(args):
    """Sampling settings in force: explicit flag > model preset > variant."""
    v = VARIANTS[args.variant]
    model = getattr(args, "model_name", None) or v["unet"]
    key, preset = (None, None) if args.no_preset else cc.find_preset(MODEL_PRESETS, model)
    s = {f: (preset or {}).get(f, v[f]) for f in PRESET_FIELDS}
    for f in PRESET_FIELDS:
        flag = getattr(args, f)
        if flag is not None:
            s[f] = flag
    args.sampling, args.preset = s, key


def sampling_line(args):
    s = args.sampling
    src = " (preset)" if args.preset else ""
    return f"{s['steps']} steps, CFG {s['cfg']:g}, {s['sampler']}/{s['scheduler']}{src}"


def names_from_info(info, kind):
    return cc.names_from_info(info, [LIST_MODEL_KINDS[kind]])


def model_files(api):
    """All files --ckpt can point at: [(name, loader_kind)], unet before ckpt."""
    info = cc.object_info(api)
    pairs = []
    for kind in MODEL_KINDS:
        for n in names_from_info(info, kind):
            if all(n != existing for existing, _ in pairs):
                pairs.append((n, kind))
    return pairs


def resolve_model(api, want):
    """Map a full or partial model filename to (exact_name, loader_kind|None).

    kind is None when the file is not in the catalog: the name is passed through
    unchanged, because Cloud does not enumerate every import (private Anima
    builds run fine while missing from object_info) and its own validation is
    the real check.
    """
    pairs = model_files(api)
    want = want.strip()
    if not pairs:
        return want, None
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
        # Unlisted: submit the exact filename (Cloud needs the extension).
        return (want if os.path.splitext(base)[1] else want + ".safetensors"), None
    raise Fail("error", f"ambiguous model '{want}': "
                        + ", ".join(n for n, _ in hits[:4]) + (" ..." if len(hits) > 4 else ""), 3)


def list_models(api, kind, flt):
    if kind == "model":
        names = [n for n, _ in model_files(api)]
    else:
        names = names_from_info(cc.object_info(api), kind)
    cc.print_names(kind, names, flt)


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    pid = None
    try:
        if args.list_variants:
            for name, v in VARIANTS.items():
                print(f"{name}{' (default)' if name == DEFAULT_VARIANT else ''}: {v['desc']}")
            return 0
        if args.list_presets:
            cc.print_presets(MODEL_PRESETS, PRESET_FIELDS)
            return 0

        def make_api():
            return cc.Api(args.base_url, cc.load_key(args.key_file), f"anima_cloud/{VERSION}")

        api = None
        if not (args.resume or args.cancel or args.list_models):
            validate(args, parser)
            if args.ckpt:  # needs the catalog, so needs key + network even for --dry-run
                api = make_api()
                name, kind = resolve_model(api, args.ckpt)
                args.model_name = name
                args.model_loader = args.loader if args.loader != "auto" else (kind or "unet")
                if kind is None:
                    print(f"warning: {name} is not in the /api/object_info catalog "
                          f"(Cloud does not list every import); submitting as-is",
                          file=sys.stderr if args.dry_run else sys.stdout)
                set_prefix(args)
            resolve_sampling(args)
            graph = build_graph(args)
            if args.dry_run:
                print(json.dumps({"prompt": graph}, indent=1))
                return 0

        api = api or make_api()

        if args.list_models:
            list_models(api, args.list_models, args.filter)
            return 0
        if args.cancel:
            cc.cancel(api, args.cancel)
            return 0

        args.out = cc.ensure_out_dir(args.out or cc.default_out(OUT_SUBDIR))
        cc.resume_args(args.out, args.key_file)
        if args.resume:
            pid = args.resume
            local_prefix = f"anima_job_{pid[:8]}"
        else:
            pid = cc.submit(api, graph)
            local_prefix = args.local_prefix

        status, st = cc.wait_for_job(api, pid, args.wait, args.stall)
        cc.emit_paths(cc.finish(api, pid, status, st, args.out, local_prefix, ".png"))
        if not args.resume:
            emit(variant=args.variant, size=f"{args.width}x{args.height}", seed=args.seed)
            emit(model=getattr(args, "model_name", None) or VARIANTS[args.variant]["unet"],
                 loader=getattr(args, "model_loader", "unet"), sampling=sampling_line(args))
        emit(prompt_id=pid)
        return 0
    except Fail as e:
        return cc.report(e, pid)
    except KeyboardInterrupt:
        return cc.interrupted(pid)


if __name__ == "__main__":
    sys.exit(main())
