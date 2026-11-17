#!/usr/bin/env python3
"""qwen_image_edit - submit a Qwen-Image-Edit workflow (2509 / 2511 / Rapid-AIO) to Comfy Cloud.

Uploads up to three reference images, submits the job, downloads the PNG. Python 3.10+
stdlib only (plus skills/_shared/comfy_cloud.py from this repo). Prints a short
`key: value` block.

Setups (--model): aio (default) = one Rapid-AIO checkpoint with the accelerator baked in;
2511 / 2509 = UNET + Qwen2.5-VL text encoder + qwen_image VAE, with the 8-step Lightning LoRA
on by default.

Exit codes: 0 completed | 1 job failed/cancelled or workflow rejected (HTTP 400)
            2 network/server/stall error | 3 usage, key, credits or auth error
            4 still pending (use --resume <prompt_id>)
"""
import argparse
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "_shared"))
import comfy_cloud as cc  # noqa: E402
from comfy_cloud import Fail, emit  # noqa: E402

VERSION = "1.0.0"
OUT_SUBDIR = "qwen-image-edit"  # default --out: see comfy_cloud.default_out()

# ---------------------------------------------------------------- baked config
# From dev/qwen-image-edit/source_workflow.json (Qwen-Image-Edit 2511 + Rapid-AIO switch).
TEXT_ENCODER = ("ethanfel__Qwen25-VL-7B-Huihui-Abliterated-ComfyUI-ConvRot-INT8__"
                "qwen_2.5_vl_7b_huihui_abliterated_int8_convrot.safetensors")
VAE = "qwen_image_vae.safetensors"
SKIN_LORA = "Skin_Fix_rank64.safetensors"
DEFAULT_SKIN_LORA = 0.7
DEFAULT_LIGHTNING_STRENGTH = 1.0
DEFAULT_SHIFT = 3.0
DEFAULT_NEGATIVE = "Plastic skin, 3d"
DEFAULT_ASPECT = "2:3"
DEFAULT_MEGAPIXELS = 1.0
MAX_REFS = 3
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}

# One entry per --model choice. `loader` picks the graph's loader nodes:
#   ckpt = CheckpointLoaderSimple (MODEL out 0, CLIP out 1, VAE out 2)
#   unet = UNETLoader + CLIPLoader(type qwen_image) + VAELoader
# `lightning` is the LoRA file, or None when the setup has no Lightning build.
SETUPS = {
    "aio": {
        "loader": "ckpt",
        "model": "Phr00t__Qwen-Image-Edit-Rapid-AIO__Qwen-Rapid-AIO-NSFW-v23.safetensors",
        "clip": None,
        "vae": None,
        "lightning": None,  # accelerator baked into the checkpoint; lightning is always off
        "steps_lightning": 8, "steps_full": 8,
        "cfg_lightning": 1.0, "cfg_full": 1.0,
        "sampler": "euler_ancestral", "scheduler": "simple",
        "desc": "Rapid-AIO checkpoint, 8 steps, CFG 1, euler_ancestral/simple",
    },
    "2511": {
        "loader": "unet",
        "model": "qwen_image_edit_2511_fp8mixed.safetensors",
        "clip": TEXT_ENCODER,
        "vae": VAE,
        "lightning": "Qwen-Image-Edit-2511-Lightning-8steps-V1.0-fp32.safetensors",
        "steps_lightning": 8, "steps_full": 30,
        "cfg_lightning": 1.0, "cfg_full": 3.0,
        "sampler": "euler", "scheduler": "simple",
        "desc": "Qwen-Image-Edit 2511 + Lightning 8-step LoRA (8 steps, CFG 1)",
    },
    "2509": {
        "loader": "unet",
        "model": "qwen_image_edit_2509_fp8mixed.safetensors",
        "clip": TEXT_ENCODER,
        "vae": VAE,
        "lightning": "Qwen-Image-Edit-2509-Lightning-8steps-V1.0-bf16.safetensors",
        "steps_lightning": 8, "steps_full": 30,
        "cfg_lightning": 1.0, "cfg_full": 3.0,
        "sampler": "euler", "scheduler": "simple",
        "desc": "Qwen-Image-Edit 2509 + Lightning 8-step LoRA (8 steps, CFG 1)",
    },
}
DEFAULT_SETUP = "aio"

# ResolutionSelector labels Cloud accepts, keyed by the short form --aspect takes.
ASPECTS = {
    "1:1": "1:1 (Square)",
    "2:3": "2:3 (Portrait Photo)",
    "3:2": "3:2 (Photo)",
    "3:4": "3:4 (Portrait Standard)",
    "4:3": "4:3 (Standard)",
    "9:16": "9:16 (Portrait Widescreen)",
    "16:9": "16:9 (Widescreen)",
    "21:9": "21:9 (Ultrawide)",
}

# Per-model sampling presets. When the diffusion file in use (the setup's, or --ckpt)
# matches a key, its settings replace the setup defaults above; explicit --steps/--cfg/
# --sampler/--scheduler/--shift/--lightning-strength still win, and --no-preset ignores
# the table. Keys are filenames; matching also accepts the name without extension. Any
# subset of:
#   lightning             True/False: default state of the Lightning LoRA (2511/2509 only)
#   lightning_strength    Lightning LoRA strength (baked: 1.0)
#   steps_lightning       steps with Lightning on  (baked: 8)
#   steps_full            steps with Lightning off (baked: aio 8, 2509/2511 30)
#   cfg_lightning         CFG with Lightning on    (baked: 1.0)
#   cfg_full              CFG with Lightning off   (baked: aio 1.0, 2509/2511 3.0)
#   sampler, scheduler    KSampler names
#   shift                 ModelSamplingAuraFlow shift (baked: 3.0)
#   note                  free text shown by --list-presets
MODEL_PRESETS = {
    # "qwen_image_edit_2509_fp8mixed.safetensors": {"lightning": False, "steps_full": 28,
    #                                               "shift": 3.5, "note": "crisper text"},
}
PRESET_FIELDS = ("lightning", "lightning_strength", "steps_lightning", "steps_full",
                 "cfg_lightning", "cfg_full", "sampler", "scheduler", "shift")

# kind -> [(node class, input field)], first one present in /api/object_info wins
LIST_KINDS = {
    "model": [("UNETLoader", "unet_name")],
    "ckpt": [("CheckpointLoaderSimple", "ckpt_name")],
    "lora": [("LoraLoaderModelOnly", "lora_name")],
    "clip": [("CLIPLoader", "clip_name")],
    "sampler": [("KSampler", "sampler_name")],
    "scheduler": [("KSampler", "scheduler")],
}


# ---------------------------------------------------------------- graph
def build_graph(a):
    s = SETUPS[a.setup]
    g = {}
    if s["loader"] == "ckpt":
        g["ckpt"] = {"class_type": "CheckpointLoaderSimple",
                     "inputs": {"ckpt_name": a.model_name}}
        model, clip, vae = ["ckpt", 0], ["ckpt", 1], ["ckpt", 2]
    else:
        g["unet"] = {"class_type": "UNETLoader",
                     "inputs": {"unet_name": a.model_name, "weight_dtype": "default"}}
        g["clip"] = {"class_type": "CLIPLoader",
                     "inputs": {"clip_name": s["clip"], "type": "qwen_image",
                                "device": "default"}}
        g["vae"] = {"class_type": "VAELoader", "inputs": {"vae_name": s["vae"]}}
        model, clip, vae = ["unet", 0], ["clip", 0], ["vae", 0]

    # Model chain: Lightning (if on), skin fix, then --lora in the order given.
    if a.lightning:
        g["lightning"] = {"class_type": "LoraLoaderModelOnly",
                          "inputs": {"lora_name": s["lightning"],
                                     "strength_model": a.lightning_strength_used,
                                     "model": model}}
        model = ["lightning", 0]
    if a.skin_lora > 0:
        g["skin"] = {"class_type": "LoraLoaderModelOnly",
                     "inputs": {"lora_name": SKIN_LORA, "strength_model": a.skin_lora,
                                "model": model}}
        model = ["skin", 0]
    for i, (name, strength) in enumerate(a.loras):
        nid = f"lora_{i}"
        g[nid] = {"class_type": "LoraLoaderModelOnly",
                  "inputs": {"lora_name": name, "strength_model": strength, "model": model}}
        model = [nid, 0]

    g["aura"] = {"class_type": "ModelSamplingAuraFlow",
                 "inputs": {"shift": a.shift_used, "sampling": "flow", "model": model}}
    g["cfgnorm"] = {"class_type": "CFGNorm",
                    "inputs": {"strength": 1, "pre_cfg": False, "model": ["aura", 0]}}

    # References: only image1 is scaled, and that one node feeds both encoders and the
    # VAEEncode, so the conditioning and the latent agree on the crop.
    images = {}
    for i, name in enumerate(a.ref_names):
        g[f"ref_{i}"] = {"class_type": "LoadImage", "inputs": {"image": name}}
        images[f"image{i + 1}"] = [f"ref_{i}", 0]
    if images:
        g["scaled_0"] = {"class_type": "FluxKontextImageScale",
                         "inputs": {"image": ["ref_0", 0]}}
        images["image1"] = ["scaled_0", 0]

    for nid, text in (("pos", a.prompt_text), ("neg", a.negative)):
        g[nid] = {"class_type": "TextEncodeQwenImageEditPlus",
                  "inputs": {"clip": clip, "vae": vae, "prompt": text, **images}}

    if a.latent_used == "image":
        g["latent"] = {"class_type": "VAEEncode",
                       "inputs": {"pixels": ["scaled_0", 0], "vae": vae}}
    else:
        g["res"] = {"class_type": "ResolutionSelector",
                    "inputs": {"aspect_ratio": a.aspect_label,
                               "megapixels": a.megapixels, "multiple": 32}}
        g["latent"] = {"class_type": "EmptyLatentImage",
                       "inputs": {"width": ["res", 0], "height": ["res", 1],
                                  "batch_size": 1}}

    g["sampler"] = {"class_type": "KSampler",
                    "inputs": {"seed": a.seed,
                               "steps": a.steps_used, "cfg": a.cfg_used,
                               "sampler_name": a.sampler_used,
                               "scheduler": a.scheduler_used,
                               "denoise": a.denoise, "model": ["cfgnorm", 0],
                               "positive": ["pos", 0], "negative": ["neg", 0],
                               "latent_image": ["latent", 0]}}
    g["decode"] = {"class_type": "VAEDecode",
                   "inputs": {"samples": ["sampler", 0], "vae": vae}}
    g["save"] = {"class_type": "SaveImage",
                 "inputs": {"filename_prefix": a.prefix, "images": ["decode", 0]}}
    return g


def resolve_ref(api, ref):
    """A local file is uploaded; a bare name that is not a local file is taken as already on Cloud."""
    if not ref:
        return None
    if os.path.isfile(ref):
        return cc.upload_file(api, ref)
    if os.sep not in ref and "/" not in ref:
        print(f"warning: {ref} is not a local file; using it as a name already on Cloud")
        return ref
    raise Fail("error", f"usage: reference image not found: {ref}", 3)


# ---------------------------------------------------------------- cli
def build_parser():
    p = cc.Parser(prog="qwen_image_edit", description=__doc__,
                  formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--prompt", help="the edit instruction (what to change / keep)")
    p.add_argument("--prompt-file", metavar="FILE", help="read the prompt from FILE ('-' = stdin)")
    p.add_argument("--negative", default=DEFAULT_NEGATIVE,
                   help=f"negative prompt (default '{DEFAULT_NEGATIVE}')")
    p.add_argument("--ref", dest="refs", action="append", default=[], metavar="IMAGE",
                   help="reference image, up to 3 (image1..image3 in the order given); "
                        "a local file is uploaded")
    p.add_argument("--model", dest="setup", choices=sorted(SETUPS), default=DEFAULT_SETUP,
                   help=f"model setup (default {DEFAULT_SETUP}): "
                        + "; ".join(f"{k} = {v['desc']}" for k, v in SETUPS.items()))
    p.add_argument("--ckpt", metavar="NAME", default=None,
                   help="override the diffusion file of the setup (checkpoint for aio, unet "
                        "for 2509/2511); exact filename, .safetensors appended when missing")
    p.add_argument("--lightning", choices=("auto", "on", "off"), default="auto",
                   help="Lightning LoRA: auto = on for 2509/2511 (off for aio); "
                        "off = full steps, slower")
    p.add_argument("--no-lightning", dest="lightning", action="store_const", const="off",
                   help="same as --lightning off")
    p.add_argument("--lightning-strength", type=float, default=None, metavar="S",
                   help=f"Lightning LoRA strength, 0..2 (default {DEFAULT_LIGHTNING_STRENGTH:g} "
                        f"or the model's preset); ignored when lightning is off")
    p.add_argument("--skin-lora", type=float, default=DEFAULT_SKIN_LORA, metavar="S",
                   help=f"Skin_Fix LoRA strength, 0..2 (default {DEFAULT_SKIN_LORA:g}; 0 = off)")
    p.add_argument("--lora", dest="loras", type=cc.parse_lora, action="append", default=[],
                   metavar="NAME[:STRENGTH]",
                   help="extra model-only LoRA; repeat to stack, applied after the skin LoRA "
                        "(strength defaults to 1.0)")
    p.add_argument("--steps", type=int, default=None,
                   help="override steps (default 8 with lightning, aio 8 / else 30 without, "
                        "or the model's preset)")
    p.add_argument("--cfg", type=float, default=None,
                   help="override CFG (default 1 with lightning, aio 1 / else 3 without, "
                        "or the model's preset)")
    p.add_argument("--sampler", default=None,
                   help="override sampler (default euler for 2509/2511, euler_ancestral for aio, "
                        "or the model's preset; --list-models sampler)")
    p.add_argument("--scheduler", default=None,
                   help="override scheduler (default simple or the model's preset; "
                        "--list-models scheduler)")
    p.add_argument("--shift", type=float, default=None, metavar="X",
                   help=f"ModelSamplingAuraFlow shift, 0..20 (default {DEFAULT_SHIFT:g} "
                        f"or the model's preset)")
    p.add_argument("--denoise", type=float, default=1.0,
                   help="KSampler denoise, 0.05..1.0 (default 1.0); below 1.0 needs an "
                        "image latent (--ref without --latent empty)")
    p.add_argument("--latent", choices=("image", "empty"), default="image",
                   help="image = encode the first reference (default); empty = fresh latent "
                        "from --aspect/--megapixels (falls back to empty when there is no --ref)")
    p.add_argument("--aspect", default=DEFAULT_ASPECT, metavar="A",
                   help="aspect for the empty latent: 1:1, 2:3, 3:2, 3:4, 4:3, 9:16, 16:9, 21:9 "
                        f"(default {DEFAULT_ASPECT}); full Cloud labels also accepted")
    p.add_argument("--megapixels", type=float, default=DEFAULT_MEGAPIXELS,
                   help=f"empty latent size in megapixels, 0.1..4.0 (default {DEFAULT_MEGAPIXELS:g})")
    p.add_argument("--seed", type=int, default=None, help="default: random")
    p.add_argument("--no-preset", action="store_true",
                   help="ignore the per-model preset; use the setup's sampling settings")
    p.add_argument("--out", default=None,
                   help=f"output folder (default: $HARNESS_OUT/{OUT_SUBDIR}, else "
                        f"/workspace/artifacts/{OUT_SUBDIR} if /workspace exists, else "
                        f"./artifacts/{OUT_SUBDIR})")
    p.add_argument("--wait", type=float, default=30,
                   help="seconds to wait before returning 'pending' (default 30)")
    p.add_argument("--stall", type=float, default=900,
                   help="fail if status unchanged this long (default 900)")
    p.add_argument("--key-file", default=None)
    p.add_argument("--base-url", default=os.environ.get("COMFY_CLOUD_URL", cc.DEFAULT_BASE_URL))
    g = p.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true",
                   help="print API JSON, upload and submit nothing (no key needed)")
    g.add_argument("--resume", metavar="PROMPT_ID", help="wait for / download an existing job")
    g.add_argument("--cancel", metavar="PROMPT_ID", help="remove a job from the queue")
    g.add_argument("--list-presets", action="store_true", help="per-model sampling presets")
    g.add_argument("--list-models", choices=sorted(LIST_KINDS), metavar="KIND",
                   help=f"list Cloud options: {', '.join(sorted(LIST_KINDS))}")
    p.add_argument("--filter", default="", help="substring filter for --list-models")
    p.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return p


def read_prompt(args, parser):
    if args.prompt and args.prompt_file:
        parser.error("use --prompt or --prompt-file, not both")
    if args.prompt_file:
        try:
            text = sys.stdin.read() if args.prompt_file == "-" else open(args.prompt_file).read()
        except OSError as e:
            parser.error(f"cannot read --prompt-file: {e.strerror}")
    else:
        text = args.prompt or ""
    text = text.strip()
    if not text:
        parser.error("--prompt or --prompt-file is required")
    return text


def validate(args, parser):
    args.prompt_text = read_prompt(args, parser)
    if len(args.refs) > MAX_REFS:
        parser.error(f"at most {MAX_REFS} --ref images")
    for ref in args.refs:
        if ref and os.path.isfile(ref):
            if os.path.splitext(ref)[1].lower() not in IMAGE_EXTS:
                parser.error(f"--ref must be png/jpg/webp: {os.path.basename(ref)}")
            if os.path.getsize(ref) > MAX_UPLOAD_BYTES:
                parser.error(f"--ref over {MAX_UPLOAD_BYTES >> 20} MB: {os.path.basename(ref)}")
    if args.setup == "aio" and args.lightning == "on":
        parser.error("--model aio has the accelerator baked in and no Lightning LoRA; "
                     "--lightning on needs --model 2511 or 2509")
    if not 0 <= args.skin_lora <= 2:
        parser.error("--skin-lora must be 0..2")
    if args.lightning_strength is not None and not 0 <= args.lightning_strength <= 2:
        parser.error("--lightning-strength must be 0..2")
    if args.steps is not None and not 1 <= args.steps <= 100:
        parser.error("--steps must be 1..100")
    if args.cfg is not None and not 0 <= args.cfg <= 20:
        parser.error("--cfg must be 0..20")
    if args.shift is not None and not 0 <= args.shift <= 20:
        parser.error("--shift must be 0..20")
    if not 0.05 <= args.denoise <= 1.0:
        parser.error("--denoise must be 0.05..1.0")
    if not 0.1 <= args.megapixels <= 4.0:
        parser.error("--megapixels must be 0.1..4.0")
    if args.seed is None:
        args.seed = random.randint(0, 2**63)
    if not 0 <= args.seed < 2**64:
        parser.error("--seed must be 0..2^64-1")

    args.aspect_label = resolve_aspect(args.aspect, parser)
    args.aspect_short = args.aspect_label.split(" (")[0]

    args.model_name = args.ckpt or SETUPS[args.setup]["model"]
    if args.ckpt and not os.path.splitext(args.ckpt)[1]:
        args.model_name = args.ckpt + ".safetensors"
    resolve_sampling(args)

    # A partial denoise starts from the reference's own latent; an empty latent at
    # denoise < 1 only partly denoises noise and comes out as a flat field.
    want_image = args.latent == "image" and bool(args.refs)
    args.latent_used = "image" if want_image else "empty"
    if args.denoise < 1.0 and args.latent_used == "empty":
        why = "no --ref" if not args.refs else "--latent empty"
        parser.error(f"--denoise {args.denoise:g} needs the image latent ({why}): a partial "
                     f"denoise of an empty latent renders a flat field; add --ref and drop "
                     f"--latent empty")

    args.prefix = f"qwen_{args.setup}_{time.strftime('%y%m%d-%H%M%S')}"
    args.local_prefix = f"{args.prefix}_s{args.seed}"


def resolve_aspect(value, parser):
    """Short form ('16:9') or the full Cloud label ('16:9 (Widescreen)') -> Cloud label."""
    want = (value or "").strip()
    if want in ASPECTS:
        return ASPECTS[want]
    if want in ASPECTS.values():
        return want
    parser.error(f"unknown --aspect '{value}'; use {', '.join(ASPECTS)} "
                 f"(or a full Cloud label)")


def resolve_sampling(args):
    """Sampling settings in force: explicit flag > model preset > setup default."""
    s = SETUPS[args.setup]
    key, p = (None, None) if args.no_preset else cc.find_preset(MODEL_PRESETS, args.model_name)
    p = p or {}
    args.preset = key
    if s["lightning"] is None:  # aio: the accelerator is baked in, so Lightning is always off
        args.lightning = False
    else:
        args.lightning = (args.lightning == "on" or
                          (args.lightning == "auto" and p.get("lightning", True)))
    sfx = "lightning" if args.lightning else "full"
    args.steps_used = (args.steps if args.steps is not None
                       else p.get(f"steps_{sfx}", s[f"steps_{sfx}"]))
    args.cfg_used = (args.cfg if args.cfg is not None
                     else p.get(f"cfg_{sfx}", s[f"cfg_{sfx}"]))
    args.sampler_used = args.sampler or p.get("sampler", s["sampler"])
    args.scheduler_used = args.scheduler or p.get("scheduler", s["scheduler"])
    args.shift_used = (args.shift if args.shift is not None
                       else p.get("shift", DEFAULT_SHIFT))
    args.lightning_strength_used = (args.lightning_strength
                                    if args.lightning_strength is not None
                                    else p.get("lightning_strength",
                                               DEFAULT_LIGHTNING_STRENGTH))


def latent_line(args):
    if args.latent_used == "image":
        return "image"
    if not args.refs:
        return "empty (no refs)"
    return f"empty {args.aspect_short} {args.megapixels:g} MP"


def sampling_line(args):
    extra = ""
    if args.lightning:
        extra += f", lightning {args.lightning_strength_used:g}"
    if args.denoise != 1.0:
        extra += f", denoise {args.denoise:g}"
    src = " (preset)" if args.preset else ""
    return (f"{args.steps_used} steps, CFG {args.cfg_used:g}, "
            f"{args.sampler_used}/{args.scheduler_used}, shift {args.shift_used:g}"
            f"{extra}{src}")


def loras_line(args):
    parts = [f"skin {args.skin_lora:g}"] if args.skin_lora > 0 else []
    parts += [f"{name} {strength:g}" for name, strength in args.loras]
    return ", ".join(parts) if parts else None


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    pid = None
    try:
        if args.list_presets:
            cc.print_presets(MODEL_PRESETS, PRESET_FIELDS)
            return 0
        if not (args.resume or args.cancel or args.list_models):
            validate(args, parser)
            if args.dry_run:
                args.ref_names = [f"<upload:{os.path.basename(r)}>" for r in args.refs]
                print(json.dumps({"prompt": build_graph(args)}, indent=1))
                return 0

        api = cc.Api(args.base_url, cc.load_key(args.key_file),
                     f"qwen_image_edit/{VERSION}")

        if args.list_models:
            cc.print_names(args.list_models,
                           cc.names_from_info(cc.object_info(api),
                                              LIST_KINDS[args.list_models]),
                           args.filter)
            return 0
        if args.cancel:
            cc.cancel(api, args.cancel)
            return 0

        args.out = cc.ensure_out_dir(args.out or cc.default_out(OUT_SUBDIR))
        cc.resume_args(args.out, args.key_file)
        if args.resume:
            pid = args.resume
            local_prefix = f"qwen_job_{pid[:8]}"
        else:
            args.ref_names = [resolve_ref(api, r) for r in args.refs]
            pid = cc.submit(api, build_graph(args))
            local_prefix = args.local_prefix

        status, st = cc.wait_for_job(api, pid, args.wait, args.stall, interval=3.0)
        cc.emit_paths(cc.finish(api, pid, status, st, args.out, local_prefix, ".png"))
        if not args.resume:
            emit(image=f"{args.setup}, {len(args.refs)} ref(s), latent {latent_line(args)}",
                 sampling=sampling_line(args),
                 loras=loras_line(args),
                 seed=args.seed,
                 model=args.model_name)
        emit(prompt_id=pid)
        return 0
    except Fail as e:
        return cc.report(e, pid)
    except KeyboardInterrupt:
        return cc.interrupted(pid)


if __name__ == "__main__":
    sys.exit(main())
