"""Record building: config venue + extraction -> site record.

Phase 5 of issue #30 — extracted from scripts/scrape_happy_hours.py.
Carry-through by construction: new curated config fields can never silently
vanish from the site data again.
"""

from __future__ import annotations

# Keys that exist in config/venues.json but must never appear in the site data.
_PIPELINE_ONLY_KEYS = {"scrape_urls"}


def venue_to_site_record(venue: dict, extract: dict | None, previous: dict | None) -> dict:
    """Merge config venue + fresh extraction into a site record.

    Carry-through by construction (Phase 3, issue #30): start from ALL config
    fields (minus pipeline-only keys) and override only the runtime fields —
    so a new curated field can never silently vanish again (the old code
    hand-listed every key; `notes` and `nickname` both fell through it).
    """
    prev = previous or {}
    ex = extract or {}
    record = {k: v for k, v in venue.items() if k not in _PIPELINE_ONLY_KEYS}
    for key in ("hours", "business_hours", "notes"):
        record[key] = ex.get(key) or prev.get(key) or ""
    specials = ex.get("specials")
    if not specials:
        specials = prev.get("specials") or []
    record["specials"] = specials
    return record
