# 🐄 UX polish + data completeness round (7 items)

Bundle of small UX fixes and a data-completeness ask. All verified against the live code:

## 1. Capitalize "what" → "What" on first feature link
`index.html:50` renders `🐄what` — should be `🐄What`.

## 2. Dark mode: some buttons' text is invisible
Confirmed in browser (dark mode screenshot): the feature-button row (`🐄What`, `♈HH Horoscope`, `🐄Moo`, `🧮Tip Calc`, `❓What Cow R U?`) is **nearly invisible** — `.feature-btn` sets no `color`, so the UA default dark text sits on the dark `var(--card)` background. Venue tags (`downtown`, `dive`, ...) are also dim (`--cow-spot-2` brown on dark). Fix: explicit `color: var(--text)` (+ `font: inherit`) on `.feature-btn`; brighter tag color in dark mode.

## 3. HH Horoscope: tapping the presented drink should jump to the bar offering it
`renderHoroscope()` currently shows a random drink string (e.g. "$4 PBR") with no link. It should pick a **real special from the venue data** and be tappable → `scrollToVenue(venue.id)`.

## 4. Rename Tip Calc → Cow Calc (keep the 🧮 abacus icon)
Button `🧮 Tip Calc` and modal title `🧮 Tip Calculator (with attitude)` become **Cow Calc** (same function, same icon).

## 5. Business hours for all businesses
9 venues lack `business_hours` (of 56). 8 were researched from their own sites/listings:
- Devils Toboggan — Bar: Sun-Thu 4-11pm, Fri-Sat 4pm-Midnight (Kitchen Sun-Thu 4-8pm, Fri-Sat 4-10pm)
- Finks Deli — Mon Closed, Tue-Sat 10am-6pm, Sun 10am-4pm
- Revelry — Mon-Fri 11am-10pm, Sat-Sun 10am-10pm
- The Bacchus Pub — Mon-Thu 11am-9:30pm, Fri-Sat 11am-10pm, Sun 11am-9:30pm
- Tanoshii — Tue-Sat 4pm-close (Instagram: "Tues-Sat 4-close")
- The Haufbrau — Sun-Thu 11am-2am, Fri-Sat 1pm-2am (Yelp)
- The Molly Brown — Daily 11am-2am (Yelp)
- Stacey's Old Faithful — Mon Closed, Tue 4-9pm, Wed-Sun 11am-close (own site)
- **The Filling Station — hours not published anywhere accessible** (live-music venue; BoZone shows show times only). Document as a known gap; the scraper can try their Facebook page on the next CI run.

## 6. "Closed" status not consistently highlighted as a red button
Status pills have `.active` (green) and `.ending` (gold) but **no `.closed` class** — closed venues get no red highlight. Venue-card `.hh-status.closed` is a pale pink that doesn't read as a red button in either mode. Add a `.status-pill.closed` red style + class in `renderStatusBar`, and strengthen `.hh-status.closed` to a consistent red.

## 7. Rename "Closed" label to something funny and short
Brainstorm (short, friendly, cow-adjacent):
- **"Moo-ver"** (moved on) — primary pick
- "Grazed" / "Grazing"
- "Herd you later"
- "Pasture'd"
- "Nap time"
- "Over" / "Done" (plain but short)

Happy to swap; going with **Moo-ver** unless objected. Applies to the venue-card status text and the aria-label.
