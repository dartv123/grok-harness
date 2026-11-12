# Writing an FL2VA prompt

The prompt is passed to the model as raw text, so it has to follow this format exactly. Write it in English; only dialogue, lyrics and on-screen text stay in their original language. Adult content follows the same rules. No minors.

The tool checks the field names, the Picture labels and the landing time before submitting, and exits 3 with the reason if one is wrong.

## 1. Pick the mode from the frames you have

| Mode | Frames | Labels | Job of the prompt |
|---|---|---|---|
| **fl2va** | `--first` + `--last` | Picture 1 = first, Picture 2 = last | A continuous path from the first frame to the last |
| i2va | `--first` only | Picture 1 | Keep the opening frame and develop forward |
| l2va | `--last` only | Picture 1 (it *is* the last frame) | Invent a plausible opening and converge on the frame |

If the user has two images but it's unclear whether the clip should literally start on one and end on the other, ask. Yes means fl2va. If they want two unrelated pictures combined (a person plus a place), that's the `minimax-ref2v` skill, not this one. Don't use Ref2VA fields (`subject_definitions`, `retention_analysis`) here.

## 2. Exact shape

First line is the alignment sentence. Then one blank line. Then exactly these three fields, in this order, with these names:

```text
How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot N) aligns with the S.SS-second mark of the target video.

integrated_multimodal_description: [Shot 1] ...

overall_soundscape: ...

non_diegetic_music: ...
```

- `S.SS` is `--duration` with **exactly two decimals**: 5 s is `5.00`, 8 s is `8.00`. The tool refuses a mismatch.
- `N` is the **final shot's index**. A single-shot clip uses `Shot 1` in both places; with one cut, Picture 2 belongs to `Shot 2`.
- `[Shot 1]` has no timestamp. Later shots start `At 00:03.500,` with strictly increasing times inside the duration.
- No extra headings.

Alignment lines for the single-frame modes:

- **i2va:** `For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.`
- **l2va:** `How the reference pictures align with the target video — <Picture 1> (from [Shot N]) aligns with the S.SS-second mark of the target video.`

The three fields are the same in every mode.

## 3. Check the image pair first (fl2va)

FL2VA interpolates a path between the frames. It doesn't mix styles or change scenes. Both frames should share the same person, the same room, compatible framing and lens, compatible lighting, and a physically reachable pose or prop change. The best pair is Picture 2 edited from Picture 1.

If the pair is a different room, a different person, or a very different lens, the result dissolves or morphs. **Tell the user before submitting**, and suggest `minimax-ref2v` or two separate i2va clips instead.

One main transformation per clip. 5–8 s is the sweet spot; the tool allows 4–15 s.

## 4. The body is a path, not two captions

Don't describe the two stills. Describe the motion between them, in four beats:

**first-frame state → observable intermediate changes → narrowing differences → last-frame state**

```text
[Shot 1] <style>, <what Picture 1 shows>, matching the position, framing, and lighting established by Picture 1. The camera <motion> as <ordered intermediate actions>. Toward the end of the shot the differences narrow until <what Picture 2 shows>, landing on the exact pose, spacing, and composition established by Picture 2 at the S.SS-second mark.
```

- **Style** comes from the frames: `Live-action, cinematic` / `2D-animated` / `3D CG` / `claymation` / `watercolor` / `vintage film`.
- **Name** what the model mustn't invent: identity, wardrobe, key prop colors, which hand moves which object, start and end pose in functional terms ("closed umbrella at her side" → "open canopy overhead"), the camera, and sounds that sync to the action.
- **Don't** restate pixel detail the frames already show (hair strands, fabric weave, background clutter). It fights the keyframes.
- Prefer **one shot**. Add a cut only when the user asked for a new viewpoint. The final shot is the one that lands on Picture 2.

## 5. Camera: one move, written as a sentence

`The camera <type> with <amplitude> at <speed> ...`

Types: Zoom In/Out (focal length), Push In / Pull Out (body moves), Pan Left/Right, Truck Left/Right, Tilt Up/Down, Pedestal Up/Down, Arc Shot, Tracking Shot, Static Shot, Shake Slightly/Strongly, POV, Roll Clockwise/Counterclockwise.

Amplitude: `with small amplitude` / `with large amplitude` (omit for medium). Speed: `at slow speed` / `at fast speed` (omit for normal).

Default to a **static shot or one small, slow move**. A big fast move plus a pose change in 5 s usually wrecks the landing. Never two camera verbs in one shot.

## 6. Audio fields

The model generates stereo audio with the video. Both fields are required.

- **`overall_soundscape`**: 1–4 sentences. Ambience, physical action sounds, non-verbal human sounds (rain, footsteps, fabric, breathing). No dialogue, no score. `N/A` only if the user wants silence.
- **`non_diegetic_music`**: 1–3 sentences of instruments, tempo, rhythm and dynamics, no mood words ("emotional", "epic"). `N/A` is the normal default unless the user asked for a score. A radio, phone or singing in the scene goes in the body instead.

**Dialogue** goes in the body:

```text
The young woman with a quiet, breathy voice (S1) says: <d>[English] I get off at the next station.</d>
```

- Speaker IDs like `(S1)` stay the same across shots. Silent characters get none.
- Voice traits go outside `<d>`. Inside: the language tag and the exact words, untranslated.
- Voiceover: `says in an off-screen voiceover` followed by `while his lips remain completely closed.`
- Budget 2–3 spoken words per second. On-screen text goes in English double quotes, original language preserved.

## 7. Templates

**Default: single shot, static camera, no dialogue or score**

```text
How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot 1) aligns with the S.SS-second mark of the target video.

integrated_multimodal_description: [Shot 1] Live-action, cinematic, <subject> begins in the position and framing established by Picture 1, <start pose / prop state>. The camera holds a static shot as <ordered intermediate actions>. Toward the end of the shot the differences narrow until <end pose / prop state>, landing on the exact pose, spacing, and composition established by Picture 2 at the S.SS-second mark.

overall_soundscape: <room tone>. <one or two action sounds that match the intermediate moves>.

non_diegetic_music: N/A
```

**Two shots (only when the user asked for a cut).** Picture 2 belongs to the final shot:

```text
How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot 2) aligns with the S.SS-second mark of the target video.

integrated_multimodal_description: [Shot 1] Live-action, cinematic, <opening from Picture 1, matching position, framing, and lighting>. The camera holds a static shot as <first-half action>. [Shot 2] At 00:0X.000, the shot cuts to <new viewpoint of the same scene>. The remaining action completes and lands on the exact pose, spacing, and composition established by Picture 2 at the S.SS-second mark.

overall_soundscape: <ambience across both shots>. <action sounds for each beat>.

non_diegetic_music: N/A
```

If a spoken line crosses the cut, split it with `<scenetrans>` and say the audio continues seamlessly across the cut.

## 8. Official example (8 s, single shot)

```text
How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot 1) aligns with the 8.00-second mark of the target video.

integrated_multimodal_description: [Shot 1] Live-action, cinematic, a rain-soaked cyclist begins in the position and framing established by Picture 1, holding a closed black umbrella beside a silver bicycle. The camera pulls out with small amplitude at slow speed as she releases the bicycle handle, raises the umbrella above her shoulder, and presses the runner upward until the canopy opens. Water rolls from the expanding fabric while she steps beneath it, rotates the handle into the final angle, and settles into the pose, spacing, and composition established by Picture 2 at the end of the shot.

overall_soundscape: Rain falls steadily on the pavement, followed by the metallic click of the umbrella runner and the soft snap of the canopy opening. Water drips from the bicycle frame as distant traffic passes.

non_diegetic_music: N/A
```

Run with `--duration 8`. When a render goes wrong, see [failures.md](failures.md).
