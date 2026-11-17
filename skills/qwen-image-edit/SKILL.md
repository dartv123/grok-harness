---
name: qwen-image-edit
description: Edit images with Qwen-Image-Edit (2509 / 2511 or the Rapid AIO checkpoint) on Comfy Cloud from a plain-English instruction and 1 to 3 reference images, or generate from text alone. Use when the user wants to change, replace, restyle, restore, recompose or combine pictures (outfit swaps, object removal, text changes, pose or angle changes, putting people from several photos together).
---

# qwen-image-edit

Follow the setup and rules in [AGENTS.md](../../AGENTS.md) first. They cover setup, credits, secrets and how to handle each exit code.

The commands below use Grok's sandbox path `/home/workdir/grok-harness`. Anywhere else, replace it with the repo folder (`<repo>` in AGENTS.md); don't look for `/home/workdir`.

Up to 3 reference images and an instruction go in; one PNG comes out. Without references it generates from text.

## Generate

The prompt style is in [references/prompting.md](references/prompting.md); **read it before writing your first prompt**. Qwen edits from plain instructions: say what changes and what stays, and name images by number.

```bash
python3 /home/workdir/grok-harness/skills/qwen-image-edit/scripts/qwen_image_edit.py \
  --prompt "Replace her denim jacket with a red wool coat; keep her face, hair and the street behind her unchanged." \
  --ref /workspace/photo.png
```

- **`--ref`** is a reference image: up to 3 (png, jpg or webp, up to 25 MB), in order image 1, 2, 3. Local files are uploaded for you.
- **The output inherits image 1's shape and size** (about 1 megapixel). That's deliberate: it keeps the edit faithful. Resize the result afterwards if the user needs another size.
- **Without `--ref`** it's text-to-image at `--aspect` (default 2:3) and `--megapixels` (default 1.0).
- It usually finishes within the 30-second wait. If not, follow the `next:` line (see AGENTS.md).

| Flag | Default | Meaning |
|---|---|---|
| `--prompt "<text>"` / `--prompt-file FILE` | required | The instruction (`-` reads stdin) |
| `--ref IMAGE` | none | Reference image; repeatable, up to 3 |
| `--negative "<text>"` | `Plastic skin, 3d` | Only takes effect when CFG is above 1 (not with the default model) |
| `--model aio\|2511\|2509` | `aio` | See Models |
| `--seed N` | random | Reported; reuse it to reproduce or tweak an image |
| `--lora "file.safetensors:0.8"` | none | Extra LoRA; repeatable, applied after the skin LoRA |
| `--skin-lora S` | 0.7 | Strength of the built-in skin-texture LoRA; `0` turns it off |
| `--latent image\|empty` | `image` | `empty` uses `--aspect`/`--megapixels` even with references. Use it when the result needs a frame image 1 doesn't have (a size change, or a head the body photo crops off: the prompt can't move image 1's frame). Edits are less faithful (see notes) |
| `--aspect A` / `--megapixels M` | `2:3` / 1.0 | Output shape and size for text-to-image or `--latent empty`: `1:1`, `2:3`, `3:2`, `3:4`, `4:3`, `9:16`, `16:9`, `21:9` |
| `--denoise X` | 1.0 | Below 1 keeps more of image 1 (0.5–0.8 for a light touch). Needs a reference and the image latent |
| `--steps`, `--cfg`, `--sampler`, `--scheduler`, `--shift` | per model | Only when the user asks |
| `--lightning auto\|on\|off`, `--lightning-strength S` | per model | The speed LoRA for 2509/2511. Only when the user asks |
| `--ckpt NAME` | per model | Override the model file (exact filename) |
| `--out DIR` | see AGENTS.md | Output folder (default: the `qwen-image-edit` subfolder; see "Output folder" in AGENTS.md) |
| `--key-file PATH` | env var | File holding the Comfy Cloud API key, when the user keeps it in a file instead of `COMFY_API_KEY` (see AGENTS.md rule 3) |

**Model presets.** Some models need their own sampling settings. Those are stored in the tool and apply automatically when `--ckpt` (or the default model) matches, so don't pass sampling flags to compensate for a model. The `sampling:` line ends in `(preset)` when one was used; `--list-presets` shows them. Explicit flags still win; `--no-preset` ignores the preset.

## Models

| `--model` | What it is | Default sampling |
|---|---|---|
| `aio` | **Default.** Phr00t Qwen-Image-Edit Rapid AIO v23: one checkpoint with model, text encoder and VAE, accelerator built in | 8 steps, CFG 1, `euler_ancestral`/`simple`; no Lightning LoRA |
| `2511` | Official Qwen-Image-Edit-2511 (fp8) with an abliterated Qwen2.5-VL encoder and the Qwen VAE. Better character consistency and less drift than 2509 | Lightning 8-step LoRA: 8 steps, CFG 1, `euler`/`simple`. Without Lightning: 30 steps, CFG 3 |
| `2509` | Official Qwen-Image-Edit-2509 (fp8), same encoder and VAE | Same as 2511 with the 2509 Lightning LoRA |

Use `aio` unless the user asks for the official models. `--list-models model|ckpt|lora|clip` lists files on Cloud; private imports such as the AIO checkpoint can be missing from that list and still work.

## Model and inference notes

- **What it is:** a 20B diffusion transformer guided by a Qwen2.5-VL 7B vision-language encoder. Each reference reaches the model two ways: as a description through the encoder, and as pixels through the latent.
- **Why the output size is inherited:** the encoder always scales references to about 1 megapixel at their own aspect, and the model lines up reference and output on one shared grid. If the output canvas differs in size, it can't copy detail across and re-synthesizes the subject instead, which looks plastic and CGI. The tool therefore scales image 1 once and uses those same pixels for both the encoder and the starting latent. `--latent empty` breaks that link; use it only when the result needs a different frame or size than image 1.
- **CFG 1 means the negative prompt does nothing.** The default model and both Lightning setups run at CFG 1. The negative only matters at CFG 2.5–4 (2509/2511 with `--no-lightning`); then add terms like `smooth skin, airbrushed, plastic, waxy, cgi, 3d render`.
- **Don't add steps to a fast model "for quality."** Lightning and the AIO accelerator are distilled for their own step count at CFG 1. More steps or more CFG makes results *worse* (flatter light, weaker identity, smoother skin).
- **Partial denoise** (`--denoise` below 1) needs the image latent; with an empty latent it renders a flat field, so the tool refuses that combination.
- **Skin texture:** the built-in skin LoRA counters the plastic look. If skin still looks waxy, the usual causes are a constraint-heavy prompt, "studio lighting", or `--latent empty`; see the prompting guide.
- **2509 vs 2511 LoRAs:** both share one architecture, so LoRAs load on either, but speed LoRAs (Lightning, Turbo) only work on the version they were trained for. Style and concept LoRAs mostly carry over.

## Example result

```
status: completed
path: /workspace/artifacts/qwen-image-edit/qwen_aio_261117-120000_s4815162342.png
image: aio, 1 ref(s), latent image
sampling: 8 steps, CFG 1, euler_ancestral/simple, shift 3
loras: skin 0.7
seed: 4815162342
model: Phr00t__Qwen-Image-Edit-Rapid-AIO__Qwen-Rapid-AIO-NSFW-v23.safetensors
prompt_id: 1234abcd-...
```
