---
name: qwen-image-edit-2509-prompting
description: Reference guide for writing, rewriting, and evaluating edit instructions for Qwen-Image-Edit-2509 (Qwen/Qwen-Image-Edit-2509, "Qwen-Image-Edit-Plus"). Use this whenever a user asks to generate, improve, or debug a prompt for that model — single-image edits, multi-image composition (1-3 images), text editing, identity-preserving portrait edits, style transfer, inpainting/outpainting, or ControlNet-guided (pose/depth/edge) edits. Also useful as the system prompt for an LLM whose job is to turn a rough user request into a production-ready Qwen-Image-Edit-2509 instruction.
---

# Qwen-Image-Edit-2509 Prompting Guide

A working reference for any LLM (or human) that needs to write high-quality edit
instructions for **Qwen-Image-Edit-2509**, released 2025-09-22 by the Qwen team as
the September monthly iteration of Qwen-Image-Edit. In the `diffusers` library it is
loaded via `QwenImageEditPlusPipeline` and is often referred to informally as
"Qwen-Image-Edit-Plus."

---

## 1. What the model is and why prompting it is different

Qwen-Image-Edit-2509 is an **instruction-based image editor**, not a text-to-image
model with a mask tool. You don't describe the whole scene — you describe the
*change*. Internally it reads the input image(s) two ways at once:

- **Qwen2.5-VL (a real vision-language model)** parses the instruction and the
  image semantically — this is why it behaves less like classic CLIP-conditioned
  diffusion and more like "an LLM that also edits pixels." Natural, conversational
  instructions work; you are not limited to keyword-soup prompting.
- **A VAE encoder** preserves low-level visual appearance (texture, exact pixels,
  layout) so untouched regions of the image stay stable across the edit.

Practical consequence: **write edit instructions the way you'd brief a photo
retoucher, not the way you'd write a text-to-image prompt.** State what changes,
what must stay the same, and any specifics (color, position, wording) — don't
re-describe the entire image from scratch unless you're deliberately replacing
the whole scene.

---

## 2. What's specific to the 2509 release

Compared to the original August 2025 Qwen-Image-Edit, 2509 adds:

| Area | Improvement |
|---|---|
| **Multi-image input** | Native support for 1–3 input images in one call, trained via image concatenation. Supports combos like person+person, person+product, person+scene. Quality degrades if you push past 3 images. |
| **Person/identity consistency** | Much better preservation of facial identity across pose changes, portrait-style transfers, and old-photo restoration. |
| **Product consistency** | Preserves product identity through poster-style edits (e.g., turning a plain product photo into a styled ad). |
| **Text consistency** | Beyond changing text content, it can now edit font, color, and material of existing text while keeping the rest of the design intact. |
| **Native ControlNet conditioning** | Accepts depth maps, edge maps, and keypoint/pose maps as one of the input images to drive structural edits (e.g., "apply this pose to this person"). |

If you only need single-image, single-concept edits, most of this guide still
applies — just skip the multi-image sections.

---

## 3. Core prompting principles

1. **Be direct and specific, not descriptive-of-everything.** Name the target
   object/region, the action (add / remove / replace / recolor / restyle /
   move / rotate), and the desired result. Don't restate unrelated parts of the
   image — the model already sees them and will preserve them by default.
2. **State what must stay unchanged when it's ambiguous.** "Keep the background,
   pose, and lighting the same" prevents unwanted drift, especially on portraits.
3. **One instruction, one clear intent per sentence.** For a complex edit,
   either write one instruction with clearly separated clauses, or split it into
   a short chain of sequential edits (2509 supports iterative/chained editing —
   fix one thing, then feed the output back in as the next input).
4. **Quote exact text.** Anything that must render as literal text in the image
   goes in double quotes, in the language you want it to appear in. Don't
   translate quoted text unless you explicitly ask for a translation.
5. **Fill in vague requests with concrete, minimal detail** rather than leaving
   them ambiguous — vague instructions get inconsistent results. "Add an animal"
   → "Add a light-gray cat sitting in the bottom-right corner, facing the camera."
6. **Avoid negations as the whole instruction.** "Remove all the trees" works;
   phrasing an edit purely around what should *not* happen ("don't add trees")
   is weaker guidance than a positive instruction.
7. **For multi-image inputs, always say which image you mean.** Refer to
   "the person in image 1," "the background from image 2," etc. — never leave
   the model to guess which source an element comes from.
8. **Don't over-specify camera/render jargon for edits.** That vocabulary
   (bokeh, 85mm, octane render...) is for text-to-image generation prompts.
   For edits, plain descriptive language about the change lands better.

---

## 4. Task taxonomy

Every edit instruction fits (at least) one of these categories. Identify the
category first, then apply its specific rules. This taxonomy mirrors how the
Qwen team's own prompt-enhancement tooling classifies edit requests.

### 4.1 Add / Remove / Replace
- Clear version: name the object, its position, and key attributes (color,
  size, orientation) if not obvious from context.
- Replace = "Replace **Y** with **X**" + a short description of X's key visual
  features, so the model knows what to render, not just what to delete.
- Drop instructions that resolve to a no-op (e.g., "add zero objects").

> *Vague:* "Add an animal"
> *Better:* "Add a light-gray cat, sitting and facing the camera, in the
> bottom-right corner of the image."

### 4.2 Text editing
- Wrap literal text in double quotes; preserve original language and casing.
- Both "add new text" and "change existing text" are the same operation —
  phrase as "Replace '\<old>' with '\<new>'" (or "Replace the sign with the
  text '\<new>'" if there's no prior text).
- Only specify position/color/font/material if it matters — 2509 can carry
  these over automatically, but stating them explicitly gets more reliable
  results, especially when changing font, color, or material independent of
  content.

> "Change the text on the storefront sign from 'CAFE' to 'BAKERY', keep the
> same brown cursive font."
> "Replace 'SALE' with 'SOLD OUT' in the same bold red lettering."

### 4.3 Human / identity editing
- Explicitly protect identity: mention ethnicity/age impression, hairstyle,
  expression, and outfit that should carry over if you're only changing one
  thing.
- Keep expression, beauty, or makeup changes **subtle** — instructing large
  exaggerated changes tends to break consistency; ask for natural, restrained
  adjustments.
- Pose/angle changes: describe the target pose or viewing angle plainly
  ("turn to a three-quarter side profile," "raise the left arm") and state
  that identity should be preserved.

> *Vague:* "Change the person's hat"
> *Better:* "Replace the man's hat with a dark brown beret; keep his smile,
> short hair, and gray jacket unchanged."

### 4.4 Style transfer / conversion
- Name the style concretely with a few defining visual traits rather than a
  single adjective. "1970s disco style: flashing colored lights, mirror ball,
  mirrored walls" beats "disco style."
- If you're using a second image purely as a style reference, describe its
  color palette / brushwork / composition and say explicitly that only the
  *style* should transfer, not the reference image's content.
- **Photo colorization / restoration is its own fixed pattern** — for old or
  black-and-white photo restoration, the simplest and most reliable phrasing
  is just: "Restore and colorize the photo," optionally plus specific fixes
  ("remove the scratches and creases, keep the people's faces unchanged").

> "Convert this photo to a watercolor painting: soft edges, visible brush
> texture, muted pastel palette, light paper-grain background."

### 4.5 Inpainting / outpainting (region fill and canvas extension)
- Inpainting (regenerate a masked/described region only): describe the region
  and what should appear there, and state that the rest of the image is
  unchanged — e.g., "Fill in the torn area on the left side of the photo with
  matching wall texture and lighting; leave everything else unchanged."
- Outpainting (extend the canvas): describe what the extended area should
  logically contain, consistent with the existing scene — e.g., "Extend the
  image to the right, continuing the beach and horizon line at the same
  height and lighting."

### 4.6 Multi-image composition (2509's headline feature)
- Always name the source image per element: "the woman from image 1," "the
  product from image 2," "the background from image 3."
- Common combos: person + person (put two people together in one scene),
  person + product (person holding/using a product), person + scene
  (composite a subject into a new background).
- State what to keep from which image (e.g., "keep image 2's lighting and
  background, keep image 1's subject and pose").
- Cap it at 1–3 input images — quality is optimized for that range.

> "Place the woman from image 1 on the left and the man from image 2 on the
> right, both facing each other in the park square shown in image 2. Match
> image 2's lighting."

### 4.7 Pose / structure control via ControlNet-style inputs (native in 2509)
- Provide the condition image (depth map, edge/canny map, or keypoint/pose
  map) as one of the multi-image inputs, and reference it directly: "Apply
  the pose shown in the keypoint map to the person in image 1, keep their
  face, hair, and outfit unchanged."
- Works well for pose transfer, silhouette-preserving redesigns, and
  sketch-to-render tasks (describe the target rendering style on top of the
  sketch/edge input).

### 4.8 Novel view synthesis (rotation)
- 2509 can rotate a subject 90° or a full 180° to show the back/side.
  State the degree and axis plainly: "Rotate the object 180° to show the
  back view," or "Show this character from a three-quarter left angle."
- Particularly useful for product shots and character-design turnarounds
  from a single reference image.

---

## 5. Step-by-step process for writing a prompt

1. **Classify the request** into one (or more, for compound edits) of the
   categories in Section 4.
2. **Identify the anchor(s)** — the exact object/region/text/person being
   changed. If there's any chance of ambiguity (multiple people, multiple
   images, multiple text blocks), name it precisely.
3. **State the target outcome concretely.** Replace vague adjectives with
   specific, renderable detail (a color, a material, a pose, an exact string
   of text).
4. **Add a preservation clause** for anything that commonly drifts: identity,
   background, lighting, pose, or existing text not being edited — especially
   for portraits and product shots.
5. **Resolve contradictions before submitting.** If an instruction is
   self-contradictory ("remove all the trees but keep the trees"), fix the
   logic rather than passing it through.
6. **For multi-step or ambitious edits, prefer a short chain over one giant
   instruction.** Do the structural change first, verify, then run a second
   pass for detail correction (2509 handles iterative correction well — the
   Qwen team's own demos use this for fixing text/calligraphy errors).
7. **Keep it as short as it can be while staying unambiguous.** These are
   instructions, not scene descriptions — most effective edit prompts run one
   to a few sentences. Long, generic scene-setting text dilutes the specific
   instruction the model needs to act on.

---

## 6. Drop-in rewriting system prompt

If you're building a pipeline where an LLM turns a rough user request into a
polished Qwen-Image-Edit-2509 instruction, this system prompt operationalizes
Sections 3–5 above. Adapt the output field name to whatever your pipeline
expects.

```
You are an edit-prompt writer for Qwen-Image-Edit-2509, an instruction-based
image editing model. Given a user's rough request (and, when available, a
description of the input image(s)), produce ONE direct, specific edit
instruction.

Rules:
- Classify the request as one of: add/remove/replace, text edit, human/identity
  edit, style transfer/restoration, inpaint/outpaint, multi-image composition,
  pose/ControlNet-guided edit, or view rotation — and apply that category's
  conventions.
- If the request is vague, fill in the minimum concrete detail needed
  (color, size, position, orientation) without changing its intent.
- Wrap any literal text to render in the image in double quotes, in its
  original language and casing.
- For edits to people, name what must stay the same (identity, hairstyle,
  expression, outfit) unless that is the thing being changed. Keep expression/
  makeup changes subtle, never exaggerated.
- For multi-image input, name which numbered image each element comes from,
  and state what to keep from which image.
- For colorization/restoration of an old photo, default to: "Restore and
  colorize the photo." plus any specific fixes requested.
- For inpainting, frame it as filling a described region while leaving the
  rest unchanged. For outpainting, frame it as extending the canvas
  consistently with the existing scene.
- Resolve any contradictions in the request logically before writing the
  final instruction.
- Do not add unrelated scene description. Do not use text-to-image camera/
  render jargon. Do not add extra commentary — output only the instruction.

Output only the rewritten edit instruction.
```

---

## 7. Worked examples

| Category | Rough request | Production-ready prompt |
|---|---|---|
| Add/Remove | "put a plant somewhere" | "Add a medium potted monstera plant in the bottom-left corner of the room, next to the sofa." |
| Replace | "different jacket" | "Replace the man's blue denim jacket with a black leather bomber jacket; keep his pose and the background unchanged." |
| Text edit | "fix the date" | "Replace '2024' with '2025' on the banner, keeping the same white bold font." |
| Text style | "make the logo text look metallic" | "Change the material of the text 'NOVA' on the logo to a brushed chrome metallic finish, keep its position and size unchanged." |
| Identity/portrait | "give her a different hairstyle" | "Change the woman's hairstyle to a shoulder-length wavy bob; keep her face, expression, outfit, and the background unchanged." |
| Pose change | "make him wave" | "Change the man's pose so his right arm is raised in a wave; keep his face, outfit, and the background unchanged." |
| Style transfer | "make it a painting" | "Convert this photo to an impressionist oil painting: visible brushstrokes, soft edges, warm painterly color palette." |
| Restoration | "fix this old photo" | "Restore and colorize the photo." |
| Inpainting | "remove the tourist in the back" | "Remove the person standing in the background near the fountain; fill the area with the matching plaza pavement and sky, leaving the rest of the image unchanged." |
| Outpainting | "make it wider" | "Extend the image to the left, continuing the mountain range and cloud pattern at the same height and lighting." |
| Multi-image | "put these two people together" | "Place the woman from image 1 on the left and the man from image 2 on the right, standing together on the beach shown in image 2; match image 2's lighting and keep both people's faces and outfits unchanged." |
| ControlNet pose | "match this pose" | "Apply the pose from the keypoint map (image 2) to the person in image 1; keep their face, hair, and clothing unchanged." |
| View rotation | "show the back" | "Rotate the object 180° to show its back view, keeping the same lighting and materials." |
| Product poster | "turn this into an ad" | "Turn this plain product photo into a styled poster: add a soft gradient studio background and subtle drop shadow, keep the product itself unchanged." |

---

## 8. Technical parameters (for pipeline/API calls, not the prompt text itself)

Defaults from the official `diffusers` usage example
(`QwenImageEditPlusPipeline`):

| Parameter | Typical value | Notes |
|---|---|---|
| `num_inference_steps` | 40 | 20-30 for quick previews, 40-50 for final quality. |
| `true_cfg_scale` | 4.0 | Higher = follows the instruction more literally; too high can introduce artifacts. |
| `guidance_scale` | 1.0 | Distinct from `true_cfg_scale`; leave at the default unless you know you need to change it. |
| `negative_prompt` | `" "` (a single space) | The reference pipeline leaves this essentially empty; only add negative terms if you're seeing a specific recurring artifact. |
| Input images | 1–3 | 2509 is trained and tuned for this range; quality degrades beyond 3. |
| `num_images_per_prompt` | 1 | Increase to get multiple candidate outputs per call. |

If you're calling a hosted API (e.g., fal.ai's `qwen-image-edit-2509`/`-2511`
endpoints) rather than running `diffusers` locally, the same prompt-writing
guidance applies — only the parameter names/defaults on the wrapper may
differ slightly, so check that provider's docs for its exact schema.

---

## 9. Common failure modes and fixes

| Symptom | Likely cause | Fix |
|---|---|---|
| Face/identity drifts on an unrelated edit | No preservation clause | Add "keep face/identity/hairstyle unchanged" explicitly. |
| Whole image changes when you wanted one region | Instruction is too scene-level / phrased like a generation prompt | Rewrite as a targeted instruction naming the specific object/region only. |
| Text renders garbled or wrong language | Text wasn't quoted, or model was asked to "translate" implicitly | Quote the exact target string; state explicitly if translation is wanted. |
| Wrong element edited in a multi-image call | Source image not specified | Name the image number for every referenced element. |
| Edit is technically applied but result looks exaggerated (makeup, expression) | Instruction implied a large/dramatic change | Ask for a subtle/natural version explicitly. |
| Model "resolves" a self-contradictory instruction unpredictably | Logical conflict in the prompt | Fix the contradiction before sending it. |
| Complex multi-part edit only partially applied | Too many simultaneous asks in one instruction | Split into a short chain of edits, verifying between steps. |

---

## 10. Quick checklist before sending a prompt

- [ ] Category identified (Section 4)?
- [ ] Target object/region/text/person named precisely?
- [ ] Vague terms replaced with concrete detail?
- [ ] Anything that should stay the same explicitly protected?
- [ ] Literal text in double quotes, correct language/casing?
- [ ] Multi-image references tied to a specific image number?
- [ ] No self-contradictions?
- [ ] Prompt is as short as possible while staying unambiguous?

---

### Sources
Qwen team's official Qwen-Image-Edit-2509 release notes and README
(`QwenLM/Qwen-Image` on GitHub and the `Qwen/Qwen-Image-Edit-2509` model card
on Hugging Face), the Qwen-Image technical report, the Qwen team's own
edit-prompt-enhancement tooling (`prompt_utils.py` in that repo), and current
third-party developer guides (fal.ai, imagebyqwen.com) — synthesized and
reorganized here rather than reproduced verbatim. Model behavior and
recommended parameters can shift with future point releases (2511, 2512,
etc.); re-check the official repo/model card if something in this guide stops
matching observed behavior.
