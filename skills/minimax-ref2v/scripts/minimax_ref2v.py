#!/usr/bin/env python3
"""minimax_ref2v - submit a baked MiniMax H3 reference-to-video(+audio) workflow to Comfy Cloud.

Uploads the reference images, submits the job, downloads the clip. Python 3.10+ stdlib
only (plus skills/_shared/comfy_cloud.py from this repo). Prints a short `key: value` block.

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

VERSION = "1.1.1"
OUT_SUBDIR = "minimax-ref2v"  # default --out: see comfy_cloud.default_out()

# ---------------------------------------------------------------- baked config
# From minimax_ref2v_harness.json.
MODEL = "TenStrip__10Eros-Max__10Eros_Max_h3_8stepTURBO_beta6_int8.safetensors"
TEXT_ENCODER = "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
VIDEO_VAE = "minimax_h3_video_vae_fp16.safetensors"
AUDIO_VAE = "minimax_h3_audio_vae_fp32.safetensors"
LIGHTNING_LORA = "minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors"
STEPS_FULL, STEPS_LIGHTNING = 8, 4
SAMPLER, SCHEDULER = "res_multistep", "simple"
FPS = 24
DEFAULT_ASPECT = "4:3 (Standard)"
DEFAULT_MEGAPIXELS = 0.2
DEFAULT_DURATION = 10.0
MIN_DURATION, MAX_DURATION = 5.0, 15.0  # trained band is roughly 124..362 frames
MAX_REFS = 5  # the node takes up to 5 reference images
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
MAX_VIDEOS = 3  # official Ref2VA cap; each video's soundtrack becomes <Audio N> too
MAX_VIDEO_BYTES = 100 * 1024 * 1024
VIDEO_EXTS = {".mp4", ".webm", ".mov", ".mkv"}

# Per-model sampling presets. When the diffusion model in use (MODEL, or --ckpt) matches a
# key, its settings replace the baked ones above; explicit --sampler/--scheduler/--steps/
# --lightning still win, and --no-preset ignores the table. Keys are filenames; matching
# also accepts the name without extension. Any subset of:
#   sampler, scheduler       KSamplerSelect / BasicScheduler names
#   lightning                True/False: default state of the 4-step lightning LoRA
#   steps_lightning          steps when lightning is on  (baked: STEPS_LIGHTNING)
#   steps_full               steps when lightning is off (baked: STEPS_FULL)
#   note                     free text shown by --list-presets
MODEL_PRESETS = {
    # "some_h3_finetune.safetensors": {"sampler": "euler", "scheduler": "beta",
    #                                  "lightning": False, "steps_full": 12,
    #                                  "note": "author's recommended"},
}
PRESET_FIELDS = ("sampler", "scheduler", "lightning", "steps_lightning", "steps_full")

# kind -> [(node class, input field)], first one present in /api/object_info wins
LIST_KINDS = {
    "model": [("UNETLoader", "unet_name")],
    "lora": [("LoraLoaderModelOnly", "lora_name"), ("LoraLoader", "lora_name")],
    "aspect": [("ResolutionSelector", "aspect_ratio")],
    "sampler": [("KSamplerSelect", "sampler_name")],
    "scheduler": [("BasicScheduler", "scheduler")],
}


def frames_for(seconds):
    """Frame count the node accepts: >= 5 and congruent to 5 mod 17 (5 s -> 124, 10 s -> 243)."""
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
    g["res"] = {"class_type": "ResolutionSelector",
                "inputs": {"aspect_ratio": a.aspect, "megapixels": a.megapixels, "multiple": 8}}

    ref_inputs = {}
    for i, name in enumerate(a.ref_names):
        g[f"img_{i}"] = {"class_type": "LoadImage", "inputs": {"image": name}}
        ref_inputs[f"ref_images.ref_image_{i}"] = [f"img_{i}", 0]
    # A video reference is a batch of frames (capped at the output length, as in the source
    # graph). Its soundtrack goes to the paired ref_video_audios socket ("soundtrack of the
    # same-numbered reference video"), not ref_audios ("standalone reference audio") as in the
    # source graph. It is <Audio N> when --video-audio is ref or both.
    for i, name in enumerate(a.video_names):
        g[f"vid_{i}"] = {"class_type": "VHS_LoadVideo",
                         "inputs": {"video": name, "force_rate": a.video_fps,
                                    "custom_width": a.video_width,
                                    "custom_height": a.video_height,
                                    "frame_load_cap": a.video_frames_used,
                                    "skip_first_frames": a.video_skip, "select_every_nth": 1,
                                    "format": "AnimateDiff"}}
        ref_inputs[f"ref_videos.ref_video_{i}"] = [f"vid_{i}", 0]
        if a.video_audio in ("ref", "both"):
            ref_inputs[f"ref_video_audios.ref_video_audio_{i}"] = [f"vid_{i}", 2]
    g["ref"] = {"class_type": "MiniMaxH3ReferenceToVideo",
                "inputs": {"prompt": a.prompt_text, "width": ["res", 0], "height": ["res", 1],
                           "length": a.frames, "ref_image_size": a.ref_size,
                           "clip": ["clip", 0], "vae": ["vae", 0], "audio_vae": ["avae", 0],
                           **ref_inputs}}

    # --lora stacks model-only LoRAs in the order given. The guider sees lightning (if on)
    # then the stack. As in the source graph, the scheduler never sees the lightning LoRA,
    # so with lightning on the stack is built twice (lora_N on the guider side, sched_lora_N
    # on the scheduler side); with lightning off both sides share one chain.
    def lora(nid, name, strength, src):
        g[nid] = {"class_type": "LoraLoaderModelOnly",
                  "inputs": {"lora_name": name, "strength_model": strength, "model": src}}
        return [nid, 0]

    def stack(prefix, src):
        for i, (name, strength) in enumerate(a.loras):
            src = lora(f"{prefix}_{i}", name, strength, src)
        return src

    if a.lightning:
        model = stack("lora", lora("lightning", LIGHTNING_LORA, 1.0, ["unet", 0]))
        sched_model = stack("sched_lora", ["unet", 0])
    else:
        model = sched_model = stack("lora", ["unet", 0])

    g["sel"] = {"class_type": "KSamplerSelect", "inputs": {"sampler_name": a.sampler_used}}
    g["sched"] = {"class_type": "BasicScheduler",
                  "inputs": {"scheduler": a.scheduler_used, "steps": a.steps_used, "denoise": 1,
                             "model": sched_model}}
    g["noise"] = {"class_type": "RandomNoise", "inputs": {"noise_seed": a.seed}}
    g["guider"] = {"class_type": "BasicGuider",
                   "inputs": {"model": model, "conditioning": ["ref", 0]}}
    g["sampler"] = {"class_type": "SamplerCustomAdvanced",
                    "inputs": {"noise": ["noise", 0], "guider": ["guider", 0],
                               "sampler": ["sel", 0], "sigmas": ["sched", 0],
                               "latent_image": ["ref", 1]}}
    # Final soundtrack: generated by the model, or (passthrough / both) video 1's own track
    # fed straight to the renderer, so it lands in the clip 1:1.
    if a.passthrough_audio:
        audio = ["vid_0", 2]
    else:
        g["adec"] = {"class_type": "VAEDecodeAudio",
                     "inputs": {"samples": ["sampler", 0], "vae": ["avae", 0]}}
        audio = ["adec", 0]
    g["vdec"] = {"class_type": "VAEDecode",
                 "inputs": {"samples": ["sampler", 0], "vae": ["vae", 0]}}
    g["video"] = {"class_type": "CreateVideo",
                  "inputs": {"fps": FPS, "bit_depth": 8, "color_space": "sRGB",
                             "chroma_subsampling": "420", "codec": "auto",
                             "images": ["vdec", 0], "audio": audio}}
    g["save"] = {"class_type": "SaveVideo",
                 "inputs": {"filename_prefix": f"video/{a.prefix}", "format": "auto",
                            "format.codec": "auto", "codec": "auto", "video": ["video", 0]}}
    return g


# ---------------------------------------------------------------- uploads
def resolve_refs(api, refs, kind):
    """Local files are uploaded; a bare name that is not a local file is taken as already on Cloud."""
    names = []
    for ref in refs:
        if os.path.isfile(ref):
            names.append(cc.upload_file(api, ref))
        elif os.sep not in ref and "/" not in ref:
            print(f"warning: {ref} is not a local file; using it as a name already on Cloud")
            names.append(ref)
        else:
            raise Fail("error", f"usage: reference {kind} not found: {ref}", 3)
    return names


def resolve_aspect(api, want):
    """'16:9' -> the unique catalog option that starts with it, e.g. '16:9 (Widescreen)'."""
    if "(" in want:
        return want
    options = cc.names_from_info(cc.object_info(api), LIST_KINDS["aspect"])
    hits = [o for o in options if o == want or o.startswith(want + " ")]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        print(f"warning: aspect '{want}' not in the catalog; submitting as-is "
              f"(see --list-models aspect)")
        return want
    raise Fail("error", f"usage: ambiguous --aspect '{want}': " + ", ".join(hits[:4]), 3)


# ---------------------------------------------------------------- cli
def build_parser():
    p = cc.Parser(prog="minimax_ref2v", description=__doc__,
                  formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--prompt", help="the full six-section Ref2VA prompt (see SKILL.md)")
    p.add_argument("--prompt-file", metavar="FILE", help="read the prompt from FILE ('-' = stdin)")
    p.add_argument("--ref", dest="refs", action="append", default=[], metavar="IMAGE",
                   help=f"reference image, repeatable, 1..{MAX_REFS}: <Picture 1>, <Picture 2>, ... "
                        f"in the order given. A local file is uploaded")
    p.add_argument("--video", dest="videos", action="append", default=[], metavar="VIDEO",
                   help=f"reference video for motion/camera, repeatable, up to {MAX_VIDEOS}: "
                        f"<Video 1>, <Video 2>, ... in the order given. A local file is uploaded; "
                        f"see --video-audio for its soundtrack")
    p.add_argument("--video-audio", choices=("ref", "passthrough", "both", "off"), default="ref",
                   help="where each --video's soundtrack goes: ref = to the model as <Audio N> "
                        "(final audio is generated); passthrough = video 1's track straight into "
                        "the output 1:1, the model never hears it; both = to the model and 1:1 "
                        "into the output; off = nowhere (default ref)")
    p.add_argument("--no-video-audio", dest="video_audio", action="store_const", const="off",
                   help="same as --video-audio off")
    p.add_argument("--video-fps", type=float, default=FPS, metavar="FPS",
                   help=f"resample each --video to this frame rate before use (default {FPS}, "
                        f"the model's rate; 0 = keep the file's own rate)")
    p.add_argument("--video-skip", type=int, default=0, metavar="N",
                   help="skip the first N frames of each --video (default 0)")
    p.add_argument("--video-frames", type=int, default=None, metavar="N",
                   help="load at most N frames of each --video (default: the output length; "
                        "0 = the whole file)")
    p.add_argument("--video-width", type=int, default=0, metavar="W",
                   help="resize --video frames to this width (default 0 = keep)")
    p.add_argument("--video-height", type=int, default=0, metavar="H",
                   help="resize --video frames to this height (default 0 = keep)")
    p.add_argument("--duration", type=float, default=DEFAULT_DURATION,
                   help=f"seconds, {MIN_DURATION:g}..{MAX_DURATION:g} (default {DEFAULT_DURATION:g})")
    p.add_argument("--aspect", default=DEFAULT_ASPECT,
                   help=f"aspect ratio, e.g. '16:9' or '4:3 (Standard)' (default '{DEFAULT_ASPECT}')")
    p.add_argument("--megapixels", type=float, default=DEFAULT_MEGAPIXELS,
                   help=f"frame size in megapixels (default {DEFAULT_MEGAPIXELS}); larger is slower")
    p.add_argument("--seed", type=int, default=None, help="default: random")
    p.add_argument("--lightning", choices=("auto", "on", "off"), default="auto",
                   help=f"4-step lightning LoRA: auto = on unless the model's preset says off; "
                        f"off = {STEPS_FULL} steps, slower, better identity and cadence")
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
    p.add_argument("--ref-size", choices=("match", "max"), default="match",
                   help="reference image resolution: match = cheaper, max = best identity, slower")
    p.add_argument("--lora", dest="loras", type=cc.parse_lora, action="append", default=[],
                   metavar="NAME[:STRENGTH]",
                   help="model-only LoRA; repeat to stack, applied in the order given "
                        "(strength defaults to 1.0)")
    p.add_argument("--ckpt", "--model", dest="ckpt", metavar="NAME", default=None,
                   help=f"override the diffusion model (default {MODEL}); exact filename")
    p.add_argument("--force-prompt", action="store_true",
                   help="skip the check that every <Picture N> in the prompt has a --ref")
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


def validate(args, parser):
    args.prompt_text = read_prompt(args, parser)
    if len(args.refs) > MAX_REFS:
        parser.error(f"at most {MAX_REFS} --ref images (got {len(args.refs)})")
    if len(args.videos) > MAX_VIDEOS:
        parser.error(f"at most {MAX_VIDEOS} --video files (got {len(args.videos)})")
    if not args.refs and not args.videos:
        parser.error("give at least one --ref image or --video")
    if args.video_audio in ("passthrough", "both") and not args.videos:
        parser.error(f"--video-audio {args.video_audio} needs a --video")
    args.passthrough_audio = args.video_audio in ("passthrough", "both")
    for flag, files, exts, cap, what in (
            ("--ref", args.refs, IMAGE_EXTS, MAX_UPLOAD_BYTES, "png/jpg/webp"),
            ("--video", args.videos, VIDEO_EXTS, MAX_VIDEO_BYTES, "mp4/webm/mov/mkv")):
        for f in files:
            if os.path.isfile(f):
                if os.path.splitext(f)[1].lower() not in exts:
                    parser.error(f"{flag} must be {what}: {os.path.basename(f)}")
                if os.path.getsize(f) > cap:
                    parser.error(f"{flag} over {cap >> 20} MB: {os.path.basename(f)}")
    if not 0 <= args.video_fps <= 60:  # VHS force_rate range
        parser.error("--video-fps must be 0 (keep) or up to 60")
    if args.video_skip < 0:
        parser.error("--video-skip must be 0 or more")
    if args.video_frames is not None and args.video_frames != 0 and args.video_frames < 5:
        parser.error("--video-frames must be 0 (whole file) or at least 5")
    for flag, val in (("--video-width", args.video_width), ("--video-height", args.video_height)):
        if val and not 64 <= val <= 4096:
            parser.error(f"{flag} must be 0 (keep) or 64..4096")
    if not MIN_DURATION <= args.duration <= MAX_DURATION:
        parser.error(f"--duration must be {MIN_DURATION:g}..{MAX_DURATION:g} seconds")
    if not 0.1 <= args.megapixels <= 2.0:  # ResolutionSelector's own minimum is 0.1
        parser.error("--megapixels must be 0.1..2.0")
    if args.steps is not None and not 1 <= args.steps <= 50:
        parser.error("--steps must be 1..50")
    if args.seed is None:
        args.seed = random.randint(0, 2**50)
    if not 0 <= args.seed < 2**64:
        parser.error("--seed must be 0..2^64-1")

    if not args.force_prompt:
        have = {"Picture": len(args.refs), "Video": len(args.videos),
                "Audio": len(args.videos) if args.video_audio in ("ref", "both") else 0}
        flags = {"Picture": "--ref", "Video": "--video",
                 "Audio": "--video soundtrack sent to the model (--video-audio ref|both)"}
        for label, count in have.items():
            tags = {int(n) for n in re.findall(rf"<{label} (\d+)>", args.prompt_text)}
            if tags and max(tags) > count:
                parser.error(f"prompt uses <{label} {max(tags)}> but only {count} {flags[label]} "
                             f"given (--force-prompt to skip this check)")

    args.model_name = args.ckpt or MODEL
    if args.ckpt and not os.path.splitext(args.ckpt)[1]:
        args.model_name = args.ckpt + ".safetensors"
    resolve_sampling(args)
    args.frames = frames_for(args.duration)
    args.video_frames_used = args.frames if args.video_frames is None else args.video_frames
    args.prefix = f"ref2v_{time.strftime('%y%m%d-%H%M%S')}"
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
                args.ref_names = [f"<upload:{os.path.basename(r)}>" for r in args.refs]
                args.video_names = [f"<upload:{os.path.basename(v)}>" for v in args.videos]
                print(json.dumps({"prompt": build_graph(args)}, indent=1))
                return 0

        api = cc.Api(args.base_url, cc.load_key(args.key_file), f"minimax_ref2v/{VERSION}")

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
            local_prefix = f"ref2v_job_{pid[:8]}"
        else:
            args.aspect = resolve_aspect(api, args.aspect)
            args.ref_names = resolve_refs(api, args.refs, "image")
            args.video_names = resolve_refs(api, args.videos, "video")
            pid = cc.submit(api, build_graph(args))
            local_prefix = args.local_prefix

        status, st = cc.wait_for_job(api, pid, args.wait, args.stall, interval=3.0)
        cc.emit_paths(cc.finish(api, pid, status, st, args.out, local_prefix, ".mp4"))
        if not args.resume:
            emit(clip=f"{args.duration:g}s, {FPS} fps, {args.frames} frames, {args.aspect}",
                 refs=len(args.refs), videos=len(args.videos),
                 audio="video 1 soundtrack (1:1)" if args.passthrough_audio else "generated",
                 seed=args.seed,
                 sampling=sampling_line(args),
                 model=args.model_name)
        emit(prompt_id=pid)
        return 0
    except Fail as e:
        return cc.report(e, pid)
    except KeyboardInterrupt:
        return cc.interrupted(pid)


if __name__ == "__main__":
    sys.exit(main())
