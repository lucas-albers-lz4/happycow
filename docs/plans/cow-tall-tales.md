# Cow Tall Tales — Implementation Plan

**Status:** In review (classifier + humor harden pass)
**Branch:** `feat/cow-tall-tales`
**Feature:** Any beef-adjacent happy-hour special gets a subtle cow-name link that opens a
unique, deterministic, and completely ridiculous story about the cow whose unluck or bad
life choices brought this deal into existence.

## Why (the pitch)

The app is run by cows. The cows have lore (impostors, Cow of the Day, horoscopes). But
the deals themselves are currently lore-free. Every beef special deserves an origin story:
*bad things happened to a cow, and that is why your burger is cheap.*

## Detection (what counts as beef)

`isBeefSpecial(special)` in `assets/js/tales.js`, matching against `item + description`.
**Order is load-bearing** (also documented in `.cursor/rules/cow-tall-tales.mdc`):

1. **Fake beef → not beef FIRST:** Beyond, Impossible, veggie, plant-based, mushroom,
   portobello; `vegan`/`vegetarian` only when not preceded by `non-`/`non `
   ("non-vegetarian ribeye" stays beef). Plant-based CFS-style names die here.
2. **Override → beef:** `chicken-fried steak` / `country-fried steak` (hyphen or spaces).
   Wins even though the string contains `chicken` (after fake-beef is cleared).
3. **Competing protein → not beef:** chicken, turkey, fish, **catfish** (explicit —
   `\bfish\b` does not match it), salmon, shrimp, crab, cod, tilapia, tuna, lamb, duck.
   Mixed menus ("Catfish or Birria", "beef and chicken options") get **no** tale.
4. **Else positive keywords:** `beef, burger, steak, ribeye, sirloin, brisket, wagyu,
   kobe, short rib, prime rib, birria, carne, pastrami, philly, cheesesteak,
   corned beef, bison`
5. `pork` is deliberately NOT a negative ("3 beef & pork meatballs" is beef)

**Live data note:** Bourbon's generic "Tacos" (catfish *or* birria) is correctly
**out**. Clear beef specials across the other venues remain **in**.

## Story generation (why procedural)

Specials are LLM-extracted on every scrape (`scripts/scraper/extract.py`); curated
story fields in `data/` would be overwritten or orphaned by the next scrape. The app
already has a deterministic seeded-random idiom (`seededRandom` Park-Miller LCG +
string hash, used by nicknames and Cow of the Day). So:

- Seed = `hash(venueId + '::' + item)` — **stable per special** (does NOT use the day
  seed: the story belongs to the deal, not to the date)
- The seed picks one cow name (from a dedicated `TALE_COWS` pool, disjoint from Cow of
  the Day) and one story template, then interpolates `{cow}`, `{item}`, `{venue}`
- Full story **text** is unique across live specials via interpolation; cow+template
  pairs may recur (small pool) — that is expected
- Zero pipeline / LLM cost at runtime

### Template quality rules (enforced by tests)

- Every template includes `{cow}`, `{item}`, `{venue}`
- Copy must tolerate event names (`Steak Night`), priced items (`$8 Steak Frites`),
  and plurals — prefer "the {item} special/deal", "tonight's {item}", "ordering the
  {item}"
- Banned phrases live in `BANNED_TEMPLATE_PHRASES` and are asserted in
  `tests/tales.test.mjs` (sunny / medal / models / 10% off / bites of / guards /
  supervising / flat top)
- Awkward-item stress test renders every template against event/priced strings and
  rejects edible-only residue

## UI

- **Link:** in `render.js`, beef special rows render a subtle muted button under the
  description: `🐄 {cow}'s tale` (small, `var(--text-dim)`, dotted underline on hover;
  dark-mode safe via CSS vars)
- **Modal:** `#tale-modal` in `index.html` (same `.modal-overlay` pattern; generic
  close/backdrop binding in app.js covers it)
  - Title: cow name; subtitle: `as told by the {item} at {venue}`; body: the story
  - Body rendered via `textContent` (no HTML injection)
- **Wiring:** delegated click handler seeds from `data-tale-venue` / `data-tale-item`
  (does not require a live `specials.find` match — avoids silent no-ops)

## Files

| File | Change |
|---|---|
| `assets/js/tales.js` | `HappyCowTales`: classifier + story engine + banned-phrase list |
| `assets/js/render.js` | tale link in special rows (beef only), `esc()`'d cow name |
| `assets/js/app.js` | delegated `.tale-link` handler; modal render from dataset |
| `index.html` | `tale-modal` markup; `<script>` for tales.js; cache-bust |
| `assets/css/style.css` | `.tale-link` / `.tale-story` styles |
| `tests/tales.test.mjs` | classifier edges, determinism, live uniqueness, template quality, XSS |
| `.cursor/rules/cow-tall-tales.mdc` | agent rule so classifier/template invariants don't regress |
| `docs/plans/cow-tall-tales.md` | this plan |

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
- Runtime LLM humor generation (templates only — keep the gag $0)
