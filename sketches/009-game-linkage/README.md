# Variant: Game → Deals linkage

## Design stance
Games shouldn't be a cul-de-sac. Quiz/horoscope results map to a vibe tag group and auto-filter the deal list — whimsy that pays off.

## Key choices
- Layout: quiz card on top → active-filter banner → filtered venue list
- Interaction: answer maps to a cow mood → tags applied; day-seeded "herd cow" can also apply with one tap
- Feasibility: pure client-side mood→tag map (matches issue #83 follow-up)

## Trade-offs
- Strong at: connects personality content to the actual job (finding a drink)
- Weak at: mood→tag curation can feel arbitrary; needs a short quiz that doesn't block the list

## Best for
- Folding into Deal-First's demoted games tab so results dump you back into deals
