# Variant: Udderly Broke (+ Cow-culator)

## Design stance
Lead with money anxiety — a milk-money meter filters venues by max drink price, and a Cow-culator bar chart estimates the herd's tab cheapest-first.

## Key choices
- Layout: budget panel (meter + slider + drinks/herd inputs + chart) → filtered venue list
- Interaction: slider sets $/drink ceiling; chart recomputes tab = drink × drinks × people
- Color: green→gold→red meter gradient; over-budget cards fade

## Trade-offs
- Strong at: "what can I actually afford" — immediately useful
- Weak at: prices are sketch-curated (many live specials are "$1 off" with price 0)

## Best for
- A filter/mode layered onto Deal-First, not a standalone home
