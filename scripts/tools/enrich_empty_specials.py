#!/usr/bin/env python3
"""Enrich venues that have empty specials — sips-style fetch → LLM → review.

For each venue with no specials in data/happy_hour_data.json:
  1. Resolve own-site URLs (config scrape_urls + website; skip aggregators).
  2. Fetch pages (browser UA + Playwright fallback via scraper.fetch).
  3. LLM-extract recurring deals into data/state/enrichment_candidates.json.
  4. Optionally --apply medium/high hits into publish data + scrape_urls.

Usage:
  python3 scripts/tools/enrich_empty_specials.py
  python3 scripts/tools/enrich_empty_specials.py --venue plonk --venue tanoshii
  python3 scripts/tools/enrich_empty_specials.py --dry-run
  python3 scripts/tools/enrich_empty_specials.py --force
  python3 scripts/tools/enrich_empty_specials.py --apply

Requires DEEPSEEK_API_KEY (or ANTHROPIC_API_KEY) except for --apply-only
replay from existing candidates (use --apply with no re-extract: pass
--apply-only).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit, urlunsplit

import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from common import (  # noqa: E402
    DATA_PATH,
    ENRICHMENT_CANDIDATES_PATH,
    VENUES_PATH,
    is_aggregator,
    load_json,
    save_json,
)
from scraper.extract import (  # noqa: E402
    ANTHROPIC_API_KEY,
    MODEL,
    Special,
    call_deepseek,
    content_hash,
    normalize_hours,
    parse_raw_json,
)
from scraper.fetch import (  # noqa: E402
    BROWSER_HEADERS,
    fetch_html,
    fetch_html_playwright,
    html_to_trimmed_text,
    _should_browser_fallback,
)
from scraper.merge import reject_unparseable_hours  # noqa: E402

ENRICH_PROMPT_PATH = ROOT / "prompts" / "enrich_empty_specials.txt"
CITY_DEFAULT = "Bozeman, MT"
APPLY_CONFIDENCE = frozenset({"medium", "high"})
INTER_SLEEP = 0.5


Confidence = Literal["high", "medium", "low"]
Status = Literal["ok", "needs_site", "no_page_text", "not_found", "error"]


class EnrichResult(BaseModel):
    found: bool = False
    confidence: Literal["high", "medium", "low"] = "low"
    hours: str = ""
    specials: list[Special] = Field(default_factory=list)
    notes: str = ""
    source_urls: list[str] = Field(default_factory=list)

    @field_validator("hours", mode="before")
    @classmethod
    def norm_hours(cls, v: Any) -> str:
        return normalize_hours(str(v or ""))

    @field_validator("notes", mode="before")
    @classmethod
    def strip_notes(cls, v: Any) -> str:
        return str(v or "").strip()

    @field_validator("source_urls", mode="before")
    @classmethod
    def coerce_urls(cls, v: Any) -> list[str]:
        if not v:
            return []
        if isinstance(v, str):
            return [v]
        return [str(u) for u in v if u]


EnrichResult.model_rebuild()


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def own_site_urls(cfg_venue: dict, data_venue: dict | None = None) -> list[str]:
    """Non-aggregator scrape_urls plus website fallback (config then data)."""
    seen: set[str] = set()
    out: list[str] = []

    def add(url: str) -> None:
        u = (url or "").strip()
        if not u or is_aggregator(u):
            return
        key = u.rstrip("/")
        if key in seen:
            return
        seen.add(key)
        out.append(u)

    for u in cfg_venue.get("scrape_urls") or []:
        add(u)
    add(cfg_venue.get("website") or "")
    if data_venue:
        add(data_venue.get("website") or "")
    return out


def empty_special_ids(data: dict) -> set[str]:
    return {v["id"] for v in data.get("venues") or [] if not (v.get("specials") or [])}


def select_targets(
    cfg: dict,
    data: dict,
    venue_ids: list[str] | None = None,
) -> list[tuple[dict, dict]]:
    """Return (cfg_venue, data_venue) pairs to enrich."""
    cfg_by_id = {v["id"]: v for v in cfg.get("venues") or []}
    data_by_id = {v["id"]: v for v in data.get("venues") or []}
    if venue_ids:
        ids = [i for i in venue_ids if i in cfg_by_id]
    else:
        ids = sorted(empty_special_ids(data) & set(cfg_by_id))
    pairs = []
    for vid in ids:
        pairs.append((cfg_by_id[vid], data_by_id.get(vid) or {"id": vid, "specials": []}))
    return pairs


def fetch_own_site_text(client: httpx.Client, urls: list[str]) -> tuple[str, list[str], str]:
    """Fetch + trim own-site pages. Returns (page_text, used_urls, miss_summary)."""
    chunks: list[str] = []
    used: list[str] = []
    misses: list[str] = []

    for url in urls:
        print(f"  fetch {url}")
        result = fetch_html(client, url)
        time.sleep(INTER_SLEEP)
        text = html_to_trimmed_text(result.html) if result.ok and result.html else ""

        if _should_browser_fallback(url, result, text):
            why = result.reason if not (result.ok and not text) else "empty_extract"
            print(f"  NOTE browser fallback ({why})")
            result = fetch_html_playwright(url)
            time.sleep(INTER_SLEEP)
            text = html_to_trimmed_text(result.html) if result.ok and result.html else ""

        if not result.ok or not result.html or not text:
            misses.append(f"{url}:{result.reason if not text else 'empty_extract'}")
            continue
        chunks.append(f"[source: {url}]\n{text}")
        used.append(url)

    page_text = "\n\n".join(chunks)
    # Cap like weekly scrape
    page_text = page_text[:16_000]
    return page_text, used, ", ".join(misses[:6])


def build_enrich_prompt(name: str, city: str, urls: list[str], page_text: str, tmpl: str) -> str:
    return (
        tmpl.replace("{name}", name)
        .replace("{city}", city)
        .replace("{urls}", ", ".join(urls))
        .replace("{page_text}", page_text)
    )


def validate_enrich(data: dict | None) -> EnrichResult | None:
    if not data:
        return None
    try:
        return EnrichResult.model_validate(data)
    except ValidationError as e:
        print(f"  WARN enrich validation: {e.error_count()} error(s)", file=sys.stderr)
        return None


def llm_enrich(
    client: httpx.Client,
    venue_name: str,
    city: str,
    urls: list[str],
    page_text: str,
    tmpl: str,
) -> EnrichResult | None:
    prompt = build_enrich_prompt(venue_name, city, urls, page_text, tmpl)
    print(f"  extract via {MODEL}")
    raw = call_deepseek(client, prompt)
    result = validate_enrich(parse_raw_json(raw or ""))
    if result:
        return result
    print("  retry extract (validation/parse failed)")
    raw2 = call_deepseek(
        client,
        prompt
        + "\n\nIMPORTANT: Previous reply was invalid. Return ONLY a single JSON object, "
        "no markdown fences, matching the schema exactly.",
    )
    return validate_enrich(parse_raw_json(raw2 or ""))


def candidate_record(
    *,
    status: Status,
    confidence: Confidence | None = None,
    content_hash_val: str = "",
    source_urls: list[str] | None = None,
    hours: str = "",
    specials: list[dict] | None = None,
    notes: str = "",
) -> dict:
    return {
        "status": status,
        "confidence": confidence,
        "content_hash": content_hash_val,
        "source_urls": list(source_urls or []),
        "hours": hours,
        "specials": list(specials or []),
        "notes": notes,
        "extracted_at": utc_now(),
    }


def enrich_venue(
    client: httpx.Client,
    cfg_venue: dict,
    data_venue: dict,
    tmpl: str,
    city: str,
    prev: dict | None,
    force: bool,
) -> dict:
    vid = cfg_venue["id"]
    urls = own_site_urls(cfg_venue, data_venue)
    if not urls:
        print("  SKIP needs_site")
        return candidate_record(status="needs_site", notes="no own-site URL in config/data")

    page_text, used, miss = fetch_own_site_text(client, urls)
    if not page_text:
        print(f"  SKIP no_page_text ({miss or 'all fetches failed'})")
        return candidate_record(
            status="no_page_text",
            source_urls=urls,
            notes=miss or "no usable page text",
        )

    digest = content_hash(page_text)
    if (
        not force
        and prev
        and prev.get("content_hash") == digest
        and prev.get("status") in ("ok", "not_found")
        and prev.get("specials") is not None
    ):
        print(f"  cache hit ({digest}) — skip LLM")
        return dict(prev)

    result = llm_enrich(client, cfg_venue["name"], city, used, page_text, tmpl)
    if not result:
        return candidate_record(
            status="error",
            content_hash_val=digest,
            source_urls=used,
            notes="LLM returned invalid JSON",
        )

    specials = [s.model_dump() for s in result.specials]
    src = result.source_urls or used
    if result.found and specials:
        print(f"  found {len(specials)} special(s) conf={result.confidence}")
        return candidate_record(
            status="ok",
            confidence=result.confidence,
            content_hash_val=digest,
            source_urls=src,
            hours=result.hours,
            specials=specials,
            notes=result.notes,
        )

    print(f"  not_found conf={result.confidence}")
    return candidate_record(
        status="not_found",
        confidence=result.confidence,
        content_hash_val=digest,
        source_urls=src,
        hours=result.hours,
        specials=[],
        notes=result.notes or "no recurring deals on pages",
    )


def should_apply(rec: dict) -> bool:
    """True when candidate may merge into publish data."""
    if rec.get("status") != "ok":
        return False
    if rec.get("confidence") not in APPLY_CONFIDENCE:
        return False
    return bool(rec.get("specials"))


def apply_candidates(
    cfg: dict,
    data: dict,
    candidates: dict[str, dict],
) -> tuple[int, int, int]:
    """Merge medium/high ok candidates. Returns (applied, skipped, needs_site)."""
    cfg_by_id = {v["id"]: v for v in cfg.get("venues") or []}
    data_by_id = {v["id"]: v for v in data.get("venues") or []}
    applied = skipped = needs_site = 0

    extracts_for_hours: dict[str, dict] = {}
    pending_apply: list[tuple[str, dict]] = []

    for vid, rec in candidates.items():
        if rec.get("status") == "needs_site":
            needs_site += 1
            skipped += 1
            continue
        if not should_apply(rec):
            skipped += 1
            continue
        if vid not in data_by_id or vid not in cfg_by_id:
            skipped += 1
            continue
        pending_apply.append((vid, rec))
        extracts_for_hours[vid] = {"hours": rec.get("hours") or "", "specials": rec.get("specials") or []}

    bad_hours = set(reject_unparseable_hours(extracts_for_hours))

    for vid, rec in pending_apply:
        site = data_by_id[vid]
        cfg_v = cfg_by_id[vid]
        hours = "" if vid in bad_hours else (rec.get("hours") or "").strip()
        if hours:
            site["hours"] = hours
        site["specials"] = list(rec.get("specials") or [])
        note = (rec.get("notes") or "").strip()
        prov = f"enriched {utc_now()[:10]} conf={rec.get('confidence')}"
        site["notes"] = f"{note}; ({prov})" if note else f"({prov})"

        for url in rec.get("source_urls") or []:
            if not url or is_aggregator(url):
                continue
            existing = list(cfg_v.get("scrape_urls") or [])
            keys = {u.rstrip("/") for u in existing}
            if url.rstrip("/") not in keys:
                existing.insert(0, url)
                cfg_v["scrape_urls"] = existing
        if not (cfg_v.get("website") or "").strip():
            for url in rec.get("source_urls") or []:
                if url and not is_aggregator(url):
                    parts = urlsplit(url)
                    if parts.scheme and parts.netloc:
                        cfg_v["website"] = urlunsplit((parts.scheme, parts.netloc, "/", "", ""))
                    break
        applied += 1
        print(f"  APPLY {vid}: {len(site['specials'])} special(s)")

    if applied:
        data["last_updated"] = utc_now()
    return applied, skipped, needs_site


def load_candidates() -> dict:
    raw = load_json(ENRICHMENT_CANDIDATES_PATH, fallback={"venues": {}}) or {}
    if not isinstance(raw.get("venues"), dict):
        raw["venues"] = {}
    return raw


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--venue", action="append", dest="venues", help="venue id (repeatable)")
    ap.add_argument("--dry-run", action="store_true", help="fetch+extract; do not write candidates")
    ap.add_argument("--force", action="store_true", help="ignore candidate content-hash cache")
    ap.add_argument(
        "--apply",
        action="store_true",
        help="after extract (or with --apply-only), merge medium/high into publish data",
    )
    ap.add_argument(
        "--apply-only",
        action="store_true",
        help="skip fetch/LLM; merge from existing enrichment_candidates.json",
    )
    args = ap.parse_args()

    cfg = load_json(VENUES_PATH)
    data = load_json(DATA_PATH)
    city = cfg.get("city") or CITY_DEFAULT
    store = load_candidates()
    venues_store: dict[str, dict] = dict(store.get("venues") or {})

    if args.apply_only:
        applied, skipped, needs_site = apply_candidates(cfg, data, venues_store)
        if not args.dry_run:
            save_json(VENUES_PATH, cfg)
            save_json(DATA_PATH, data)
        print(f"\nApply-only: applied={applied} skipped={skipped} needs_site={needs_site}")
        return 0

    if not ANTHROPIC_API_KEY:
        print(
            "ERROR: DEEPSEEK_API_KEY (or ANTHROPIC_API_KEY) is not set",
            file=sys.stderr,
        )
        return 1

    if not ENRICH_PROMPT_PATH.exists():
        print(f"ERROR: missing prompt {ENRICH_PROMPT_PATH}", file=sys.stderr)
        return 1
    tmpl = ENRICH_PROMPT_PATH.read_text(encoding="utf-8")

    targets = select_targets(cfg, data, args.venues)
    if not targets:
        print("No venues to enrich (empty specials set is empty, or --venue unknown).")
        return 0

    print(f"Enriching {len(targets)} venues (model={MODEL}, force={args.force})")
    counts = {"ok": 0, "not_found": 0, "needs_site": 0, "no_page_text": 0, "error": 0}

    with httpx.Client(
        headers=BROWSER_HEADERS, follow_redirects=True, timeout=30.0
    ) as client:
        for cfg_v, data_v in targets:
            print(f"\n== {cfg_v['name']} ({cfg_v['id']}) ==")
            prev = venues_store.get(cfg_v["id"])
            rec = enrich_venue(client, cfg_v, data_v, tmpl, city, prev, args.force)
            venues_store[cfg_v["id"]] = rec
            counts[rec["status"]] = counts.get(rec["status"], 0) + 1

    store_out = {"updated_at": utc_now(), "venues": venues_store}
    if not args.dry_run:
        save_json(ENRICHMENT_CANDIDATES_PATH, store_out)
        print(f"\nWrote {ENRICHMENT_CANDIDATES_PATH}")
    else:
        print("\n(dry-run — candidates not written)")

    print(
        "Summary: "
        + " ".join(f"{k}={v}" for k, v in counts.items() if v)
    )

    if args.apply:
        applied, skipped, needs_site = apply_candidates(cfg, data, venues_store)
        if not args.dry_run and applied:
            save_json(VENUES_PATH, cfg)
            save_json(DATA_PATH, data)
            print(f"Wrote {DATA_PATH}")
            print(f"Wrote {VENUES_PATH}")
        print(f"Apply: applied={applied} skipped={skipped} needs_site={needs_site}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
