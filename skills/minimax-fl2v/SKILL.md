---
name: minimax-fl2v
description: Generate a short video clip with audio that starts on one image and lands on another (first-and-last-frame), or that animates forward from a single first frame or toward a single last frame, using MiniMax H3 FL2VA on Comfy Cloud. Use when the user gives a start frame and an end frame, asks to animate a still, or wants a clip that ends on a given image.
---

# minimax-fl2v

Follow the setup and rules in [AGENTS.md](../../AGENTS.md) first. They cover setup, credits, secrets and how to handle each exit code.

The commands below use Grok's sandbox path `/home/workdir/grok-harness`. Anywhere else, replace it with the repo folder (`<repo>` in AGENTS.md); don't look for `/home/workdir`.

One or two frames go in, one MP4 (24 fps, with generated audio) comes out. For combining unrelated pictures (a person, an outfit, a place) into a new scene, use `minimax-ref2v` instead.

## Generate

Write the prompt to a file, then run the tool. The prompt format is in [references/prompting.md](references/prompting.md); **read it before writing your first prompt**.

```bash
cat > /tmp/fl2v_prompt.txt <<'EOF'
How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with ...
...
EOF
python3 /home/workdir/grok-harness/skills/minimax-fl2v/scripts/minimax_fl2v.py \
  --prompt-file /tmp/fl2v_prompt.txt --first /workspace/start.png --last /workspace/end.png
```

- **`--first`** is the frame the clip starts on, and **`--last`** the frame it lands on. Png, jpg or webp, up to 25 MB; local files are uploaded for you. **Don't swap them**; that is the most common silent failure.
- **The mode follows the frames given:** both is **fl2va** (Picture 1 = first, Picture 2 = last), `--first` only is **i2va**, and `--last` only is **l2va** (the single frame is Picture 1). At least one is required.
- **The clip takes its size and aspect ratio from the first frame** (the last frame when there's no first), scaled to `--megapixels`.
- **The prompt is sent exactly as written.** The tool refuses it (exit 3, nothing submitted) when a field is missing, it mentions a Picture with no matching frame, or its landing time doesn't match `--duration` (`--force-prompt` skips these checks).
- **Before submitting an fl2va job, check the pair:** same person, same place, compatible framing and light. If they're unrelated, tell the user it will morph and suggest `minimax-ref2v` instead (see the prompting guide).
- **A clip takes a minute or more.** The tool returns within about 30 seconds with `status: pending` and a `next:` command; run it until it completes (see AGENTS.md).

| Flag | Default | Meaning |
|---|---|---|
| `--prompt "<text>"` / `--prompt-file FILE` | required | The prompt (`-` reads stdin). Prefer the file |
| `--first IMAGE` / `--last IMAGE` | — | Start frame / end frame (see above) |
| `--duration S` | 5 | 4 to 15 seconds; 5–8 is the sweet spot. Must match `S.SS` in the alignment line |
| `--megapixels M` | 0.2 | Frame size. Larger is slower and costs more |
| `--seed N` | random | Always reported; reuse it to reproduce or tweak a clip |
| `--no-lightning` | lightning on | Turns off the 8-step turbo LoRA and uses 20 steps. Slower. Same as `--lightning off` (`--lightning on` forces it on) |
| `--lightning-strength S` | 1.0 | Turbo LoRA strength, 0 to 2. Only when the user asks. Ignored with lightning off |
| `--lora "file.safetensors:0.8"` | none | Model-only LoRA. Repeat to stack; they apply in the order given. Strength defaults to 1.0 |
| `--steps N` | 8 (20 without lightning) | Override the step count. Only when the user asks |
| `--sampler NAME` / `--scheduler NAME` | `res_multistep` / `simple` | Override the sampler or scheduler. Only when the user asks |
| `--ckpt NAME` | `minimax_h3_fl2va_pruned_int8_convrot.safetensors` | Override the diffusion model (exact filename). See Models |
| `--out DIR` | see AGENTS.md | Output folder (default: the `minimax-fl2v` subfolder; see "Output folder" in AGENTS.md) |
| `--key-file PATH` | env var | File holding the Comfy Cloud API key, when the user keeps it in a file instead of `COMFY_API_KEY` (see AGENTS.md rule 3) |

**Model presets.** Some models need their own sampler, scheduler, steps or lightning setting. Those are stored in the tool and apply automatically when `--ckpt` (or the default model) matches, so don't pass sampling flags to compensate for a model. The `sampling:` result line ends in `(preset)` when one was used. `--list-presets` shows them. Explicit flags still win, and `--no-preset` ignores the preset; use either only when the user asks.

When the user says a clip looks wrong (teleports, morphs, misses the last frame), check [references/failures.md](references/failures.md) and suggest a fix instead of resubmitting on your own.

## Models

Use the default unless the user asks for a different model.

| Model (`--ckpt`) | |
|---|---|
| `minimax_h3_fl2va_pruned_int8_convrot.safetensors` | Default. The dedicated (vanilla) FL2VA checkpoint |
| `TenStrip__10Eros-Max__10Eros_Max_h3_8stepTURBO_beta6_int8.safetensors` | Hybrid H3 checkpoint (also used by `minimax-ref2v`) |
| `TenStrip__10Eros-Max__10Eros_Max_h3_8stepTURBO_beta7_int8HQ.safetensors` | Hybrid |
| `TenStrip__10Eros-Max__10Eros_Max_h3_TURBO-hybrid_beta5_int8.safetensors` | Hybrid |
| `10erosMaxInt8Ref2va_v11.safetensors` | Hybrid |

Compatible LoRAs (pass with `--lora "<file>:<strength>"`; only when the user asks for one). Use the recommended strength unless the user gives another:

| LoRA (`--lora`) | Recommended strength |
|---|---|
| `MysticXXX_MMH3-V5-ref2va.safetensors` | 0.5 (`--lora "MysticXXX_MMH3-V5-ref2va.safetensors:0.5"`) |
| `MysticXXX_MMH3-V4.safetensors` | 0.5 (`--lora "MysticXXX_MMH3-V4.safetensors:0.5"`) |

## Finding LoRA and model names

```bash
python3 /home/workdir/grok-harness/skills/minimax-fl2v/scripts/minimax_fl2v.py --list-models lora --filter <text>
```

Kinds: `model`, `lora`, `sampler`, `scheduler`. Cloud doesn't list every imported model, so a name missing from the list can still work.

## Example result

```
status: completed
path: /workspace/artifacts/minimax-fl2v/fl2v_261113-011500_s4815162342.mp4
clip: fl2va, 5s, 24 fps, 124 frames, 0.2 MP
seed: 4815162342
sampling: 8 steps (lightning), res_multistep/simple
model: minimax_h3_fl2va_pruned_int8_convrot.safetensors
prompt_id: 1234abcd-...
```
