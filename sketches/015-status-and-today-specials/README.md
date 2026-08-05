# Variant: Status clarity + today’s day specials (015)

## Design stance
Fork of [014](../014-mobile-dense-rows/) / live dense rows. Same phone shell; two readability fixes before promoting to production.

## What’s new vs 014 / live

| | 014 / live | 015 |
|---|---|---|
| HH over | Right-side `—` (easy to miss) | **`over`** in red |
| Day specials | Flat list; headline = `specials[0]` | Green `.special-row.today`; headline prefers today’s day deal |
| Expand | Toast only | Tap expands specials (Bridger auto-open for demo) |

## Demo clock
**Monday Aug 3, 2026 · 5:12pm**

- Monday specials (Bridger Cod Cakes, Filling Station wings, Spirits Men’s night, Wild Rye Mule Monday) light green.
- `Mon-Fri 3-5pm` / `Daily 3-5pm` windows are **over** (Copper, Shine).
- Live windows still show green countdowns (`Daily 4-6pm`, etc.).

## Verification
1. Compare with [014](../014-mobile-dense-rows/) in the gallery.
2. Confirm red **over** on closed rows (not an em dash).
3. On Bridger expand: Monday row green; Tuesday+ plain.
4. Bridger collapsed headline should be Monday Cod Cakes (not whatever sat at `[0]` only by luck — here `[0]` is Monday anyway; check Filling Station / Spirits for prefer-today).
