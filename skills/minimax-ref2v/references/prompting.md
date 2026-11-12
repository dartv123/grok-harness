# Writing a Ref2VA prompt

The prompt is passed to the model as raw text, so it has to follow this format exactly. Write it in English; only dialogue and on-screen text may be in another language. No minors.

Labels are `<Subject N>`, `<Picture N>` (the Nth `--ref`), `<Video N>` (the Nth `--video`) and `<Audio N>` (the soundtrack of the Nth `--video`). Use only labels you actually pass files for. If you give no `--video`, ignore the video and audio parts of this guide.

## Shape

Six sections, in this order, with these exact names and no extra headings:

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

## Labels

- `<Picture N>` is the Nth `--ref` image (1-based, in command-line order).
- `<Subject N>` is a reusable visible thing: a person, outfit, object, room or style. Number subjects from 1 independently of pictures.
- If a picture only supplies a person, product or room, describe it as a Subject line. Do not also create a standalone `<Picture N>` line, unless that image is a literal first frame or keyframe.
- One subject can combine pictures (face from Picture 1, outfit from Picture 2). One picture can give several subjects.
- A label keeps one meaning in every section. Never use a label that is not defined in `subject_definitions` and wired as a `--ref`.

## Sections

**subject_definitions**: one line per tracked item, naming the source picture and the features that matter. If a character speaks, tag them here as `<Subject 1> (S1)` and use only that ID later.

**summary**: one short paragraph starting with a square-bracket task prefix. Use `[reference generation]` (pictures guide identity, outfit, location or style; the default) or `[keyframe completion]` (a picture is a real first or last frame). Join with ` + ` if both apply.

**retention_analysis**: one line per label: `<Subject 1> (appears in [Shot 1]): marker - what stays locked.`

| Marker | Meaning |
|---|---|
| `fully_preserved` | Keep the defined role intact |
| `partially_preserved` | Still used, some traits change |
| `weak_reference` | Broad style or atmosphere only |

**detailed_description**: one or two style sentences, then shots. Shot 1 has no timestamp; later shots start `At 00:03.500,`. Name a subject's visible traits the first time it appears, then reuse the label. Describe the camera as type plus amplitude plus speed. Speech: `<Subject 1> (S1)` then a dialogue tag with language and exact words, e.g. `says: <d>[English] We made it.</d>`. Voiceover: say it is off-screen and the lips stay closed. Aim for 350 to 500 words unless the clip is short with a single action; dialogue-heavy clips should fit the spoken timeline first.

**overall_soundscape**: 1 to 4 sentences of ambience, physical sounds and non-verbal sounds. No dialogue here.

**non_diegetic_music**: instrumentation, tempo and dynamics, or `N/A`.

## Template: identity from one picture

```text
subject_definitions:
<Subject 1> is the woman whose face, hair, skin, and wardrobe come from <Picture 1>.

summary:
[reference generation] The target video shows <Subject 1> performing <one action> while keeping the identity and wardrobe defined from <Picture 1>.

retention_analysis:
<Subject 1> (appears in [Shot 1]): fully_preserved - facial identity, hair, and wardrobe remain consistent.

detailed_description:
The target video is live-action, handheld close-up, matching the lighting quality of <Picture 1>.
[Shot 1] <Subject 1> begins <start state>. The camera holds a static shot as <ordered actions>. <Subject 1> ends in <end state>.

overall_soundscape:
<room tone and action sounds>.

non_diegetic_music:
N/A
```

## Template: face, outfit and room from three pictures

```text
subject_definitions:
<Subject 1> is the woman whose face, hair, and body identity come from <Picture 1> and whose outfit comes from <Picture 2>.
<Subject 2> is the room and lighting from <Picture 3>.

summary:
[reference generation] The target video places <Subject 1> inside <Subject 2> wearing the outfit from <Picture 2>.

retention_analysis:
<Subject 1> (appears in [Shot 1]): fully_preserved - face from <Picture 1> and outfit geometry from <Picture 2> stay locked; do not blend the two wardrobes.
<Subject 2> (appears in [Shot 1]): fully_preserved - room layout and light direction from <Picture 3> stay locked.

detailed_description:
The target video is live-action in the lighting of <Subject 2>.
[Shot 1] <Subject 1> stands in <Subject 2> and <action>.

overall_soundscape:
<room tone>.

non_diegetic_music:
N/A
```

If the pictures conflict, say which wins: face over outfit, outfit over room, unless the user says otherwise.

## Template: a picture as the literal first frame

Use `[keyframe completion + reference generation]`, add the line `<Picture 1> is the first frame of [Shot 1].` to `subject_definitions`, and add `<Picture 1> ([Shot 1] first frame): fully_preserved - opening composition, pose, and lighting match <Picture 1>.` to `retention_analysis`. Open `detailed_description` with `[Shot 1] The shot opens on <Picture 1>.`

## Using a reference video

`<Video N>` donates motion, camera path, cuts, rhythm and cadence. It does not replace subject labels: a person pulled out of a clip still gets a `<Subject N>` line.

- **Summary prefix:** `[reference generation]` when the video only donates motion or camera. `video editing` is for modifying the source clip in place, and `video continuation` for resuming after it; don't use them just because a video is present. Add `audio reuse` (copy the soundtrack) or `audio reference` (timbre or rhythm only) when `<Audio N>` is used, joined with ` + `.
- **Retention markers for a video:** `attribute_transfer` (its motion or camera moves onto a different subject; the usual choice) or `weak_reference`. `fully_preserved` on a `<Video N>` means "keep the whole clip's structure", which is an edit job and lets the source performer and location leak in.
- **Retention markers for audio:** `fully_copy` (the soundtrack is the final track 1:1), `partially_copy`, `reference` (timbre, delivery or rhythm; nothing copied) or `weak_reference`. `fully_copy` locks the soundtrack only; it does not drive the mouth or body, so the visual rhythm still comes from `<Video N>`.
- **No audio wanted?** Pass `--no-video-audio`, and don't mention `<Audio N>`.
- **Don't over-prompt motion.** If a video supplies the performance, write "follow `<Video 1>`" with the same beats and timestamps instead of a second stroke-by-stroke description; invented extra motion fights the clip.
- **The video's face beats your pictures.** A close, face-filling clip carries more identity than a still in a different pose, and the source performer can win. Define a motion dummy subject, and make the pictures win:

```text
subject_definitions:
<Subject 1> is the person whose appearance comes from <Picture 1>, never the performer from <Video 1>.
<Subject 2> is a motion dummy from <Video 1> only: body timing and camera. It carries zero identity. Discard its face, hair and clothes.
<Video 1> is motion and camera only.

retention_analysis:
<Subject 1> (appears in [Shot 1]): fully_preserved - identity and wardrobe from <Picture 1>. The pictures beat <Video 1> if they conflict.
<Subject 2>: attribute_transfer - kinematics and camera only.
<Video 1> (motion and camera): attribute_transfer - transfer timing and camera path onto <Subject 1>; do not copy the source performer, location or clothes.
```

  Also use `--ref-size max`, and give a picture of the target person already in the target scene and camera, made without the motion video, as `<Picture 1>`. If a clip keeps stealing the face, shrink it with `--video-width` / `--video-height` (short edge about 512 to 640), or ask the user for a cropped clip.
- **Reference video specs:** at least 5 frames (about 0.2 s). The tool resamples clips to 24 fps by default, but a sparse or low-fps source (a few frames a second) still becomes held poses, not keyframes, so give it a real-motion clip. Only the first frames up to the output length are used. If the soundtrack is `fully_copy`, keep `--duration` no longer than the video, or the audio dies after the file ends.
- **Cost:** video tokens ride every sampler step, so expect roughly 2 to 3 times the wall time of a stills-only run, and more at high resolution.
- **A video is semantic, not an editor.** Expect drift in cuts and faces; don't promise a pixel-exact copy.

## Common problems

| Symptom | Fix |
|---|---|
| Identity comes from the wrong picture | `<Picture N>` is the Nth `--ref`. Recount after adding or reordering files |
| Outfit bleeds into the face, or the room restyles the person | Split into separate subjects, state a priority, and mark the loser `weak_reference` |
| Identity is loose or the motion looks sloppy | Re-run once with `--no-lightning` and `--ref-size max`, if the user agrees (it costs credits) |
| Soft, generic motion | `detailed_description` must be a shot timeline that cites labels where they apply, not a plot paragraph |
| Identity soup | Too many pictures. The limit is 5; two clean references beat five vague ones; drop any picture that has no sentence of work |
