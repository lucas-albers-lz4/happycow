# Happy Cow — Development Guide

How to set up the repo, verify it, and do the common maintenance tasks.
Read [architecture.md](architecture.md) first for the system map.

## Local setup

```bash
git clone https://github.com/lucas-albers-lz4/happycow.git && cd happycow
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

**Python gotcha:** the repo needs `httpx`, `trafilatura`, `pydantic`, `tenacity`,
`beautifulsoup4`, `lxml` — system Python is PEP-668-managed, so **always use the
venv** (`source .venv/bin/activate`). Background terminal shells resolve to system
python3, so re-activate or call the venv binary explicitly.

**Env vars (only needed for scraping, not for validation/tests):**

```bash
export DEEPSEEK_API_KEY=...          # DeepSeek API key
export DEEPSEEK_MODEL=deepseek-v4-flash
# Optional: ANTHROPIC_BASE_URL (defaults to https://api.deepseek.com/anthropic)
```

## Verify your setup (run all of these — they're fast)

```bash
node --test                                          # hours parser suite (19 tests)
python3 scripts/validate_data.py                     # full data gate: schema/coverage/parity/hours
node scripts/validate_hours.mjs data/happy_hour_data.json
python3 -m py_compile scripts/*.py scripts/scraper/*.py
node --check assets/js/app.js && node --check assets/js/hours.js
```

All green = the repo is sound. CI runs the same gates on every PR.

## Common tasks

### Add or edit a venue (static data)

Edit `config/venues.json` — the **curated source of truth**. New fields carry
through to the site data automatically (carry-through by construction); keep the
entry's `id` as `kebab-case`. Then re-run the validators.

### Curate happy-hour specials (the human part)

The scraper's LLM extraction is a starting point, not the end: every curated
special should be verified against the venue's own site. Rules that keep the data
honest:

- `price: 0` + discount wording in `description` (e.g. `"$1.00 off well drinks"`)
  → the UI renders `—`. `price: 0` with no wording at all fails validation.
- Unpriced deals: append `(price not specified)` to the description.
- No published HH at all → set `notes: "No published happy hour — verified <date>"`
  (the 100%-coverage invariant).
- Sources: official venue site > dedicated HH subpage > clean aggregator.
  **mthappyhour pages are contaminated** — never copy a snippet without checking
  the venue's own site.
- JS-rendered menus (Wix/Squarespace/React) return nav-only text to plain fetches
  — record hours + a "deals on JS-rendered menu" note, or do a browser pass.

### Re-scrape one venue

```bash
python scripts/scrape_happy_hours.py --venue ale-works --dry-run   # preview only
python scripts/scrape_happy_hours.py --venue ale-works --force     # bypass content-hash cache
```

### Run discovery / closure check

```bash
python scripts/discover_venues.py --write      # find new venues (CI best-effort)
python scripts/check_venue_status.py --dry-run # closure flags without persisting state
python scripts/check_venue_status.py           # full run: state + data/state/closure_report.md
```

### Remove a closed venue (sanctioned way — never hand-edit)

```bash
python scripts/remove_venue.py <id> --reason "closed June 2026, X taking over"
```

Removes from config + data AND writes a tombstone — discovery can never re-add it.
First confirm the closure (news/FB announcement) — the venue may be open with
changed hours instead.

### Change the hours grammar

Edit `assets/js/hours.js` + add cases to `tests/hours.test.mjs` (fixture = the 22
distinct hours strings in live data + edge cases). Run `node --test`. When a new
test fails, check the expectation before touching the parser — the fixture matrix
is ground truth; hand-invented examples drift.

### Add an aggregator host

Edit `scripts/common.py` **only** — `AGGREGATOR_HOSTS` is single-sourced there and
imported by every script. (`maps.google.com` is covered via `google.com`'s suffix
match.)

## CI

- `.github/workflows/scrape.yml` — Sun + Thu 14:00 UTC: discover → scrape →
  closure check → **validate (fails the job before commit)** → commit → Pages
  redeploys. Manual trigger with a `skip_discovery` input for fast re-scrapes.
- `.github/workflows/ci.yml` — every PR: validate data + `node --test`.

## PR workflow (user conventions)

1. Scope work as a **GitHub issue first**, then reference it in the PR.
2. One concern per commit, emoji-prefixed messages matching repo style (🐄🍗🔍).
3. **PRs stay open** for the user to review — merge only when they say so.
4. After merging, verify **on `main`** (checkout main + pull, then check the log
   and re-run the gates) — a post-merge check done on the feature branch is not a
   check of main.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `ModuleNotFoundError: httpx` | Not in the venv — activate it first |
| `gh pr create` says "uses '&' backgrounding" | The terminal guard refuses `&` in command strings — write the PR body to a file and use `--body-file` |
| Scraper prints `SKIP <url>: aggregator page doesn't match venue` | The contamination guard working — page is another venue's content; verify against the official site |
| `validate_data.py` fails on a price-0 special | Missing discount/free wording in the description — add it or `(price not specified)` |
| Venue status shows `unknown` for empty hours | Expected — venues with no published HH window show no badge (specials still show) |
