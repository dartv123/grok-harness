# Anima Prompting Reference

Source: official model card, circlestone-labs/Anima (Hugging Face).

## Contents
1. Prompt modes
2. Tag order
3. Tag vocabulary (quality, time, meta, safety, artist)
4. Dataset tags (non-anime styles)
5. Natural-language rules
6. Worked examples
7. Common mistakes

## 1. Prompt modes

Anima accepts three modes, all trained:
- **Pure tags** (Danbooru style) — most precise for characters, outfits, composition.
- **Pure natural language** — better for scene description, relationships, lighting. Needs ≥2 sentences.
- **Mixed** — tags and sentences in any order. Common pattern: quality/artist tags first, then prose.

Trained with random tag dropout, so you don't need every tag; a focused set beats an exhaustive dump.

## 2. Tag order

```
[quality / meta / year / safety] [1girl / 1boy / 1other / 2girls ...] [character] [series] [artist] [general tags]
```
Order within a section doesn't matter.

Formatting:
- lowercase, spaces instead of underscores (`blunt bangs`, `fur-trimmed gloves`)
- exception: `score_9` … `score_1` keep underscores
- where Danbooru and Gelbooru differ, use the Gelbooru tag
- weighting works but needs strong weights: `(chibi:2)`, not `(chibi:1.2)`

## 3. Tag vocabulary

**Quality — human-rated:** `masterpiece, best quality, good quality, normal quality, low quality, worst quality`

**Quality — aesthetic-model (PonyV7 scorer):** `score_9 … score_1`

Either family, both, or neither all work. Don't use `score_*` with the Aesthetic variant (positive or negative).

**Time period:** specific `year 2025`, `year 2024`, … or bucket `newest, recent, mid, early, old`. Useful to pull era-specific art styles (e.g. `old` for 90s cel look).

**Meta:** `highres, absurdres, anime screenshot, official art, jpeg artifacts, ...`. `anime screenshot` gives a TV-anime frame look.

**Safety:** `safe, sensitive, nsfw, explicit`. Always set one. For SFW, `safe` in positive and `nsfw, explicit` in negative (negative only matters when CFG > 1).

**Artist:** prefix with `@` — `@big chungus`. Without `@` the effect is very weak. Artist tags are the main style lever on the Base model.

## 4. Dataset tags (non-anime styles)

Non-anime training data came from LAION-POP (ye-pop) and DeviantArt, photos filtered out. Their captions are labeled by a dataset tag on the **first line**, optionally followed by a second line with alt-text (ye-pop) or artwork title (DeviantArt), then the caption.

```
ye-pop
For Sale: Others by Arun Prem
Abstract, oil painting of three faceless, blue-skinned figures. ...
```
```
deviantart
Flame
Digital painting of a fiery dragon with glowing yellow eyes, black horns, ...
```
Use these for Western digital painting, fantasy illustration, abstract/oil-painting looks. Newlines matter; pass the prompt with real `\n` line breaks.

## 5. Natural-language rules

- Standard English capitalization for character and series names ("Fern from Sousou no Frieren").
- More descriptive is better; very short prose prompts give unpredictable results.
- Name a character, then describe their base appearance. With multiple characters this is essential — a bare list of names confuses the model.
- Quality/artist tags can lead: `masterpiece, best quality, @artist. An anime girl with ...`

## 6. Worked examples

**Full tag prompt (official example, Base):**
```
year 2025, newest, normal quality, score_5, highres, safe, 1girl, oomuro sakurako, yuru yuri, @nnn yryr, smile, brown hair, hat, solo, fur-trimmed gloves, open mouth, long hair, gift box, fang, skirt, red gloves, blunt bangs, gloves, one eye closed, shirt, brown eyes, santa costume, red hat, skin fang, twitter username, white background, holding bag, fur trim, simple background, brown skirt, bag, gift bag, looking at viewer, santa hat, ;d, red shirt, box, gift, fur-trimmed headwear, holding, red capelet, holding box, capelet
```

**Natural language with character:**
```
masterpiece, best quality, safe. Digital artwork of Fern from Sousou no Frieren, with long purple hair and purple eyes, wearing a black coat over a white dress with puffy sleeves. She stands on a windswept hill at dusk holding a wooden staff, the sky behind her streaked orange and violet.
```

**Two characters (describe each):**
```
masterpiece, best quality, safe, 2girls. Frieren from Sousou no Frieren, a small elf with long white twin-tailed hair and green eyes in a white and gold robe, sits on a rock reading a grimoire. Beside her stands Fern, a tall girl with long straight purple hair and purple eyes in a black coat, looking down at the book over Frieren's shoulder. Forest clearing, soft morning light.
```

**Original character, mixed:**
```
masterpiece, best quality, newest, safe, 1boy, solo, @artist name, silver hair, short hair, red eyes, black military coat, gloves, katana, rain, night, city, neon lights. A lone swordsman stands on a rooftop in heavy rain, neon signs reflecting in the puddles around his boots.
```

## 7. Common mistakes

| Mistake | Fix |
|---|---|
| `long_hair` underscores | `long hair` |
| artist name without `@` | `@name` |
| `score_*` tags with Aesthetic | remove them |
| relying on negative prompt with Turbo | CFG 1 ignores it; put constraints in positive |
| one-line prose prompt | ≥2 descriptive sentences |
| list of character names only | name + appearance for each |
| SDXL-strength weights `(x:1.2)` | `(x:1.8–2)` |
| asking for photorealism | wrong model; Anima is illustration-only |
| long in-image text | single words at best |
