---
name: grok-imagine-image-prompting
description: Reference guide for writing effective prompts for xAI Grok Imagine image generation, single-image editing, multi-image compositing (up to 3 refs), style transfer, and iterative multi-turn refinements. Use whenever crafting, improving, debugging, or evaluating prompts for Grok Imagine / grok-imagine-image-2.0 / grok-imagine-image-quality, especially merge/composite tasks, identity-preserving edits, or sequential refinements.
---

# Grok Imagine Image Prompting Guide

Focused prompting and compositing knowledge for xAI's Grok Imagine API (`grok-imagine-image-2.0` / `grok-imagine-image-quality`).

Use this when writing or refining prompts for text-to-image generation, single-image edits, multi-image merges/composites, style transfers, or multi-turn iterative editing.

---

## Core Principles for All Prompts

- Be concrete about composition. Order details as: subject → action → setting → lighting → mood. This produces more controllable results than a single adjective-heavy sentence.
- For pure generation (no source images), write a clear descriptive text prompt covering the above elements.
- Prefer one focused intent per prompt. Complex changes work better as sequential multi-turn edits than one overloaded instruction.

---

## Prompting for Single-Image Edits

The model preserves everything you do not mention. Therefore:

- **State the single change explicitly.**  
  Example: "change the sky to sunset orange"  
  Do **not** re-describe the entire scene.

- **Name what to keep** when the edit is subtle or when drift has been a problem.  
  Example: "keep the subject's pose and expression unchanged; only change the background"

- **One aesthetic shift per turn** for style transfer.  
  Stacking multiple style instructions in one prompt is less predictable than sequential multi-turn edits (feed the previous output back as the next input image).

Style transfer examples:
- "Render this as a pencil sketch with detailed shading"
- "Render this image as an oil painting in the style of impressionism"

---

## Multi-Image Compositing (up to 3 references)

Combine subjects, transfer style from one image to another, or compose a new scene from up to three source images in a single request.

### Key behaviors
- **Order matters.** Images are processed in the order they are supplied.
- Aspect ratio defaults to the **first** input image unless you explicitly override it with `aspect_ratio`.
- Sources can be mixed (URL, base64 data URI, or file_id).

### Prompting rules for merges / composites
- Explicitly describe the desired final composition (who is where, what they are doing, overall mood/lighting).
- **Always constrain with negatives** to prevent the model from inventing extra elements:  
  "no additional people or animals"  
  "no extra objects"  
  Merge prompts drift toward inventing extras if you do not constrain them.
- State what must stay the same from each source when identity or style preservation is critical.

**Good composite prompt pattern:**
```
Show all subjects sitting together on the grass in a sunny park. 
Casual relaxed mood, natural daylight, warm tones. 
No additional people or animals.
```

**Style transfer across images:**
Describe the target aesthetic while referencing the source(s). Keep the instruction focused on the transfer rather than re-describing every detail.

---

## Multi-Turn / Iterative Editing

For progressive refinement (e.g. base scene → swap furniture → adjust lighting → change camera):

1. Generate or start with a base image.
2. Feed each output URL (or persisted file) back as the next input.
3. Apply **one deliberate change per turn**.

This is more reliable than packing many instructions into a single prompt.

Because default output URLs are temporary, use them immediately or persist them first if the chain will take more than a few minutes.

---

## Quick Prompting Checklist

| Goal                        | Do this                                                                 | Avoid                                      |
|-----------------------------|-------------------------------------------------------------------------|--------------------------------------------|
| Single change               | Name the exact change only                                              | Re-describing the whole image              |
| Subtle edit / prevent drift | Explicitly name what to keep                                            | Assuming the model will magically preserve |
| Multi-image merge           | Describe final scene + negative constraints ("no additional…")          | Leaving the composition unconstrained      |
| Style transfer              | One clear aesthetic target per turn                                     | Stacking multiple styles in one prompt     |
| Complex sequence            | One change per multi-turn step                                          | One giant overloaded prompt                |
| Composition control         | Subject → action → setting → lighting → mood                            | Vague adjective soup                       |

---

## Sources

Extracted from the Grok Imagine skill (API docs verified against xAI Imagine documentation as of August 2026). Focused exclusively on prompting strategy and multi-image compositing behavior.
