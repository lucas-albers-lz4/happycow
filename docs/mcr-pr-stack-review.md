# Zen MCR — Happy Cow PR Stack (#7, #8, #10)

**Reviewed:** `origin/main...feat/expandable-hours` (1,779 insertions, 11 files)
**Reviewers (3 free Zen models):** `mimo-v2.5-free` · `nemotron-3-ultra-free` · `big-pickle`
**Date:** 2026-08-01 · Raw reviews: `/tmp/mcr-prs/reviews/`

---

## Consensus findings (2+ models agreed — highest confidence)

### 🔴 1. `is_duplicate` name-only match defeats multi-city discovery
**Files:** `scripts/discover_venues.py` (`is_duplicate`)
**Found by:** all 3 models

```python
def is_duplicate(cand, by_name, by_addr):
    if norm_name(cand.name) in by_name:
        return True   # <-- drops ANY same-named venue in ANY city
```

A venue named the same as an existing one but in a *different* target city (Belgrade/Four Corners/Gallatin Gateway) is silently dropped — exactly the Plonk-in-Missoula-vs-Plonk-in-Bozeman case the code comments claim to solve. The name+street-number dedup exists in `absorb()` (candidate vs candidate) but **not** in `is_duplicate()` (candidate vs existing config).

**Fix:** require name *and* street-number agreement in `is_duplicate`, or scope the name lookup by city.

### 🔴 2. Real duplicate in shipped data: Wild Rye Distilling vs Wildrye Distilling
**Files:** `config/venues.json` + `data/happy_hour_data.json`
**Found by:** big-pickle

Both venues exist at the **same address** (111 E Oak St Suite 1E vs #1e):
- `wild-rye-distilling` (original config) — "Wild Rye Distilling"
- `wildrye-distilling` (discovered from mthappyhour) — "Wildrye Distilling"

`norm_name` treats them as different (`"wild rye"` vs `"wildrye"` — space), and `norm_address` keeps `suite 1e` vs `#1e`, so dedup missed it. The site shows the same bar twice.

**Fix:** merge into one record (keep `wild-rye-distilling`, drop the discovered duplicate), and tighten `norm_name` to collapse spaces (it already does — the issue is the name *in the source*; a manual merge is needed).

### 🟠 3. `parse_page` hardcodes `city="Bozeman"`
**Files:** `scripts/discover_venues.py`
**Found by:** all 3 models

Every curated/page candidate gets `city="Bozeman"` regardless of real location. Consequence: Stacey's Old Faithful (Gallatin Gateway) gets a Google Maps query of `"Stacey's Old Faithful Bar & Steakhouse Bozeman MT"` — wrong city link.

**Fix:** derive city from the parsed address or the curated config entry, not a constant.

### 🟠 4. Unescaped `innerHTML` of scraped/LLM text
**Files:** `assets/js/app.js` (`renderVenueCard`)
**Found by:** mimo + big-pickle

`venue.hours`, `venue.business_hours`, `venue.notes` are interpolated straight into `innerHTML`. Data originates from scraped third-party pages + LLM output, so a venue could inject markup. Pre-existing pattern (specials already did this), but PR #10 adds three more fields.

**Fix:** escape pipeline-sourced strings, or build text nodes via `textContent`.

---

## Valid single-model findings

| # | Finding | Model | Severity |
|---|---|---|---|
| 5 | `parse_business_hours` walks `heading.find_parent()` — could harvest a whole page container if HTML structure changes; validate a weekday run before writing | big-pickle | 🟠 Medium |
| 6 | CI swallows discovery failures (`\|\| echo`), and `lxml`/`httpx` deps must stay pinned in `requirements.txt` | big-pickle | 🟠 Medium |
| 7 | `absorb()` comment contradicts code (comment says same-name/diff-street skipped; code keeps both) | big-pickle | 🟡 Low |
| 8 | Website regex over-excludes URLs containing "facebook" etc. anywhere in the path | nemotron | 🟡 Low |
| 9 | `slugify` collisions (e.g. "The Pour House" vs "Pour House" → `pour-house`) break DOM ids (`hours-${id}`) | big-pickle | 🟡 Low |
| 10 | Backfill opens files without context managers; write+append is fragile | mimo | 🟡 Low |
| 11 | `next_page_url` `startswith("next")` can chase non-pagination links; no page cap | big-pickle, nemotron | 🟡 Low |
| 12 | `--source` filter doesn't apply to curated venues | big-pickle | 🟡 Low |
| 13 | Address format inconsistency (`611 E Main St` vs `101 E Main St, Bozeman`) makes city extraction fragile | big-pickle, nemotron | 🟡 Low |
| 14 | No retry/backoff in discovery `fetch()`; only 0.5-0.7s sleep | nemotron | 🟡 Low |
| 15 | Unused: `CITY_KEYWORDS`, `seed_name` param; typo'd sentinel `"find yourhappy hour"` | nemotron, big-pickle | 🟢 Nit |

---

## Checked and rejected (false positives)

| Claim | Why rejected |
|---|---|
| `NoneType` crash in `parse_mthappyhour_dir` (mimo #1) | Line 193-194 guards with `if card else ""` — no crash path |
| Business-hours "Closed" days lost (nemotron #3) | Verified output keeps them: `Rialto: Mon-Thu Closed, Fri-Sat 7pm-Close` |
| `normalize_hours` corrupts business hours (nemotron #5, big-pickle #5) | Ran it: `Mon-Thu 11am-12am, Fri-Sat 11am-2am` passes through unchanged |
| Stale `venue_count`/`venue_ids` in config (nemotron #7/#26, big-pickle) | Those fields only exist in the synthetic review context I generated, not in the real config |
| Cross-city same-street false duplicates via `norm_address` (nemotron #1 variant) | `is_duplicate` address path requires exact normalized-address key match; real risk is the name-only path (#1 above) |

---

## Verdict

**Mergeable with fixes.** The architecture is sound and the UI work (expandable panels, a11y attributes, dark mode) is well-reviewed. Three things should be fixed before or right after merge:

1. **Fix `is_duplicate` name-only match** (blocks the feature's stated purpose)
2. **Merge the Wild Rye / Wildrye duplicate** (visible data bug on the live site)
3. **Stop hardcoding `city="Bozeman"`** in `parse_page` (wrong Maps links for non-Bozeman venues)

XSS escaping (#4) is worth doing as a fast follow-up since it hardens a pre-existing pattern.

*Raw reviews saved in `/tmp/mcr-prs/reviews/` (mimo-v2.5-free.md, nemotron-3-ultra-free.md, big-pickle.md).*
