# Venue Closure Check — 2026-08-16 14:16 UTC

Checked 53 venues. **5 flagged for review.**

| Venue | Signal |
|---|---|
| Applebee’s Bozeman | `SITE_DEAD x5 (https://www.applebees.com/en/restaurants-bozeman-mt/1108-north-7th-avenue-91019)` |
| The Bunkhouse Brewery | `SITE_DEAD x5 (https://www.bunkhousebrewery.com/)` |
| Tanoshii | `SITE_DEAD x5 (https://tanoshiimt.com/)` |
| Bar 3 BBQ and Brewery | `SITE_DEAD x5 (https://bar3bbq.com/)` |
| Rialto Bar – Burn Box | `SITE_DEAD x5 (https://www.larkbozeman.com/)` |

No venue is auto-removed — review the flags, then update data manually.
To remove a confirmed-closed venue:
  python scripts/remove_venue.py <id> --reason "closed ..."
  (records a tombstone in data/state/removed_venues.json so discovery won't re-add it)
