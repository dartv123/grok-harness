# Writing a Grok Imagine image prompt

## Rules for every prompt

1. **Natural language, not tag soup.** Write 30–80 words in plain, flowing sentences. No comma-separated keyword lists (`8k, masterpiece, ultra-detailed, trending on artstation`) and no keyword negative lists (`no blur, no extra fingers`); Grok ignores or mishandles both. (A plain sentence that rules out extras in a composite is different; see below.)
2. **Front-load the subject.** The first 15–20 words carry the most weight. Open with the shot type, the main subject and what it's doing.
3. **One subject, one intent.** Keep one clear focal subject per image, and one focused intent per prompt. Complex changes work better as a sequence of edits than as one overloaded instruction.
4. **Director and camera vocabulary.** Use real photography terms (lens focal length, lighting direction, film stock, framing) instead of vague mood adjectives.

## Text to image: the order

1. **Shot type and subject:** framing, who or what is in the shot, and 1–2 concrete visual traits.
2. **Action and setting:** what they're doing and the specific physical place.
3. **Lighting and atmosphere:** light source, direction, time of day, weather or texture, mood.
4. **Camera and style:** lens (`35mm`, `85mm`, `macro`), depth of field, and medium (`editorial film photography`, `3D isometric render`, `cel-shaded anime`).

> Medium close-up portrait of an elderly watchmaker with silver-rimmed glasses leaning over a wooden workbench, carefully inspecting tiny brass gears with tweezers. Warm afternoon sunlight streams through a dusty workshop window, casting crisp shadows across scattered tools. Shot on 85mm lens, shallow depth of field, Kodak Portra 400 film grain, natural editorial photography.

## Editing one image (`--ref`)

**The model keeps everything you don't mention.** So:

- **State the single change, and only that.** "Change the sky to a sunset orange." Don't re-describe the whole scene; restating it invites drift.
- **Name what to keep** when the edit is subtle or drift has been a problem: "Keep her pose and expression unchanged; only change the background to a snowy street."
- **Style transfer is one aesthetic per edit:** "Render this as a pencil sketch with detailed shading." Stacking several styles in one prompt is unpredictable.

With `--aspect auto`, the result keeps the reference's shape.

## Compositing several images (up to 3 `--ref`)

Combine subjects, move a style from one image to another, or build a new scene from up to three references in one job.

- **Order matters.** The first `--ref` is image 1, and so on. Refer to them that way ("the woman from image 1 wearing the jacket from image 2"). With `--aspect auto`, the output takes the **first** image's shape.
- **Describe the final composition explicitly:** who is where, doing what, and the overall light and mood.
- **Rule out extras in a plain sentence.** Merges drift toward inventing people and objects. End with a constraint like "No additional people or animals." This is a sentence describing the scene, not a keyword negative list.
- **Say what must stay the same from each source** when identity or a style has to survive.

```text
Show the woman from image 1 and the dog from image 2 sitting together on the grass in a sunny park. Casual, relaxed mood, natural daylight, warm tones. No additional people or animals.
```

## Iterating in steps

For a progressive change (base scene, then swap the furniture, then adjust the light), run one edit per step and pass the previous result's `path:` as the next `--ref`. One deliberate change per step is more reliable than one giant prompt.

**Every step is a paid submission.** Only chain steps when the user asks for them, and say how many you plan before starting.

## Quick checklist

| Goal | Do | Avoid |
|---|---|---|
| New image | Subject → action → setting → light → camera and style | Adjective soup, keyword lists |
| Single change | Name the exact change only | Re-describing the whole image |
| Subtle edit | Name what to keep | Assuming it will be preserved |
| Composite | Describe the final scene and end with "No additional …" | Leaving the composition open |
| Style transfer | One aesthetic per edit | Several styles at once |
| Complex sequence | One change per step, previous output as `--ref` | One overloaded prompt |

## When the user only wants prompt ideas

If the user asks for prompts rather than images, offer 3 distinct variations (for example cinematic realism, stylized or editorial, and dynamic action), ready to paste. Don't generate them unless asked; each generation costs credits.
