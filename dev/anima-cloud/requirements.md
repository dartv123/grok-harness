# Anima Comfy Cloud Harness — Requirements & Sandbox Target Specs

## Goal
Thin CLI (Python or binary) that takes a short prompt + flags, submits a pre-baked Anima workflow to Comfy Cloud, downloads the result, and returns only a tiny summary. No large graphs, base64, or long JSON in the chat context.

## Interface
```bash
anima_cloud \
  --prompt "1girl, long hair, ..." \
  --variant turbo|aesthetic|base|base+turbo \
  --width 832 --height 1216 \
  --seed 42 \
  --batch 1 \
  --lora "name.safetensors:0.8" \
  --out /workspace/artifacts/anima \
  --dry-run
```

## Core behavior
- Load API key from `COMFY_API_KEY` / `COMFYUI_API_KEY` or `/home/workdir/.grok/secrets/comfy_api_key`. Never print the full key.
- Baked-in API-format workflows for the four variants (model, steps, CFG, sampler, quality prefix/negative already set). CLI only swaps text, seed, size, optional extra LoRA, and filename prefix.
- POST to `https://cloud.comfy.org/api/prompt`.
- Poll `/api/jobs/{id}` until completed/failed (with reasonable timeout + stagnation handling).
- Download output via `/api/view` and save locally under the `--out` dir.
- Print only a short result block, e.g.:
  ```
  status: completed
  path: /workspace/artifacts/anima/xxx.png
  prompt_id: ...
  ```
  Failures return status + short error, no full response dump.

## Constraints
- Python stdlib + `requests` only, or a static/dynamic Linux x86_64 binary.
- No GetNode/SetNode or other Cloud-unsupported nodes in the baked graphs.
- Default to Turbo (fast, CFG 1) unless variant is specified.
- Support optional extra model-only LoRA via `--lora`.
- One-shot by default; no auto-retry loops that spam the queue.
- Keep tool-visible output under ~15 lines so the LLM context stays light.

## Nice-to-haves
- `--dry-run` that dumps the final API JSON to stdout.
- `--list-variants` / `--list-models` that hit `/api/object_info` if needed.
- Filename prefix that includes variant + short timestamp.

## Sandbox target deployment specs

| Item | Value |
|------|--------|
| OS | Debian 12 (bookworm), Linux 6.12.8+ x86_64 |
| Arch | x86_64 (Intel Xeon Platinum 8481C, KVM) |
| CPU | 2 cores |
| RAM | ~1.9 GiB available |
| Disk | 50G total, ~46G free on `/` and `/tmp` |
| User | root |
| Working dir | `/workspace/artifacts` (user-visible) |

### Runtimes present
- Python 3.10.21 (`python3` / `python`) + `requests`
- Node.js v20.20.2 + npm 10.8.2
- Rust 1.98.1 (`rustc`)
- gcc
- No Go

### Network
- Outbound HTTPS works

### Binary / script notes
- Static or dynamically linked Linux x86_64 binary is fine.
- Drop under `/workspace`, `/tmp`, or `/home/workdir` and `chmod +x`.
- Can read env vars and files under `/home/workdir/.grok/secrets/`.
- Keep stdout short if the tool result should stay small in context.
