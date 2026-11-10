# anima_cloud

A single-file Python 3.10+ tool that uses only the standard library. It submits a built-in Anima workflow to Comfy Cloud, downloads the image, and prints a short `key: value` result block.

## Setup in the sandbox (each conversation)

```bash
curl -fsSL -o /home/workdir/anima_cloud.py https://raw.githubusercontent.com/dartv123/grok-harness/main/anima_cloud.py
```

Provide the API key in one of these places, checked in this order:

1. `COMFY_API_KEY` env var
2. `COMFYUI_API_KEY` env var
3. `--key-file PATH`
4. `/home/workdir/.grok/secrets/comfy_api_key`

## Usage

```bash
python3 /home/workdir/anima_cloud.py --prompt "1girl, long hair, ..." [--seed 42] \
  [--width 832 --height 1216] [--batch 1] [--lora "name.safetensors:0.8"] \
  [--negative "..."] [--out /workspace/artifacts/anima]
```

The tool waits up to `--wait` seconds (default 25, which fits the 30 s tool-call limit). If the job hasn't finished by then, it prints `status: pending` and a `next:` command. Run that command to keep waiting; it never resubmits the job.

| Command | Purpose |
|---|---|
| `--resume ID [--wait 25]` | Keep waiting for an existing job, then download it |
| `--cancel ID` | Remove a job from the Cloud queue |
| `--dry-run` | Print the API JSON; nothing is submitted and no key is needed |
| `--list-variants` | Show the built-in variants |
| `--list-models unet\|lora\|clip\|vae\|ckpt [--filter s]` | List model files on Cloud |
| `--hires-lora auto\|on\|off` | Control the aesthetic-boost LoRA (auto: on at ≥ 2 MP) |
| `--steps N`, `--cfg X` | Override the variant's sampler settings |

**Exit codes**

| Code | Meaning |
|---|---|
| 0 | Completed |
| 1 | Job failed, or the workflow was rejected |
| 2 | Network, server or stall error |
| 3 | Usage, key, auth or credits error |
| 4 | Still pending |

## Built-in workflow (`base`)

- **Diffusion model:** `divingAnima_v90.safetensors`
- **Text encoder:** `qwen_3_06b_base`
- **VAE:** `qwen_image_vae`
- **Sampler:** 20 steps, CFG 2, `er_sde`/`simple`

The graph uses only core nodes. The original graph used custom nodes to switch the aesthetic LoRA on at ≥ 2 MP; that logic now lives in Python. To add variants (turbo, base+turbo), edit `VARIANTS` at the top of the script.

## API notes (Comfy Cloud)

- Submit with `POST /api/prompt`, using an `X-API-Key` header.
- Poll `GET /api/job/{id}/status`, which returns `pending`, `in_progress`, `completed`, `error` or `cancelled`.
- Once the job is finished, `GET /api/jobs/{id}` returns its outputs.
- `GET /api/view` returns a 302 redirect to a signed Google Cloud Storage URL. The tool fetches that URL without the API key.
