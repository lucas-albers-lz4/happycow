# UI Prototype Sketches

Throwaway HTML mockups exploring new visual directions for Happy Cow. Not wired into the app — these are for comparison and iteration (see issues #79–#83).

**Open the [gallery](index.html) to compare all variants side-by-side.** Start with Wave D (#85) or Wave C (synthesis).

## Wave D — mobile wireframe capture (#85)

| Sketch | Stance | Key ideas |
|---|---|---|
| [013-mobile-deal-first](013-mobile-deal-first/) | Locked mobile composition | Phone frame ~380px, ending-soonest pin, Pick for me / What they're having, compact deal rows, vibe chips, games in tab bar |
| [014-mobile-dense-rows](014-mobile-dense-rows/) | Condensed venue format | Same shell as 013; left-aligned name / deal / hours·place; no chevron; compact time status |

## Wave C — synthesis (feedback-driven)

Deal-First as the spine. Vibe / Spin / Cow-pare / pub crawl folded in without stealing the main job.

| Sketch | Stance | Key difference |
|---|---|---|
| [011-form-follows-fun](011-form-follows-fun/) | Tabs carry extras | Bottom: Deals · Vibe · Spin · More. Compare button on cards → tray. Crawl in More. |
| [012-deal-plus-pocket](012-deal-plus-pocket/) | Quieter chrome | "Spin the herd" on home. 3 tabs (Deals · Vibe · More). Tiny ⇄ compare. Crawl in More. |

## Wave A — home-screen directions (#80–#82)

| Sketch | Stance | Key ideas |
|---|---|---|
| [001-deal-first](001-deal-first/) | Utilitarian / action-first | Pinned "ending soonest" card, decision shortcuts, multi-select vibe chips, games demoted to bottom tab bar, herd counter |
| [002-mood-board](002-mood-board/) | Playful / vibe-first | Mood cow-faces, Sacred Cow of the Day, happy-hour heatmap, streak banner, crowd moo-ters |
| [003-grazing-map](003-grazing-map/) | Spatial / exploration | SVG Bozeman map with cow pins, distances in moos, cowbell countdowns, Cow Path crawl planner |

## Wave B — remaining ideas (#83)

| Sketch | Idea | Key ideas |
|---|---|---|
| [004-the-herd](004-the-herd/) | The Herd | Group consensus voting with mini cow avatars + live tallies |
| [005-udderly-broke](005-udderly-broke/) | Udderly Broke + Cow-culator | Milk-money meter + cheapest-first tab estimate chart |
| [006-mooch-list](006-mooch-list/) | Mooch List | Value leaderboard podium + cowbell ratings |
| [007-cow-pare](007-cow-pare/) | Cow-pare | Side-by-side venue comparison with cow-crowned winner |
| [008-mooty-booty](008-mooty-booty/) | Moo-ty Booty | Spin-the-wheel over live venues |
| [009-game-linkage](009-game-linkage/) | Game → deals | Quiz result auto-applies a vibe filter to the deal list |
| [010-day-planner](010-day-planner/) | Day planner | Day-of-week + time slider recomputes statuses |

### Explicitly not sketched (with reason)

| Idea | Verdict |
|---|---|
| Cowbell Countdown (6) | Already in [003](003-grazing-map/) — portable pattern, no standalone sketch |
| Crowd Moo-ter (10) | Already in [002](002-mood-board/) — persistence is a production concern |
| Rumor Mill (13) | Rejected for now — needs user-generated / anonymous tip storage we don't have; note dependency and skip |

## Conventions

- One variant per directory: `NNN-name/index.html` + `README.md`
- Self-contained HTML (inline CSS/JS, no build step)
- Real venue subset + cream/leather theme tokens
- Demo clock (`const NOW = new Date('2026-08-05T17:12:00')`) so live/soon/closed statuses render deterministically
- Dark mode toggle on every variant

## Verification

Open `sketches/index.html` via a local static server, click through Wave A and Wave B, and exercise each sketch's primary interaction (filters, votes, spin, day picker, etc.).
