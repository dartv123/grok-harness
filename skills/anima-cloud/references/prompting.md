# Writing an Anima prompt

Anima was trained on Danbooru tags, natural-language captions, and mixes of both. All three work. The tool sends your prompt exactly as written: no quality prefix and no negative prompt are added, so write them yourself.

## 1. Prompt modes

- **Pure tags** (Danbooru style): the most precise for characters, outfits and composition.
- **Pure natural language:** better for scenes, relationships between characters, and lighting. Needs at least 2 descriptive sentences; one short sentence gives unpredictable results.
- **Mixed:** tags and sentences in any order. A common pattern is quality and artist tags first, then prose.

Training used random tag dropout, so a focused set of tags beats an exhaustive dump.

## 2. Tag order and formatting

```
[quality / meta / year / safety] [1girl / 1boy / 1other / 2girls ...] [character] [series] [artist] [general tags]
```

Order within a section doesn't matter.

- Lowercase, **spaces instead of underscores**: `long hair`, `blunt bangs`, `fur-trimmed gloves`. The one exception: `score_9` … `score_1` keep their underscore.
- Where Danbooru and Gelbooru spell a tag differently, use the Gelbooru spelling.
- **Weighting needs stronger weights than SDXL:** `(chibi:2)`, not `(chibi:1.2)`. Use 1.8–2 for a visible effect.

## 3. Tag vocabulary

| Kind | Tags | Notes |
|---|---|---|
| Quality (human-rated) | `masterpiece, best quality, good quality, normal quality, low quality, worst quality` | |
| Quality (aesthetic scorer) | `score_9` … `score_1` | Either family, both, or neither. Some finetunes push into "AI slop" with `score_*`; drop them if results look overcooked |
| Time | `year 2025`, `year 2024`, … or `newest, recent, mid, early, old` | Pulls era-specific styles; `old` gives a 90s cel look |
| Meta | `highres, absurdres, anime screenshot, official art, jpeg artifacts` | `anime screenshot` gives a TV-anime frame look |
| Safety | `safe, sensitive, nsfw, explicit` | **Always set one.** Short or vague prompts can drift. For SFW work: `safe` in the prompt and `nsfw, explicit` in `--negative` |
| Artist | `@name`, e.g. `@nnn yryr` | **Must start with `@`**, otherwise the effect is very weak. Artist tags are the strongest style lever |

## 4. Non-anime styles (dataset tags)

The non-anime training data came from LAION-POP (`ye-pop`) and DeviantArt (`deviantart`), with photos filtered out. Put the dataset tag on the **first line**, optionally a second line with an alt-text or artwork title, then the caption. The line breaks matter, so use `--prompt-file`.

```
deviantart
Flame
Digital painting of a fiery dragon with glowing yellow eyes, black horns, and molten scales, perched on a volcanic ridge.
```

Use this for Western digital painting, fantasy illustration, oil-painting or abstract looks.

## 5. Natural-language rules

- Standard English capitalization for character and series names: "Fern from Sousou no Frieren".
- More descriptive is better.
- **Name a character, then describe their appearance.** With several characters this is essential; a bare list of names makes the model merge or swap them.
- Quality and artist tags can lead: `masterpiece, best quality, @artist. An anime girl with ...`

## 6. Examples

**Tags (official style):**
```
year 2025, newest, normal quality, score_5, highres, safe, 1girl, oomuro sakurako, yuru yuri, @nnn yryr, smile, brown hair, hat, solo, fur-trimmed gloves, open mouth, long hair, gift box, fang, skirt, red gloves, blunt bangs, one eye closed, brown eyes, santa costume, red hat, white background, holding bag, looking at viewer, ;d, red capelet
```

**Natural language with a known character:**
```
masterpiece, best quality, safe. Digital artwork of Fern from Sousou no Frieren, with long purple hair and purple eyes, wearing a black coat over a white dress with puffy sleeves. She stands on a windswept hill at dusk holding a wooden staff, the sky behind her streaked orange and violet.
```

**Two characters, each described:**
```
masterpiece, best quality, safe, 2girls. Frieren from Sousou no Frieren, a small elf with long white twin-tailed hair and green eyes in a white and gold robe, sits on a rock reading a grimoire. Beside her stands Fern, a tall girl with long straight purple hair and purple eyes in a black coat, looking down at the book over Frieren's shoulder. Forest clearing, soft morning light.
```

**Original character, mixed:**
```
masterpiece, best quality, newest, safe, 1boy, solo, silver hair, short hair, red eyes, black military coat, gloves, katana, rain, night, city, neon lights. A lone swordsman stands on a rooftop in heavy rain, neon signs reflecting in the puddles around his boots.
```

A typical negative for SFW work (`--negative`):
```
worst quality, low quality, score_1, score_2, score_3, artist name, blurry, jpeg artifacts, chromatic aberration, nsfw, explicit
```

## 7. Common mistakes

| Mistake | Fix |
|---|---|
| `long_hair` with underscores | `long hair` |
| Artist name without `@` | `@name` |
| No safety tag | Add `safe` / `sensitive` / `nsfw` / `explicit` |
| One-line prose prompt | At least 2 descriptive sentences |
| A list of character names only | Name plus appearance for each |
| SDXL-strength weights `(x:1.2)` | `(x:1.8)` to `(x:2)` |
| Long text inside the image | Single words at best; Anima can't render text reliably |
| Asking for photorealism | Anima is an illustration model. For photos use `grok-imagine`; `--ckpt real-dream-v5-anima-bf16` only leans more realistic |
