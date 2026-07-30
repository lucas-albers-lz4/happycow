# Happy Cow 🐄🍸

A self-funding happy hour directory for small cities. 30 rotating cow cartoons, daily prophecies, venue roulette, and all the happy hour deals you can drink.

## How it works

- **Data**: Scraped twice a week with DeepSeek Flash → `data/happy_hour_data.json`
- **Hosting**: GitHub Pages (free)
- **Domain**: Cloudflare Registrar (at cost, ~$10/yr)
- **Cows**: 30 unique illustrations generated via AI, one-time cost ~$1.50
- **Magic**: All interactive features are vanilla JS + localStorage — zero backend

## Scrape pipeline

Curated venues live in `config/venues.json` (static fields: tags, maps, scrape URLs).
`.github/workflows/scrape.yml` runs Sun + Thu ~8am MT:

1. Fetch each venue's `scrape_urls`
2. DeepSeek Flash extracts hours + specials (`prompts/extract_happy_hour.txt`)
3. Merges into `data/happy_hour_data.json` (keeps previous on failure)
4. Commits to `main` → Pages redeploys

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DEEPSEEK_API_KEY=...
python scripts/scrape_happy_hours.py --dry-run
python scripts/scrape_happy_hours.py --venue bacchus-pub
```

Required repo secret: `DEEPSEEK_API_KEY` (same key as sre-ai-llm-work).

## Local dev

```bash
python3 -m http.server 8000
# or just open index.html in a browser
```

## Investment model

Principle needed at 4% SWR: **$619** — runs forever.
