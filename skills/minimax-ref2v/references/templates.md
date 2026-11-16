# Ref2VA fill-in templates

Keep the six section names and their order (see [prompting.md](prompting.md)). Renumber labels to match the files you actually pass: `<Picture N>` is the Nth `--ref`, `<Video N>` the Nth `--video`, and `<Audio N>` the soundtrack of the Nth `--video`. This tool takes no standalone audio files.

## Summary prefixes

The `summary` starts with one or more of these in square brackets, joined with ` + `. Don't invent others.

| Prefix | When |
|---|---|
| `reference generation` | Files guide identity, style, motion, camera or storyboard. The default |
| `keyframe completion` | A picture is a real first, last or middle frame, not just an identity sheet |
| `video editing` | Modifying the source clip in place |
| `video continuation` | New frames resume after the source clip ends |
| `audio reuse` | The soundtrack is copied in full or in part |
| `audio reference` | Timbre, rhythm or texture only; nothing copied |

A video's presence doesn't make it `video editing`: if it only donates motion or camera, it's `reference generation`.

## Retention markers

| For | Marker | Meaning |
|---|---|---|
| Subject / Picture / Video | `fully_preserved` | Keep the role intact |
| | `partially_preserved` | Still used, some traits change |
| | `attribute_transfer` | Traits move onto a different subject (motion from a video onto the person from a picture) |
| | `weak_reference` | Broad style, category or atmosphere only |
| Audio | `fully_copy` | The soundtrack is the final track 1:1 |
| | `partially_copy` | Copy a span or layer, then add, drop or replace |
| | `reference` | Timbre, delivery or rhythm; no signal copied |
| | `weak_reference` | Category similarity only |

Don't put speaker IDs like `(S1)` in `retention_analysis`.

## A. One picture: identity only (the most common job)

`<Picture 1>` is a character or product sheet, not a literal first frame.

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

Don't add a standalone `<Picture 1>` line unless that picture is a real frame anchor.

## B. A picture as the literal first frame, plus identity

```text
subject_definitions:
<Subject 1> is the woman whose appearance comes from <Picture 1>.
<Picture 1> is the first frame of [Shot 1].

summary:
[keyframe completion + reference generation] The target video begins from <Picture 1> and continues with <Subject 1> performing <action>.

retention_analysis:
<Subject 1> (appears in [Shot 1]): fully_preserved - identity and wardrobe stay locked.
<Picture 1> ([Shot 1] first frame): fully_preserved - opening composition, pose, and lighting match <Picture 1>.

detailed_description:
The target video is live-action and begins from <Picture 1>.
[Shot 1] The shot opens on <Picture 1>. <Subject 1> then <action path>.

overall_soundscape:
<ambience and foley>.

non_diegetic_music:
N/A
```

If the user also needs an exact last frame, use the `minimax-fl2v` skill instead.

## C. Face from Picture 1, outfit from Picture 2, room from Picture 3

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

If they conflict: face wins over outfit, outfit over room, unless the user says otherwise.

## D. Identity from a picture, motion from a video (don't copy the performer)

Run with `--ref <person> --video <motion clip>`.

```text
subject_definitions:
<Subject 1> is the woman whose appearance comes from <Picture 1> and whose body motion comes from <Video 1>.
<Video 1> is the motion-timing and camera-path reference only.

summary:
[reference generation] The target video puts <Subject 1> into a new scene while transferring only the motion cadence and camera direction of <Video 1>.

retention_analysis:
<Subject 1> (appears in [Shot 1]): fully_preserved - facial identity and wardrobe from <Picture 1> stay locked.
<Video 1> (motion and camera): attribute_transfer - transfer only head/body timing and camera path onto <Subject 1>; do not copy the source performer, location, or clothes.

detailed_description:
The target video is live-action.
[Shot 1] <Subject 1> performs the action with the cadence referenced from <Video 1> while the camera follows that same path.

overall_soundscape:
<new-scene ambience and foley>.

non_diegetic_music:
N/A
```

If the clip has sound you don't want, run with `--video-audio off` and leave `<Audio 1>` out.

## E. Voice timbre vs the exact track

Both come from a `--video`'s soundtrack, which is `<Audio N>` for the same N.

**Timbre only** (run with the default `--video-audio ref`):

```text
<Audio 1> is the voice-timbre reference for <Subject 1> (S1).
```
```text
<Audio 1>: reference - follow timbre and delivery without copying the source signal.
```

**Exact track** (lipsync, karaoke, a reused take). Run with **`--video-audio both`**; the prompt alone doesn't copy the track.

```text
<Audio 1> is the complete soundtrack reused in the target video.
```
```text
summary:
[reference generation + audio reuse] ...

retention_analysis:
<Audio 1>: fully_copy - <Audio 1> is reused 1:1 as the target video's complete final audio track.
```

Then cite `<Audio 1>` inside the shot where the mouth has to match, and keep `--duration` no longer than the clip.

## F. Edit or continue a video

Replace the performer in a clip while keeping its camera, cuts and sound. Run with `--video <clip> --ref <new person> --video-audio both`.

```text
subject_definitions:
<Video 1> is the source video for the target video edit.
<Subject 1> is the replacement identity from <Picture 1>.
<Audio 1> is the synchronized audio track of <Video 1> and is reused in the target video.

summary:
[video editing + audio reuse] The target video edits <Video 1> by replacing the performer with <Subject 1> while keeping the original camera path, cuts, and soundtrack.

retention_analysis:
<Video 1> (camera, cuts, environment, timing): fully_preserved - framing, handheld drift, background, and action timing stay locked.
<Subject 1> (appears throughout): fully_preserved - replacement identity stays locked.
<Audio 1>: fully_copy - original soundtrack remains the final track.
```

**Continuation** uses `[video continuation]` and says the new clip resumes after the last frame of `<Video 1>`. Between separate jobs it's a soft handoff, not a seamless join: pass the last 2 or more seconds of clip A as `--video` (`--video-skip` to the tail), and optionally the next motion phrase as a second `--video`. Only chain when clip A's face already held; a leaked face in the tail gets cemented.

## G. In-scene picture plus a motion dummy (when a close-up video stole the face)

`<Picture 1>` is a still of the *target* person already in this shot and camera, made without the motion video (an image edit or a new generation). `<Picture 2>` is a plain face close-up. `<Video 1>` donates kinematics only. Run with `--ref-size max`, and consider `--video-width`/`--video-height` around 512–640 on the short edge to weaken the clip's face.

```text
subject_definitions:
<Subject 1> is the person already shown in this shot in <Picture 1>. Facial identity is tied to <Picture 2> and must match <Picture 1>. Never the performer from <Video 1>.
<Subject 2> is a motion dummy from <Video 1> only. Zero identity. Discard dummy face, hair, and wardrobe.
<Picture 1> is the in-scene reference for <Subject 1>.
<Picture 2> is the face-identity sheet only.
<Video 1> is motion and camera only.
<Audio 1> is the soundtrack of <Video 1>.

summary:
[reference generation + audio reuse] The target video shows <Subject 1> as in <Picture 1>, moving with <Video 1>. Face follows <Picture 1> and <Picture 2>. Dummy identity is discarded.

retention_analysis:
<Subject 1>: fully_preserved - look of <Picture 1>, face locked to <Picture 2>. Pictures beat <Video 1>.
<Subject 2>: attribute_transfer - kinematics and camera only.
<Picture 1>: fully_preserved - in-scene identity, pose, wardrobe, angle.
<Picture 2>: fully_preserved - face only. Wins if <Picture 1> and <Video 1> fight.
<Video 1>: attribute_transfer - timing and camera. Do not copy dummy identity.
<Audio 1>: fully_copy - complete final track.

detailed_description:
Live-action, same camera as <Picture 1>. Only <Subject 1> is visible.
[Shot 1] Same body as <Picture 1>. Follow <Video 1> / <Subject 2> for the opening phrase. Face stays <Picture 1> / <Picture 2>.
At 00:05.000, [Shot 2] follow <Video 1> for the next phrase. No dummy face.

overall_soundscape:
The track from <Audio 1> plays unchanged.

non_diegetic_music:
N/A
```

That prompt copies the soundtrack, so run it with `--video-audio both`. Don't add a frame grabbed from the dummy clip as another picture, and if the in-scene still already shows the dummy's face, don't use it.
