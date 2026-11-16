# Ref2VA failure modes

## Wrong checkpoint

**Symptom:** Tags ignored, or the graph looks like first/last frame I2V.

**Fix:** `minimax_h3_ref2va_*` + `MiniMaxH3ReferenceToVideo`. FL2VA weights will not honor this six-section contract.

## Tag / slot mismatch

**Symptom:** Identity comes from the wrong photo.

**Fix:** `<Picture 1>` is whatever is wired to `ref_image_1`, in that order. Recount after adding a slot. Same for video and audio families.

## Two jobs, one file, no split

**Symptom:** Outfit bleeds into face, or the room restyles the person.

**Fix:** Separate subjects. State a priority. `fully_preserved` on the winner, `weak_reference` on the loser if needed.

## `fully_preserved` on a motion clip

**Symptom:** Source performer or location leaks into the new scene.

**Fix:** Motion clips are usually `attribute_transfer` or `weak_reference`. `fully_preserved` on `<Video N>` means "keep that video's structure," which is an edit job, not a motion donation.

## Video face beats standing identity stills

**Symptom:** The person in the motion clip wins. Beauty / standing plates lose.

**Cause:** A close face-filling video has more identity tokens than stills in a different pose.

**Fix:** Make an in-scene still of the target person in the target camera first, without the motion video. Wire it as Picture 1. Keep the face close-up as Picture 2. Extract a motion-dummy Subject from Video N with zero identity. `ref_image_size: max` on stills, downscale the video. See `video-refs.md`. Throw the still away if the dummy is already in it.

## Low-fps video used as keyframes

**Symptom:** Frozen poses, invented motion, lost cadence.

**Fix:** Load the performance at native 24-25 fps. Sparse frames are not Add Guide pins.

## Audio expected to drive the body

**Symptom:** Rhythm track or sex audio is copied, mouth and hips ignore it.

**Fix:** `fully_copy` locks the soundtrack only. Visual clock is Video N.

## Output longer than the video or audio file

**Symptom:** After the file ends, motion drifts and audio dies or gibbers.

**Fix:** Match duration to the file, `partially_copy` the tail, or loop the wav. H3 will not invent 10 faithful seconds from a 5 s pack.

## Promised pixel-perfect video copy

**Symptom:** Cuts and faces drift. User thought Ref2VA was an NLE.

**Fix:** Say it out loud — Ref2VA is semantic. For a literal first-to-last still path use FL2VA. For a true recut, use `video editing` + `fully_copy` audio and still expect drift.

## Audio-only input

**Symptom:** Node / API rejects, or voice appears on a random body.

**Fix:** Pair audio with an image or video. Bind `<Audio N>` to `<Subject N> (S1)` in definitions.

## Lips out of sync with a song

**Cause:** Retention said `reference` (timbre) instead of `fully_copy`.

**Fix:** `fully_copy` if the track must be the final audio. Cite `<Audio 1>` in the shot at the lyric.

## detailed_description is a plot paragraph

**Symptom:** Soft, generic motion. Labels never appear in the shots.

**Fix:** Style sentence, then `[Shot 1]`, then visible state changes. Insert each label at the frame it matters.

## Invented label

**Symptom:** Model chases `<Picture 4>` that was never wired.

**Fix:** Every label in summary / retention / body must exist in `subject_definitions` and on the graph.

## Too many refs

**Symptom:** Identity soup. Official cap is 9 / 3 / 3 / 12 mixed.

**Fix:** Drop files that do not have a sentence of work. Two clean refs beat seven vague ones.

## Hosted vs local

**Symptom:** A chatty brief works on Hailuo and dies in Comfy.

**Fix:** Local open weights need the six-section brick. Context-IR is not in the Comfy node.
