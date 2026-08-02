"""Orchestration + CLI for the scrape pipeline.

Phase 5 of issue #30 — extracted from scripts/scrape_happy_hours.py.
Run via the backward-compat entry point: python scripts/scrape_happy_hours.py
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

from common import CACHE_PATH, DATA_PATH, PROMPT_PATH, VENUES_PATH, save_json
from scraper.extract import ANTHROPIC_API_KEY, MODEL, extract_venue
from scraper.merge import reject_unparseable_hours, venue_to_site_record

# Optional truth-pipeline provenance (shadow; suppress gated by truth_config)
try:
    from adapters.scrape_bridge import observation_from_scrape
    from common import EVIDENCE_DIR, TRUTH_CONFIG_PATH, SHADOW_DECISIONS_PATH, load_json as _load
    from truth.schema import ObservationStore
    from truth.synthesize import apply_decisions_to_record

    _TRUTH_AVAILABLE = True
except Exception:  # noqa: BLE001
    _TRUTH_AVAILABLE = False

ROOT = Path(__file__).resolve().parent.parent.parent
USER_AGENT = "happycow-scraper/1.0 (+https://github.com/lucas-albers-lz4/happycow)"
REQUEST_TIMEOUT = 30.0


def load_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def run(
    dry_run: bool = False,
    venue_ids: list[str] | None = None,
    force: bool = False,
) -> int:
    if not ANTHROPIC_API_KEY:
        print(
            "ERROR: DEEPSEEK_API_KEY (or ANTHROPIC_API_KEY) is not set — "
            "cannot scrape any venues; aborting before venue loop",
            file=sys.stderr,
        )
        return 1

    config = load_json(VENUES_PATH)
    prompt_tmpl = PROMPT_PATH.read_text()
    previous = load_json(DATA_PATH) if DATA_PATH.exists() else {}
    prev_by_id = {v["id"]: v for v in previous.get("venues", [])}
    cache = load_json(CACHE_PATH) if CACHE_PATH.exists() else {}
    if not isinstance(cache, dict):
        cache = {}
    # Support either flat {id: ...} or {"venues": {id: ...}}
    if "venues" in cache and isinstance(cache["venues"], dict):
        cache_venues = cache["venues"]
    else:
        cache_venues = {k: v for k, v in cache.items() if isinstance(v, dict) and "content_hash" in v}

    city = config.get("city", "Bozeman, MT")
    venues = config.get("venues", [])
    if venue_ids:
        want = set(venue_ids)
        venues = [v for v in venues if v["id"] in want]

    print(f"Scraping {len(venues)} venues for {city} (model={MODEL}, force={force})")

    # Phase A: extract all venues (LLM / cache). Do not merge yet — hours need
    # one batched Node parse check across the whole run (issue #41).
    pending: list[tuple[dict, dict | None, bool]] = []
    cache_hits = 0
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/json"}
    with httpx.Client(headers=headers, follow_redirects=True, timeout=REQUEST_TIMEOUT) as client:
        for venue in venues:
            print(f"\n== {venue['name']} ({venue['id']}) ==")
            extract, from_cache = extract_venue(
                client, venue, city, prompt_tmpl, cache_venues, force=force
            )
            if from_cache:
                cache_hits += 1
            pending.append((venue, extract, from_cache))

    # Phase B: single Node invocation — reject unparseable non-empty hours.
    extracts_by_id = {
        venue["id"]: extract
        for venue, extract, _ in pending
        if extract is not None
    }
    bad_ids = set(reject_unparseable_hours(extracts_by_id))
    # Keep cache in sync so a cache hit does not re-offer the bad string.
    for vid in bad_ids:
        cached = cache_venues.get(vid)
        if cached and isinstance(cached.get("extract"), dict):
            cached["extract"]["hours"] = ""

    # Phase C: merge into site records.
    results = []
    ok = fail = kept = 0
    truth_store = None
    suppress_enabled = False
    shadow_by_id: dict = {}
    if _TRUTH_AVAILABLE:
        truth_store = ObservationStore(EVIDENCE_DIR)
        tcfg = _load(TRUTH_CONFIG_PATH, fallback={}) or {}
        suppress_enabled = bool(tcfg.get("suppress_enabled"))
        shadow = _load(SHADOW_DECISIONS_PATH, fallback={}) or {}
        for vid, fields in (shadow.get("venues") or {}).items():
            from truth.schema import Decision

            shadow_by_id[vid] = {
                k: Decision.model_validate(v) for k, v in fields.items()
            }

    for venue, extract, _from_cache in pending:
        prev = prev_by_id.get(venue["id"])
        usable = (
            extract
            and extract.get("status") == "ok"
            and (extract.get("hours") or extract.get("specials"))
        )
        if usable:
            ok += 1
            record = venue_to_site_record(venue, extract, prev)
            if truth_store is not None and not dry_run:
                cached = cache_venues.get(venue["id"]) or {}
                obs = observation_from_scrape(
                    venue,
                    extract,
                    list(cached.get("sources") or venue.get("scrape_urls") or []),
                    content_hash=str(cached.get("content_hash") or ""),
                )
                if obs:
                    truth_store.write(obs)
        elif prev:
            kept += 1
            print(f"  keeping previous data for {venue['id']}")
            record = venue_to_site_record(venue, None, prev)
        else:
            fail += 1
            record = venue_to_site_record(venue, {"hours": "", "specials": []}, None)

        if suppress_enabled and venue["id"] in shadow_by_id:
            record = apply_decisions_to_record(
                record, shadow_by_id[venue["id"]], suppress_enabled=True
            )
        results.append(record)

    if venue_ids:
        scraped_ids = {v["id"] for v in results}
        for old in previous.get("venues", []):
            if old["id"] not in scraped_ids:
                results.append(old)

    out = {
        "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "city": city,
        "population": config.get("population", previous.get("population", 0)),
        "venues": results,
    }
    cache_out = {
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "venues": cache_venues,
    }

    print(f"\nDone: ok={ok} kept_previous={kept} empty={fail} cache_hits={cache_hits}")
    if dry_run:
        print(json.dumps(out, indent=2))
        return 0

    if ok == 0:
        print(
            "ERROR: ok=0 — no venues were successfully scraped; "
            "skipping data/cache write to avoid a fake successful refresh",
            file=sys.stderr,
        )
        return 1

    save_json(DATA_PATH, out)
    save_json(CACHE_PATH, cache_out)
    print(f"Wrote {DATA_PATH}")
    print(f"Wrote {CACHE_PATH}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Scrape Bozeman happy hours")
    parser.add_argument("--dry-run", action="store_true", help="Print JSON, don't write")
    parser.add_argument(
        "--venue",
        action="append",
        dest="venues",
        help="Only scrape this venue id (repeatable)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore content-hash cache and always call the LLM",
    )
    args = parser.parse_args()
    sys.exit(run(dry_run=args.dry_run, venue_ids=args.venues, force=args.force))


if __name__ == "__main__":
    main()
