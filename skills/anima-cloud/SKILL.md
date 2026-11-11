---
name: anima-cloud
description: Generate anime/illustration images from a text prompt with the Anima model on Comfy Cloud. Use when the user asks for an anime-style image, character art or illustration, or asks to regenerate one with a different seed, size or LoRA.
---

# anima-cloud

Follow the setup and rules in [AGENTS.md](../../AGENTS.md) first. They cover setup, credits, secrets and how to handle each exit code.

## Generate

```bash
python3 /home/workdir/grok-harness/skills/anima-cloud/scripts/anima_cloud.py --prompt "<tags>"
```

- **The prompt is used exactly as written.** No quality tags or negative prompt are added. Write the full prompt yourself as comma-separated Danbooru-style tags, adding quality tags such as `masterpiece, best quality` if you want them.
- **It returns within about 30 seconds.** Longer jobs come back as `status: pending` with a `next:` command (see AGENTS.md).

| Flag | Default | Meaning |
|---|---|---|
| `--negative "<tags>"` | empty | Negative prompt |
| `--width W --height H` | 832 × 1216 | Multiples of 16, between 256 and 4096. Examples: 1216×832 landscape, 1024×1024 square |
| `--seed N` | random | Always reported; reuse it to reproduce or tweak an image |
| `--ckpt NAME` | variant's model | Override the model file (`--model` is an alias). See below |
| `--batch N` | 1 | 1–8 images in one job |
| `--lora "file.safetensors:0.8"` | none | Extra LoRA. Repeatable; strength defaults to 1.0 |
| `--out DIR` | `/workspace/artifacts/anima` | Output folder |

Images of 2 MP or more (for example 1536×1536) automatically use a high-res aesthetic LoRA. You don't need to do anything for this.

## Custom checkpoints and diffusion models

`--ckpt` loads a different model instead of the variant default (`divingAnima_v90.safetensors`). It accepts any model on the account, either a diffusion model (loaded with `UNETLoader`) or a full checkpoint (`CheckpointLoaderSimple`); the loader is picked automatically from which list the file is in.

```bash
python3 /home/workdir/grok-harness/skills/anima-cloud/scripts/anima_cloud.py \
  --prompt "<tags>" --ckpt silvermoonmixAnimaEvolved_v23.safetensors
```

- **Partial names are fine.** An exact filename wins; otherwise basename, then a unique substring. Ambiguous or unknown names exit 3 with the candidates, and nothing is submitted.
- `--ckpt` **queries `/api/object_info` first**, so it needs the key (and network) even with `--dry-run`.
- Sampler settings stay the variant's (`--steps` / `--cfg` override them). The CLIP and VAE stack is unchanged.
- The result block gains `model:` and `loader:` lines, and the filename gets a short model tag.

## Finding LoRA names

`--lora` needs the exact filename on Cloud. Look it up instead of guessing:

```bash
python3 /home/workdir/grok-harness/skills/anima-cloud/scripts/anima_cloud.py --list-models lora --filter <text>
```

`--list-models model` lists everything `--ckpt` accepts (diffusion models and checkpoints).

## Example

```bash
python3 /home/workdir/grok-harness/skills/anima-cloud/scripts/anima_cloud.py --prompt "1girl, silver hair, school uniform, cherry blossoms, smile" --width 832 --height 1216
```

```
status: completed
path: /workspace/artifacts/anima/anima_base_261110-221500_s4815162342.png
variant: base
size: 832x1216
seed: 4815162342
prompt_id: 1234abcd-...
```
