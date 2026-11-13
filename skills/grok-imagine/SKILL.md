---
name: grok-imagine
description: Generate or edit images with xAI Grok Imagine on Comfy Cloud, from a natural-language prompt and optionally up to 3 reference images. Use when the user asks for a Grok Imagine image, a photoreal or general-purpose image from a plain-English description, or an edit of an existing picture.
---

# grok-imagine

Follow the setup and rules in [AGENTS.md](../../AGENTS.md) first. They cover setup, credits, secrets and how to handle each exit code.

The commands below use Grok's sandbox path `/home/workdir/grok-harness`. Anywhere else, replace it with the repo folder (`<repo>` in AGENTS.md); don't look for `/home/workdir`.

A prompt, and optionally reference images, go in; one or more PNGs come out. For anime and illustration from Danbooru-style tags, use `anima-cloud` instead.

## Generate

The prompt style is in [references/prompting.md](references/prompting.md); **read it before writing your first prompt**. Grok wants plain sentences, not tags.

```bash
python3 /home/workdir/grok-harness/skills/grok-imagine/scripts/grok_imagine.py \
  --prompt "Medium close-up portrait of ..." --aspect 2:3
```

Edit an existing picture by passing it with `--ref`:

```bash
python3 /home/workdir/grok-harness/skills/grok-imagine/scripts/grok_imagine.py \
  --prompt "Keep her face and pose; change the outfit to a red winter coat." --ref /workspace/photo.png
```

- **`--ref`** is a reference image: up to 3 (png, jpg or webp, up to 25 MB), in order image 1, 2, 3. Local files are uploaded for you. Without `--ref` it's text-to-image.
- **Don't create or pass blank images.** The default model needs none. The older models get blank placeholders added automatically where they need them.
- **Text-only with `--aspect auto` gives a square (1:1) image.** Pass the ratio you want; with `--ref`, `auto` keeps the reference's shape.
- **Every image costs credits** (this is a paid partner model). `--count` multiplies the cost; keep it at 1 unless the user asks for several.
- **The seed doesn't make results repeatable.** Grok is nondeterministic; the same prompt and seed give a different image each time.
- It usually finishes within the 30-second wait. If not, follow the `next:` line (see AGENTS.md).

| Flag | Default | Meaning |
|---|---|---|
| `--prompt "<text>"` / `--prompt-file FILE` | required | The prompt (`-` reads stdin) |
| `--ref IMAGE` | none | Reference image to edit or draw from; repeatable, up to 3 |
| `--aspect A` | `auto` | `1:1`, `2:3`, `3:2`, `3:4`, `4:3`, `9:16`, `16:9`, `9:19.5`, `19.5:9`, `9:20`, `20:9`, `1:2`, `2:1`, or `auto` |
| `--resolution 1K\|2K` | `1K` | Output resolution |
| `--count N` | 1 | 1–10 images in one job. Each one costs credits |
| `--quality medium\|low` | `low` | Higher quality costs more per image. Use `medium` only when the user asks for better quality |
| `--model NAME` | `grok-imagine-image-2.0` | See Models. Only when the user asks |
| `--seed N` | random | 0–2147483647. Reported, but doesn't reproduce an image |
| `--out DIR` | see AGENTS.md | Output folder (default: the `grok-imagine` subfolder; see "Output folder" in AGENTS.md) |
| `--key-file PATH` | env var | File holding the Comfy Cloud API key, when the user keeps it in a file instead of `COMFY_API_KEY` (see AGENTS.md rule 3) |

## Models

`--list-models` prints this table (no key needed). Use the default unless the user asks.

| Model | Refs | Aspect | Notes |
|---|---|---|---|
| `grok-imagine-image-2.0` | up to 3 | yes | Default. `--quality low` (default) or `medium`. No blank images needed |
| `grok-imagine-image` | up to 3 | yes | Older standard model; gets blank placeholders |
| `grok-imagine-image-quality` | up to 3 | yes | Retired by xAI on 2026-11-02; runs as 2.0 at low quality |
| `grok-imagine-image-pro` | 1 | no | Retired; runs as 2.0 at low quality; no `--aspect` |

## Example result

```
status: completed
path: /workspace/artifacts/grok-imagine/grok_261113-233000_s402267919.png
image: grok-imagine-image-2.0, 2:3, 1K, 1 image(s), 0 ref(s), quality low
seed: 402267919
prompt_id: 1234abcd-...
```
