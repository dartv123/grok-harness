# Ref2VA failure modes

When the user says a clip looks wrong, match it against this list before rewriting the whole prompt. Suggest the fix and let the user decide; each rerun costs credits.

| Symptom | Cause | Fix |
|---|---|---|
| Tags ignored, or it behaves like first/last-frame video | A non-Ref2VA model via `--ckpt` (for example the FL2VA checkpoint) | Use the default model or one from the skill's Models list. For literal first and last frames, use `minimax-fl2v` |
| Identity comes from the wrong picture | Label and file order disagree | `<Picture N>` is the Nth `--ref`. Recount after adding or reordering files; same for `--video` |
| Outfit bleeds into the face, or the room restyles the person | Two jobs from one file with no split | Separate subjects, state a priority, `fully_preserved` on the winner, `weak_reference` on the loser |
| The source performer or location leaks in | `fully_preserved` on a motion clip | Motion clips are `attribute_transfer` or `weak_reference`. `fully_preserved` on `<Video N>` means "keep the clip's structure", which is an edit |
| The person from the video wins over the pictures | A close, face-filling clip carries more identity than stills in another pose | Template G: in-scene picture as `<Picture 1>`, face close-up as `<Picture 2>`, a motion-dummy subject, `--ref-size max`, and a downscaled video (`--video-width`/`--video-height`) |
| Frozen poses, invented motion, lost cadence | A sparse or low-fps clip used as keyframes | Pass a real-motion clip; leave `--video-fps` at 24 |
| The set and framing of the video leak in (walls, tripod) | A 16:9 performance teaching a portrait canvas, or the reverse | Ask the user for a clip cropped toward the output `--aspect` |
| Soundtrack copied but mouth and body ignore it | Audio was expected to drive motion | `fully_copy` locks the track only; the visual clock comes from `<Video N>` |
| Soundtrack wasn't copied at all | `fully_copy` in the prompt, but the tool's default `--video-audio ref` | Rerun with `--video-audio both` |
| Motion drifts and audio dies near the end | Output longer than the reference clip | Keep `--duration` at or below the clip length, or `partially_copy` the tail |
| Lips out of sync with a song | Retention said `reference` (timbre) instead of `fully_copy` | `fully_copy`, `--video-audio both`, and cite `<Audio 1>` in the shot at the lyric |
| Soft, generic motion; labels never appear in shots | `detailed_description` is a plot paragraph | A style sentence, then `[Shot 1]` with visible state changes, citing each label where it matters |
| The model chases a label that does nothing | A label used but never defined or passed | Every label in the summary, retention and body must be in `subject_definitions` and match a file. The tool refuses undefined `<Picture N>`/`<Video N>`/`<Audio N>` numbers |
| Identity soup | Too many references | The tool takes 5 pictures; two clean references beat five vague ones. Drop any file with no sentence of work |
| Loose identity or sloppy motion | Lightning (the fast 4-step pass) is on by default | Offer a rerun with `--no-lightning` and `--ref-size max` |
| User expected a pixel-exact copy of the video | Ref2VA is semantic, not a video editor | Say so up front. Cuts and faces will drift even with `video editing` and `fully_copy` |
