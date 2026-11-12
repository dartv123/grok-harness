---
name: minimax-ref2v
description: Generate a short video clip with audio from reference images, and optionally a reference video for motion, camera and soundtrack, using MiniMax H3 Ref2VA on Comfy Cloud. Use when the user gives one or more pictures (a person, outfit, product, location) or a motion clip and wants them turned into a new clip, or asks to regenerate a clip with a different seed, length or aspect ratio.
---

# minimax-ref2v

Follow the setup and rules in [AGENTS.md](../../AGENTS.md) first. They cover setup, credits, secrets and how to handle each exit code.

Reference images (and optionally reference videos) go in, one MP4 (24 fps, with generated audio) comes out. Separate audio files are not supported; a reference video's own soundtrack is the only audio reference.

## Generate

Write the prompt to a file, then run the tool. The prompt format is in [references/prompting.md](references/prompting.md); **read it before writing your first prompt**.

```bash
cat > /tmp/ref2v_prompt.txt <<'EOF'
subject_definitions:
...
EOF
python3 /home/workdir/grok-harness/skills/minimax-ref2v/scripts/minimax_ref2v.py \
  --prompt-file /tmp/ref2v_prompt.txt --ref /workspace/a.png --ref /workspace/b.png
```

- **`--ref`** is a reference image: up to 5 (png, jpg or webp, up to 25 MB each), repeatable. Local files are uploaded for you. **Order matters:** the first `--ref` is `<Picture 1>` in the prompt, the second `<Picture 2>`, and so on. Start with 2 to 4.
- **`--video`** is a reference video for motion and camera: up to 3 (mp4, webm, mov or mkv, up to 100 MB each), repeatable, in order `<Video 1>`, `<Video 2>`. Its soundtrack is passed as `<Audio N>` with the same number, unless you add `--no-video-audio`. By default only the first frames matching `--duration` are loaded; `--video-skip` and `--video-frames` pick a different span.
- **At least one `--ref` or `--video` is required.**
- **The prompt is sent exactly as written.** It must be the full six-section brick. The tool refuses a prompt that mentions a `<Picture N>`, `<Video N>` or `<Audio N>` with no matching file (`--force-prompt` skips the check).
- **A clip takes minutes.** The tool returns within about 30 seconds with `status: pending` and a `next:` command; run it until it completes (see AGENTS.md).

| Flag | Default | Meaning |
|---|---|---|
| `--prompt "<text>"` / `--prompt-file FILE` | required | The prompt (`-` reads stdin). Prefer the file for anything multi-line |
| `--no-video-audio` | audio on | Don't pass the reference videos' soundtracks as `<Audio N>` |
| `--video-fps F` | 24 | Resample each `--video` to this rate first (the model works at 24). `0` keeps the file's own rate |
| `--video-skip N` | 0 | Skip the first N frames of each `--video` (at 24 fps, 48 frames = 2 s) |
| `--video-frames N` | output length | Load at most N frames of each `--video`; `0` loads the whole file |
| `--video-width W` / `--video-height H` | 0 (keep) | Resize the `--video` frames, e.g. to stop a close-up face in the clip beating the pictures |
| `--duration S` | 10 | 5 to 15 seconds. 5 / 10 / 15 s are 124 / 243 / 362 frames |
| `--aspect A` | `4:3 (Standard)` | e.g. `16:9`, `9:16`, `1:1`, `3:4`. `--list-models aspect` shows the exact options |
| `--megapixels M` | 0.2 | Frame size. Larger is slower and costs more |
| `--seed N` | random | Always reported; reuse it to reproduce or tweak a clip |
| `--no-lightning` | lightning on | Turns off the 4-step lightning LoRA and uses 8 steps. Slower; use it for a final identity-locked pass |
| `--ref-size match\|max` | `match` | `max` keeps identity best from the stills but is slower |
| `--lora "file.safetensors:0.8"` | none | Model-only LoRA. Repeat to stack; they apply in the order given. Strength defaults to 1.0 |
| `--steps N` | 4 (8 without lightning) | Override the step count |
| `--ckpt NAME` | baked model | Override the diffusion model (exact filename; `--list-models model` shows what is on the account) |
| `--out DIR` | `/workspace/artifacts/minimax-ref2v` | Output folder |

Lightning is a fast pass and can be sloppy on identity and cadence. If the person in the clip doesn't match the references, tell the user and offer `--no-lightning` (and `--ref-size max`) instead of resubmitting on your own.

## Finding LoRA and model names

```bash
python3 /home/workdir/grok-harness/skills/minimax-ref2v/scripts/minimax_ref2v.py --list-models lora --filter <text>
```

Kinds: `model`, `lora`, `aspect`.

## Example result

```
status: completed
path: /workspace/artifacts/minimax-ref2v/ref2v_261112-221500_s4815162342.mp4
clip: 10s, 24 fps, 243 frames, 4:3 (Standard)
refs: 2
seed: 4815162342
steps: 4 (lightning)
model: TenStrip__10Eros-Max__10Eros_Max_h3_8stepTURBO_beta6_int8.safetensors
prompt_id: 1234abcd-...
```
