---
name: grok-imagine-prompter
description: Crafts optimized, director-style image and video prompts specifically tailored for xAI Grok Imagine (Image 2.0 and Video 1.5). Use when the user wants to write, refine, or storyboard prompts for Grok Imagine.
---

# Grok Imagine Prompting Skill

## Core Rules for Grok Imagine
1. **Natural Language Over Tag Soup:** Write 30–80 words in plain, flowing sentences. Never use comma-separated keyword spam (e.g., `8k, masterpiece, ultra-detailed, trending on artstation`) or negative prompts (`no blur, no extra fingers`), which Grok Imagine ignores or mishandles.
2. **Front-Load the Subject:** Grok places the highest weight on the first 15–20 words. Put the shot type, primary subject, and core action immediately at the start.
3. **One Subject, One Beat:** Keep one clear focal subject per image. For video, pack only a single physical action and one camera move into a clip.
4. **Director & Camera Vocabulary:** Use real photography and cinema terms (lens focal length, lighting direction, film stock, framing) rather than vague mood adjectives.

## Image Prompt Formula (Grok Imagine Image 2.0)
Structure every image prompt in this exact order:
1. **Shot Type & Subject:** Framing + who/what is in the shot + 1–2 concrete visual traits.
2. **Action & Setting:** What they are doing + specific physical environment.
3. **Lighting & Atmosphere:** Light source, direction, time of day, and weather/texture.
4. **Camera & Style:** Lens (e.g., `35mm`, `85mm`, `macro`), depth of field, and medium/aesthetic (e.g., `editorial film photography`, `3D isometric render`, `cel-shaded anime`).

**Example Output:**
> *Medium close-up portrait of an elderly watchmaker with silver-rimmed glasses leaning over a wooden workbench, carefully inspecting tiny brass gears with tweezers. Warm afternoon sunlight streams through a dusty workshop window, casting crisp shadows across scattered tools. Shot on 85mm lens, shallow depth of field, Kodak Portra 400 film grain, natural editorial photography.*

## Video Prompt Formula (Grok Imagine Video 1.5)
When the user wants a video prompt (Text-to-Video or Image-to-Video):
1. **Visual & Action:** Describe the single continuous motion clearly. (If animating a starting still image, omit static background details and describe only what moves.)
2. **Camera Movement:** Specify one clean camera move (e.g., `slow dolly-in`, `low-angle tracking shot`, `handheld pan`, `locked-off tripod shot`).
3. **Native Synchronized Audio:** Always include an explicit `Audio:` line describing dialogue (keep spoken lines short for clean lip-sync), sound effects, ambience, or music.

**Example Output:**
> *The camera performs a slow dolly-in on a lone knight standing on a windswept cliff at dusk. She lowers her broadsword, turns her head toward the lens, and says quietly, "It ends tonight." Heavy wind lifts her tattered cloak while distant storm clouds roll overhead. Audio: howling wind, low thunder rumble, clear spoken dialogue, no background music.*

## Workflow When Invoked
1. Ask or infer whether the user needs **Image**, **Text-to-Video**, or **Image-to-Video** (plus aspect ratio like `16:9`, `9:16`, or `1:1`).
2. Deliver **3 distinct prompt variations** (e.g., *Cinematic Realism*, *Stylized/Editorial*, and *Dynamic Action*) ready to copy-paste into Grok Imagine.
3. Offer a quick **Shot-by-Shot Extension** if they want to turn a single prompt into a multi-clip sequence.
