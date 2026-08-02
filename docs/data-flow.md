# Happy Cow — Data Flow

How data gets from the real world into the site, who writes what, and what
happens when things fail. Phase 4 of [issue #30](https://github.com/lucas-albers-lz4/happycow/issues/30).

## The pipeline (one CI job, Sun + Thu 14:00 UTC)

```
config/venues.json  ──►  discover_venues.py  ──►  (new venues appended to config)
        │                      │
        │                      ▼
        └──►  scrape_happy_hours.py ──► data/happy_hour_data.json
                    │
                    ▼
        check_venue_status.py ──► data/state/closure_state.json
                                  data/state/closure_report.md (human review)
                    │
                    ▼
        validate_data.py + validate_hours.mjs   ← fail the job on any violation
                    │
                    ▼
        check_data_regression.py               ← regression gate vs HEAD baseline
                    │
                    ▼
        commit → GitHub Pages deploys automatically
```

## Files and their writers

| File | Writer(s) | What it holds | Regenerated? |
|---|---|---|---|
| `config/venues.json` | humans (curation), `discover_venues.py` | **Source of truth**: id, name, address, phone, website, maps, tags, noise/mood, nickname(+alts), `scrape_urls`, new curated fields | No — durable |
| `data/happy_hour_data.json` | `scrape_happy_hours.py` | Site data: config fields + `hours`, `business_hours`, `specials`, `notes` (runtime) | Yes — every scrape |
| `data/state/scrape_cache.json` | `scrape_happy_hours.py` | Page content hashes → skip DeepSeek on unchanged pages | Yes |
| `data/state/closure_state.json` | `check_venue_status.py` | Per-venue consecutive site-failure counters | Yes |
| `data/state/removed_venues.json` | `remove_venue.py` | Tombstones (normalized name+address) — discovery skips them | Append-only |
| `data/state/closure_report.md` | `check_venue_status.py` | Human-review report of closure flags | Yes |
| `schema/venue.schema.json` | humans | The venue-record contract | No |

**State convention (Phase 4):** all runtime state lives under `data/state/`,
written atomically (tmp + rename via `scripts/common.py` `save_json`/
`save_text`) so a crash can't truncate a file. `common.py` is the single
source for paths and the aggregator-host set.

> **Note:** this repo is served by GitHub Pages, so **everything committed is
> public** — including `data/state/`. State contains hashes and flags only;
> never put secrets here. (The site data itself is intentionally public.)

## Who owns what

- **Static/curated fields** (name, address, tags, nickname, …) — `config/venues.json` wins.
- **Runtime fields** (`hours`, `business_hours`, `specials`, `notes`) — fresh LLM extraction wins; previous data is the fallback when the LLM returns nothing; the site keeps the old values rather than blanking them.
- **New curated fields** — carried through by construction: `venue_to_site_record()` starts from ALL config fields (minus `scrape_urls` and other pipeline-only keys) and overrides only runtime fields. A new config field can never silently vanish from the site data again.

## Source hierarchy + contamination guard

1. **Own-site pages first** (curated `scrape_urls` — HH subpages, menus) — early-break applies only *after* this phase.
2. **Aggregators last** (mthappyhour, bozemanmagazine, menupix, yelp, facebook, google, visit-bozeman, sellout) — and only if the page **matches the venue** (name + street number/word). mthappyhour pages were caught 3× carrying other venues' content; the guard skips non-matching pages (log: `SKIP … contamination guard`). Own-site pages missing the venue name get a soft WARN, not a skip (addresses often live in trimmed footers).
3. LLM extraction (`prompts/extract_happy_hour.txt`) → pydantic-validated; rule 1 is "invent nothing".

## Failure semantics

| Failure | Behavior |
|---|---|
| Venue page fetch fails / LLM returns nothing | Keep previous data for that venue (never blank) |
| `discover_venues.py` crashes | Logged, job continues with existing venues (best-effort) |
| **Validation fails** (schema / hours grammar / coverage / parity) | **Job fails before commit** — broken JSON never reaches Pages |
| **Regression gate fails** (venue drop / hours wipe / specials collapse) | **Job fails before commit** — run `python scripts/check_data_regression.py --allow-regression` locally to inspect; set `--allow-regression` in the workflow step for intentional bulk changes |
| `check_venue_status.py` flags a venue (site dead 2× runs / closure wording) | Report-only. Human reviews `data/state/closure_report.md` |
| Closure confirmed by a human | `python scripts/remove_venue.py <id> --reason "…"` → removes from config + data, writes tombstone; discovery can never re-add it |

## Manual interventions (documented on purpose)

- `python scripts/remove_venue.py <id> --reason "closed June 2026"` — closure removal (tombstones the venue).
- Editing `config/venues.json` `scrape_urls` — add a venue's own HH page; it outranks aggregators.
- Known-gap notes: set `notes` on a venue in the **site data** with "(verified …)" so the coverage invariant (specials OR note) stays satisfied.
- `python scripts/scrape_happy_hours.py --venue <id> --force` — re-scrape one venue, bypassing the cache.

## Regression gate (issue #40)

`scripts/check_data_regression.py` runs **after** validate and **before** commit in `scrape.yml`.
It compares the candidate `data/happy_hour_data.json` (just produced by the scraper) to the
HEAD version (via `git show HEAD:data/happy_hour_data.json`).

Hard-fail conditions:
- **VENUE_COUNT_DROP** — fewer venues than baseline
- **MISSING_IDS** — baseline ids absent from candidate (unexplained removal)
- **SPECIALS_COVERAGE** — more than `SPECIALS_DROP_THRESHOLD` (default 2) venues lost all specials
- **HOURS_WIPE** — more than `HOURS_WIPE_THRESHOLD` (default 1) venues lost hours entirely
- **COVERAGE_BROKEN** — venues with no specials AND no notes

Report (always printed): count + ids of venues whose hours/specials hash changed — this
feeds issue #46 (change attribution).

**Mode precedence / PR mode (#46):** in a future PR-check workflow the hard-fail should
become a PR review comment instead of a bare `exit 1`.  Until PR mode is wired, `exit 1`
is the only signal.  `--allow-regression` is the escape hatch: it prints the full report
but always exits 0 — use it for intentional bulk data changes.

## Fail-fast gates (issue #50)

The scraper exits non-zero (and writes nothing) in two cases:
1. **Missing API key** — `DEEPSEEK_API_KEY` (or `ANTHROPIC_API_KEY`) absent before the venue loop; job log says why.
2. **ok == 0** — every venue was either kept-previous or failed; no fresh data was extracted. `data/happy_hour_data.json` is not written and `last_updated` is unchanged. Pairs with the #40 regression gate: #40 catches quality drops vs HEAD; #50 catches "nothing scraped at all."

## Write safety

All JSON writes (config, data, tombstones, scrape cache) go through `common.save_json` (atomic tmp+rename). A crash or interrupt cannot leave a truncated file. Scripts that write JSON:
- `scripts/scraper/cli.py` — scrape output + cache
- `scripts/remove_venue.py` — config, data, tombstone
- `scripts/discover_venues.py` — config (discovery appends)

## One-shot maintenance scripts

Scripts under `scripts/tools/` are manual-only and must never be added to the scrape CI workflow:
- `scripts/tools/backfill_business_hours.py` — one-time business-hours backfill; do not schedule.
- `scripts/tools/discover_hh_pages.py` — one-time HH page discovery seed; do not schedule.

## Scrape CI git add scope

The "Commit updated data" step in `.github/workflows/scrape.yml` stages only runtime outputs:
`data/happy_hour_data.json`, `data/state/`, `config/venues.json`.

Source files (`scripts/`, `assets/`, etc.) are never staged by CI — any change there goes through a normal PR. This prevents accidental script commits from automated runs.

## Reading list

- `scripts/common.py` — paths + shared constants + atomic writers
- `docs/architecture-refactor-plan.md` — the refactor roadmap (phases 1–3 done)
- `schema/venue.schema.json` — the venue-record contract
- `assets/js/hours.js` + `tests/hours.test.mjs` — the hours grammar (single source of truth)
