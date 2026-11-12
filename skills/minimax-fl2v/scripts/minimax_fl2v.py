#!/usr/bin/env python3
"""minimax_fl2v - submit a baked MiniMax H3 first/last-frame-to-video(+audio) workflow to Comfy Cloud.

Uploads the first and/or last frame, submits the job, downloads the clip. Python 3.10+
stdlib only (plus skills/_shared/comfy_cloud.py from this repo). Prints a short
`key: value` block.

Modes (picked from the frames given): fl2va = --first + --last, i2va = --first only,
l2va = --last only.

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

VERSION = "1.0.0"
OUT_SUBDIR = "minimax-fl2v"  # default --out: see comfy_cloud.default_out()

# ---------------------------------------------------------------- baked config
# From dev/minimax-fl2v/source_workflow.json (minimax_fl2va_api.json).
MODEL = "minimax_h3_fl2va_pruned_int8_convrot.safetensors"
TEXT_ENCODER = "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
VIDEO_VAE = "minimax_h3_video_vae_fp16.safetensors"
AUDIO_VAE = "minimax_h3_audio_vae_fp32.safetensors"
LIGHTNING_LORA = "minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors"
STEPS_FULL, STEPS_LIGHTNING = 20, 8
SAMPLER, SCHEDULER = "res_multistep", "simple"
FPS = 24
DEFAULT_MEGAPIXELS = 0.2
DEFAULT_DURATION = 5.0
MIN_DURATION, MAX_DURATION = 4.0, 15.0  # model range; 5-8 s is the sweet spot
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
PROMPT_FIELDS = ("integrated_multimodal_description:", "overall_soundscape:", "non_diegetic_music:")

# Per-model sampling presets. When the diffusion model in use (MODEL, or --ckpt) matches a
# key, its settings replace the baked ones above; explicit --sampler/--scheduler/--steps/
# --lightning still win, and --no-preset ignores the table. Keys are filenames; matching
# also accepts the name without extension. Any subset of:
#   sampler, scheduler       KSamplerSelect / BasicScheduler names
#   lightning                True/False: default state of the turbo LoRA
#   steps_lightning          steps when lightning is on  (baked: STEPS_LIGHTNING)
#   steps_full               steps when lightning is off (baked: STEPS_FULL)
#   note                     free text shown by --list-presets
MODEL_PRESETS = {
    # "some_h3_fl2va_build.safetensors": {"lightning": False, "steps_full": 24, "note": "..."},
}
PRESET_FIELDS = ("sampler", "scheduler", "lightning", "steps_lightning", "steps_full")

# kind -> [(node class, input field)], first one present in /api/object_info wins
LIST_KINDS = {
    "model": [("UNETLoader", "unet_name")],
    "lora": [("LoraLoaderModelOnly", "lora_name"), ("LoraLoader", "lora_name")],
    "sampler": [("KSamplerSelect", "sampler_name")],
    "scheduler": [("BasicScheduler", "scheduler")],
}


def frames_for(seconds):
    """Frame count the node accepts: >= 5 and congruent to 5 mod 17 (5 s -> 124, 8 s -> 192)."""
    n = max(5, round(seconds * FPS))
    return n + (5 - n % 17) % 17


# ---------------------------------------------------------------- graph
def build_graph(a):
    g = {}
    g["unet"] = {"class_type": "UNETLoader",
                 "inputs": {"unet_name": a.model_name, "weight_dtype": "default"}}
    g["clip"] = {"class_type": "CLIPLoader",
                 "inputs": {"clip_name": TEXT_ENCODER, "type": "minimax", "device": "default"}}
    g["vae"] = {"class_type": "VAELoader", "inputs": {"vae_name": VIDEO_VAE}}
    g["avae"] = {"class_type": "VAELoader", "inputs": {"vae_name": AUDIO_VAE}}

    # Each frame is scaled to the same pixel budget (multiples of 32, as the node wants).
    # The clip size comes from the first frame, or the last frame when there is no first.
    frames, size_src = {}, None
    for key, name in (("first", a.first_name), ("last", a.last_name)):
        if not name:
            continue
        g[f"{key}_img"] = {"class_type": "LoadImage", "inputs": {"image": name}}
        g[f"{key}_scaled"] = {"class_type": "ImageScaleToTotalPixels",
                              "inputs": {"image": [f"{key}_img", 0], "upscale_method": "nearest-exact",
                                         "megapixels": a.megapixels, "resolution_steps": 32}}
        frames[f"{key}_frame"] = [f"{key}_scaled", 0]
        size_src = size_src or f"{key}_scaled"
    g["size"] = {"class_type": "GetImageSize", "inputs": {"image": [size_src, 0]}}
    g["i2v"] = {"class_type": "MiniMaxH3ImageToVideo",
                "inputs": {"prompt": a.prompt_text, "width": ["size", 0], "height": ["size", 1],
                           "length": a.frames, "clip": ["clip", 0], "vae": ["vae", 0], **frames}}

    # Model chain: turbo LoRA (if on), then --lora in the order given. Guider and scheduler
    # share it, as in the source graph's If/Else switch.
    model = ["unet", 0]
    chain = ([("lightning", LIGHTNING_LORA, 1.0)] if a.lightning else []) + \
        [(f"lora_{i}", n, s) for i, (n, s) in enumerate(a.loras)]
    for nid, name, strength in chain:
        g[nid] = {"class_type": "LoraLoaderModelOnly",
                  "inputs": {"lora_name": name, "strength_model": strength, "model": model}}
        model = [nid, 0]

    g["sel"] = {"class_type": "KSamplerSelect", "inputs": {"sampler_name": a.sampler_used}}
    g["sched"] = {"class_type": "BasicScheduler",
                  "inputs": {"scheduler": a.scheduler_used, "steps": a.steps_used, "denoise": 1,
                             "model": model}}
    g["noise"] = {"class_type": "RandomNoise", "inputs": {"noise_seed": a.seed}}
    g["guider"] = {"class_type": "BasicGuider",
                   "inputs": {"model": model, "conditioning": ["i2v", 0]}}
    g["sampler"] = {"class_type": "SamplerCustomAdvanced",
                    "inputs": {"noise": ["noise", 0], "guider": ["guider", 0],
                               "sampler": ["sel", 0], "sigmas": ["sched", 0],
                               "latent_image": ["i2v", 1]}}
    g["adec"] = {"class_type": "VAEDecodeAudio",
                 "inputs": {"samples": ["sampler", 0], "vae": ["avae", 0]}}
    g["vdec"] = {"class_type": "VAEDecode",
                 "inputs": {"samples": ["sampler", 0], "vae": ["vae", 0]}}
    g["video"] = {"class_type": "CreateVideo",
                  "inputs": {"fps": FPS, "bit_depth": 8, "color_space": "sRGB",
                             "chroma_subsampling": "none", "codec": "none",
                             "images": ["vdec", 0], "audio": ["adec", 0]}}
    g["save"] = {"class_type": "SaveVideo",
                 "inputs": {"filename_prefix": f"video/{a.prefix}", "format": "auto",
                            "format.codec": "auto", "codec": "auto", "video": ["video", 0]}}
    return g


def resolve_frame(api, ref):
    """A local file is uploaded; a bare name that is not a local file is taken as already on Cloud."""
    if not ref:
        return None
    if os.path.isfile(ref):
        return cc.upload_file(api, ref)
    if os.sep not in ref and "/" not in ref:
        print(f"warning: {ref} is not a local file; using it as a name already on Cloud")
        return ref
    raise Fail("error", f"usage: frame image not found: {ref}", 3)


# ---------------------------------------------------------------- cli
def build_parser():
    p = cc.Parser(prog="minimax_fl2v", description=__doc__,
                  formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--prompt", help="the full FL2VA prompt: alignment line + three fields (see SKILL.md)")
    p.add_argument("--prompt-file", metavar="FILE", help="read the prompt from FILE ('-' = stdin)")
    p.add_argument("--first", metavar="IMAGE",
                   help="first frame (Picture 1); the clip starts on it and takes its size/aspect")
    p.add_argument("--last", metavar="IMAGE",
                   help="last frame (Picture 2, or Picture 1 when there is no --first); the clip lands on it")
    p.add_argument("--duration", type=float, default=DEFAULT_DURATION,
                   help=f"seconds, {MIN_DURATION:g}..{MAX_DURATION:g} (default {DEFAULT_DURATION:g}); "
                        f"the prompt's S.SS mark must match")
    p.add_argument("--megapixels", type=float, default=DEFAULT_MEGAPIXELS,
                   help=f"frame size in megapixels (default {DEFAULT_MEGAPIXELS}); larger is slower")
    p.add_argument("--seed", type=int, default=None, help="default: random")
    p.add_argument("--lightning", choices=("auto", "on", "off"), default="auto",
                   help=f"turbo LoRA: auto = on ({STEPS_LIGHTNING} steps) unless the model's preset says off; "
                        f"off = {STEPS_FULL} steps, slower")
    p.add_argument("--no-lightning", dest="lightning", action="store_const", const="off",
                   help="same as --lightning off")
    p.add_argument("--steps", type=int, default=None,
                   help=f"override steps (default {STEPS_LIGHTNING} with lightning, {STEPS_FULL} without, "
                        f"or the model's preset)")
    p.add_argument("--sampler", default=None,
                   help=f"override sampler (default {SAMPLER} or the model's preset; --list-models sampler)")
    p.add_argument("--scheduler", default=None,
                   help=f"override scheduler (default {SCHEDULER} or the model's preset; "
                        f"--list-models scheduler)")
    p.add_argument("--no-preset", action="store_true",
                   help="ignore the per-model preset; use the baked sampling settings")
    p.add_argument("--lora", dest="loras", type=cc.parse_lora, action="append", default=[],
                   metavar="NAME[:STRENGTH]",
                   help="model-only LoRA; repeat to stack, applied in the order given "
                        "(strength defaults to 1.0)")
    p.add_argument("--ckpt", "--model", dest="ckpt", metavar="NAME", default=None,
                   help=f"override the diffusion model (default {MODEL}); exact filename")
    p.add_argument("--force-prompt", action="store_true",
                   help="skip the prompt checks (field names, Picture labels, S.SS vs --duration)")
    p.add_argument("--out", default=None,
                   help=f"output folder (default: $HARNESS_OUT/{OUT_SUBDIR}, else "
                        f"/workspace/artifacts/{OUT_SUBDIR} if /workspace exists, else "
                        f"./artifacts/{OUT_SUBDIR})")
    p.add_argument("--wait", type=float, default=30,
                   help="seconds to wait before returning 'pending' (default 30)")
    p.add_argument("--stall", type=float, default=1800,
                   help="fail if status unchanged this long (default 1800)")
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


def check_prompt(args, parser):
    """Catch the prompt mistakes that silently wreck an FL2VA render (see the prompting guide)."""
    text, hint = args.prompt_text, " (--force-prompt to skip this check)"
    missing = [f[:-1] for f in PROMPT_FIELDS if f not in text]
    if missing:
        parser.error(f"prompt is missing the field(s) {', '.join(missing)}; "
                     f"see references/prompting.md{hint}")
    pictures = {int(n) for n in re.findall(r"Picture (\d+)", text)}
    have = 2 if args.mode == "fl2va" else 1
    if pictures and max(pictures) > have:
        parser.error(f"prompt uses Picture {max(pictures)} but {args.mode} has only "
                     f"{have} frame{'s' if have > 1 else ''}{hint}")
    if args.mode == "fl2va" and 2 not in pictures:
        parser.error(f"fl2va prompt must align Picture 2 with the end of the clip{hint}")
    if args.mode in ("fl2va", "l2va"):
        marks = re.findall(r"aligns with the (\d+(?:\.\d+)?)-second mark", text)
        if not marks:
            parser.error(f"prompt has no 'aligns with the S.SS-second mark' alignment line{hint}")
        landing = marks[-1]
        want = {f"{args.duration:.2f}", f"{args.frames / FPS:.2f}"}
        if landing not in want:
            parser.error(f"alignment line lands at {landing} s but --duration is {args.duration:g} "
                         f"(write {args.duration:.2f}, or change --duration){hint}")


def validate(args, parser):
    args.prompt_text = read_prompt(args, parser)
    if not args.first and not args.last:
        parser.error("give --first and --last (fl2va), or just one of them (i2va / l2va)")
    args.mode = "fl2va" if args.first and args.last else ("i2va" if args.first else "l2va")
    for flag, f in (("--first", args.first), ("--last", args.last)):
        if f and os.path.isfile(f):
            if os.path.splitext(f)[1].lower() not in IMAGE_EXTS:
                parser.error(f"{flag} must be png/jpg/webp: {os.path.basename(f)}")
            if os.path.getsize(f) > MAX_UPLOAD_BYTES:
                parser.error(f"{flag} over {MAX_UPLOAD_BYTES >> 20} MB: {os.path.basename(f)}")
    if not MIN_DURATION <= args.duration <= MAX_DURATION:
        parser.error(f"--duration must be {MIN_DURATION:g}..{MAX_DURATION:g} seconds")
    if not 0.1 <= args.megapixels <= 2.0:
        parser.error("--megapixels must be 0.1..2.0")
    if args.steps is not None and not 1 <= args.steps <= 60:
        parser.error("--steps must be 1..60")
    if args.seed is None:
        args.seed = random.randint(0, 2**50)
    if not 0 <= args.seed < 2**64:
        parser.error("--seed must be 0..2^64-1")
    args.frames = frames_for(args.duration)
    if not args.force_prompt:
        check_prompt(args, parser)

    args.model_name = args.ckpt or MODEL
    if args.ckpt and not os.path.splitext(args.ckpt)[1]:
        args.model_name = args.ckpt + ".safetensors"
    resolve_sampling(args)
    args.prefix = f"fl2v_{time.strftime('%y%m%d-%H%M%S')}"
    args.local_prefix = f"{args.prefix}_s{args.seed}"


def resolve_sampling(args):
    """Sampling settings in force: explicit flag > model preset > baked."""
    key, p = (None, None) if args.no_preset else cc.find_preset(MODEL_PRESETS, args.model_name)
    p = p or {}
    args.preset = key
    args.lightning = (args.lightning == "on" or
                      (args.lightning == "auto" and p.get("lightning", True)))
    if args.lightning:
        default_steps = p.get("steps_lightning", STEPS_LIGHTNING)
    else:
        default_steps = p.get("steps_full", STEPS_FULL)
    args.steps_used = args.steps or default_steps
    args.sampler_used = args.sampler or p.get("sampler", SAMPLER)
    args.scheduler_used = args.scheduler or p.get("scheduler", SCHEDULER)


def sampling_line(args):
    light = " (lightning)" if args.lightning else ""
    src = " (preset)" if args.preset else ""
    return f"{args.steps_used} steps{light}, {args.sampler_used}/{args.scheduler_used}{src}"


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
                args.first_name = args.first and f"<upload:{os.path.basename(args.first)}>"
                args.last_name = args.last and f"<upload:{os.path.basename(args.last)}>"
                print(json.dumps({"prompt": build_graph(args)}, indent=1))
                return 0

        api = cc.Api(args.base_url, cc.load_key(args.key_file), f"minimax_fl2v/{VERSION}")

        if args.list_models:
            cc.print_names(args.list_models,
                           cc.names_from_info(cc.object_info(api), LIST_KINDS[args.list_models]),
                           args.filter)
            return 0
        if args.cancel:
            cc.cancel(api, args.cancel)
            return 0

        args.out = cc.ensure_out_dir(args.out or cc.default_out(OUT_SUBDIR))
        cc.resume_args(args.out, args.key_file)
        if args.resume:
            pid = args.resume
            local_prefix = f"fl2v_job_{pid[:8]}"
        else:
            args.first_name = resolve_frame(api, args.first)
            args.last_name = resolve_frame(api, args.last)
            pid = cc.submit(api, build_graph(args))
            local_prefix = args.local_prefix

        status, st = cc.wait_for_job(api, pid, args.wait, args.stall, interval=3.0)
        cc.emit_paths(cc.finish(api, pid, status, st, args.out, local_prefix, ".mp4"))
        if not args.resume:
            emit(clip=f"{args.mode}, {args.duration:g}s, {FPS} fps, {args.frames} frames, "
                      f"{args.megapixels:g} MP",
                 seed=args.seed, sampling=sampling_line(args), model=args.model_name)
        emit(prompt_id=pid)
        return 0
    except Fail as e:
        return cc.report(e, pid)
    except KeyboardInterrupt:
        return cc.interrupted(pid)


if __name__ == "__main__":
    sys.exit(main())
