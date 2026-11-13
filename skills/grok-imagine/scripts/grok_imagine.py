#!/usr/bin/env python3
"""grok_imagine - submit a baked Grok Imagine image workflow to Comfy Cloud.

Uploads the reference images, submits the job, downloads the images. Python 3.10+
stdlib only (plus skills/_shared/comfy_cloud.py from this repo). Prints a short
`key: value` block.

The default is grok-imagine-image-2.0 at quality low. Text-only prompts use
GrokImageNode: no image inputs and no blank EmptyImage nodes, and its --aspect auto
means 1:1 (that node has no auto). With --ref it uses GrokImageEditNodeV2, also
without blanks, and a custom --aspect works with a single reference image.

The older models (grok-imagine-image-quality, grok-imagine-image,
grok-imagine-image-pro) still need at least one image input, so blank EmptyImage
nodes fill the gap. A custom --aspect there is only honoured with 2+ image inputs,
so a blank is added for that too. xAI retired -quality and -pro: they now run as
grok-imagine-image-2.0 at low quality.

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

VERSION = "1.1.0"
OUT_SUBDIR = "grok-imagine"  # default --out: see comfy_cloud.default_out()

# ---------------------------------------------------------------- baked config
# From dev/grok-imagine/object_info_grok.json (GrokImageEditNodeV2).
ASPECTS = ("auto", "1:1", "2:3", "3:2", "3:4", "4:3", "9:16", "16:9",
           "9:19.5", "19.5:9", "9:20", "20:9", "1:2", "2:1")
RESOLUTIONS = ("1K", "2K")
QUALITIES = ("medium", "low")
DEFAULT_MODEL = "grok-imagine-image-2.0"
DEFAULT_ASPECT = "auto"
DEFAULT_RESOLUTION = "1K"
DEFAULT_QUALITY = "low"
MAX_COUNT = 10
MAX_SEED = 2147483647
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}

# Limits from the node's per-model specs. max_images = the images autogrow cap,
# aspect = has model.aspect_ratio, quality = allowed model.quality (none but 2.0),
# blank_for_aspect = blanks may be added to fill the image inputs (2.0 needs none).
MODELS = {
    "grok-imagine-image-quality": {"max_images": 3, "aspect": True, "quality": (),
                                   "blank_for_aspect": True,
                                   "note": "retired: runs as 2.0 low"},
    "grok-imagine-image-2.0": {"max_images": 3, "aspect": True, "quality": QUALITIES,
                               "blank_for_aspect": False, "note": "default"},
    "grok-imagine-image": {"max_images": 3, "aspect": True, "quality": (),
                           "blank_for_aspect": True, "note": ""},
    "grok-imagine-image-pro": {"max_images": 1, "aspect": False, "quality": (),
                               "blank_for_aspect": True,
                               "note": "retired: runs as 2.0 low"},
}
MAX_REFS = max(spec["max_images"] for spec in MODELS.values())


def dummy_count(args):
    """Blank EmptyImages needed: 1 image input minimum, 2 when --aspect is not auto.

    grok-imagine-image-2.0 needs none: text-only prompts use GrokImageNode and the
    edit node takes its aspect with a single reference image.
    """
    if not MODELS[args.model]["blank_for_aspect"]:
        return 0
    need = 1 if args.aspect == "auto" else 2
    return max(0, need - len(args.refs))


# ---------------------------------------------------------------- graph
def build_graph(a):
    g = {}
    spec = MODELS[a.model]
    if a.model == "grok-imagine-image-2.0" and not a.ref_names:
        # Text-to-image: GrokImageNode has flat (non-combo) inputs and no images.
        inputs = {"model": a.model,
                  "prompt": a.prompt_text,
                  "aspect_ratio": a.aspect_sent,
                  "number_of_images": a.count,
                  "seed": a.seed,
                  "resolution": a.resolution}
        if spec["quality"]:
            inputs["quality"] = a.quality_used
        g["grok"] = {"class_type": "GrokImageNode", "inputs": inputs}
    else:
        images = []
        for i, name in enumerate(a.ref_names):
            g[f"ref_{i}"] = {"class_type": "LoadImage", "inputs": {"image": name}}
            images.append(f"ref_{i}")
        for i in range(a.dummies):
            g[f"dummy_{i}"] = {"class_type": "EmptyImage",
                               "inputs": {"width": 512, "height": 512, "batch_size": 1, "color": 0}}
            images.append(f"dummy_{i}")

        inputs = {"prompt": a.prompt_text,
                  "seed": a.seed,
                  "model": a.model,
                  "model.resolution": a.resolution,
                  "model.number_of_images": a.count}
        if spec["aspect"]:
            inputs["model.aspect_ratio"] = a.aspect_sent
        if spec["quality"]:
            inputs["model.quality"] = a.quality_used
        for i, nid in enumerate(images):
            inputs[f"model.images.image_{i + 1}"] = [nid, 0]
        g["grok"] = {"class_type": "GrokImageEditNodeV2", "inputs": inputs}
    g["save"] = {"class_type": "SaveImage",
                 "inputs": {"filename_prefix": a.prefix, "images": ["grok", 0]}}
    return g


# ---------------------------------------------------------------- uploads
def resolve_refs(api, refs):
    """Local files are uploaded; a bare name that is not a local file is taken as already on Cloud."""
    names = []
    for ref in refs:
        if os.path.isfile(ref):
            names.append(cc.upload_file(api, ref))
        elif os.sep not in ref and "/" not in ref:
            print(f"warning: {ref} is not a local file; using it as a name already on Cloud")
            names.append(ref)
        else:
            raise Fail("error", f"usage: reference image not found: {ref}", 3)
    return names


# ---------------------------------------------------------------- cli
def build_parser():
    p = cc.Parser(prog="grok_imagine", description=__doc__,
                  formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--prompt", help="what to generate, or how to edit the --ref image(s)")
    p.add_argument("--prompt-file", metavar="FILE", help="read the prompt from FILE ('-' = stdin)")
    p.add_argument("--ref", dest="refs", action="append", default=[], metavar="IMAGE",
                   help=f"reference image, repeatable, up to {MAX_REFS}: image 1, image 2, ... "
                        f"in the order given. A local file is uploaded; a bare name is used as "
                        f"a name already on Cloud")
    p.add_argument("--model", choices=tuple(MODELS), default=DEFAULT_MODEL,
                   help=f"Grok Imagine model (default {DEFAULT_MODEL}); text-only 2.0 "
                        f"prompts need no blanks, older models add them; --list-models "
                        f"for limits")
    p.add_argument("--aspect", choices=ASPECTS, default=DEFAULT_ASPECT,
                   help=f"output aspect ratio (default {DEFAULT_ASPECT}); for a "
                        f"text-only {DEFAULT_MODEL} run auto means 1:1; older models need "
                        f"2 image inputs for a ratio other than auto, so one blank is "
                        f"added when needed")
    p.add_argument("--resolution", choices=RESOLUTIONS, default=DEFAULT_RESOLUTION,
                   help=f"output resolution (default {DEFAULT_RESOLUTION})")
    p.add_argument("--quality", choices=QUALITIES, default=None,
                   help=f"quality level; {DEFAULT_MODEL} only "
                        f"(default {DEFAULT_QUALITY} for that model)")
    p.add_argument("--count", type=int, default=1,
                   help=f"number of images, 1..{MAX_COUNT} (default 1)")
    p.add_argument("--seed", type=int, default=None,
                   help=f"0..{MAX_SEED} (default: random)")
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
    g.add_argument("--list-models", action="store_true",
                   help="print the model table (no key or network needed)")
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
    spec = MODELS[args.model]
    if len(args.refs) > spec["max_images"]:
        parser.error(f"{args.model} takes at most {spec['max_images']} --ref image(s) "
                     f"(got {len(args.refs)})")
    if args.aspect != "auto" and not spec["aspect"]:
        parser.error(f"{args.model} has no --aspect (only 'auto')")
    if args.quality is not None and not spec["quality"]:
        parser.error(f"{args.model} has no --quality")
    args.quality_used = (args.quality or DEFAULT_QUALITY) if spec["quality"] else None
    # GrokImageNode has no 'auto': a text-only 2.0 job sends (and reports) 1:1.
    args.aspect_sent = args.aspect
    if args.model == "grok-imagine-image-2.0" and not args.refs and args.aspect == "auto":
        args.aspect_sent = "1:1"
    args.dummies = dummy_count(args)
    total = len(args.refs) + args.dummies
    if total > spec["max_images"]:
        parser.error(f"{args.model} takes at most {spec['max_images']} image input(s); "
                     f"{len(args.refs)} ref(s) + {args.dummies} blank(s) = {total}")
    if not 1 <= args.count <= MAX_COUNT:
        parser.error(f"--count must be 1..{MAX_COUNT}")
    if args.seed is None:
        args.seed = random.randint(0, MAX_SEED)
    if not 0 <= args.seed <= MAX_SEED:
        parser.error(f"--seed must be 0..{MAX_SEED}")
    for ref in args.refs:
        if os.path.isfile(ref):
            if os.path.splitext(ref)[1].lower() not in IMAGE_EXTS:
                parser.error(f"--ref must be png/jpg/webp: {os.path.basename(ref)}")
            if os.path.getsize(ref) > MAX_UPLOAD_BYTES:
                parser.error(f"--ref over {MAX_UPLOAD_BYTES >> 20} MB: {os.path.basename(ref)}")
    args.prefix = f"grok_{time.strftime('%y%m%d-%H%M%S')}"
    args.local_prefix = f"{args.prefix}_s{args.seed}"


def print_models():
    print(f"models: {len(MODELS)} (default {DEFAULT_MODEL})")
    print(f"  {'model':<28} {'refs':>4}  {'aspect':<6}  {'quality':<11}  note")
    for name, spec in MODELS.items():
        quality = ", ".join(spec["quality"]) or "no"
        print(f"  {name:<28} {spec['max_images']:>4}  "
              f"{'yes' if spec['aspect'] else 'no':<6}  {quality:<11}  {spec['note'] or '-'}")


def result_line(args):
    line = (f"{args.model}, {args.aspect_sent}, {args.resolution}, {args.count} image(s), "
            f"{len(args.refs)} ref(s)")
    if args.quality_used:
        line += f", quality {args.quality_used}"
    return line


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    pid = None
    try:
        if args.list_models:
            print_models()
            return 0
        if not (args.resume or args.cancel):
            validate(args, parser)
            if args.dry_run:
                args.ref_names = [f"<upload:{os.path.basename(r)}>" for r in args.refs]
                print(json.dumps({"prompt": build_graph(args)}, indent=1))
                return 0

        api = cc.Api(args.base_url, cc.load_key(args.key_file), f"grok_imagine/{VERSION}")

        if args.cancel:
            cc.cancel(api, args.cancel)
            return 0

        args.out = cc.ensure_out_dir(args.out or cc.default_out(OUT_SUBDIR))
        cc.resume_args(args.out, args.key_file)
        if args.resume:
            pid = args.resume
            local_prefix = f"grok_job_{pid[:8]}"
        else:
            args.ref_names = resolve_refs(api, args.refs)
            pid = cc.submit(api, build_graph(args), partner=True)
            local_prefix = args.local_prefix

        status, st = cc.wait_for_job(api, pid, args.wait, args.stall, interval=2.0)
        cc.emit_paths(cc.finish(api, pid, status, st, args.out, local_prefix, ".png"))
        if not args.resume:
            emit(image=result_line(args), seed=args.seed)
        emit(prompt_id=pid)
        return 0
    except Fail as e:
        return cc.report(e, pid)
    except KeyboardInterrupt:
        return cc.interrupted(pid)


if __name__ == "__main__":
    sys.exit(main())
