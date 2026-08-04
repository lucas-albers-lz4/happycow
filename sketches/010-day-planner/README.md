# Variant: Day Planner

## Design stance
Happy hour isn't only a "right now" problem — people plan Thursday at 5 and weekend crawls. A day + time picker recomputes live/soon/closed from the existing hours grammar.

## Key choices
- Layout: 7-day strip → time slider → live/soon/closed stats → sorted venue list
- Interaction: injectable `now` (day offset + minutes); demo defaults to Wed 5:12pm
- Feasibility: matches issue #83 — `hhStatus` already takes injectable now; no data-model change

## Trade-offs
- Strong at: "is this even happening Thursday?" planning; complements Mood Board heatmap
- Weak at: doesn't show *which* specials change by day (data is mostly daily windows)

## Best for
- A control on the home screen of Deal-First or Mood Board
