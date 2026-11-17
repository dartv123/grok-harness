---
name: qwen-image-edit-2511
description: Prompt and wire Qwen-Image-Edit-2509/2511 correctly — natural-language prompt patterns, multi-image referencing, negative-prompt rules, sampler presets, and the latent/resolution wiring that causes plastic, CGI-looking output.
globs:
  - "**/*.json"
---

# Qwen-Image-Edit 2511 — prompting and wiring

## Overview

Qwen-Image-Edit is a 20B MMDiT with a **Qwen2.5-VL-7B vision-language model as its
conditioning encoder**. Two control paths exist and they are not interchangeable:

| Path | Carries | Effect |
|---|---|---|
| **CONDITIONING** (via `TextEncodeQwenImageEditPlus`) | semantic instruction + reference-as-description | *steers* denoising |
| **LATENT** (`VAEEncode` / node output) | reference as pixels | *seeds* the sampler's starting state |

A reference image passed through the text-encoder node arrives as a **VLM description**,
not as pixels. This distinction is the source of most "why does it look plasticky" bugs.

Base model: `Qwen/Qwen-Image-Edit-2511` (Apache-2.0, 20,430,401,088 params BF16).
2511's stated improvements over 2509: mitigated image drift, better character
consistency, integrated LoRA capacity, industrial-design generation, geometric reasoning.

---

## The scale trap — read this first

**Symptom:** materials come back plastic / CGI, printed detail comes back as a generic
shape, the subject is re-synthesised rather than edited. **Nothing errors.** There is no
warning. The image simply is not the edit you asked for.

**Mechanism:** `TextEncodeQwenImageEdit` / `TextEncodeQwenImageEditPlus` do **not take a
size**. They scale every reference to a hard-coded `int(1024 * 1024)` px — **~1.05 MP, at
the source's own aspect ratio** — VAE-encode it, and hand the result to the model as a
reference latent (`comfy_extras/nodes_qwen.py`).

The model then lays reference tokens and output tokens on **one shared, centred
coordinate grid** (`comfy/ldm/qwen_image/model.py`, `process_img`). Reference position
(i, j) and output position (i, j) mean the same place **only when the two grids are the
same size**. When they differ, the model cannot copy detail across the gap and
re-synthesises the subject instead.

The official templates therefore run the source through `FluxKontextImageScale`, then
feed the sampler a `VAEEncode` of *that same scaled image*, so both branches see the same
pixels at the same ~1 MP scale and the same aspect. Every `PREFERRED_KONTEXT_RESOLUTIONS`
entry is ~1.05 MP for the same reason.

| Output latent | vs ~1.05 MP reference | Result |
|---|---|---|
| ~1.05 MP, same aspect | match | correct edit |
| 2 MP portrait | **1.24x linear** | re-synthesise; plastic materials |
| 1024x1024 over a square source | coincide | fine — pure luck |

### The two failing pairings

1. **`EmptyLatentImage` + edit conditioner, denoise < 1.0** — renders a flat,
   near-uniform field, *always*. The encoder emits CONDITIONING only, so the latent is
   genuinely empty, and a truncated sigma schedule exists to preserve an incoming latent
   that here has nothing in it.
2. **`EmptyLatentImage` + edit conditioner, denoise = 1.0** — renders a plausible image
   that is **not your source**, unless its width and height happen to equal the geometry
   the encoder derived. This is the trap: it depends on a source you may not have looked
   at, and it fails silently.

### Correct wiring

```
LoadImage ──► FluxKontextImageScale ──┬──► TextEncodeQwenImageEditPlus (image1..image3)
                                      └──► VAEEncode ──► KSampler.latent_image
```

**A `VAEEncode` removes the coincidence — it cannot be the wrong size, because it is
derived from the same pixels the encoder saw.**

`TextEncodeQwenImageEditPlusAdvance_lrzjason` (pack `qweneditutils`) emits the latent
directly on output [1], which eliminates the separate `EmptyLatentImage`/`VAEEncode`.

> **Rule of thumb: on an edit graph you do not choose the output size — you inherit it.**
> Resize the *result* afterwards, never the sampling geometry. The resolution tables
> published for Qwen-Image (1328x1328, 1104x1472, …) are for **text-to-image**. Picking
> one for an edit graph is the documented cause of the plastic-materials bug.

### Quick self-check on any Qwen edit graph

- [ ] Does `KSampler.latent_image` come from a `VAEEncode` (or an advanced encode node's
      latent output) rather than an `EmptyLatentImage`?
- [ ] Is `denoise` a deliberate choice, and if `< 1.0`, is the latent source-derived?
- [ ] Are reference images scaled once, upstream, and shared by **both** the conditioner
      and the latent branch?
- [ ] Resolution is inherited from the source, not typed in.

---

## Prompting

**Style: natural language. Prompt weights `(word:1.2)` are NOT honoured.**

The model behaves like a captioner-then-editor, not a keyword tagger. Length limits on
the hosted API are 800 tokens for most models (1,300 for the `qwen-image-2.0` series);
the system truncates silently past that.

### Core rules

1. **Say what changes AND what stays.** The single most-repeated instruction across
   vendors: *be specific about what should change and what should stay the same*.
   "Make it better" fails; "enhance the lighting and add warm sunset tones" works.
2. **Reference images by ordinal, explicitly.** In multi-image graphs you MUST state
   which element comes from which image, using the model's own convention:
   - `The girl from Image 1 is wearing the black dress from Image 2 and sitting in the
     pose from Image 3.`
   - `Change the furniture leather difference in image 1 to the fur material in image 2.`
     *(the official ComfyUI template's default prompt)*
   - `The magician bear is on the left, the alchemist bear is on the right, facing each
     other in the central park square.`
3. **For people, name the invariants.** `preserve the facial features`, `keep the same
   hairstyle and expression`.
4. **Describe observable properties, not evaluations.** Identity, materials, lighting
   direction, texture, colour temperature. The model has no notion of "better".
5. **Placement words are honoured.** left / right / centre / foreground / background,
   and explicit camera framing.
6. **For text editing**, say whether the font should be preserved or changed, and
   describe the target typography if changing.
7. **For products**, describe both the positioning and the target background/context.

### Prompt-writing technique: assert presence, don't forbid absence

Negation is weak even when negatives are active. `"do not expose any X"` mentions X
twice, creates an actively-suppressed feature, and pushes the render toward a normalised,
airbrushed result.

| Weak | Strong |
|---|---|
| `do not show the glans` | `the foreskin is drawn fully forward over the head` |
| `keep her face unchanged` | `her face and skin as in the first reference: freckling across the nose and cheeks, visible pores, uneven tone` |
| `dimmed studio lighting` | `dim indoor light from the left, warm colour temperature, deep shadow on the right` |
| `film grain effect` | `film grain, slight noise in the shadows` |

Two specific traps:

- **Repetitive imperative/constraint clauses** (`must remain 100% unchanged`, `exactly as
  shown`, `zero visible…`) bias the model toward stiff, over-normalised, plastic
  reconstruction. It spends capacity satisfying prohibitions instead of rendering
  material. Fewer, denser descriptive tokens beat many prohibitive ones.
- **`studio lighting` is the plastic-lighting recipe.** Studio light is smooth, even and
  shadowless. Specify a *source* and a *direction* (`light from the left, deep shadow on
  the right`) instead.

### Negative prompts — supported, but only when CFG is live

Qwen-Image **does** honour a real negative prompt; it is not Flux. But it needs
`cfg > 1` to do anything.

- **CFG 1.0 (Lightning/distilled):** the negative branch is inert. An empty negative
  string is correct and costs nothing.
- **CFG 2.5–4:** the negative becomes live. Populate it:
  `low resolution, error, worst quality, low quality, disfigured, extra fingers, bad proportions`
  plus task-specific terms (`smooth skin, airbrushed, plastic, waxy, cgi, 3d render, studio lighting`).
- Prefer `ConditioningZeroOut` when you genuinely want an empty negative.

---

## Sampler settings

| Variant | Steps | CFG | Sampler | Scheduler | Denoise | LoRA |
|---|---|---|---|---|---|---|
| **Stock 2511** | 20 (vendor ref) / 28–40 (hosted API) | 2.5–4.5 | euler | simple | 1.0 | none |
| **Lightning 4-step** | 4 | 1.0 | euler | simple | 1.0 | 2511-Lightning-4steps |
| **Lightning 8-step** | 8 | 1.0 | euler | simple | 1.0 | Lightning-8steps |
| Partial-denoise edit | 20–40 | 2.5–4 | euler | simple | 0.5–0.8 | none |

- The official ComfyUI 2511 template defaults to
  `Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors` and a randomising seed.
- `ModelSamplingAuraFlow` (shift ≈ 3.0–3.1) and `CFGNorm` (strength 1) appear in the
  official pipeline: `UNETLoader → [LoRA] → ModelSamplingAuraFlow → CFGNorm → MODEL`.
- **Sub-1.0 denoise rows REQUIRE a source-derived latent** (see the scale trap).

### ⚠ Distilled LoRAs are out-of-distribution outside their step count

A Lightning LoRA is trained to produce a finished image in **exactly** its own step
count at **CFG 1**. Running it at 20 steps / CFG 2.5 samples the distilled velocity field
outside its training envelope and **regresses to the mean of the training distribution** —
which for most Qwen LoRAs is a beauty-filtered dataset. The observable result is *worse*
skin texture, weaker identity, flatter light than the fast setting.

**Do not "add steps for quality" on a Lightning graph.** Match the step count to the
distill, or remove the distill and re-tune from the stock baseline.

---

## Resolution

Native operating point ≈ **1.6 MP** for generation graphs:

| Aspect | Resolution |
|---|---|
| 1:1 | 1024x1024 or 1328x1328 |
| 2:3 | 768x1152, 1024x1536, 1104x1472 |
| 3:4 | 960x1280, 1080x1440 |
| 16:9 | 1280x720, 1664x928 |
| 9:16 | 720x1280, 928x1664 |

**On an edit graph, ignore this table.** Size is inherited from the source (~1.05 MP
through the conditioner). See the scale trap.

Hosted-API input constraints (for reference): images 384–3072 px per axis for best
results, ≤ 10 MB; output pixel count between 512² and 2048², snapped to multiples of 16.

---

## Texture realism loop (portraits / skin)

The structural causes of plastic skin, in order of impact:

1. **Latent is empty noise** rather than a source-derived latent → the subject is
   rebuilt from a description and the reference's real pore texture cannot survive.
   *Fix: `VAEEncode` the scaled reference into the sampler.*
2. **Distilled sampler over-stepped** (see above). *Fix: match steps to the distill.*
3. **Smoothness-oriented LoRAs stacked without counterweight.** *Fix: pair with a skin
   LoRA and low-strength the smoothing ones.*
4. **Constraint-heavy prompt.** *Fix: rewrite in observational voice.*
5. **High `shift`** front-loads coarse structure and starves the late steps where fine
   texture forms. *Fix: sweep shift ~1.5–3.0.*

Community-standard workaround stack: `er_sde · beta57 · 8 steps` + a skin-fix LoRA
(strength 0.7–1.2). A second low-denoise pass (0.2–0.35) with a detail/skin LoRA injects
pore-level high frequency; a sampler can only preserve it, not create it.

---

## LoRA compatibility notes

- 2509 and 2511 share an identical architecture (same pipeline class, same 20,430,401,088
  params, same shard counts) — LoRAs **load** across them with no shape errors.
- They are **not interchangeable in effect**. 2511 continued training from 2509, so
  `W + Δ` computed against 2509 lands on a shifted `W`. Concept LoRAs survive; tool /
  accelerator LoRAs (Lightning, Turbo, step distillation) do not — always match those
  natively. Edit-semantics LoRAs (relight, angle, object manipulation) half-work.
- 2511 integrated selected community LoRAs (e.g. lighting enhancement, novel viewpoints)
  directly into the base, so some effects need no LoRA at all.

---

## Vendor sources

- [Qwen/Qwen-Image-Edit-2511 model card](https://huggingface.co/Qwen/Qwen-Image-Edit-2511) — official, incl. the multi-image prompt example
- [Alibaba Model Studio — Qwen-Image Edit API](https://www.alibabacloud.com/help/en/model-studio/qwen-image-edit-api) — official prompt/style guidance, token limits, recommended resolutions
- [Replicate — Qwen Image Edit 2511](https://replicate.com/qwen/qwen-image-edit-2511/readme) — "How to get good results" prompt guidance
- [fal — Qwen Image Edit 2511 Developer Guide](https://fal.ai/learn/devs/qwen-image-edit-2511-developer-guide) — parameters, guidance-scale ranges
- [ComfyUI docs — Qwen-Image-Edit-2511 native workflow](https://docs.comfy.org/tutorials/image/qwen/qwen-image-edit-2511)
- Comfy Cloud catalog prompting guide for `qwen_image_edit_2511_fp8mixed.safetensors`
- Empirical/community: the scale-trap mechanism and both failing pairings are documented
  from ComfyUI graph behaviour; the distilled-LoRA over-stepping result is
  empirically confirmed on rendered A/B comparisons.

**Confidence:** settings tables and the latent/resolution rules are well-sourced. The
"assert presence, don't forbid absence" technique is a strong empirical pattern, not a
vendor statement.
