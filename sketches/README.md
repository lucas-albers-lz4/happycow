# UI Prototype Sketches

Throwaway HTML mockups exploring new visual directions for Happy Cow. Not wired into the app — these are for comparison and iteration (see issue #77).

## Variants

| Sketch | Stance | Key ideas |
|---|---|---|
| [001-deal-first](001-deal-first/) | Utilitarian / action-first | Pinned "ending soonest" card, decision shortcuts, multi-select vibe chips, games demoted to bottom tab bar, herd counter |
| [002-mood-board](002-mood-board/) | Playful / vibe-first | Mood cow-faces, Sacred Cow of the Day, happy-hour heatmap, streak banner, crowd moo-ters |
| [003-grazing-map](003-grazing-map/) | Spatial / exploration | SVG Bozeman map with cow pins, distances in moos, cowbell countdowns, Cow Path crawl planner |

## Conventions

- One variant per directory: `NNN-stance-name/index.html` + `README.md`
- Self-contained HTML (inline CSS/JS, no build step)
- Real venue data from `data/happy_hour_data.json` (subset), current theme tokens
- Demo clock (`const NOW = new Date(...)`) so live/soon/closed statuses and countdowns render deterministically
- Interactive: filters, tabs, mood board, heatmap, map pins all work in-browser
- Dark mode toggle on every variant

## Verification

Each variant was checked in-browser before being added: layout screenshot review, status-engine correctness (hours parser handles `Daily 4-6pm` style ranges), and interaction tests (filtering, tab switching, path planner).
