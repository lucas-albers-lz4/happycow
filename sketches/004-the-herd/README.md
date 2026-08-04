# Variant: The Herd

## Design stance
Happy hour is often a group decision. Put the herd on the screen — mini cow avatars vote, tallies crown a consensus venue.

## Key choices
- Layout: gradient hero with friend avatars → tappable venue list with vote bars
- Interaction: select a friend, tap a venue to cast their vote; auto-advances to next undecided friend; crown on majority winner
- Color: existing cream/leather tokens; green winner ring

## Trade-offs
- Strong at: group nights, resolving "I don't care / you pick"
- Weak at: needs shared session state in production (sketch is single-device demo)

## Best for
- A feature layer on Deal-First or Mood Board, not a whole home-screen replacement
