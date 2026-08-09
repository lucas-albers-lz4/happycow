#!/usr/bin/env python3
"""Venue truth pipeline CLI — shadow decisions by default.

  python scripts/run_venue_truth.py
  python scripts/run_venue_truth.py --fixture data/eval/overture_fixture.json
  python scripts/run_venue_truth.py --overpass
  python scripts/run_venue_truth.py --suppress          # warns unless config allows
  python scripts/run_venue_truth.py --force-suppress    # explicit override (dangerous)

Writes:
  data/evidence/<venue-id>/*.json   (local / CI artifact; not committed)
  data/state/shadow_decisions.json
  data/state/review_queue.json
  data/state/cost_counters.json

Does NOT modify happy_hour_data.json unless truth_config.suppress_enabled
(or --force-suppress).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# scripts/ on path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    BOZEMAN_BBOX,
    COST_COUNTERS_PATH,
    DATA_PATH,
    EVIDENCE_DIR,
    EVAL_DIR,
    OVERPASS_CACHE_PATH,
    OVERTURE_CACHE_PATH,
    REVIEW_QUEUE_PATH,
    SHADOW_DECISIONS_PATH,
    TRUTH_CONFIG_PATH,
    VENUES_PATH,
    load_json,
    save_json,
)
from adapters import overture as overture_adapter  # noqa: E402
from adapters import overpass as overpass_adapter  # noqa: E402
from adapters.scrape_bridge import observation_from_scrape  # noqa: E402
from truth.agreement import agree_venue, venue_has_primary  # noqa: E402
from truth.budget import empty_counters, merge_counters, rank_uncertain  # noqa: E402
from truth.schema import ObservationStore, utc_now_iso  # noqa: E402
from truth.synthesize import apply_decisions_to_record, decisions_needing_review  # noqa: E402


def default_truth_config() -> dict:
    return {
        "suppress_enabled": False,
        "top_n_uncertain": 10,
        "retain_per_family": 5,
        "run_overpass": False,
    }


def load_truth_config() -> dict:
    cfg = default_truth_config()
    cfg.update(load_json(TRUTH_CONFIG_PATH, fallback={}) or {})
    return cfg


def observations_from_site_data(venues: list[dict], site: dict) -> list:
    """Provenance bridge: treat current published extract as scrape observations."""
    by_id = {v["id"]: v for v in site.get("venues") or []}
    out = []
    for venue in venues:
        rec = by_id.get(venue["id"])
        if not rec:
            continue
        extract = {
            "status": "ok",
            "hours": rec.get("hours") or "",
            "business_hours": rec.get("business_hours") or "",
            "specials": rec.get("specials") or [],
            "notes": rec.get("notes") or "",
        }
        urls = list(venue.get("scrape_urls") or [])
        obs = observation_from_scrape(venue, extract, urls)
        if obs:
            out.append(obs)
    return out


def run(
    *,
    fixture: Path | None = None,
    force_overture: bool = False,
    run_overpass: bool = False,
    suppress: bool = False,
    force_suppress: bool = False,
    top_n: int | None = None,
    write: bool = True,
) -> int:
    config = load_json(VENUES_PATH)
    venues = config.get("venues") or []
    site = load_json(DATA_PATH, fallback={}) if DATA_PATH.exists() else {}
    tcfg = load_truth_config()
    if top_n is None:
        top_n = int(tcfg.get("top_n_uncertain") or 10)

    store = ObservationStore(EVIDENCE_DIR, retain_per_family=int(tcfg.get("retain_per_family") or 5))
    counters = empty_counters()
    all_obs_by_venue: dict[str, list] = {v["id"]: [] for v in venues}

    # 1) Overture priors
    fix = fixture or (EVAL_DIR / "overture_fixture.json")
    fix_path = fix if fix.exists() else None
    overture_obs, ometa = overture_adapter.fetch_or_cache(
        venues,
        BOZEMAN_BBOX,
        OVERTURE_CACHE_PATH,
        fixture_path=fix_path,
        force_refresh=force_overture,
    )
    counters["overture_matches"] = ometa.get("matches") or 0
    print(f"Overture: source={ometa.get('source')} candidates={ometa.get('candidates')} matches={ometa.get('matches')}")
    if ometa.get("failed") or ometa.get("empty_live"):
        print(
            "ERROR: Overture live path failed or returned empty — "
            "shadow priors may be incomplete",
            file=sys.stderr,
        )
        if force_overture:
            return 1
    for obs in overture_obs:
        all_obs_by_venue.setdefault(obs.venue_id, []).append(obs)

    # 2) Provenance from current site data (scrape bridge)
    scrape_obs = observations_from_site_data(venues, site)
    counters["scrape_observations"] = len(scrape_obs)
    counters["fetches"] += len(scrape_obs)  # legacy key; counts observations
    for obs in scrape_obs:
        all_obs_by_venue.setdefault(obs.venue_id, []).append(obs)

    # 3) Optional Overpass patrol
    if run_overpass or tcfg.get("run_overpass"):
        op_obs, op_meta = overpass_adapter.run_patrol(venues, OVERPASS_CACHE_PATH)
        counters["overpass_signals"] = op_meta.get("matched") or 0
        print(f"Overpass: removed={op_meta.get('removed')} matched={op_meta.get('matched')}")
        for obs in op_obs:
            all_obs_by_venue.setdefault(obs.venue_id, []).append(obs)

    # 4) Persist observations + agree
    shadow: dict = {"updated_at": utc_now_iso(), "venues": {}}
    review: list = []
    decisions_by_venue = {}

    for venue in venues:
        vid = venue["id"]
        obs_list = all_obs_by_venue.get(vid) or []
        if write:
            for obs in obs_list:
                store.write(obs)
        primary = venue_has_primary(venue)
        decisions = agree_venue(vid, obs_list, has_primary_source=primary)
        decisions_by_venue[vid] = decisions
        shadow["venues"][vid] = {
            k: d.model_dump() for k, d in decisions.items()
        }
        for d in decisions_needing_review(decisions):
            review.append(
                {
                    "venue_id": vid,
                    "name": venue.get("name"),
                    "field": d.field.value if hasattr(d.field, "value") else d.field,
                    "kind": d.kind.value if hasattr(d.kind, "value") else d.kind,
                    "value": d.value,
                    "rationale": d.rationale,
                    "cited_sources": d.cited_sources,
                    "queued_at": utc_now_iso(),
                }
            )
        counters["venues_processed"] += 1

    top = rank_uncertain(venues, decisions_by_venue, venue_has_primary, top_n=top_n)
    counters["top_n_selected"] = top
    counters["escalations"] = len(top)
    print(f"Top-{top_n} uncertain: {', '.join(top) or '(none)'}")

    # Shadow-first: config gate is authoritative. --suppress alone cannot bypass.
    # --force-suppress is an explicit double-confirmation for intentional live writes.
    suppress_enabled = bool(tcfg.get("suppress_enabled")) or bool(force_suppress)
    if suppress and not suppress_enabled:
        print(
            "NOTE: --suppress ignored because data/state/truth_config.json "
            "has suppress_enabled=false (enable after eval precision OK, "
            "or pass --force-suppress)",
            file=sys.stderr,
        )
    if suppress_enabled and write and site.get("venues"):
        new_venues = []
        for rec in site["venues"]:
            dec = decisions_by_venue.get(rec["id"]) or {}
            new_venues.append(apply_decisions_to_record(rec, dec, suppress_enabled=True))
        site = dict(site)
        site["venues"] = new_venues
        site["last_updated"] = utc_now_iso()
        save_json(DATA_PATH, site)
        print(f"Suppress applied → wrote {DATA_PATH}")

    if write:
        save_json(SHADOW_DECISIONS_PATH, shadow)
        save_json(REVIEW_QUEUE_PATH, {"updated_at": utc_now_iso(), "items": review})
        prior = load_json(COST_COUNTERS_PATH, fallback={})
        merged = merge_counters(prior, counters)
        save_json(COST_COUNTERS_PATH, {"updated_at": utc_now_iso(), **merged})
        if not TRUTH_CONFIG_PATH.exists():
            save_json(TRUTH_CONFIG_PATH, default_truth_config())
        print(f"Wrote {SHADOW_DECISIONS_PATH}")
        print(f"Wrote {REVIEW_QUEUE_PATH} ({len(review)} items)")
        print(f"Review flags: {sum(1 for i in review if i['kind'] in ('suppressed', 'conflicted', 'needs_review'))}")

    return 0


def main() -> None:
    p = argparse.ArgumentParser(description="Venue truth shadow pipeline")
    p.add_argument("--fixture", type=Path, help="Overture fixture JSON (default: data/eval/overture_fixture.json)")
    p.add_argument("--force-overture", action="store_true", help="Refresh Overture from S3")
    p.add_argument("--overpass", action="store_true", help="Run Overpass weekly patrol")
    p.add_argument(
        "--suppress",
        action="store_true",
        help="Request suppress apply (honored only if truth_config.suppress_enabled)",
    )
    p.add_argument(
        "--force-suppress",
        action="store_true",
        help="Override config and apply suppress to happy_hour_data.json (dangerous)",
    )
    p.add_argument("--top-n", type=int, default=None, help="Uncertainty budget top-N")
    p.add_argument("--dry-run", action="store_true", help="Do not write evidence/state")
    args = p.parse_args()
    sys.exit(
        run(
            fixture=args.fixture,
            force_overture=args.force_overture,
            run_overpass=args.overpass,
            suppress=args.suppress,
            force_suppress=args.force_suppress,
            top_n=args.top_n,
            write=not args.dry_run,
        )
    )


if __name__ == "__main__":
    main()
