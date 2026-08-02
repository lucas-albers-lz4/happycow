"""Record building: config venue + extraction -> site record.

Phase 5 of issue #30 — extracted from scripts/scrape_happy_hours.py.
Carry-through by construction: new curated config fields can never silently
vanish from the site data again.

Issue #41: batch-reject unparseable hours via check_hours_batch.mjs so a bad
LLM hours string never overwrites a previously good value.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

# Keys that exist in config/venues.json but must never appear in the site data.
_PIPELINE_ONLY_KEYS = {"scrape_urls"}

_CHECK_HOURS_BATCH = Path(__file__).resolve().parent / "check_hours_batch.mjs"


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


def reject_unparseable_hours(extracts: dict[str, dict]) -> list[str]:
    """Clear hours on extracts that fail parseHours (one Node invocation).

    Mutates extract dicts in place: sets hours to "" for failing ids so
    venue_to_site_record falls back to previous hours. Specials are untouched.
    Returns the list of venue ids that had unparseable non-empty hours.
    """
    candidates = []
    for vid, ex in extracts.items():
        if not ex:
            continue
        h = (ex.get("hours") or "").strip()
        if h:
            candidates.append({"id": vid, "hours": h})
    if not candidates:
        return []

    try:
        proc = subprocess.run(
            ["node", str(_CHECK_HOURS_BATCH)],
            input=json.dumps(candidates),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except FileNotFoundError:
        print("ERROR: node not found — cannot batch-check hours", file=sys.stderr)
        return []
    except subprocess.TimeoutExpired:
        print("ERROR: check_hours_batch.mjs timed out", file=sys.stderr)
        return []

    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        print(f"ERROR: check_hours_batch failed: {err}", file=sys.stderr)
        return []

    try:
        payload = json.loads((proc.stdout or "").strip() or "{}")
    except json.JSONDecodeError:
        print("ERROR: check_hours_batch returned non-JSON", file=sys.stderr)
        return []

    bad = [str(x) for x in (payload.get("bad") or []) if x]
    for vid in bad:
        ex = extracts.get(vid)
        if not ex:
            continue
        bad_h = ex.get("hours")
        ex["hours"] = ""
        print(
            f"  REJECT unparseable hours for {vid}: {bad_h!r} "
            f"— keeping previous hours; specials still applied",
            file=sys.stderr,
        )
    return bad
