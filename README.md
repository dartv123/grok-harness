# grok-harness

Command-line tools that let an LLM agent (Grok, in its sandbox) run image workflows on remote services. Each tool returns a short, fixed-format result, so large workflow graphs and API responses never enter the agent's context.

The agent reads **[AGENTS.md](AGENTS.md)**: setup, shared rules, the output contract and the skill index. Point Grok there.

## Layout

```
AGENTS.md                      agent entry point: setup, rules, contract, skill index
skills/<name>/SKILL.md         when and how to use one tool (tool-specific only)
skills/<name>/scripts/         the tool itself (one script, no install step)
skills/_shared/comfy_cloud.py  plumbing shared by the Comfy Cloud tools: API client, polling, download, exit codes
dev/<name>/                    maintainer material; agents are told to ignore it
```

## Skills

| Skill | Status |
|---|---|
| `anima-cloud` | `base` variant (divingAnima v9.0, 20 steps, CFG 2). `--ckpt` swaps in any other Anima model / checkpoint on the account |
| `minimax-ref2v` | MiniMax H3 reference-to-video with audio. Up to 5 reference images and up to 3 reference videos (uploaded by the tool; a video's soundtrack becomes `<Audio N>`, and `--video-audio passthrough|both` puts it into the output 1:1), 5–15 s at 24 fps, stackable `--lora`, lightning LoRA on by default (`--no-lightning` for 8 steps). No separate audio files |

### Compatible models (`--ckpt`)

**anima-cloud**

| File | Notes |
|---|---|
| `divingAnima_v90.safetensors` | Default (`base` variant) |
| `silvermoonmixAnimaEvolved_v23.safetensors` | Silvermoon Mix Anima Evolved v2.3 |
| `real-dream-v5-anima-bf16.safetensors` | Photoreal-leaning Anima build |

All three load with `UNETLoader`. Partial names work (`--ckpt silvermoon`). Cloud's `/api/object_info` does not list every imported model (these three are missing from it), so `--ckpt` submits an unknown name as-is and lets the job decide; `--loader unet|ckpt` forces the loader if `auto` guesses wrong. Other models on the account may work too; check with `--list-models model --filter <text>`.

**minimax-ref2v**

| File | Notes |
|---|---|
| `TenStrip__10Eros-Max__10Eros_Max_h3_8stepTURBO_beta6_int8.safetensors` | Default |
| `TenStrip__10Eros-Max__10Eros_Max_h3_8stepTURBO_beta7_int8HQ.safetensors` | |
| `TenStrip__10Eros-Max__10Eros_Max_h3_TURBO-hybrid_beta5_int8.safetensors` | |
| `10erosMaxInt8Ref2va_v11.safetensors` | |
| `minimax_h3_ref2va_pruned_int8_convrot.safetensors` | |

Pass the exact filename (the `.safetensors` extension may be left off). Unlike anima-cloud, no partial-name lookup is done.

Compatible LoRAs for minimax-ref2v (via `--lora`, recommended strength 0.5): `MysticXXX_MMH3-V5-ref2va.safetensors`, `MysticXXX_MMH3-V4.safetensors`.

All these lists are repeated in each skill's SKILL.md for the agent; update both when they change. Sampling settings for a model that needs its own go in `MODEL_PRESETS` (next section). None are defined yet.

### Model presets (both skills)

When a model needs its own sampling settings, add it to `MODEL_PRESETS` near the top of the tool's script instead of telling the agent to pass flags. The preset applies automatically whenever that model is in use (the default model or `--ckpt`). Precedence: explicit flag > preset > baked default. `--no-preset` ignores it and `--list-presets` shows the table.

| Tool | Preset keys |
|---|---|
| `anima_cloud.py` | `steps`, `cfg`, `sampler`, `scheduler`, `note` |
| `minimax_ref2v.py` | `sampler`, `scheduler`, `lightning` (True/False), `steps_lightning`, `steps_full`, `note` |

Keys are model filenames. Matching also accepts the name without the extension. The lookup lives in `skills/_shared/comfy_cloud.py` (`find_preset`), so a new tool can reuse it.

## Adding a workflow

1. **Script:** create `skills/<name>/scripts/<tool>.py`. Use only the Python 3.10 standard library, so the agent can run it straight after download. For Comfy Cloud, import `skills/_shared/comfy_cloud.py` (API client, key loading, polling, download, error blocks) and keep only the graph, flags and result block in the tool; the setup tarball ships the whole repo, so the import needs no install step. Follow the output contract in AGENTS.md: `key: value` lines, exit codes 0–4, a `next:` line for pending jobs, and no automatic resubmission.
2. **Skill file:** add `skills/<name>/SKILL.md` with `name` and `description` frontmatter. Include only what's specific to the tool (when to use it, the command, flags, quirks). Don't repeat the rules from AGENTS.md.
3. **Index:** add a row to the Skills table in AGENTS.md.
4. **Tests:** put source workflows, notes and test servers in `dev/<name>/`.

A new variant of an existing workflow (for example Anima turbo) doesn't need a new skill. Add it to `VARIANTS` in the script and list it in that skill's SKILL.md.

## Testing anima-cloud locally

```bash
python3 dev/anima-cloud/mock_cloud.py 18100 18101 ok &   # modes: ok | fail | slow | badnode
COMFY_API_KEY=sk-test-1234 COMFY_CLOUD_URL=http://127.0.0.1:18100 \
  python3 skills/anima-cloud/scripts/anima_cloud.py --prompt test --out /tmp/anima-test
```

The mock server prints `LEAK!` to stderr if the API key is ever sent to the storage host.

## Testing minimax-ref2v locally

```bash
python3 dev/minimax-ref2v/mock_cloud.py 18120 18121 ok &   # modes: ok | fail | slow | badnode | badupload
COMFY_API_KEY=sk-test-1234 COMFY_CLOUD_URL=http://127.0.0.1:18120 \
  python3 skills/minimax-ref2v/scripts/minimax_ref2v.py --prompt-file prompt.txt \
  --ref a.png --ref b.png --duration 5 --out /tmp/ref2v-test
```

The mock also prints `BADGRAPH:` to stderr if a submitted graph is miswired (bad frame count, dangling link, missing upload). `--dry-run` prints the API JSON without a key or network.
