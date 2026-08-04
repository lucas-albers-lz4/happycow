# Variant: Grazing Map

## Design stance
Happy hour is a spatial problem — where do I walk to? Put the venues on a stylized map of downtown Bozeman with cows as pins, distances in "moos", and a tap-to-plan bar crawl.

## Key choices
- Layout: SVG map card on top (streets: Main, Babcock, Grand, Mendel, Russian, Willson, Riddle), crawl planner bar, venue list below
- Typography: system stack; tiny SVG street labels with halo (paint-order stroke) for legibility over grid lines
- Color: existing tokens; cream map background, leather-brown streets, red dashed crawl route with numbered stops
- Interaction: tap cows to pin; 2+ pins draws a dashed path + numbered stops + "X moos · Y min walk"; clear button; cowbell 🔔 jiggle animation on cards opening within 15 min; dark mode

## Trade-offs
- Strong at: spatial answers ("what's near me / walkable"), the Cow Path planner is a genuinely useful group feature
- Weak at: needs distance/geolocation data that doesn't exist yet (moos are mocked); SVG map is hand-drawn, not real geography; most ambitious to build

## Best for
- A stretch feature, not the next PR — the map + moo-distance need a data model first; the cowbell countdown is trivially portable to the other variants
