"""Weekly Overpass snapshot diff for restaurant churn (free, no LLM)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import httpx

from truth.identity import names_match, street_token
from truth.schema import ExtractionMethod, Observation, utc_now_iso

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Bozeman-ish bbox south,west,north,east for Overpass
DEFAULT_BBOX = (45.55, -111.20, 45.85, -110.90)


def build_query(bbox: tuple[float, float, float, float] = DEFAULT_BBOX) -> str:
    s, w, n, e = bbox
    return f"""
[out:json][timeout:90];
(
  node["amenity"~"restaurant|bar|pub|cafe|fast_food"]({s},{w},{n},{e});
  way["amenity"~"restaurant|bar|pub|cafe|fast_food"]({s},{w},{n},{e});
);
out center tags;
""".strip()


def fetch_snapshot(
    client: httpx.Client | None = None,
    *,
    bbox: tuple[float, float, float, float] = DEFAULT_BBOX,
) -> list[dict[str, Any]]:
    own = client is None
    client = client or httpx.Client(timeout=120.0)
    try:
        r = client.post(OVERPASS_URL, data={"data": build_query(bbox)})
        r.raise_for_status()
        elements = r.json().get("elements") or []
    finally:
        if own:
            client.close()
    places = []
    for el in elements:
        tags = el.get("tags") or {}
        name = tags.get("name")
        if not name:
            continue
        lat = el.get("lat") or (el.get("center") or {}).get("lat")
        lon = el.get("lon") or (el.get("center") or {}).get("lon")
        addr = " ".join(
            x
            for x in [
                tags.get("addr:housenumber"),
                tags.get("addr:street"),
                tags.get("addr:city"),
            ]
            if x
        )
        places.append(
            {
                "osm_key": f"{el.get('type')}/{el.get('id')}",
                "name": name,
                "address": addr,
                "lat": lat,
                "lon": lon,
                "amenity": tags.get("amenity"),
            }
        )
    return places


def diff_snapshots(
    previous: list[dict[str, Any]],
    current: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    prev_by = {p["osm_key"]: p for p in previous if p.get("osm_key")}
    curr_by = {p["osm_key"]: p for p in current if p.get("osm_key")}
    removed = [prev_by[k] for k in prev_by.keys() - curr_by.keys()]
    added = [curr_by[k] for k in curr_by.keys() - prev_by.keys()]
    return {"removed": removed, "added": added}


def match_removed_to_venues(
    removed: list[dict[str, Any]],
    venues: list[dict],
) -> list[tuple[str, dict[str, Any]]]:
    hits: list[tuple[str, dict[str, Any]]] = []
    for place in removed:
        for venue in venues:
            if not names_match(venue.get("name") or "", place.get("name") or ""):
                continue
            vt = street_token(venue.get("address") or "")
            pt = street_token(place.get("address") or "")
            if vt and pt and vt != pt:
                continue
            hits.append((venue["id"], place))
            break
    return hits


def observations_from_removals(
    hits: list[tuple[str, dict[str, Any]]],
    *,
    observed_at: str | None = None,
) -> list[Observation]:
    when = observed_at or utc_now_iso()
    out = []
    for venue_id, place in hits:
        excerpt = (
            f"OSM element {place.get('osm_key')} ({place.get('name')}) "
            f"present in previous Overpass snapshot, absent in current"
        )
        out.append(
            Observation(
                venue_id=venue_id,
                observed_at=when,
                source_url=f"overpass:{place.get('osm_key')}",
                source_type="overpass",
                source_family="overpass",
                extraction_method=ExtractionMethod.HEURISTIC,
                evidence_excerpt=excerpt[:500],
                matched_name=place.get("name"),
                matched_address=place.get("address"),
                payload={"business_status": "likely_closed", "osm": place},
            )
        )
    return out


def run_patrol(
    venues: list[dict],
    cache_path: Path,
    *,
    client: httpx.Client | None = None,
    dry_run_snapshot: list[dict[str, Any]] | None = None,
) -> tuple[list[Observation], dict[str, Any]]:
    """Fetch current snapshot, diff vs cache, return likely_closed observations."""
    meta: dict[str, Any] = {"removed": 0, "added": 0, "matched": 0}
    if dry_run_snapshot is not None:
        current = dry_run_snapshot
    else:
        try:
            current = fetch_snapshot(client)
        except Exception as e:  # noqa: BLE001
            print(f"WARN overpass fetch failed: {e}", file=sys.stderr)
            return [], {**meta, "error": str(e)}

    previous: list[dict[str, Any]] = []
    if cache_path.exists():
        previous = json.loads(cache_path.read_text(encoding="utf-8")).get("places") or []

    diff = diff_snapshots(previous, current)
    meta["removed"] = len(diff["removed"])
    meta["added"] = len(diff["added"])
    hits = match_removed_to_venues(diff["removed"], venues)
    meta["matched"] = len(hits)

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(
            {"updated_at": utc_now_iso(), "places": current},
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return observations_from_removals(hits), meta
