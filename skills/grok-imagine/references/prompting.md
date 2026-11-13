# Writing a Grok Imagine image prompt

## Rules

1. **Natural language, not tag soup.** Write 30–80 words in plain, flowing sentences. No comma-separated keyword lists (`8k, masterpiece, ultra-detailed, trending on artstation`) and no negative phrasing (`no blur, no extra fingers`); Grok ignores or mishandles both.
2. **Front-load the subject.** The first 15–20 words carry the most weight. Open with the shot type, the main subject and what it's doing.
3. **One subject, one beat.** Keep one clear focal subject per image.
4. **Director and camera vocabulary.** Use real photography terms (lens focal length, lighting direction, film stock, framing) instead of vague mood adjectives.

## Order

Write every prompt in this order:

1. **Shot type and subject:** framing, who or what is in the shot, and 1–2 concrete visual traits.
2. **Action and setting:** what they're doing and the specific physical place.
3. **Lighting and atmosphere:** light source, direction, time of day, weather or texture.
4. **Camera and style:** lens (`35mm`, `85mm`, `macro`), depth of field, and medium (`editorial film photography`, `3D isometric render`, `cel-shaded anime`).

Example:

> Medium close-up portrait of an elderly watchmaker with silver-rimmed glasses leaning over a wooden workbench, carefully inspecting tiny brass gears with tweezers. Warm afternoon sunlight streams through a dusty workshop window, casting crisp shadows across scattered tools. Shot on 85mm lens, shallow depth of field, Kodak Portra 400 film grain, natural editorial photography.

## Editing with reference images

With `--ref`, the prompt describes the change, not the whole picture again. Name what to keep and what to change: "Keep her face, hair and pose from the image; replace the school uniform with a red winter coat and add light snowfall." With several references, say which image supplies what ("the woman from image 1 wearing the jacket from image 2").

## Aspect ratio

Pick the ratio for the content and pass it with `--aspect`: `9:16` or `2:3` for portraits and phone wallpapers, `16:9` for landscapes and scenes, `1:1` for icons and avatars. Leave it `auto` when editing and the result should keep the reference's shape.

## When the user only wants prompt ideas

If the user asks for prompts rather than images, offer 3 distinct variations (for example cinematic realism, stylized or editorial, and dynamic action), ready to paste. Don't generate them unless asked; each generation costs credits.
