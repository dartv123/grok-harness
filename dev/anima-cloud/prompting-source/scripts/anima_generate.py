#!/usr/bin/env python3
"""Generate images with Anima via a ComfyUI server's HTTP API.

Stdlib only. Builds an API-format graph matching the official Comfy template
(UNETLoader -> [LoRAs] -> KSampler, CLIPLoader type=stable_diffusion,
EmptyLatentImage, Qwen-Image VAE), submits to /prompt, polls /history,
downloads outputs from /view.

  python anima_generate.py --variant turbo --prompt "1girl, ..." --out ./outputs
  python anima_generate.py --variant base --prompt "..." --dry-run > workflow_api.json
"""
import argparse
import json
import os
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

CLIP_DEFAULT = "qwen_3_06b_base.safetensors"
VAE_DEFAULT = "qwen_image_vae.safetensors"
TURBO_LORA = "anima-turbo-lora-v0.2.safetensors"

BASE_PREFIX = "masterpiece, best quality, score_7, safe, "
BASE_NEG = ("worst quality, low quality, score_1, score_2, score_3, artist name, "
            "blurry, jpeg artifacts, chromatic aberration, nsfw, explicit")
AES_PREFIX = "masterpiece, best quality, safe, "
AES_NEG = ("worst quality, low quality, artist name, blurry, jpeg artifacts, "
           "chromatic aberration, nsfw, explicit")

PRESETS = {
    "turbo": dict(unet="anima-turbo-v1.1.safetensors", steps=10, cfg=1.0,
                  sampler="euler", scheduler="simple",
                  prefix=AES_PREFIX, negative="", loras=[]),
    "aesthetic": dict(unet="anima-aesthetic-v1.1.safetensors", steps=30, cfg=4.0,
                      sampler="er_sde", scheduler="simple",
                      prefix=AES_PREFIX, negative=AES_NEG, loras=[]),
    "base": dict(unet="anima-base-v1.0.safetensors", steps=30, cfg=4.0,
                 sampler="er_sde", scheduler="simple",
                 prefix=BASE_PREFIX, negative=BASE_NEG, loras=[]),
    "turbo-lora": dict(unet="anima-base-v1.0.safetensors", steps=8, cfg=1.0,
                       sampler="euler", scheduler="simple",
                       prefix=BASE_PREFIX, negative="",
                       loras=[(TURBO_LORA, 1.0)]),
}


def snap16(v):
    return max(16, int(round(v / 16.0)) * 16)


def parse_lora(s):
    name, _, strength = s.partition(":")
    return name, float(strength) if strength else 1.0


def build_graph(a):
    g = {
        "unet": {"class_type": "UNETLoader",
                 "inputs": {"unet_name": a.unet, "weight_dtype": a.weight_dtype}},
        "clip": {"class_type": "CLIPLoader",
                 "inputs": {"clip_name": a.clip, "type": "stable_diffusion",
                            "device": "default"}},
        "vae": {"class_type": "VAELoader", "inputs": {"vae_name": a.vae}},
    }
    model_ref = ["unet", 0]
    for i, (name, strength) in enumerate(a.loras):
        nid = f"lora{i}"
        g[nid] = {"class_type": "LoraLoaderModelOnly",
                  "inputs": {"model": model_ref, "lora_name": name,
                             "strength_model": strength}}
        model_ref = [nid, 0]
    g["pos"] = {"class_type": "CLIPTextEncode",
                "inputs": {"text": a.full_prompt, "clip": ["clip", 0]}}
    g["neg"] = {"class_type": "CLIPTextEncode",
                "inputs": {"text": a.negative, "clip": ["clip", 0]}}
    g["latent"] = {"class_type": "EmptyLatentImage",
                   "inputs": {"width": a.width, "height": a.height,
                              "batch_size": a.batch}}
    g["sampler"] = {"class_type": "KSampler",
                    "inputs": {"model": model_ref, "seed": a.seed, "steps": a.steps,
                               "cfg": a.cfg, "sampler_name": a.sampler,
                               "scheduler": a.scheduler, "positive": ["pos", 0],
                               "negative": ["neg", 0], "latent_image": ["latent", 0],
                               "denoise": 1.0}}
    g["decode"] = {"class_type": "VAEDecode",
                   "inputs": {"samples": ["sampler", 0], "vae": ["vae", 0]}}
    g["save"] = {"class_type": "SaveImage",
                 "inputs": {"images": ["decode", 0], "filename_prefix": a.prefix_name}}
    return g


def http(method, url, headers, body=None, timeout=60):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    for k, v in headers.items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def run(a, graph):
    base = a.server.rstrip("/")
    try:
        resp = json.loads(http("POST", f"{base}/prompt", a.headers,
                               {"prompt": graph, "client_id": str(uuid.uuid4())}))
    except urllib.error.HTTPError as e:
        sys.exit(f"ComfyUI rejected the graph ({e.code}):\n{e.read().decode(errors='replace')}")
    except urllib.error.URLError as e:
        sys.exit(f"Cannot reach ComfyUI at {base}: {e.reason}. Use --dry-run to export the graph.")
    if resp.get("node_errors"):
        sys.exit("Node errors:\n" + json.dumps(resp["node_errors"], indent=2))
    pid = resp["prompt_id"]
    print(f"queued prompt_id={pid} seed={a.seed}", file=sys.stderr)

    deadline = time.time() + a.timeout
    while time.time() < deadline:
        hist = json.loads(http("GET", f"{base}/history/{pid}", a.headers))
        if pid in hist:
            entry = hist[pid]
            status = entry.get("status", {})
            if status.get("status_str") == "error":
                sys.exit("Execution error:\n" + json.dumps(status.get("messages"), indent=2))
            break
        time.sleep(1.0)
    else:
        sys.exit(f"Timed out after {a.timeout}s waiting for {pid}")

    os.makedirs(a.out, exist_ok=True)
    saved = []
    for node_out in entry.get("outputs", {}).values():
        for img in node_out.get("images", []):
            q = urllib.parse.urlencode({"filename": img["filename"],
                                        "subfolder": img.get("subfolder", ""),
                                        "type": img.get("type", "output")})
            data = http("GET", f"{base}/view?{q}", a.headers, timeout=120)
            path = os.path.join(a.out, img["filename"])
            with open(path, "wb") as f:
                f.write(data)
            saved.append(path)
    for p in saved:
        print(p)
    if not saved:
        sys.exit("Job finished but returned no images.")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--prompt", required=True, help="Positive prompt (tags and/or prose)")
    p.add_argument("--variant", choices=PRESETS, default="turbo")
    p.add_argument("--negative", help="Override preset negative prompt")
    p.add_argument("--raw", action="store_true",
                   help="Don't prepend the preset quality prefix or use preset negative")
    p.add_argument("--width", type=int, default=1024)
    p.add_argument("--height", type=int, default=1024)
    p.add_argument("--steps", type=int)
    p.add_argument("--cfg", type=float)
    p.add_argument("--sampler")
    p.add_argument("--scheduler")
    p.add_argument("--seed", type=int, help="Default: random")
    p.add_argument("--batch", type=int, default=1)
    p.add_argument("--lora", action="append", default=[], metavar="FILE[:STRENGTH]",
                   help="Extra model-only LoRA (repeatable), appended after preset LoRAs")
    p.add_argument("--unet")
    p.add_argument("--clip", default=CLIP_DEFAULT)
    p.add_argument("--vae", default=VAE_DEFAULT)
    p.add_argument("--weight-dtype", default="default",
                   help="UNETLoader weight_dtype (default, fp8_e4m3fn, ...)")
    p.add_argument("--server", default=os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188"))
    p.add_argument("--header", action="append", default=[], metavar="'K: V'",
                   help="Extra HTTP header, e.g. auth for a proxied remote ComfyUI")
    p.add_argument("--out", default="./outputs")
    p.add_argument("--prefix-name", default="anima", help="SaveImage filename_prefix")
    p.add_argument("--timeout", type=int, default=600)
    p.add_argument("--dry-run", action="store_true", help="Print API graph JSON and exit")
    a = p.parse_args()

    pre = PRESETS[a.variant]
    a.unet = a.unet or pre["unet"]
    a.steps = a.steps or pre["steps"]
    a.cfg = a.cfg if a.cfg is not None else pre["cfg"]
    a.sampler = a.sampler or pre["sampler"]
    a.scheduler = a.scheduler or pre["scheduler"]
    a.loras = list(pre["loras"]) + [parse_lora(s) for s in a.lora]
    if a.negative is None:
        a.negative = "" if a.raw else pre["negative"]
    a.full_prompt = a.prompt if a.raw else pre["prefix"] + a.prompt
    a.seed = a.seed if a.seed is not None else random.randint(0, 2**50)
    a.headers = dict(h.split(":", 1) for h in a.header)
    a.headers = {k.strip(): v.strip() for k, v in a.headers.items()}

    w, h = snap16(a.width), snap16(a.height)
    if (w, h) != (a.width, a.height):
        print(f"note: snapped resolution to {w}x{h} (multiples of 16)", file=sys.stderr)
    a.width, a.height = w, h
    px = w * h
    if not (512 * 512 <= px <= 1536 * 1536):
        print(f"warning: {w}x{h} is outside Anima's 512^2..1536^2 range", file=sys.stderr)
    if a.cfg <= 1.0 and a.negative:
        print("note: CFG<=1, negative prompt will have no effect", file=sys.stderr)

    graph = build_graph(a)
    if a.dry_run:
        print(json.dumps(graph, indent=2))
        return
    run(a, graph)


if __name__ == "__main__":
    main()
