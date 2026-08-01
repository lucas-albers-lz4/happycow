# Deferrable hardening from the Zen MCR

The 3-model Zen MCR (mimo-v2.5-free, nemotron-3-ultra-free, big-pickle) on the PR stack (#7/#8/#10) flagged a set of **deferrable** items — non-blocking, but worth cleaning up. They were deliberately deferred to keep the stack mergeable; this issue tracks them.

## Items to fix

### Discovery pipeline (`scripts/discover_venues.py`)

1. **Pagination safety** — `next_page_url` uses `label.startswith(("next", "older posts"))` which can chase non-pagination links ("Next event", "Next: read more"), and there is **no page cap** — a site that cycles `?page=N` would loop forever (only self-link equality is guarded). *[big-pickle, nemotron]*
2. **No retry/backoff in `fetch()`** — single attempt for both discovery and backfill; transient 429/5xx kills the run. The main scraper already has tenacity-based retry. *[nemotron]*
3. **Slugify collisions** — "The Pour House" and "Pour House" both → `pour-house`; a duplicate id breaks DOM ids (`hours-${id}`) and `aria-controls` targeting. Should guarantee uniqueness (append street number or counter). *[big-pickle]*
4. **`--source` doesn't filter curated venues** — `--source mthappyhour-dir` still fetches/parses all curated pages, contradicting documented usage. *[big-pickle]*
5. **Dead code** — unused `CITY_KEYWORDS` constant; `seed_name` param of `parse_page` unused (after the city refactor it's only a dict fallback — clarify); typo'd sentinel `"find yourhappy hour"` (should be `"find your happy hour"`). *[nemotron, big-pickle]*

### Backfill (`scripts/backfill_business_hours.py`)

6. **File handles** — `json.load(open(...))` / `json.dump(data, open(..., "w"))` without context managers; the write+append-newline dance is fragile. *[mimo, big-pickle]*
7. **Retry/backoff** — same as #2.

### Frontend (`assets/js/app.js`, `assets/css/style.css`)

8. **`prefers-reduced-motion`** — the `hours-in` panel animation should be disabled for users who request reduced motion. *[nemotron]*
9. **Hardcoded dark-mode color** — `.hours-value { color: #f2e6d3 }` should use a CSS variable like the rest of the theme. *[nemotron]*
10. **`wirePanelToggle` defined per card** — tiny closure-per-venue; hoist to module scope. *[nemotron]*

### Other

11. **Website regex over-excludes** — `(?!.*(?:facebook|...))` excludes any URL *containing* those strings anywhere (e.g. `example.com/facebook-page`); should match domain-level only. *[nemotron]*

## Out of scope (accepted)

- Retry in the main scraper already exists (tenacity).
- Address-format inconsistency across venues is a data-normalization follow-up, not code.
- `INTER_REQUEST_SLEEP` tuning — current values are fine for mthappyhour.

## Acceptance criteria

- Discovery run (dry-run) still finds 0 new venues after re-running on current data (idempotent, no dupes, no regressions).
- Pagination loop is bounded (max pages); `startswith` matching tightened.
- Slugified ids are unique even for colliding names.
- `--source` restricts curated parsing too.
- Backfill uses context managers and retries transient failures.
- No dead code; sentinel typo fixed.
- Frontend honors `prefers-reduced-motion`; dark-mode color uses a variable; toggle wiring hoisted.
