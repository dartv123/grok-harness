# Writing a Qwen-Image-Edit prompt

Qwen-Image-Edit is an **instruction-based editor**. Its text encoder is a real vision-language model (Qwen2.5-VL) that reads your instruction and the reference images together, so write the prompt the way you'd brief a photo retoucher: plain sentences describing the change. Not tags, and not a whole-scene description.

**Prompt weights like `(word:1.2)` are ignored.** Keep prompts short: most good edit prompts are one to a few sentences.

## Core rules

1. **Say what changes and what stays.** "Make it better" fails; "Warm the lighting to a late-afternoon sunset and keep the people unchanged" works. Untouched parts are preserved by default, so don't re-describe them.
2. **Name every image by number** when there are several: "The woman from image 1 wears the black dress from image 2 and sits in the pose from image 3." Image 1 is the first `--ref`.
3. **For people, name the invariants:** "keep her face, hairstyle and expression." Keep expression, makeup or beauty changes subtle; big dramatic changes break identity.
4. **Describe observable properties, not judgments:** materials, light direction, texture, color temperature. The model has no notion of "better".
5. **Placement words work:** left, right, center, foreground, background, and explicit framing.
6. **Quote literal text** in double quotes, in its original language and casing: `Replace "CAFE" with "BAKERY" in the same brown cursive font.`
7. **Fill in vague requests with concrete, minimal detail:** "add an animal" → "Add a light-gray cat sitting in the bottom-right corner, facing the camera."
8. **No camera or render jargon for edits** (bokeh, 85mm, octane). That's text-to-image vocabulary.

## Assert presence, don't forbid absence

Negations are weak and push results toward smooth, airbrushed renders. Describe what *should* be there.

| Weak | Strong |
|---|---|
| keep her face unchanged | her face and skin as in image 1: freckles across the nose and cheeks, visible pores, uneven tone |
| dimmed studio lighting | dim indoor light from the left, warm color temperature, deep shadow on the right |
| film grain effect | film grain, slight noise in the shadows |

- **Avoid piles of constraint clauses** ("must remain 100% unchanged", "exactly as shown", "zero visible…"). They make the render stiff and plastic. Fewer, denser descriptive words win.
- **"Studio lighting" is the plastic-lighting recipe.** Name a light source and a direction instead.

## Task types

Identify the type first, then apply its pattern.

| Type | Pattern | Example |
|---|---|---|
| Add / remove / replace | Name the object, position and key attributes. Replace = "Replace Y with X" plus what X looks like | "Replace the man's blue denim jacket with a black leather bomber jacket; keep his pose and the background unchanged." |
| Text | Quote old and new text; say whether the font is kept | "Replace '2024' with '2025' on the banner, keeping the same white bold font." |
| Person / identity | Change one thing, protect the rest | "Change the woman's hairstyle to a shoulder-length wavy bob; keep her face, expression, outfit and the background unchanged." |
| Pose | Describe the target pose plainly | "Change the man's pose so his right arm is raised in a wave; keep his face, outfit and the background unchanged." |
| Style | Name the style with a few concrete traits | "Convert this photo to a watercolor painting: soft edges, visible brush texture, muted pastel palette, light paper grain." |
| Restoration | Fixed phrasing works best | "Restore and colorize the photo." plus specific fixes |
| Inpaint / outpaint | Describe the region and what fills it; say the rest is unchanged | "Extend the image to the right, continuing the beach and horizon at the same height and lighting." |
| Multi-image | Source of every element by number, and what to keep from which | "Place the woman from image 1 on the left and the man from image 2 on the right, standing on the beach shown in image 2; match image 2's lighting." |
| Pose or structure map | Pass a depth, edge or keypoint map as one of the images | "Apply the pose from the keypoint map (image 2) to the person in image 1; keep their face, hair and clothing unchanged." |
| View rotation | Degree and direction | "Rotate the object 180° to show its back view, keeping the same lighting and materials." |
| Product poster | Positioning plus target background | "Turn this plain product photo into a poster with a soft gradient background and a subtle drop shadow; keep the product unchanged." |

## Text-to-image (no `--ref`)

Without reference images, the tool samples from an empty latent at `--aspect` and `--megapixels`. Then a normal descriptive prompt is fine: subject, setting, light and style, in plain sentences.

## Iterating

For ambitious or multi-part edits, run a short chain: do the structural change first, check it, then pass that result's `path:` as the next `--ref` for detail fixes. **Each step is a paid submission,** so chain only when the user asks, and say how many steps you plan.

## Checklist before running

- Task type identified?
- The target object, region, text or person named precisely?
- Vague words replaced with concrete detail?
- What must stay the same protected, described positively?
- Literal text in double quotes?
- Every element tied to an image number (multi-image)?
- No contradictions, and as short as it can be?

## When a result looks wrong

| Symptom | Fix |
|---|---|
| Face or identity drifts on an unrelated edit | Add a positive preservation clause for the face, hair and expression |
| The whole image changed instead of one region | Rewrite as a targeted instruction naming only that object or region |
| Garbled text or the wrong language | Quote the exact string; ask for translation explicitly if wanted |
| The wrong element edited (multi-image) | Name the image number for every element |
| Exaggerated makeup or expression | Ask for a subtle, natural version |
| Only part of a complex edit applied | Split it into a chain of edits |
| Plastic, waxy or CGI-looking skin and materials | Check the result line says `latent image`, not `empty`; rewrite constraint-heavy prompts in observational voice; name a light direction instead of "studio lighting" |
| Wrong-looking image that isn't your source | `--latent empty` was used with references; drop it so the output inherits image 1's size |
