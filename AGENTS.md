# Agent instructions: grok-harness

This repo holds command-line tools ("harnesses") that run image and media workflows on remote services. Each tool comes with a skill describing when and how to use it. These rules apply to every tool here, whichever agent or environment runs them. Each skill only adds what's specific to its tool.

## Setup and paths

**`<repo>`** means the folder containing this AGENTS.md. The commands in the skills are written for Grok's sandbox, where `<repo>` is `/home/workdir/grok-harness`. Anywhere else, replace that prefix with the real `<repo>` path.

- **Already reading this file from disk?** Then the repo is already there and that folder is `<repo>`. Don't download it again.
- **Only have the URL?** Download the repo into a folder you can write to, and use that folder as `<repo>`:

  ```bash
  mkdir -p <repo> && curl -fsSL https://github.com/dartv123/grok-harness/archive/refs/heads/main.tar.gz | tar xz -C <repo> --strip-components=1
  ```

  In Grok's sandbox, use `/home/workdir/grok-harness`. The sandbox resets between conversations, so download again only when the files are missing.
- **Don't go looking** for `/home/workdir`, `/workspace` or `.grok` on other machines. Those paths exist only in Grok's sandbox, and the tools work without them.
- **Requirements:** `python3` 3.10 or newer and outbound HTTPS. Nothing to install.

Then open the `SKILL.md` for the task at hand.

## Skills

| Skill | Use for |
|---|---|
| [`anima-cloud`](skills/anima-cloud/SKILL.md) | Anime/illustration images from text prompts (Anima model on Comfy Cloud) |
| [`minimax-ref2v`](skills/minimax-ref2v/SKILL.md) | Short video clips with audio from reference images and/or reference videos for motion, camera and sound (MiniMax H3 Ref2VA on Comfy Cloud) |

## Rules

1. **Tools are black boxes.** Don't read, unpack, modify or debug scripts (including `skills/_shared/`) or anything under `dev/` unless the user explicitly asks. Run the documented commands and act on the output.
2. **Every submission costs credits.** Submit once per user request. Never resubmit to get around a pending, stalled or failed job. Don't try variations the user didn't ask for.
3. **Secrets.** The tools read the API key from `COMFY_API_KEY` or `COMFYUI_API_KEY`, from `--key-file PATH`, or (in Grok's sandbox only) `/home/workdir/.grok/secrets/comfy_api_key`. The user tells you which applies. If none is set up, ask the user. Don't search the filesystem for keys. Never print, echo, log or paste a key, including in commands you show.
4. **Showing results.** When a run completes, show the user every file listed in `path:` or `paths:`. Those paths are absolute and always correct. Use them as printed and don't guess the location. See "Output folder" below.

## Output folder

Unless you pass `--out DIR`, each tool saves to a subfolder named after it, in the first of these that applies:

1. `$HARNESS_OUT/<tool>`, if the `HARNESS_OUT` environment variable is set
2. `/workspace/artifacts/<tool>`, if `/workspace` exists (Grok's sandbox)
3. `./artifacts/<tool>`, under the current directory

The folder is checked before anything is submitted. If it can't be created, the tool exits 3 and no credits are spent.

## Output and exit codes (all tools)

Each tool prints a few `key: value` lines, including `status:`, and exits with one of these codes:

| Exit | `status` | What to do |
|---|---|---|
| 0 | `completed` | Show the files in `path:` / `paths:`. |
| 4 | `pending` | The job is still running. Run the exact command on the `next:` line, as many times as needed. It never starts a new job. |
| 1 | `error` / `failed` / `cancelled` | The job or request was rejected. Tell the user the `error:` line. Don't retry unless asked. |
| 2 | `error` / `stalled` | Network or service problem. Tell the user. You may run `--resume <prompt_id>` once. |
| 3 | `error` | Key, credits, auth or a bad flag. Tell the user the `error:` line. Don't retry. |

Only use a `prompt_id` that a tool printed. `--resume <prompt_id>` keeps waiting for and downloads a job. `--cancel <prompt_id>` removes a job from the queue. Use `--cancel` only when the user asks.
