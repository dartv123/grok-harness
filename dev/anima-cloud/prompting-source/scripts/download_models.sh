#!/usr/bin/env bash
# Download Anima model files into a ComfyUI install.
#   COMFYUI_DIR=/path/to/ComfyUI ./download_models.sh [turbo|aesthetic|base|turbo-lora|all]
# Default variant: turbo. Shared text encoder + VAE are always fetched (skipped if present).
# Set HF_TOKEN if your HF account/network requires auth.
set -euo pipefail
COMFY="${COMFYUI_DIR:-./ComfyUI}"
VARIANT="${1:-turbo}"
REPO="https://huggingface.co/circlestone-labs/Anima/resolve/main/split_files"
LORA_REPO="https://huggingface.co/circlestone-labs/Anima-Official-LoRAs/resolve/main"
AUTH=(); [[ -n "${HF_TOKEN:-}" ]] && AUTH=(-H "Authorization: Bearer ${HF_TOKEN}")

fetch() { # url dest
  local url="$1" dest="$2"
  mkdir -p "$(dirname "$dest")"
  if [[ -s "$dest" ]]; then echo "skip  $dest"; return; fi
  echo "get   $dest"
  curl -fL --retry 3 -C - "${AUTH[@]}" -o "$dest.part" "$url" && mv "$dest.part" "$dest"
}

fetch "$REPO/text_encoders/qwen_3_06b_base.safetensors" "$COMFY/models/text_encoders/qwen_3_06b_base.safetensors"
fetch "$REPO/vae/qwen_image_vae.safetensors"            "$COMFY/models/vae/qwen_image_vae.safetensors"

dm() { fetch "$REPO/diffusion_models/$1" "$COMFY/models/diffusion_models/$1"; }
case "$VARIANT" in
  turbo)      dm anima-turbo-v1.1.safetensors ;;
  aesthetic)  dm anima-aesthetic-v1.1.safetensors ;;
  base)       dm anima-base-v1.0.safetensors ;;
  turbo-lora) dm anima-base-v1.0.safetensors
              fetch "$LORA_REPO/anima-turbo-lora-v0.2.safetensors" "$COMFY/models/loras/anima-turbo-lora-v0.2.safetensors" ;;
  all)        dm anima-turbo-v1.1.safetensors; dm anima-aesthetic-v1.1.safetensors; dm anima-base-v1.0.safetensors
              fetch "$LORA_REPO/anima-turbo-lora-v0.2.safetensors" "$COMFY/models/loras/anima-turbo-lora-v0.2.safetensors" ;;
  *) echo "unknown variant: $VARIANT" >&2; exit 1 ;;
esac
echo "done. Restart ComfyUI or refresh model lists."
