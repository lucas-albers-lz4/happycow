# Variant: Mobile deal-first (Claude wireframe v2)

## Design stance
Locked **mobile-first** composition from the Claude brainstorm reorder — deal urgency first, games demoted to the tab bar, dense scan list instead of card stacks.

**Source:** [issue #85](https://github.com/lucas-albers-lz4/happycow/issues/85) · [Claude share](https://claude.ai/share/f0d69042-0408-42d8-abb3-87c4caa23cf8) · wireframe `happycow_reordered_wireframe_v2.html`

## Regions (top → bottom)

| Region | Content |
|---|---|
| Header | Brand (“Happy cow”) + `4/30 collected` badge |
| Pinned card | Ending soonest — venue, deal, closes-in countdown, area |
| Shortcuts | **Pick for me** · **What they're having** |
| Vibe chips | All vibes · Patio · Craft beer · Dive |
| Venue list | Compact rows: name + special, hours · area, chevron |
| Tab bar | Deals · Horoscope · Split tab · Cow quiz |

## vs sketch 001

- Explicit **phone frame (~380px)** — this is the mobile capture
- **Compact rows**, not stacked cards
- Wireframe copy: Pick for me / What they're having; tabs Horoscope / Split tab / Cow quiz
- Herd counter in chrome, not a separate surface

## Non-goals
- Desktop layout
- Real herd persistence / live social “what they're having”
- Full Horoscope / Split / Quiz screens (stubs only)

## Verification
Open at phone width (or use the built-in frame). Confirm ending-soonest countdown, chip filtering, shortcut toasts, fixed Deals-default tab bar.
