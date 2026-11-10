# anima_cloud

Generates anime images with Anima on Comfy Cloud. One command in, one image path out.

**Treat this tool as a black box.** Don't read, unpack, modify or debug `anima_cloud.py` unless the user explicitly asks you to. Run the commands below and act on the output.

## Setup (once per conversation)

```bash
curl -fsSL -o /home/workdir/anima_cloud.py https://raw.githubusercontent.com/dartv123/grok-harness/main/anima_cloud.py
```

The user tells you how the API key is provided. The tool reads it from `COMFY_API_KEY` or `COMFYUI_API_KEY`, from `--key-file PATH`, or from `/home/workdir/.grok/secrets/comfy_api_key`. Never print or echo the key.

## Generate

```bash
python3 /home/workdir/anima_cloud.py --prompt "<tags>"
```

- **The prompt is used exactly as you write it.** No quality tags or negative prompt are added. Write the full prompt yourself, for example `masterpiece, best quality, 1girl, long hair, ...` if you want quality tags.
- **Run it as a normal command.** It returns within about 30 seconds.

Optional flags:

| Flag | Default | Meaning |
|---|---|---|
| `--negative "<tags>"` | empty | Negative prompt |
| `--width W --height H` | 832 × 1216 | Size. Multiples of 16, between 256 and 4096 |
| `--seed N` | random | The seed is always reported, so a result can be reproduced |
| `--batch N` | 1 | 1–8 images |
| `--lora "file.safetensors:0.8"` | none | Extra LoRA; repeatable |
| `--out DIR` | `/workspace/artifacts/anima` | Where images are saved |

## Read the result

Every run prints a few `key: value` lines and exits with a code. For example:

```
status: completed
path: /workspace/artifacts/anima/anima_base_261110-221500_s42.png
seed: 42
prompt_id: 1234abcd-...
```

| Exit | `status` | What to do |
|---|---|---|
| 0 | `completed` | Show the image at `path` (or each one under `paths:`) to the user. |
| 4 | `pending` | Still generating. Run the exact command on the `next:` line. Repeat until it finishes. This never starts a new job. |
| 1 | `error` / `failed` / `cancelled` | Tell the user the `error:` line. Don't retry unless they ask. |
| 2 | `error` / `stalled` | Network or Cloud problem. Tell the user. You may run the `--resume <prompt_id>` command once. |
| 3 | `error` | Key, credits, auth or a bad flag. Tell the user the `error:` line. Don't retry. |

**Rules**
- Never resubmit a prompt to work around a pending, stalled or failed job. Each submission costs Cloud credits.
- Only resume or cancel a job with the `prompt_id` the tool printed.

## Other commands

| Command | Use |
|---|---|
| `--resume <prompt_id>` | Keep waiting for a job and download it |
| `--cancel <prompt_id>` | Remove a job from the Cloud queue |
| `--list-models lora --filter <text>` | Find exact LoRA filenames for `--lora` (also works with `unet`, `clip`, `vae`) |
| `--dry-run` | Print the request without submitting. Only use it when the user asks |
