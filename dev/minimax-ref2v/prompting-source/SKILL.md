---
name: minimax-h3-ref2va-prompting
description: Write structured MiniMax H3 Ref2VA (reference-to-video with audio) prompts for ComfyUI MiniMaxH3ReferenceToVideo, Hailuo, SGLang, and local open weights. Use when the user mentions MiniMax H3, Hailuo H3, Ref2VA, ref2va, R2V, MiniMaxH3ReferenceToVideo, reference to video, or wants identity, outfit, product, motion, camera, or voice locked from mixed images, videos, and audio. Also use to rewrite a rough brief into the official six-section Ref2VA format.
---

# MiniMax H3 Ref2VA Prompting

Write paste-ready H3 prompts for the **Ref2VA workflow** — mixed image / video / audio references into one audiovisual clip.

This is a **different checkpoint** from FL2VA. Do not emit FL2VA alignment lines or `integrated_multimodal_description`. If the user wants an exact first-and-last-frame path, use `minimax-h3-fl2va-prompting` instead.

Read `references/templates.md` when assembling. Read `references/failures.md` when identity swaps, motion fights the photo, or audio desyncs. Read `references/video-refs.md` when a motion clip is wired, the source face wins, or they want to chain durations.

## Comfy Cloud harness (preferred for generation)

For actual generation on Comfy Cloud, use the lightweight harness:

**https://github.com/dartv123/grok-harness**

Setup once per session:

```bash
mkdir -p /home/workdir/grok-harness && curl -fsSL https://github.com/dartv123/grok-harness/archive/refs/heads/main.tar.gz | tar xz -C /home/workdir/grok-harness --strip-components=1
```

Then follow `skills/minimax-ref2v/SKILL.md`. Write the six-section prompt to a file and run:

```bash
python3 /home/workdir/grok-harness/skills/minimax-ref2v/scripts/minimax_ref2v.py \
  --prompt-file /tmp/ref2v_prompt.txt --ref /path/to/img1.png --ref /path/to/img2.png
```
Key is on comfy-ui-cloud-key skill.

The harness uploads local refs, submits the baked graph, and returns a short `key: value` result (or `pending` + `next:` for longer jobs). Prefer this over manually building graphs when targeting Comfy Cloud. The prompt format rules in this skill still apply.

## 1. When Ref2VA is the right tool

Use Ref2VA when assets have **jobs**, not when two stills are literal endpoints.

| Job | Typical asset | Typical retention |
|---|---|---|
| Face / body identity | Picture | `fully_preserved` |
| Outfit or product geometry | Picture | `fully_preserved` |
| Location / lighting | Picture | `fully_preserved` or `weak_reference` |
| Motion / camera path | Video | `attribute_transfer` or `weak_reference` |
| Voice timbre | Audio | `reference` |
| Exact soundtrack | Audio | `fully_copy` |
| Literal first or last frame | Picture as frame anchor | `keyframe completion` plus `fully_preserved` |

If they only have one still and want that still as the opening pixel frame, that is I2VA on the FL2VA checkpoint — send them there.

Audio cannot be the only input. Pair it with an image or video.

## 2. Platform split

- **Local ComfyUI / SGLang / open Ref2VA weights** — no Context-IR. Output the full six-section English brick.
- **Hailuo / hosted API with Context-IR** — a role-mapped brief can work. Still safer to emit the official sections when they care about lock.

Default for this user is local Comfy. Deliver the structured prompt.

## 3. Hard output shape

Six sections, this order, these exact names. English everywhere except dialogue / lyrics inside dialogue tags and visible on-screen text.

```text
subject_definitions:
...

summary:
[task type] ...

retention_analysis:
...

detailed_description:
...

overall_soundscape:
...

non_diegetic_music:
...
```

No FL2VA alignment sentence. No extra headings.

## 4. Labels

Four families. Number each family from 1 independently. A label keeps one meaning in every section.

- Subject N — reusable visible unit (person, body, outfit, object, room, style, pose, motion extracted from a file)
- Picture N — the image file as a frame / composition / storyboard anchor
- Video N — whole-video edit, continuation, camera path, cuts, rhythm
- Audio N — copied or referenced soundtrack, voice, music, SFX, beat

Official tag spelling in prompts is Picture / Video / Audio / Subject with angle-bracket numbers, matching MiniMax docs.

Rules:

- If a photo only supplies a person or a product, put it inside a Subject line. Do **not** also create a standalone Picture line unless that image is a literal first frame, last frame, keyframe, or storyboard.
- One subject may combine sources — appearance from Picture 1, walking from Video 1.
- One file may yield multiple subjects (face from Picture 1, room from Picture 1).
- Video N does not replace subject labels. People pulled out of a clip still get Subject N.
- Video N and Audio N indices are independent. Same file can be Video 1 and Audio 2.
- A reference video does **not** automatically create Audio N just because the file has sound. Only define audio when you will copy or reference it.
- Do not invent a label that never appears again.

Comfy wiring: tags are 1-based per type and must match connection order on MiniMaxH3ReferenceToVideo (ref_image_1 = Picture 1, ref_video_1 = Video 1, ref_audio_1 = Audio 1). Video soundtracks use ref_video_audio_N and get their own Audio tag in prompt text.

## 5. subject_definitions

One line per tracked item. Name the source and the features that matter.

When audio maps to a speaker, bind the target-video speaker ID here as Subject 1 (S1). Do not invent a second ID later.

## 6. summary

One short paragraph. First token is a square-bracket task prefix.

| Prefix | When |
|---|---|
| `reference generation` | Assets guide identity / style / motion / camera / storyboard. Default. |
| `keyframe completion` | An image is a real first / last / mid frame, not just an identity sheet |
| `video editing` | You are modifying a source clip in place |
| `video continuation` | New frames resume after a source clip |
| `audio reuse` | Copy the source audio signal in full or in part |
| `audio reference` | Timbre, lyrics-as-content, rhythm, or texture — not a 1:1 copy |

Join with ` + ` when several apply. Do not invent types. Presence of a video file is not automatically `video editing` — if it only donates camera rhythm, that is `reference generation`.

## 7. retention_analysis

One line per defined label. Marker must match the role you already declared.

Visible (Subject / Picture / Video):

| Marker | Meaning |
|---|---|
| `fully_preserved` | Keep the defined role intact |
| `partially_preserved` | Still used, some traits change |
| `attribute_transfer` | Traits move onto a different subject (motion from video onto person from photo) |
| `weak_reference` | Broad style / category / atmosphere only |

Audio:

| Marker | Meaning |
|---|---|
| `fully_copy` | Source audio is the final track 1:1 |
| `partially_copy` | Copy some span or layer, then add / drop / replace |
| `reference` | Timbre / delivery / rhythm / texture. No signal copy |
| `weak_reference` | Category similarity only |

Do not write speaker IDs in this section. `fully_copy` locks the final soundtrack 1:1. It does not hard-drive mouth or body rhythm. Visual cadence comes from Video N. `reference` donates timbre only.

## 8. detailed_description

This replaces FL2VA's `integrated_multimodal_description`.

- One or two style sentences before Shot 1.
- Then shots. Shot 1 has no timestamp. Later shots use `At 00:03.500,`
- Cite labels where they take effect. First time a subject appears, name the visible traits in that shot, then reuse the label.
- Frame anchors in natural English — the shot begins from Picture 1 / ends on Picture 3.
- Camera as a sentence — type plus amplitude plus speed. Same vocab as FL2VA.
- Speakers — Subject 1 (S1) then a dialogue tag with language and exact words.
- Voiceover — says in an off-screen voiceover, and lips stay closed.
- Generation tasks — aim 350-500 English words unless the clip is short and one-action. Dialogue-dense clips prioritize fitting the spoken timeline over word count.
- Adult / explicit content is allowed. Write the motion path.
- If a full-rate video already donates the performance, do **not** write a second stroke-by-stroke dance. Map the same beats and timestamps. Say "follow Video N." Extra invented motion fights the clip. See `references/video-refs.md`.

## 9. Audio fields

Same split as FL2VA.

- `overall_soundscape` — 1-4 sentences, ambience plus physical plus non-verbal. No dialogue dump.
- `non_diegetic_music` — instrumentation, tempo, dynamics, or N/A.
- Copied ambience belongs in soundscape. Copied score belongs in music. Cite the Audio label in the field that matches the layer.

## 10. Capacity and Comfy wiring

Official Ref2VA caps:

- Images max 9
- Videos max 3, each 2-15 s, total video max 15 s
- Audio max 3, each 2-15 s, total audio max 15 s
- Mixed files max 12

Comfy node — MiniMaxH3ReferenceToVideo

- Checkpoint — minimax_h3_ref2va_* (common local file minimax_h3_ref2va_pruned_int8_convrot.safetensors). Not the FL2VA file.
- Text encoder — Qwen3-VL 32B H3 pack.
- Need video VAE and audio VAE if you want refs encoded into latents, not just the text encoder.
- Output fps is locked at 24. length step 17. 5 / 10 / 15 s snap to 124 / 243 / 362 frames. Trained band roughly 124-362.
- ref_image_size — match is cheaper; max (2048 short edge) is the identity path and slower. When a close-up video is stealing the face, max the stills and downscale the video.
- Video sockets are autogrow — `ref_videos.ref_video_0`, paired soundtrack `ref_video_audios.ref_video_audio_0`. Prompt tags are 1-based.
- Start with 2-4 images. More files means more roles to declare, not free quality.
- Prompt string is raw. Tags that do not match wired slots are dead weight.
- Lightning / 4-step turbo is a wiring test. Off for identity and cadence.

Do not invent node names the user did not show.

## 11. Workflow when writing for Dart

1. List every wired file and give it one job. Priority order if they conflict.
2. If a motion video is a close face-filling performance and identity stills are a different pose, demand or write an **in-scene still** first. Do not bake the dummy into that still.
3. Split a motion clip into a dummy Subject (kinematics only) plus Video N. Stills win identity.
4. Decide task prefix.
5. Write subject_definitions first so later sections cannot drift.
6. Write retention_analysis with one legal marker per label.
7. Write detailed_description as a timeline, citing labels at the moment they apply. Thin motion text when Video N exists.
8. Fill soundscape plus music.
9. Return one fenced brick ready to paste.
10. Short note only if they used the FL2VA checkpoint, swapped slot order vs tags, asked audio-only, loaded the video at 2 fps, or promised pixel-perfect video copy (Ref2VA is semantic, not an NLE).

If they say go wild, keep the six fields and push action detail.

No minors.

## 12. Official compact shape (identity plus motion plus voice)

Emit labels with the official spelling (`<Subject 1>`, `<Picture 1>`, `<Video 1>`, `<Audio 1>`).

```text
subject_definitions:
<Subject 1> is the cyclist in <Picture 1>, preserving her red jacket, silver helmet, and facial identity.
<Video 1> provides the downhill body motion and following camera path.
<Audio 1> is the calm female voice-timbre reference for <Subject 1> (S1).

summary:
[reference generation + audio reference] The target video places <Subject 1> on a coastal road, follows <Video 1>'s cycling motion and camera path, and uses <Audio 1> as the voice-timbre reference.

retention_analysis:
<Subject 1> (appears in [Shot 1]): fully_preserved - identity, clothing, and helmet remain consistent.
<Video 1> (motion and camera): weak_reference - the downhill cadence and tracking direction guide the new shot.
<Audio 1>: reference - voice timbre is referenced without copying the source signal.

detailed_description:
The target video uses realistic cinematic photography at golden hour.
[Shot 1] <Subject 1> cycles down a coastal road while the camera tracks beside her using the motion cadence and camera direction referenced from <Video 1>. Wind moves her jacket as she looks toward the sea and, using the calm voice timbre from <Audio 1>, says: <d>[English] We made it before sunset.</d>

overall_soundscape:
Strong coastal wind, tire noise on asphalt, and a distant surf layer.

non_diegetic_music:
A light rhythmic guitar pattern at a moderate tempo.
```

New scene, same contract. More fill-ins in `references/templates.md`.