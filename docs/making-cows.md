# 🐄 Making More Cows

How the Happy Cow cow images are made, so anyone can generate new ones that match the existing set.

## TL;DR

The cows are **AI-generated PNGs** (1024×1024) created with the `image_generate` tool using Google Gemini 3 Pro Image (via OpenRouter). They *look* like SVGs (flat vector style, bold outlines) but they are raster PNGs.

**One image per cow. No SVG files in the repo.**

## The Working Prompt Template

The exact prompt style that produced the current 30-cow set:

```
Simple cartoon cow character with [ACCESSORY/LOOK] and [EXPRESSION],
flat vector style with bold black outlines, brown and white patches,
standing on two legs, sticker style, isolated on white background
```

The base cow (used as the visual "default" in docs and the original from which the set grew):

```
A cute simple cartoon cow, full body, standing front-facing, flat vector
style with bold black outlines, brown and white patches, simple round eyes,
small horns, standing on two legs, friendly smile, isolated on white
background, clean high-contrast design perfect for a small app icon,
minimal detail, sticker style
```

### Example variations that produced cows in the set

| Accessory / look | Expression |
|---|---|
| PARTY HAT | confused |
| SUNGLASSES | looking cool |
| *(any accessory)* | friendly smile |

## The Generation Pipeline

1. **Generate** one image per cow:
   ```
   image_generate(aspect_ratio="square", prompt="<template with variation>")
   ```
   Output lands in the image cache, e.g. `/root/.hermes/cache/images/openrouter_gen_20260730_015013_09a49251.png`

2. **Name it** with the repo convention:
   - `assets/cows/cow-0.png` … `assets/cows/cow-29.png` — the 30 rotating cows
   - `assets/cows/cow-base.png` — the base/hero cow
   - `assets/cows/cow-pending-1.png` … `cow-pending-4.png` — "coming soon" placeholder cows

3. **Copy into the repo** (this is how the originals were placed):
   ```bash
   cp /root/.hermes/cache/images/openrouter_gen_*.png /tmp/happycow/assets/cows/cow-N.png
   ```

4. **Commit and push** — the site picks them up automatically (static assets, no rebuild).

## Wiring a New Cow Into the App

Cows are driven by three places in `assets/js/app.js`:

| Location | What it does |
|---|---|
| `COW_NAMES` array | Holds the 30 cow names (index-aligned with the PNGs: `cow-0.png` ↔ `COW_NAMES[0]`). **Add a new name here for each new cow.** |
| `getCowForDay()` | `Math.floor(rng() * 30)` picks the daily cow from 30. **Bump 30 → 31, 32, … as you add cows.** |
| `IMPOSTORS = [13, 21, 23, 25, 27]` | The 5 "impostor" cow indices (mutant, bulls, giraffe, beagle). Optional — only if a new cow is an impostor. |

The `cow-collected` counter in the UI shows `X/30` — it derives from `COW_NAMES.length` behavior via the `state.collected` array, so keep the count in sync.

## Consistency Rules (what makes a cow "look right")

- **Same style keywords every time**: `flat vector style with bold black outlines, brown and white patches, standing on two legs, sticker style, isolated on white background`
- **Square aspect ratio** (1024×1024) — the app renders cows as circles (`border-radius: 50%`), so keep the cow centered with margin around it
- **White/light background** — the app relies on the image blending into cream cards; busy backgrounds look broken
- **Keep the same color palette**: brown + white patches, tan snout, black outlines. Hue-shifted cows (used in early experiments via CSS `hue-rotate`) were abandoned in favor of unique PNGs — but CSS filters are still a valid cheap trick for bonus variants

## Cost & Time

- ~30 cows cost roughly **$1.50** one-time via OpenRouter image generation
- Each cow takes ~1 tool call (a few seconds)
- Zero ongoing cost — images are static assets served from GitHub Pages

## Why Not Real SVGs?

An early plan was: generate one base PNG + CSS `hue-rotate`/overlay filters to synthesize 30 cows. It was abandoned because `hue-rotate` does nothing useful on black outlines, and filter-based variants looked cheap. Unique AI-generated PNGs won. If you ever want *true* SVGs (e.g. for an animated mascot), trace a generated PNG with `potrace` — but for the current site, PNGs are the process.
