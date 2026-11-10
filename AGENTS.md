# Agent instructions: grok-harness

This repo holds command-line tools ("harnesses") that run image and media workflows on remote services. Each tool comes with a skill describing when and how to use it. These rules apply to every tool here. Each skill only adds what's specific to its tool.

## Setup (once per conversation; the sandbox resets)

```bash
mkdir -p /home/workdir/grok-harness && curl -fsSL https://github.com/dartv123/grok-harness/archive/refs/heads/main.tar.gz | tar xz -C /home/workdir/grok-harness --strip-components=1
```

Run this again only if the files are missing. Then open the `SKILL.md` for the task at hand.

## Skills

| Skill | Use for |
|---|---|
| [`anima-cloud`](skills/anima-cloud/SKILL.md) | Anime/illustration images from text prompts (Anima model on Comfy Cloud) |

## Rules

1. **Tools are black boxes.** Don't read, unpack, modify or debug scripts or anything under `dev/` unless the user explicitly asks. Run the documented commands and act on the output.
2. **Every submission costs credits.** Submit once per user request. Never resubmit to get around a pending, stalled or failed job. Don't try variations the user didn't ask for.
3. **Secrets.** The user tells you how API keys are provided. Never print, echo, log or paste a key, including in commands you show.
4. **Showing results.** Output files go under `/workspace/artifacts/`. When a run completes, show the user every file listed in `path:` or `paths:`.

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
