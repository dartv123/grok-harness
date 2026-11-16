# Ref2VA fill-in templates

Keep the six field names and section order. Renumber labels to match the files actually wired.

## A. One still — identity only (most common local job)

Picture 1 is a character/product sheet, not a literal first frame.

```text
subject_definitions:
<Subject 1> is the woman whose face, hair, skin, and wardrobe come from <Picture 1>.
<Subject 2> is the second visible body / product / location also taken from <Picture 1> if needed.

summary:
[reference generation] The target video shows <Subject 1> performing <one action> while keeping the identity and wardrobe defined from <Picture 1>.

retention_analysis:
<Subject 1> (appears in [Shot 1]): fully_preserved - facial identity, hair, and wardrobe remain consistent.
<Subject 2> (appears in [Shot 1]): fully_preserved - listed traits remain consistent.

detailed_description:
The target video is live-action, handheld close-up, matching the lighting quality of <Picture 1>.
[Shot 1] <Subject 1> begins <start state>. The camera holds a static shot as <ordered actions>. <Subject 1> ends in <end state>.

overall_soundscape:
<room tone and action sounds>.

non_diegetic_music:
N/A
```

Do not add a standalone `<Picture 1>` line unless that still is a real frame anchor.

## B. Still as literal first frame plus identity

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

If they also need an exact last frame, that is usually FL2VA, not this template.

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

Priority line if they conflict: face wins over outfit, outfit wins over room, unless the user inverted it.

## D. Photo identity + video motion (do not copy the performer)

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

## E. Voice timbre vs exact track

Timbre only:

```text
<Audio 1> is the voice-timbre reference for <Subject 1> (S1).
```

```text
<Audio 1>: reference - follow timbre and delivery without copying the source signal.
```

Exact lipsync / karaoke / reused take:

```text
<Audio 1> is the complete soundtrack reused in the target video.
```

```text
summary:
[reference generation + audio reuse] ...

retention_analysis:
<Audio 1>: fully_copy - <Audio 1> is reused 1:1 as the target video's complete final audio track.
```

Then cite `<Audio 1>` inside the shot where the mouth has to match.

## F. Video edit / continue

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

Continuation uses `video continuation` and says the new clip resumes after the last frame of `<Video 1>`. Across separate executes this is a soft handoff (tail of clip A as Video 1, next dummy phrase as Video 2), not a warm latent. Only chain if clip A's face already held.

## G. In-scene still plus motion dummy (use when a close-up video stole the face)

Picture 1 is a generated or edited frame of the *target* person already in the shot. Picture 2 is the raw face plate. Video 1 is kinematics only.

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
<Subject 1>: fully_preserved - look of <Picture 1>, face locked to <Picture 2>. Stills beat <Video 1>.
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

Do not add a raw frame from the dummy clip as another Picture.
