#!/usr/bin/env python3
"""Replay golden eval corpus against agreement v1. Exit 1 on mismatch."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import EVAL_DIR, TOMBSTONES_PATH, VENUES_PATH, load_json
from adapters.overture import match_venues_to_candidates, observations_from_matches, load_fixture
from truth.agreement import agree_venue, venue_has_primary
from truth.schema import ExtractionMethod, Observation

GOLDEN = EVAL_DIR / "golden_venues.json"
FIXTURE = EVAL_DIR / "overture_fixture.json"


def _as_list(x):
    return x if isinstance(x, list) else [x]


def obs_from_spec(venue_id: str, spec: dict) -> Observation:
    return Observation(
        venue_id=venue_id,
        observed_at=spec.get("observed_at") or "2026-08-01T00:00:00Z",
        source_url=spec.get("source_url") or "",
        source_type=spec["source_type"],
        source_family=spec.get("source_family") or spec["source_type"],
        extraction_method=ExtractionMethod.HEURISTIC,
        evidence_excerpt=spec.get("evidence_excerpt") or "",
        payload=spec.get("payload") or {},
    )


def check_case(case: dict, venues_by_id: dict, fixture_places: list) -> list[str]:
    errors = []
    cid = case["id"]

    if case.get("expect_tombstoned"):
        vid = case["venue_id"]
        if vid in venues_by_id:
            errors.append(f"{cid}: venue_id {vid} still in config (expected tombstone)")
        tomb_ids = set()
        if TOMBSTONES_PATH.exists():
            tomb = load_json(TOMBSTONES_PATH)
            tomb_ids = {v.get("id") for v in (tomb.get("venues") or []) if v.get("id")}
        if vid not in tomb_ids:
            errors.append(f"{cid}: venue_id {vid} missing from {TOMBSTONES_PATH.name}")
        return errors

    if case.get("expect_no_overture_match"):
        venue = case["venue"]
        cand = case["overture_candidate"]
        matches = match_venues_to_candidates([venue], [cand], min_score=0.5)
        if venue["id"] in matches:
            errors.append(f"{cid}: expected no Overture match for namesake, got {matches[venue['id']]}")
        return errors

    if case.get("synthetic"):
        venue = case["venue"]
        observations = [obs_from_spec(venue["id"], s) for s in case.get("observations") or []]
        primary = venue_has_primary(venue)
        decisions = agree_venue(venue["id"], observations, has_primary_source=primary)
    else:
        venue = venues_by_id.get(case["venue_id"])
        if not venue:
            return [f"{cid}: venue_id {case['venue_id']} not in config"]
        matches = match_venues_to_candidates([venue], fixture_places)
        observations = observations_from_matches(matches)
        # Add a synthetic aggregator HH observation for Santa Fe class
        if case.get("scenario") == "closed_aggregator_only":
            observations.append(
                obs_from_spec(
                    venue["id"],
                    {
                        "source_type": "aggregator",
                        "source_family": "mthappyhour",
                        "payload": {
                            "business_status": "open",
                            "hours": "Daily 3-6pm, Fri-Sat 10pm-12am",
                            "specials": [
                                {
                                    "item": "$5 Margarita",
                                    "price": 5,
                                    "category": "drinks",
                                    "description": "",
                                }
                            ],
                        },
                        "observed_at": "2026-07-01T00:00:00Z",
                    },
                )
            )
        # confirmed_open must exercise own-site corroboration (Overture alone ≠ verified)
        if case.get("scenario") == "confirmed_open":
            website = venue.get("website") or "https://example.com/"
            observations.append(
                obs_from_spec(
                    venue["id"],
                    {
                        "source_type": "own_site",
                        "source_family": "own_site",
                        "source_url": website,
                        "payload": {
                            "business_status": "open",
                            "hours": "Mon-Fri 3-6pm",
                            "specials": [],
                        },
                        "observed_at": "2026-08-01T00:00:00Z",
                    },
                )
            )
        primary = venue_has_primary(venue)
        decisions = agree_venue(venue["id"], observations, has_primary_source=primary)

    status = decisions.get("business_status")
    if not status:
        errors.append(f"{cid}: missing business_status decision")
        return errors

    exp_kinds = _as_list(case["expected_status_kind"])
    kind = status.kind.value if hasattr(status.kind, "value") else status.kind
    if kind not in exp_kinds:
        errors.append(f"{cid}: status kind={kind} not in {exp_kinds} (value={status.value})")

    exp_vals = _as_list(case.get("expected_status_value") or [])
    if exp_vals and status.value not in exp_vals:
        errors.append(f"{cid}: status value={status.value} not in {exp_vals}")

    exp_sp = case.get("expected_specials_kind")
    if exp_sp:
        sp = decisions.get("specials")
        sk = sp.kind.value if sp and hasattr(sp.kind, "value") else (sp.kind if sp else None)
        if sk != exp_sp:
            errors.append(f"{cid}: specials kind={sk} expected {exp_sp}")

    return errors


def main() -> int:
    golden = load_json(GOLDEN)
    config = load_json(VENUES_PATH)
    venues_by_id = {v["id"]: v for v in config.get("venues") or []}
    fixture_places = load_fixture(FIXTURE)
    errors = []
    for case in golden.get("cases") or []:
        errors.extend(check_case(case, venues_by_id, fixture_places))

    if errors:
        print("EVAL FAIL:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"EVAL OK: {len(golden.get('cases') or [])} cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
