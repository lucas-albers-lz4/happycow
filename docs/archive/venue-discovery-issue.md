## Problem

The Happy Cow site is missing bars it should list. Two known misses:

- **The Filling Station** (2005 N Rouse Ave) — Bozeman's original dive bar / live music venue since 1976
- **The Molly Brown** (703 W Babcock) — "Casino Happy Hour", 20 taps, 8 pool tables

The pipeline could never find them — or any new bar — because:

1. **Discovery was never wired up.** `config/venues.json` had a `discovery_seeds` section, but `scripts/scrape_happy_hours.py` never reads it. The scraper only iterates the hand-curated `venues` array, so the list was frozen at 26 and could only grow by manual edits.
2. **The only seed was incomplete.** The single seed (`mthappyhour.com/happy-hours-near/bozeman/`) lists only ~10 venues, and its full directory misses **14 Bozeman venues** the site should have (Cafe Fresco, Hooked Sushi, The Pour House, The Cannery, Valhalla Meadery, The Bay, The Buck, The Bunkhouse Brewery, Last Best Place Brewery, Sidewall Pizza, Tanoshii, Korner Klub, Wildrye Distilling, Backcountry Burger Bar).
3. **Dive bars are invisible to directories.** The Filling Station, The Molly Brown, and The Haufbrau appear in **no** directory source at all — they only exist on Bozeman Magazine / Visit Bozeman style pages. So even a perfect directory scrape would never surface them.

## Solution

A generalized discovery script (`scripts/discover_venues.py`) that:

- Reads `discovery_seeds` + `curated_venues` from `config/venues.json` (the config that was previously dead)
- Parses directory index pages: name / address / city / happy-hour summary / URL, with pagination and card validation
- Parses individual venue pages (h1 name, address, phone, category tags) for dive bars no directory indexes
- Dedups against existing venues (normalized name + shared street number/address match) and filters to the target city
- `--dry-run` reports; `--write` appends new venue stubs (id, address, phone, maps link, `scrape_urls`) to config so the existing scraper then enriches them with real happy-hour data

CI (`scrape.yml`) now runs discovery before scraping, so **the venue list grows automatically on every scheduled run** — no more hand-curation required.

## Result

First run discovered **16 new Bozeman venues** (26 → 42), including all three named bars plus the 14 directory venues above.

## Verification

- `python scripts/discover_venues.py` (dry-run) → 16 new venues, clean dedup, no garbage cards
- `python scripts/discover_venues.py --write` → appends to config, idempotent on re-run
- `python scripts/scrape_happy_hours.py --dry-run --venue the-filling-station` → fetches the venue page, falls back to previous data when no LLM key is present
- The three dive bars are pre-seeded in `data/happy_hour_data.json` so they render on the site immediately; the scraper enriches hours/specials on the next scheduled run with the `DEEPSEEK_API_KEY` secret
