# Architecture Refactor Plan — Non-Fragile Scraping + Calculations

Issue: [#30](https://github.com/lucas-albers-lz4/happycow/issues/30) · Status: proposed · Date: 2026-08-02

Priorities are ordered by **user-facing risk**, not size. Every phase ends with the repo in a working state (shippable increments, not a big-bang rewrite).

---

## Phase 1 — Hours parser + calculation tests (fixes a live bug)

**Why first:** The Bay showed "closed" at 8:41pm during its live 8–9pm window. The hours/status logic is the most user-visible code in the app and it's untested.

**Tasks**
1. Define the hours grammar explicitly (one canonical form):
   - `Daily 3-5pm` · `Mon-Fri 4-7pm` · `Fri 12-8pm` · `Mon 3-close`
   - Multi-window: `Daily 3-5pm & 8-9pm` (The Bay)
   - Secondary windows: `Daily 3-6pm, Fri-Sat 10pm-12am` (Santa Fe), `Daily 3-6pm & 9pm-close` (Pour House)
   - Midnight crossing (`10pm-12am`, `9pm-close`) and `12am`/`12pm` endpoints
2. Extract parsing into a pure module `assets/js/hours.js` (or `app.js` + a node-testable twin) with one `parseHours(str) → [{days, startMin, endMin, isClose}]` — used by `isHHLive`, `getStartMinutes`, `timeUntil`, and the "Opens in X" badge.
3. Fix known gaps: multi-window liveness (live if ANY window is active), `close` → venue close time (business_hours), midnight-crossing math.
4. Unit tests (`node --test`): fixture matrix of every hours string currently in `data/happy_hour_data.json` + edge cases. Assert: `isHHLive` at representative times, `timeUntil`, day-range wrapping (Sun-Thu).
5. Update the extraction prompt (`prompts/extract_happy_hour.txt`) to emit the canonical grammar and add a **validator that rejects non-parsing hours strings** at scrape time.

**Success criteria:** every distinct hours string in the live data parses; the fixture matrix is green; The Bay is `live` at 8:30pm; Dave's "3-close" no longer `unknown`.

---

## Phase 2 — Shared constants + contamination guard

**Why:** `AGGREGATOR_HOSTS` is copy-pasted in 3 scripts (already hand-synced once). mthappyhour pages were caught carrying other venues' data 3× — the scraper would LLM-extract contaminated text as fact.

**Tasks**
1. `scripts/common.py`: single source for `AGGREGATOR_HOSTS`, path constants, `load_json/save_json`, user agents. Import from scrape/discover/closure/remove scripts; delete the copies.
2. Contamination guard in `scrape_happy_hours.py` `gather_page_text`: a page only counts as a venue's own entry if the venue's **name AND street address** appear in the trimmed text (address match: street number + street name). Pages failing the check are logged and skipped (prev-data fallback keeps existing entries).
3. Provenance: add `source` URL per special in the extraction schema (already implicitly in page text; make it explicit in the record) so a human can audit any entry back to its page.

**Success criteria:** zero duplicated constant sets; a synthetic contaminated page (venue A's content under venue B's URL) is rejected in a unit test; every special in the data carries a source URL.

---

## Phase 3 — Data schema + CI validation

**Why:** a bad merge/LLM output ships broken JSON straight to GitHub Pages; config and data can silently drift; new fields get dropped by `venue_to_site_record()`.

**Tasks**
1. `schema/venue.schema.json` (JSON Schema): required keys, types, `hours` grammar regex, `price` semantics rule (price 0 must have discount wording in description, else `notes` says free), `id` uniqueness, allowed categories.
2. `scripts/validate_data.py`: checks — JSON parses; schema valid; id-set parity between config and data; no venue without specials **and** without notes (the 100%-coverage invariant); nicknames present; hours strings parse via the Phase-1 parser.
3. CI: add a `Validate data` step in `scrape.yml` **before** the commit step (fail the job on invalid output). Also run it on PRs (a small `ci.yml` with `on: pull_request`).
4. `venue_to_site_record()`: build from a whitelist + carry-through list so new fields can't silently vanish (regression test for notes/nickname).

**Success criteria:** invalid data cannot reach the commit step; PR CI blocks schema-violating changes; the coverage invariant is enforced by CI, not by me.

---

## Phase 4 — State consolidation + data-flow documentation

**Why:** 4 state artifacts with different writers (`scrape_cache.json`, `closure_state.json`, `removed_venues.json`, `closure_report.md`); the pipeline's shape is only in README prose.

**Tasks**
1. Consolidate runtime state under `data/state/`: `scrape_cache.json`, `closure_state.json`, `removed_venues.json` — one directory, one writer convention (write-atomic: tmp + rename), one loader in `common.py`.
2. `docs/data-flow.md`: the full pipeline (config → discovery → scrape → merge → closure check → validate → commit → Pages), who writes what, fallback semantics (LLM fail → keep previous), and the manual interventions (remove_venue, known-gap notes).
3. Update README's pipeline section to point at the doc.

**Success criteria:** one state directory; the data-flow doc matches the code (walk through it once end-to-end); no writer touches a file it doesn't own.

---

## Phase 5 — Module split + CI hardening

**Why:** `scrape_happy_hours.py` ~650 lines; CI workflow 30-min timeout for discovery+scrape+closure+commit with no per-step failure isolation beyond a couple of `|| true`s.

**Tasks**
1. Split the scraper into `scripts/scraper/`: `fetchers.py` (HTTP + trim), `extraction.py` (LLM call + pydantic), `merge.py` (`venue_to_site_record` + cache), `cli.py`. Public behavior unchanged.
2. CI: per-step timeouts, explicit failure classification (transient retry vs permanent → flag in closure report), and a `workflow_dispatch` convenience that skips discovery.
3. Optional stretch: a `--venue`-scoped scrape for manual re-runs is already supported — document it.

**Success criteria:** scraper modules import cleanly; the CI job time is bounded per-step; a one-line change to shared constants requires touching exactly one file.

---

## Explicit non-goals (v1)
- No backend/database — static JSON + Pages stays.
- No rewriting the LLM extraction into rules-only (the LLM handles unstructured menus; the guard + schema contain it).
- No multi-city expansion.

## Suggested execution order
Phase 1 → 3 (both unblock correctness/CI safety) → 2 → 4 → 5. Phases 1, 3, and 4 are independently shippable PRs.
