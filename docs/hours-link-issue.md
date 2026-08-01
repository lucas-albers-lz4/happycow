## Feature Request

Each venue card currently shows two action links when expanded: **📍 Directions** and **🔗 Website**. Add a third link — **🕐 Hours** — that, when tapped, expands an inline panel showing the venue's happy hour window.

## Why

The happy hour window (e.g. "Daily 4-6pm") is currently only shown as small dim text in the card header. Users hunting for a specific deal window have to squint at the summary line. A dedicated, tappable Hours link makes the window prominent and easy to check at a glance, and gives a natural place for future hours-related detail (secondary windows, notes) to live.

## Acceptance criteria

1. Expanded venue card shows a **🕐 Hours** link next to Directions / Website.
2. Tapping **Hours** expands an inline panel (gold-accented, matching the cow theme) showing:
   - a small "HAPPY HOUR" label
   - the venue's `hours` string in bold (e.g. "Daily 4-6pm")
   - any optional `notes` field if present in the data
3. Tapping again collapses it.
4. Only renders the Hours link when the venue actually has `hours` data (newly added venues awaiting a scrape show no link, same as the conditional Website link).
5. Works in dark mode.
6. Accessible: `aria-expanded` / `aria-controls` on the toggle, `hidden` attribute on the panel.
