---
name: anima-image-gen
description: Generate anime / illustration images with the Anima 2B text-to-image model (CircleStone Labs x Comfy Org) through ComfyUI. Covers variant selection (Base, Aesthetic, Turbo, Turbo LoRA), model download and placement, Danbooru-tag + natural-language prompt construction, sampler/CFG/step settings, and submitting jobs to a ComfyUI server via its HTTP API. Use this skill whenever the user mentions Anima, anima-base, anima-turbo, anima-aesthetic, circlestone-labs, or asks to generate anime art, character illustrations, manga-style or non-photorealistic images with a local/cloud ComfyUI setup, or wants an Anima ComfyUI workflow JSON, even if they don't name the model explicitly but are in an anime-image context.
---

# Anima Image Generation

Anima is a 2B-parameter DiT text-to-image model (fine-tune of NVIDIA Cosmos-Predict2-2B) trained on several million anime images plus ~800k non-anime artworks, anime data cut-off Sept 2025. It uses a Qwen3-0.6B text encoder and the Qwen-Image VAE. It is natively supported in ComfyUI via standard `UNETLoader` / `CLIPLoader` / `VAELoader` nodes. There is no official diffusers pipeline, so ComfyUI (local, remote VPS, or Comfy Cloud) is the execution path.

It is bad at photorealism (by design) and at long text rendering. Don't route realism requests to it.

## Comfy Cloud harness (preferred for cloud)

For Comfy Cloud generation, use the lightweight harness at:

**https://github.com/dartv123/grok-harness**

Setup once per session (sandbox resets):

```bash
mkdir -p /home/workdir/grok-harness && curl -fsSL https://github.com/dartv123/grok-harness/archive/refs/heads/main.tar.gz | tar xz -C /home/workdir/grok-harness --strip-components=1
```

Then follow `skills/anima-cloud/SKILL.md` inside the repo. Run:

```bash
python3 /home/workdir/grok-harness/skills/anima-cloud/scripts/anima_cloud.py --prompt "<tags>"
```
Key is on comfy-ui-cloud-key skill.

The harness keeps graphs and large responses out of context and returns a short `key: value` result. Prefer this over building graphs manually when targeting Comfy Cloud.

## 1. Pick a variant

| Variant | File (`models/diffusion_models/`) | Steps | CFG | Use when |
|---|---|---|---|---|
| Turbo v1.1 | `anima-turbo-v1.1.safetensors` | 8–12 | 1 | Default. Fast prompt iteration, stable strong house style, less diversity |
| Aesthetic v1.1 | `anima-aesthetic-v1.1.safetensors` | 30–50 | 4–5 | Best quality at full step count |
| Base v1.0 | `anima-base-v1.0.safetensors` | 30–50 | 4–5 | Max diversity / style adherence via artist tags; LoRA training target. Plain default style |
| Base + Turbo LoRA | base + `models/loras/anima-turbo-lora-v0.2.safetensors` (strength 1.0) | 8 | 1 | Official Comfy template's fast path; keeps base + user LoRAs stackable |

The model author recommends starting with Turbo. Aesthetic v1.0b exists as an alternate (pure aesthetic finetune, no merged style LoRAs); the author prefers 1.0/1.1. `anima-preview*.safetensors` are obsolete previews — don't use them unless asked.

**CFG 1 caveat:** at CFG 1 ComfyUI skips the unconditional pass, so the negative prompt has no effect on Turbo. Steer Turbo with the positive prompt only.

## 2. Model files

Shared by every variant:
- `models/text_encoders/qwen_3_06b_base.safetensors` (~1.1 GB)
- `models/vae/qwen_image_vae.safetensors` (~242 MB — same file as Qwen-Image; may already exist)

Diffusion models are ~4.2 GB each. All from HF repo `circlestone-labs/Anima` under `split_files/{diffusion_models,text_encoders,vae}/`; the turbo LoRA is in `circlestone-labs/Anima-Official-LoRAs`. Run `scripts/download_models.sh` (see its header for usage). ComfyUI must be recent — if nodes/model type fail to load, update ComfyUI first.

Fits comfortably on consumer GPUs; the 2B DiT in bf16 plus a 0.6B encoder is roughly 8 GB class VRAM territory.

## 3. Build the prompt

Anima was trained on Danbooru tags, natural-language captions, and mixes of both. Full rules and tag vocabulary are in `references/prompting.md` — read it when composing anything beyond a simple prompt, when the user wants a specific artist/character, or when outputs look off.

Essentials:
- Tags are lowercase with spaces, not underscores (`long hair`, not `long_hair`). Only `score_N` keeps the underscore.
- Tag order: `[quality/meta/year/safety] [1girl/1boy/...] [character] [series] [artist] [general tags]`.
- Artist tags **must** be prefixed with `@` (`@nnn yryr`), otherwise the effect is very weak.
- Always include a safety tag (`safe`, `sensitive`, `nsfw`, `explicit`). Short/vague prompts can drift into undesired content; `safe` in positive plus `nsfw, explicit` in negative is the default for SFW work.
- Natural language: at least 2 descriptive sentences; normal capitalization for character/series names; name a character, then describe their appearance (critical with multiple characters).
- Prompt weighting needs higher weights than SDXL, e.g. `(chibi:2)`.
- Prefer Gelbooru tag spelling where Danbooru and Gelbooru differ.

Quality prefix / negative per variant:

| Variant | Positive prefix | Negative |
|---|---|---|
| Base | `masterpiece, best quality, score_7, safe, ` | `worst quality, low quality, score_1, score_2, score_3, artist name, blurry, jpeg artifacts, chromatic aberration` |
| Aesthetic | `masterpiece, best quality, safe, ` (no `score_*` anywhere — it pushes into slop) | `worst quality, low quality, artist name, blurry, jpeg artifacts, chromatic aberration` |
| Turbo | `masterpiece, best quality, safe, ` | ignored at CFG 1 |

## 4. Settings

- Resolution: 512² to 1536² total pixels. Keep both sides multiples of 16. Good defaults: 1024×1024, 832×1216 (portrait), 1216×832 (landscape), 896×1152, 1152×896.
- Samplers (author's picks):
  - `er_sde` — neutral, flat colors, sharp lines. Default for Base/Aesthetic.
  - `euler_ancestral` — softer, thinner lines, can lean 2.5D; tolerates higher CFG.
  - `dpmpp_2m_sde_gpu` — like er_sde with more variety; can get wild.
  - `euler` — slightly more creative; good with Turbo/Aesthetic. Default for Turbo.
- Scheduler: `simple` (official template). For painterly/realistic textures, `beta57` from the RES4LYF custom node pack emphasizes low-noise timesteps.

## 5. Generate

`scripts/anima_generate.py` (Python stdlib only) builds an API-format ComfyUI graph, submits it to `/prompt`, polls `/history`, and downloads outputs via `/view`. Variant presets fill in model file, steps, CFG, sampler, and quality prefix/negative; any flag overrides the preset.

```bash
# Turbo, defaults
python scripts/anima_generate.py --variant turbo \
  --prompt "1girl, fern (sousou no frieren), sousou no frieren, long purple hair, purple eyes, black coat, white dress, standing in a flower field, wind, looking at viewer" \
  --server http://127.0.0.1:8188 --out ./outputs

# Aesthetic, portrait, fixed seed, 4 images
python scripts/anima_generate.py --variant aesthetic --width 832 --height 1216 \
  --seed 42 --batch 4 --prompt "..."

# Inspect the graph without a server (pipe into other tooling / commit to repo)
python scripts/anima_generate.py --variant base --prompt "..." --dry-run > workflow_api.json
```

Run `python scripts/anima_generate.py -h` for all flags (`--raw` disables the auto quality prefix/negative; `--lora name.safetensors:0.8` stacks extra model-only LoRAs; `--unet/--clip/--vae` override filenames if the user renamed them).

If the user has no reachable ComfyUI server, produce the workflow with `--dry-run` and tell them to load it via ComfyUI → Workflow → Open (API JSON) or POST it themselves. Comfy Cloud also offers official templates "Anima Base v1" and "Anima Preview".

## 6. Troubleshooting

- `Value not in list` for a model name → file isn't in the expected folder or name differs; list with `GET /object_info/UNETLoader`.
- Text encoder load error / wrong clip type → outdated ComfyUI. The official template uses `CLIPLoader` type `stable_diffusion`, which relies on auto-detection added in recent builds; update ComfyUI.
- Plain/bland output on Base → expected; add artist tags (`@name`) and quality tags, or switch to Aesthetic/Turbo.
- Burned/over-saturated → lower CFG (3.5–4), or switch sampler to `euler_ancestral`.
- Characters merged/confused in multi-character scenes → describe each character's appearance explicitly after naming them.
- Negative prompt "doing nothing" on Turbo → CFG 1; see caveat above.
- Speed: community node pack ANIMA_BOOSTER (fp16 loader, TeaCache, SageAttention, torch.compile) claims ~3.5–5× speedup on NVIDIA. Third-party; evaluate before production use.

## 7. License (flag this for any product/commercial context)

Weights: CircleStone Labs Non-Commercial License + NVIDIA Open Model License (derivative of Cosmos-Predict2). **Generated images may be used commercially** (selling images, commissions, game/VN assets). **Not allowed without a commercial license:** hosting the model behind a paid API, on a paid generation platform, embedding weights in a monetized product, or powering a feature of a monetized product. Commercial licensing: tdrussell@circlestone.ai. If the user's use case is a service/product integration, raise this before building.
