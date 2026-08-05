# Venue Closure Check — 2026-08-05 03:12 UTC

Checked 55 venues. **0 flagged for review.**

| Venue | Signal |
|---|---|
| _none_ | |

No venue is auto-removed — review the flags, then update data manually.
To remove a confirmed-closed venue:
  python scripts/remove_venue.py <id> --reason "closed ..."
  (records a tombstone in data/state/removed_venues.json so discovery won't re-add it)
