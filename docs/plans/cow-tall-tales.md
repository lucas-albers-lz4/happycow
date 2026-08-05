# Cow Tall Tales — Implementation Plan

**Status:** Proposed
**Branch:** `feat/cow-tall-tales`
**Feature:** Any beef-adjacent happy-hour special gets a subtle cow-name link that opens a
unique, deterministic, and completely ridiculous story about the cow whose unluck or bad
life choices brought this deal into existence.

## Why (the pitch)

The app is run by cows. The cows have lore (impostors, Cow of the Day, horoscopes). But
the deals themselves are currently lore-free. Every beef special deserves an origin story:
*bad things happened to a cow, and that is why your burger is cheap.*

## Detection (what counts as beef)

`isBeefSpecial(special)` in a new pure module `assets/js/tales.js`, matching against
`item + description` (lowercased, word-boundary regex):

- **Positive words:** `beef, burger, steak, ribeye, sirloin, brisket, wagyu, kobe,
  short rib, prime rib, birria, carne, pastrami, philly, cheesesteak, corned beef,
  bison` (bison counts — she's cow-adjacent and the stories write themselves)
- **Negative words:** `veggie, vegan, vegetarian, plant, chicken, turkey, fish, salmon,
  shrimp, crab, lamb, mushroom, portobello` — a negative word anywhere suppresses the
  tale even if a positive word is present ("chicken burger" is not beef)
- `pork` is deliberately NOT a negative ("3 beef & pork meatballs" is beef)

**Verified against live data (2026-08-05):** 11 beef specials across 8 venues
(bitterroot-bistro ×3, bourbon ×1 (birria), brigade ×1, the-bay ×3, the-filling-station
×1, spectators-bar-and-grill ×2). Correctly rejected: "Craft Beer Sliders" (no beef
wording), "Nana Rose's Meatball Dinner" (no beef wording), "Breakfast sandwich or
burrito" (no beef wording).

## Story generation (why procedural)

Specials are LLM-extracted on every scrape (`scripts/scraper/extract.py`); curated
story fields in `data/` would be overwritten or orphaned by the next scrape. The app
already has a deterministic seeded-random idiom (`seededRandom` Park-Miller LCG +
string hash, used by nicknames and Cow of the Day). So:

- Seed = `nicknameSeed-style hash(venueId + '::' + item)` — **stable per special** (does
  NOT use the day seed: the story belongs to the deal, not to the date)
- The seed picks one cow name (from a dedicated `TALE_COWS` pool) and one story template
  (from ~26 templates across three motifs: **bad luck**, **bad life choices**, and
  **general ridiculousness**), then interpolates `{cow}`, `{item}`, `{venue}`
- Result: every beef special gets its own fixed, unique story; future scrapes that add
  new beef specials get stories automatically; no data/pipeline changes

## UI

- **Link:** in `render.js`, beef special rows render a subtle muted button under the
  description: `🐄 {cow}'s tale` (small, `var(--text-dim)`, dotted underline on hover;
  dark-mode safe via CSS vars)
- **Modal:** new `#tale-modal` in `index.html` (same `.modal-overlay` pattern; the
  generic close/backdrop binding in app.js covers it with zero extra wiring)
  - Title: cow name; subtitle: `as told by the {item} at {venue}`; body: the story
  - Body rendered via `textContent` (no HTML injection)
- **Wiring:** delegated click handler in app.js on `#venue-list` for `.tale-link`
  (checked before the `.venue-toggle` branch), looks up the venue+special from
  `data-tale-venue` / `data-tale-item`, renders the modal

## Files

| File | Change |
|---|---|
| `assets/js/tales.js` | **NEW** — `HappyCowTales`: `isBeefSpecial`, `taleFor(venueId, special, venueName)`, cow pool, template pool, string hash + LCG (self-contained) |
| `assets/js/render.js` | tale link in special rows (beef only), `esc()`'d cow name |
| `assets/js/app.js` | delegated `.tale-link` handler; modal render |
| `index.html` | `tale-modal` markup; `<script>` for tales.js (before render.js); version bumps `?v=20260805` |
| `assets/css/style.css` | `.tale-link` styles + dark variant |
| `tests/tales.test.mjs` | **NEW** — classifier cases, determinism, cross-venue distinctness over live data, no unrendered `{slots}`, `esc` applied in card HTML |

## Verification

```bash
node --test                              # includes tests/tales.test.mjs (auto-discovery)
node --check assets/js/tales.js && node --check assets/js/render.js && node --check assets/js/app.js
python3 scripts/validate_data.py         # unchanged data, must still pass
node scripts/validate_hours.mjs data/happy_hour_data.json
```

## Out of scope

- Stories for non-beef specials (drinks, chicken, fish) — future wave if the cows demand it
- Data-side story fields (would die on the next scrape — see above)
- Server-side anything (static site; all client-side)
