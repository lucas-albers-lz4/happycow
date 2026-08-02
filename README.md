# Happy Cow 🐄🍸

A self-funding happy hour directory for small cities. 30 rotating cow cartoons, daily prophecies, venue roulette, and all the happy hour deals you can drink.

## How it works

- **Data**: Scraped twice a week with DeepSeek Flash → `data/happy_hour_data.json`
- **Hosting**: GitHub Pages (free)
- **Domain**: Cloudflare Registrar (at cost, ~$10/yr)
- **Cows**: 30 unique illustrations generated via AI, one-time cost ~$1.50
- **Magic**: All interactive features are vanilla JS + localStorage — zero backend

## Scrape pipeline

Curated venues live in `config/venues.json` (source of truth: static fields, tags, maps, scrape URLs, nicknames).
`.github/workflows/scrape.yml` runs Sun + Thu ~8am MT — see **[docs/data-flow.md](docs/data-flow.md)** for the full pipeline (discovery, scraping, closure check, validation, fallback semantics).

In brief: own-site pages (curated `scrape_urls`) are fetched first — aggregators (mthappyhour et al.) are last, and only accepted when the page matches the venue (name + street), guarding against the cross-venue contamination mthappyhour is prone to. DeepSeek Flash extracts hours + specials (`pydantic` validates, +1 retry); previous data is kept on any failure. A validation gate (schema, hours grammar via the JS parser, coverage, config/data parity) fails the job before anything commits. GitHub Pages redeploys on every commit to `main`.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DEEPSEEK_API_KEY=...
python scripts/scrape_happy_hours.py --dry-run
python scripts/scrape_happy_hours.py --venue brigade
python scripts/scrape_happy_hours.py --force   # ignore cache
```

Required repo secret: `DEEPSEEK_API_KEY` (same key as sre-ai-llm-work).

## Local dev

```bash
python3 -m http.server 8000
# or just open index.html in a browser
```

## Making more cows

Want to add to the herd? See [docs/making-cows.md](docs/making-cows.md) for the exact generation process, prompt template, and wiring steps.

## Sound credits

- `assets/sounds/moo.mp3` — real cow moo, sourced from [BigSoundBank](https://bigsoundbank.com/cow-moos-s0546.html) (CC0 / public domain equivalent, no attribution required). Trimmed, filtered (60–900 Hz), and normalized for a clean 1.8s bellow.

## Investment model

Principle needed at 4% SWR: **$619** — runs forever.
