# FL2VA failure modes

When the user says a clip looks wrong, match it against this list before rewriting the whole prompt. Don't resubmit on your own; suggest the fix and let the user decide.

## Teleport / snap to last frame

**Cause:** No intermediate actions. The body said "then she is in the Picture 2 pose."

**Fix:** Write 3–6 observable steps between the two stills. Hands, object states, weight shifts, fabric. End with "differences narrow" / "settles into."

## Cross-dissolve / smear morph

**Cause:** The two frames do not share a physical path — different room, lens, person, or lighting. Or the prompt described two scenes instead of one action.

**Fix:** Rebuild Picture 2 from Picture 1. If the user insists on unrelated frames, say FL2VA is the wrong tool and point them at the `minimax-ref2v` skill or two separate i2va clips.

## Last frame never arrives

**Cause:** Alignment `Shot N` / `S.SS` does not match the graph. Or the body wandered into a new composition and never named the landing.

**Fix:** Check `--first` and `--last` aren't swapped. Put Picture 2 on the final shot in the alignment line. End the last sentence on "composition established by Picture 2 at the S.SS-second mark."

## Identity / wardrobe drift

**Cause:** The path sentences introduced a new outfit, hair, or body. Or the two photos already disagree.

**Fix:** Carry the same anchors into every motion sentence ("the same cream knit sweater", "the same closed black umbrella"). Do not restyle mid-shot.

## Hands / object mush

**Cause:** Too many manipulations for the duration, or the object changes identity (phone becomes a glass).

**Fix:** One object job. Name the grip and the state change ("presses the runner upward until the canopy opens"). Drop extra props.

## Camera wrecks the landing

**Cause:** Large fast move plus a pose change. Or a cut when they needed a push-in.

**Fix:** Static, or one `small amplitude` / `slow speed` move. Never two camera verbs in one shot.

## Action finishes at 2 s, then idles

**Cause:** Under-specified middle on a long clip. H3 burns the action early.

**Fix:** Pace the intermediates across the duration ("through the middle of the shot", "toward the end"). Match action count to seconds — one clear transformation per 5–8 s.

## Talking-head mush / wrong language

**Cause:** Long dialogue, missing `(S1)`, or rewritten lines inside `<d>`.

**Fix:** 2–3 words per second. Voice traits outside the tag. Exact user words inside. Off-screen VO must lock the mouth closed.

## Silence when they wanted audio, or score leaking into the room

**Cause:** Empty / missing sound fields, or diegetic source dumped into `non_diegetic_music`.

**Fix:** Always fill `overall_soundscape` from the action. Radio / singing / phone = body field. Audience-only score = `non_diegetic_music`. True mute = `N/A` in both only if requested.

## Prompt looks right, result is wrong

**Cause:** `--first` and `--last` swapped, or a `--ckpt` that isn't an FL2VA-capable model.

**Fix:** Those are setup problems. Don't "prompt harder" until the frames and model are right. The tool already checks that `S.SS` matches `--duration`.
