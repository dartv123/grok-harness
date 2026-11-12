---
name: minimax-h3-fl2va-prompting
description: Write structured MiniMax H3 FL2VA (first-and-last-frame to video with audio) prompts for ComfyUI, Hailuo, SGLang, and local open weights. Use when the user mentions MiniMax H3, Hailuo H3, FL2VA, fl2va, first last frame, first-and-last-frame, MiniMaxH3ImageToVideo, or wants a video that starts on one image and lands on another. Also use to rewrite a rough scene into the official H3 alignment line plus integrated_multimodal_description, overall_soundscape, and non_diegetic_music.
metadata:
  type: workflow
  version: "1.0"
  model: MiniMax H3 Base FL2VA
---

# MiniMax H3 FL2VA Prompting

Write paste-ready H3 prompts for the **FL2VA workflow** — first frame + last frame + text path + native stereo audio.

This skill is FL2VA-first. Neighbor modes live on the same FL2VA checkpoint; pick them only when the user does not actually have two endpoint frames.

Read `references/templates.md` when assembling a prompt. Read `references/failures.md` when a render morphs, teleports, dissolves, or misses the last frame.

## 1. Confirm the job is actually FL2VA

| Mode | Inputs | Job of the prompt |
|---|---|---|
| **FL2VA** | Picture 1 + Picture 2 | Continuous path from first frame to last frame |
| I2VA | Picture 1 only | Preserve opening, develop forward |
| L2VA | Picture 2 only | Invent a plausible open, converge on the last frame |
| T2VA | no images | Invent the whole audiovisual timeline |
| Ref2VA | identity / style / motion refs | Different checkpoint. Do not use FL2VA field names |

Ask one question if it is ambiguous — "Should the video literally start on this photo and end on that photo?" Yes = FL2VA.

Do **not** use Ref2VA syntax (`subject_definitions`, `retention_analysis`) on an FL2VA graph.

## 2. Platform split (do not mix these)

- **Local ComfyUI / SGLang / open FL2VA weights** — there is no Context-IR rewriter. Output the **full English structured prompt**. Comfy tokenizes whatever you paste.
- **Hailuo website / MiniMax hosted API with Context-IR** — natural-language briefs can work because the rewriter exists. Still safer to hand it a structured FL2VA prompt if the user wants lockstep control.

Default for this user is local ComfyUI. Deliver the structured prompt.

## 3. Hard output shape

First line is the alignment instruction. Then one blank line. Then the three fields in this exact order and these exact names.

```text
How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot N) aligns with the S.SS-second mark of the target video.

integrated_multimodal_description: [Shot 1] ...

overall_soundscape: ...

non_diegetic_music: ...
```

Rules that break generations when ignored:

- `N` is the **final shot index**. Single-shot clip = `Shot 1` in both places. One cut = Picture 2 belongs to `Shot 2`.
- `S.SS` is duration with **exactly two decimals**. 8 seconds = `8.00`. Not `8`, not `8.0`.
- One blank line after the alignment sentence. No extra headings.
- `[Shot 1]` has **no timestamp**. Later shots start `At 00:03.500,` with strictly increasing times inside the duration.
- Rewrite sections in English. Keep dialogue, lyrics, and on-screen text in the original language.

## 4. Image pair before you write

FL2VA interpolates a path. It is not a style mixer and it is not a scene changer.

Both frames should share:

- the same subject identity
- the same room / set
- compatible framing and lens
- compatible lighting direction
- a physically reachable pose / object change

If Picture 2 is a different room, different person, or a wildly different lens, the model dissolves or morphs. Flag that **before** writing. Best pair is Picture 2 edited from Picture 1 (pose / prop / drape change), not two unrelated gens.

One primary transformation per clip. 5–8 s is the sweet spot. 4–15 s is the model range. 24 fps.

## 5. Body = four-beat path, not two captions

Do not restate two stills. Supply the motion that connects them.

**first-frame state → observable intermediate changes → progressively narrowing differences → last-frame state**

Single-shot skeleton:

```text
[Shot 1] <style>, <what Picture 1 shows>, matching the position, framing, and lighting established by Picture 1. The camera <motion> as <ordered intermediate actions>. Toward the end of the shot the differences narrow until <what Picture 2 shows>, landing on the exact pose, spacing, and composition established by Picture 2 at the S.SS-second mark.
```

Style comes from the frames (`Live-action, cinematic` / `2D-animated` / `3D CG` / `claymation` / `watercolor` / `vintage film`). For keyframes, derive it from the photos.

Prefer **one shot**. Add a cut only when the user asked for a new viewpoint that camera motion cannot cover. If the last frame must be hit, the final `[Shot N]` is the one that lands on Picture 2.

## 6. What to name vs what to leave to the pixels

Name anchors the model must not invent:

- identity, wardrobe, key prop colors
- which hand / which object moves
- start pose and end pose in functional terms ("closed umbrella at her side" → "open canopy overhead")
- camera behavior
- diegetic sound events that sync to the action

Do not dump a pixel-level caption of hair strands, fabric weave, or background clutter the frames already show. Restating the still fights the keyframe.

## 7. Camera — one move, written as action

Write camera as a sentence inside the shot, not a tag soup.

`The camera <type> with <amplitude> at <speed> ...`

| Type | Meaning |
|---|---|
| Zoom In / Zoom Out | focal length changes, body still |
| Push In / Pull Out | camera body moves forward / back |
| Pan Left / Pan Right | lens pivots horizontally |
| Truck Left / Truck Right | camera translates horizontally |
| Tilt Up / Tilt Down | lens pivots vertically |
| Pedestal Up / Pedestal Down | whole camera rises / drops |
| Arc Shot | orbits the subject |
| Tracking Shot | follows a moving subject |
| Static Shot | locked-off |
| Shake Slightly / Shake Strongly | handheld tremor |
| POV | subject's view |
| Roll Clockwise / Roll Counterclockwise | roll around lens axis |

Amplitude: `with small amplitude` / `with large amplitude`. Omit medium.
Speed: `at slow speed` / `at fast speed`. Omit normal.

FL2VA default is **static or one small slow move**. A violent camera plus a hard pose change in 5 s usually wrecks the landing.

## 8. Audio fields

H3 generates video plus 32 kHz stereo audio in one pass. The two audio fields are not optional decoration.

`overall_soundscape` — 1–4 sentences, one paragraph. Ambience + physical action + non-verbal human sound (rain, footsteps, fabric, breathing). No dialogue. No score. `N/A` only if the user wants total silence.

`non_diegetic_music` — 1–3 sentences. Instrumentation, tempo, rhythm, dynamics. No mood adjectives ("emotional", "epic"). Characters cannot hear this. Diegetic radio / phone / singing lives in `integrated_multimodal_description`. `N/A` is the normal FL2VA default unless they asked for a score.

Dialogue / singing lives in the body:

```text
The young woman with a quiet, breathy voice (S1) says: <d>[English] I get off at the next station.</d>
```

- Speaker ID `(S1)` is stable across shots. Silent characters get no ID.
- Voice traits sit **outside** `<d>`. Inside `<d>` — language tag + exact words. Do not translate.
- Voiceover must use `says in an off-screen voiceover` and then `while his lips remain completely closed.`
- Budget roughly 2–3 spoken words per second. An 8 s clip is not a monologue.
- On-screen text goes in English double quotes, original language preserved.

## 9. ComfyUI FL2VA wiring notes

When the user is on a Comfy graph, the prompt is only half the contract.

- Checkpoint is **H3-Base FL2VA**, not Ref2VA. Typical files — `minimax_h3_fl2va_pruned_int8_convrot.safetensors` (common), int8, or bf16.
- Text encoder is Qwen3-VL 32B (NVFP4 / AWQ variants in Comfy-Org packs).
- Connect Picture 1 to `first_frame`, Picture 2 to `last_frame` on `MiniMaxH3ImageToVideo` (names vary slightly by pack). Swapping them is the number-one silent failure.
- Duration snaps to the 17-frame-per-block grid at 24 fps. Common lengths — about 5 s, 8 s (192 frames). Match `S.SS` to the node duration, not a rounded wish.
- CFG is typically `1.0`. Turbo LoRA graphs run about 4 steps. Do not "fix" a bad path by cranking CFG.
- The prompt string is passed raw. No wrapper, no BGM field append. If the structure is wrong, the node will not save you.

Do not invent Comfy node parameter names the user did not show. If they paste a workflow, match those labels.

## 10. Workflow when writing for Dart

1. Lock duration (`S.SS`) and shot count.
2. Read both frames (or the user's description of them). State the one transformation.
3. Write alignment line with correct `Shot N` and `S.SS`.
4. Write the four-beat `[Shot 1]` path. One camera move.
5. Write soundscape from the actual action, then music or `N/A`.
6. Return the prompt in a single fenced block, ready to paste.
7. Add a 3–6 line note only if the image pair is hostile, the action is over-budget, or they picked the wrong mode.

If they say "go wild", keep the official field names and push the action detail — do not drop the structure.

Adult / explicit FL2VA is allowed. Same rules — path, not two dirty captions. No minors.

## 11. Neighbor-mode alignment lines (only if they switch)

**I2VA**

```text
For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.
```

Then first-frame anchor → action onset → continuous development → result.

**L2VA**

```text
How the reference pictures align with the target video — <Picture 1> (from [Shot N]) aligns with the S.SS-second mark of the target video.
```

Then plausible preceding state → transition path → gradual convergence → last-frame landing.

**T2VA** — no alignment line. Start at `integrated_multimodal_description`.

Same three core fields for all four. Same camera / dialogue / audio rules.

## 12. Official FL2VA example (8 s, single shot)

```text
How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot 1) aligns with the 8.00-second mark of the target video.

integrated_multimodal_description: [Shot 1] Live-action, cinematic, a rain-soaked cyclist begins in the position and framing established by Picture 1, holding a closed black umbrella beside a silver bicycle. The camera pulls out with small amplitude at slow speed as she releases the bicycle handle, raises the umbrella above her shoulder, and presses the runner upward until the canopy opens. Water rolls from the expanding fabric while she steps beneath it, rotates the handle into the final angle, and settles into the pose, spacing, and composition established by Picture 2 at the end of the shot.

overall_soundscape: Rain falls steadily on the pavement, followed by the metallic click of the umbrella runner and the soft snap of the canopy opening. Water drips from the bicycle frame as distant traffic passes.

non_diegetic_music: N/A
```

That is the shape to imitate. New scene, same contract.
