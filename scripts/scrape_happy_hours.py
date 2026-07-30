#!/usr/bin/env python3
"""
Happy Cow scraper — fetch venue pages, extract happy hours via DeepSeek,
merge into data/happy_hour_data.json for GitHub Pages.

Pattern borrowed from sre-ai-llm-work/scripts/scan-sites.py (Messages API),
stripped of issue queues / Assayer / labels.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
VENUES_PATH = ROOT / "config" / "venues.json"
DATA_PATH = ROOT / "data" / "happy_hour_data.json"
PROMPT_PATH = ROOT / "prompts" / "extract_happy_hour.txt"

ANTHROPIC_API_KEY = (
    os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
)
ANTHROPIC_BASE_URL = os.environ.get(
    "ANTHROPIC_BASE_URL", "https://api.deepseek.com/anthropic"
).rstrip("/")
MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash")

USER_AGENT = "happycow-scraper/1.0 (+https://github.com/lucas-albers-lz4/happycow)"
REQUEST_TIMEOUT = 30
INTER_REQUEST_SLEEP = 1.5
MAX_PAGE_CHARS = 12000


def load_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "iframe"]):
        tag.decompose()
    text = soup.get_text("\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text[:MAX_PAGE_CHARS]


def fetch_url(url: str) -> str | None:
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return html_to_text(resp.text)
    except Exception as e:
        print(f"  WARN fetch failed {url}: {e}", file=sys.stderr)
        return None


def call_deepseek(prompt: str) -> str | None:
    if not ANTHROPIC_API_KEY:
        print(
            "ERROR: DEEPSEEK_API_KEY (or ANTHROPIC_API_KEY) not set",
            file=sys.stderr,
        )
        return None
    try:
        resp = requests.post(
            f"{ANTHROPIC_BASE_URL}/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": MODEL,
                "max_tokens": 2048,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=90,
        )
        resp.raise_for_status()
        return resp.json()["content"][0]["text"]
    except Exception as e:
        print(f"  ERROR DeepSeek call: {e}", file=sys.stderr)
        return None


def parse_extract_json(raw: str) -> dict | None:
    if not raw:
        return None
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try first {...} blob
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None


def normalize_specials(raw) -> list[dict]:
    if not isinstance(raw, list):
        return []
    out = []
    for item in raw[:12]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("item") or "").strip()
        if not name:
            continue
        try:
            price = float(item.get("price", 0))
        except (TypeError, ValueError):
            price = 0.0
        cat = str(item.get("category") or "drinks").lower()
        if cat not in ("drinks", "food"):
            cat = "drinks"
        out.append(
            {
                "item": name,
                "price": price,
                "category": cat,
                "description": str(item.get("description") or "").strip(),
            }
        )
    return out


def normalize_hours(hours: str) -> str:
    if not hours:
        return ""
    h = hours.strip()
    # Light cleanup: collapse spaces around day hyphen
    h = re.sub(r"\s*-\s*", "-", h, count=1) if re.match(r"^[A-Za-z]", h) else h
    # Ensure "Daily" capitalization
    if h.lower().startswith("daily "):
        h = "Daily " + h[6:]
    return h


def extract_venue(venue: dict, city: str, prompt_tmpl: str) -> dict | None:
    urls = venue.get("scrape_urls") or []
    if venue.get("website") and venue["website"] not in urls:
        urls = [venue["website"], *urls]

    chunks = []
    for url in urls:
        print(f"  fetch {url}")
        text = fetch_url(url)
        time.sleep(INTER_REQUEST_SLEEP)
        if text:
            chunks.append(f"[source: {url}]\n{text}")

    if not chunks:
        print(f"  SKIP {venue['id']}: no page text")
        return None

    page_text = "\n\n".join(chunks)[: MAX_PAGE_CHARS * 2]
    prompt = prompt_tmpl.format(
        name=venue["name"],
        city=city,
        urls=", ".join(urls),
        page_text=page_text,
    )
    print(f"  extract via {MODEL}")
    raw = call_deepseek(prompt)
    data = parse_extract_json(raw or "")
    if not data:
        print(f"  SKIP {venue['id']}: bad/empty model JSON")
        if raw:
            print(f"  raw[:300]={raw[:300]!r}", file=sys.stderr)
        return None

    status = data.get("status", "ok")
    hours = normalize_hours(str(data.get("hours") or ""))
    specials = normalize_specials(data.get("specials"))
    if status == "not_found" or (not hours and not specials):
        print(f"  not_found for {venue['id']}")
        return {"status": "not_found", "hours": "", "specials": [], "notes": data.get("notes")}

    return {
        "status": "ok",
        "hours": hours,
        "specials": specials,
        "notes": data.get("notes"),
    }


def venue_to_site_record(venue: dict, extract: dict | None, previous: dict | None) -> dict:
    """Merge curated static fields with extracted hours/specials; keep prior on failure."""
    prev = previous or {}
    hours = (extract or {}).get("hours") or prev.get("hours") or ""
    specials = (extract or {}).get("specials")
    if not specials:
        specials = prev.get("specials") or []

    return {
        "id": venue["id"],
        "name": venue["name"],
        "address": venue.get("address") or prev.get("address") or "",
        "phone": venue.get("phone") or prev.get("phone") or "",
        "website": venue.get("website") or prev.get("website") or "",
        "maps": venue.get("maps") or prev.get("maps") or "",
        "hours": hours,
        "tags": venue.get("tags") or prev.get("tags") or [],
        "noise_level": venue.get("noise_level") or prev.get("noise_level") or "",
        "mood": venue.get("mood") or prev.get("mood") or "",
        "specials": specials,
    }


def run(dry_run: bool = False, venue_ids: list[str] | None = None) -> int:
    config = load_json(VENUES_PATH)
    prompt_tmpl = PROMPT_PATH.read_text()
    previous = load_json(DATA_PATH) if DATA_PATH.exists() else {}
    prev_by_id = {v["id"]: v for v in previous.get("venues", [])}

    city = config.get("city", "Bozeman, MT")
    venues = config.get("venues", [])
    if venue_ids:
        want = set(venue_ids)
        venues = [v for v in venues if v["id"] in want]

    print(f"Scraping {len(venues)} venues for {city} (model={MODEL})")
    results = []
    ok = fail = kept = 0

    for venue in venues:
        print(f"\n== {venue['name']} ({venue['id']}) ==")
        extract = extract_venue(venue, city, prompt_tmpl)
        prev = prev_by_id.get(venue["id"])
        if extract and extract.get("status") == "ok" and (extract.get("hours") or extract.get("specials")):
            ok += 1
            record = venue_to_site_record(venue, extract, prev)
        else:
            if prev:
                kept += 1
                print(f"  keeping previous data for {venue['id']}")
                record = venue_to_site_record(venue, None, prev)
            else:
                fail += 1
                record = venue_to_site_record(venue, {"hours": "", "specials": []}, None)
        results.append(record)

    # Preserve any previous venues not in this run (partial --venue filter)
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

    print(f"\nDone: ok={ok} kept_previous={kept} empty={fail}")
    if dry_run:
        print(json.dumps(out, indent=2))
        return 0

    save_json(DATA_PATH, out)
    print(f"Wrote {DATA_PATH}")
    return 0 if ok > 0 or kept > 0 else 1


def main():
    parser = argparse.ArgumentParser(description="Scrape Bozeman happy hours")
    parser.add_argument("--dry-run", action="store_true", help="Print JSON, don't write")
    parser.add_argument(
        "--venue",
        action="append",
        dest="venues",
        help="Only scrape this venue id (repeatable)",
    )
    args = parser.parse_args()
    sys.exit(run(dry_run=args.dry_run, venue_ids=args.venues))


if __name__ == "__main__":
    main()
