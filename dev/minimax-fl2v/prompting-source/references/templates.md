# FL2VA fill-in templates

Substitute duration, shot index, style, and the actual path. Keep field names and the blank line after the alignment sentence.

## A. Default — single shot, no dialogue, no score

Use this unless they asked for cuts, speech, or music.

```text
How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot 1) aligns with the S.SS-second mark of the target video.

integrated_multimodal_description: [Shot 1] Live-action, cinematic, <subject> begins in the position and framing established by Picture 1, <start pose / prop state>. The camera holds a static shot as <ordered intermediate actions>. Toward the end of the shot the differences narrow until <end pose / prop state>, landing on the exact pose, spacing, and composition established by Picture 2 at the S.SS-second mark.

overall_soundscape: <room tone>. <one or two action sounds that match the intermediate moves>.

non_diegetic_music: N/A
```

## B. Single shot with a small camera move

```text
How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot 1) aligns with the S.SS-second mark of the target video.

integrated_multimodal_description: [Shot 1] Live-action, cinematic, <subject> begins in the position and framing established by Picture 1, <start state>. The camera pushes in with small amplitude at slow speed as <ordered intermediate actions>. Fabric / objects / light respond in sequence. The motion settles into the pose, spacing, and composition established by Picture 2 at the end of the shot.

overall_soundscape: <ambience>. <synced action sounds>.

non_diegetic_music: N/A
```

## C. Single shot with one spoken line

Keep the line short. Voice traits outside `<d>`.

```text
How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot 1) aligns with the S.SS-second mark of the target video.

integrated_multimodal_description: [Shot 1] Live-action, cinematic, the woman shown in Picture 1 begins in that exact seat, wardrobe, and framing. The camera holds a static shot as she <action>. The woman with a <pitch / timbre / rate> voice (S1) says: <d>[English] <exact line>.</d> She finishes the motion and settles into the pose, spacing, and composition established by Picture 2 at the S.SS-second mark.

overall_soundscape: <room tone and action sounds. No dialogue repeat.>

non_diegetic_music: N/A
```

## D. Two shots — only when they asked for a cut

Picture 2 must belong to the final shot. Cut time inside the duration, three decimals after the seconds in `At 00:03.500`.

```text
How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot 2) aligns with the S.SS-second mark of the target video.

integrated_multimodal_description: [Shot 1] Live-action, cinematic, <opening from Picture 1, matching position, framing, and lighting>. The camera holds a static shot as <first-half action>. [Shot 2] At 00:0X.000, the shot cuts to <new viewpoint of the same scene>. The remaining action completes and lands on the exact pose, spacing, and composition established by Picture 2 at the S.SS-second mark.

overall_soundscape: <ambience across both shots>. <action sounds for each beat>.

non_diegetic_music: N/A
```

If a spoken line crosses the cut, split it with `<scenetrans>` and say the audio continues seamlessly across the cut.

## E. Score instead of silence

```text
non_diegetic_music: Sparse piano notes at a slow tempo, joined by a quiet sustained pad that fades out at the end.
```

Describe instruments, tempo, rhythm, dynamics. No "emotional / cinematic / beautiful".

## F. Duration cheat sheet

Write `S.SS` to match the node, not a marketing number.

| Asked length | Alignment ending |
|---|---|
| 5 seconds | `5.00` |
| 6 seconds | `6.00` |
| 8 seconds | `8.00` |
| 10 seconds | `10.00` |
| 12 seconds | `12.00` |
| 15 seconds | `15.00` |

Local Comfy duration often snaps to the 17-frame block grid at 24 fps. If the user gives a frame count, convert — frames / 24 — then format to two decimals.

## G. I2VA / L2VA one-liners (only if mode changes)

I2VA first line:

```text
For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.
```

L2VA first line (Picture 1 here *is* the last frame):

```text
How the reference pictures align with the target video — <Picture 1> (from [Shot N]) aligns with the S.SS-second mark of the target video.
```
