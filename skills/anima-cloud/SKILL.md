---
name: anima-cloud
description: Generate anime/illustration images from a text prompt with the Anima model on Comfy Cloud. Use when the user asks for an anime-style image, character art or illustration, or asks to regenerate one with a different seed, size or LoRA.
---

# anima-cloud

Follow the setup and rules in [AGENTS.md](../../AGENTS.md) first. They cover setup, credits, secrets and how to handle each exit code.

The commands below use Grok's sandbox path `/home/workdir/grok-harness`. Anywhere else, replace it with the repo folder (`<repo>` in AGENTS.md); don't look for `/home/workdir`.

## Generate

```bash
python3 /home/workdir/grok-harness/skills/anima-cloud/scripts/anima_cloud.py --prompt "<tags>"
```

- **The prompt is used exactly as written.** No quality tags or negative prompt are added. Write the full prompt yourself. The prompt rules are in [references/prompting.md](references/prompting.md); **read it before writing your first prompt.** The essentials: lowercase tags with spaces (`long hair`, not `long_hair`), artist tags start with `@`, always include a safety tag (`safe`, `sensitive`, `nsfw` or `explicit`), and name each character before describing them.
- **It returns within about 30 seconds.** Longer jobs come back as `status: pending` with a `next:` command (see AGENTS.md).

| Flag | Default | Meaning |
|---|---|---|
| `--negative "<tags>"` | empty | Negative prompt |
| `--width W --height H` | 832 × 1216 | Multiples of 16, between 256 and 4096. Examples: 1216×832 landscape, 1024×1024 square |
| `--seed N` | random | Always reported; reuse it to reproduce or tweak an image |
| `--ckpt NAME` | variant's model | Override the model file (`--model` is an alias). See below |
| `--loader KIND` | `auto` | Loader for `--ckpt`: `auto` \| `unet` (UNETLoader) \| `ckpt` (CheckpointLoaderSimple) |
| `--batch N` | 1 | 1–8 images in one job |
| `--lora "file.safetensors:0.8"` | none | Extra LoRA. Repeatable; strength defaults to 1.0 |
| `--steps N` / `--cfg X` | 20 / 2 | Override steps or CFG. Only when the user asks |
| `--sampler NAME` / `--scheduler NAME` | `er_sde` / `simple` | Override the sampler or scheduler (`--list-models sampler` / `scheduler`). Only when the user asks |
| `--out DIR` | see AGENTS.md | Output folder (default: the `anima` subfolder; see "Output folder" in AGENTS.md) |
| `--key-file PATH` | env var | File holding the Comfy Cloud API key, when the user keeps it in a file instead of `COMFY_API_KEY` (see AGENTS.md rule 3) |

Images of 2 MP or more (for example 1536×1536) automatically use a high-res aesthetic LoRA. You don't need to do anything for this.

## Model and inference notes

- **What it is:** Anima is a 2B DiT text-to-image model (a fine-tune of NVIDIA Cosmos-Predict2) trained on anime plus some non-anime artwork, with a Qwen3 0.6B text encoder and the Qwen-Image VAE. It is an illustration model: weak at photorealism and at text inside the image.
- **The default is a community finetune.** `divingAnima_v90` runs at 20 steps, CFG 2, `er_sde`/`simple`. CFG above 1 means **`--negative` takes effect.** (On Anima Turbo-style models at CFG 1 the negative does nothing; put constraints in the prompt instead.)
- **Size:** about 0.25 to 2.4 megapixels works (512×512 up to 1536×1536); both sides multiples of 16. Good shapes: 1024×1024, 832×1216, 1216×832, 896×1152, 1152×896. At 2 MP and above the high-res aesthetic LoRA switches on automatically.
- **Samplers,** if the user asks for a different look (`--sampler`): `er_sde` neutral, flat colors, sharp lines (default); `euler_ancestral` softer, thinner lines, can lean 2.5D, tolerates higher CFG; `dpmpp_2m_sde_gpu` like `er_sde` with more variety, can get wild; `euler` slightly more creative.
- **Troubleshooting** (report to the user; don't resubmit on your own): plain or bland output → add `@artist` and quality tags; burned or oversaturated → lower `--cfg` or try `euler_ancestral`; characters merged → describe each one after naming them.
- **License:** generated images may be used commercially. Hosting the model itself behind a paid service needs a commercial license from the model's author.

## Custom checkpoints and diffusion models

`--ckpt` loads a different model instead of the variant default (`divingAnima_v90.safetensors`). Use the default unless the user asks for another model or a style one of these is known for.

| Model (`--ckpt`) | Use for |
|---|---|
| `divingAnima_v90.safetensors` | Default |
| `silvermoonmixAnimaEvolved_v23.safetensors` | Silvermoon Mix Anima Evolved v2.3 |
| `real-dream-v5-anima-bf16.safetensors` | A more photoreal look |

These three are confirmed to work. `--ckpt` also accepts any other model on the account, either a diffusion model (loaded with `UNETLoader`) or a full checkpoint (`CheckpointLoaderSimple`); the loader is picked automatically from which list the file is in.

```bash
python3 /home/workdir/grok-harness/skills/anima-cloud/scripts/anima_cloud.py \
  --prompt "<tags>" --ckpt silvermoonmixAnimaEvolved_v23.safetensors
```

- **Partial names are fine.** An exact filename wins; otherwise basename, then a unique substring. An ambiguous substring exits 3 with the candidates, and nothing is submitted.
- **A name the catalog does not know is still submitted**, with a `warning:` line. Cloud does not enumerate every import — private Anima builds run fine while missing from `/api/object_info` — so Cloud's own validation is the check. If the file really is absent the job fails with a `value_not_in_list` node error (exit 1).
- `--loader unet|ckpt` forces the loader instead of picking it from the catalog (default `auto`: diffusion model where listed, `UNETLoader` when unlisted).
- `--ckpt` **queries `/api/object_info` first**, so it needs the key (and network) even with `--dry-run`.
- **Sampling settings follow the model.** Models that need their own steps, CFG, sampler or scheduler have a preset stored in the tool, applied automatically. Other models use the variant's settings. Don't pass sampling flags to compensate for a model. `--list-presets` shows the presets. Explicit flags still win, and `--no-preset` ignores the preset; use either only when the user asks. The CLIP and VAE stack is unchanged.
- The result block shows `model:` and `loader:`, and the filename gets a short model tag.

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
model: divingAnima_v90.safetensors
loader: unet
sampling: 20 steps, CFG 2, er_sde/simple
prompt_id: 1234abcd-...
```
