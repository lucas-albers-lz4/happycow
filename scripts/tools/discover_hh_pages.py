#!/usr/bin/env python3
"""Discover happy-hour page candidates for venues missing specials.

Phase A of the HH enrichment process — happycow issue #18.

For each venue missing specials:
  1. Determine its own website (prefer non-aggregator scrape_urls, else the
     data file's website field).
  2. Probe common happy-hour subpaths and scan sitemap.xml for pages that
     mention happy hour / specials / drinks.
  3. Emit a ranked candidate list for human review (Phase B: the human adds
     the winning URLs to config/venues.json scrape_urls).

Usage:
  python3 scripts/discover_hh_pages.py                 # all venues missing specials
  python3 scripts/discover_hh_pages.py --venue plonk   # single venue (repeatable)
  python3 scripts/discover_hh_pages.py --json /tmp/hh-candidates.json

Output is a markdown table to stdout (plus optional JSON).
Venues with no known own-site are reported as NEEDS_SITE — find their site,
add it to scrape_urls, and re-run.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from common import is_aggregator

import httpx

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "venues.json"
DATA_PATH = ROOT / "data" / "happy_hour_data.json"

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) HappyCowDiscovery/1.0"
TIMEOUT = 6.0

# Hosts that are directories/aggregators, not the venue's own site.
# Single source of truth: scripts/common.py (Phase 2, issue #30).

# Candidate subpaths to probe on a venue's own site.
HH_PATHS = [
    "/happy-hour",
    "/happyhour",
    "/happy-hours",
    "/happy-hour-menu",
    "/hh",
    "/specials",
    "/drink-menu",
    "/drinks-menu",
    "/drinks",
    "/menu",
]

KEYWORD_RE = re.compile(
    r"happy hour|happy-hour|specials?\b|draft|well drink|martini|margarita|"
    r"wings|appetizer|half price|half-price|2-4-1|two for one",
    re.IGNORECASE,
)
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.DOTALL | re.IGNORECASE)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def own_site_urls(venue: dict) -> list[str]:
    """Venue-owned website URLs from config scrape_urls / data website field."""
    urls: list[str] = []
    for u in venue.get("scrape_urls") or []:
        if not is_aggregator(u):
            urls.append(u.rstrip("/"))
    return urls


def page_text(resp: httpx.Response) -> str:
    """Rough text extraction: strip scripts/styles/tags."""
    raw = resp.text
    raw = re.sub(r"<script[^>]*>.*?</script>", " ", raw, flags=re.DOTALL | re.IGNORECASE)
    raw = re.sub(r"<style[^>]*>.*?</style>", " ", raw, flags=re.DOTALL | re.IGNORECASE)
    return re.sub(r"<[^>]+>", " ", raw)


def sitemap_urls(base: str, client: httpx.Client) -> list[str]:
    """All <loc> URLs from base/sitemap.xml (best-effort)."""
    try:
        r = client.get(urljoin(base + "/", "sitemap.xml"))
        if r.status_code != 200 or "xml" not in (r.headers.get("content-type", "")):
            return []
        return re.findall(r"<loc>\s*(.*?)\s*</loc>", r.text, re.DOTALL)
    except Exception:
        return []


def probe(base: str, path: str, client: httpx.Client) -> dict | None:
    url = urljoin(base + "/", path.lstrip("/"))
    try:
        r = client.get(url, follow_redirects=True)
        if r.status_code != 200:
            return None
        text = page_text(r)
        score = 0
        title_m = TITLE_RE.search(r.text)
        title = re.sub(r"\s+", " ", title_m.group(1)).strip()[:80] if title_m else ""
        if re.search(r"happy\s*hour", title, re.I):
            score += 3
        if re.search(r"happy\s*hour", text, re.I):
            score += 2
        if re.search(r"\b(special|draft|well drink|martini|half price)\b", text, re.I):
            score += 1
        if score == 0:
            return None
        return {"url": str(r.url), "score": score, "title": title, "status": r.status_code}
    except Exception:
        return None


def discover_venue(venue: dict, client: httpx.Client) -> dict:
    vid = venue["id"]
    sites = own_site_urls(venue)
    if not sites:
        return {"id": vid, "name": venue["name"], "status": "NEEDS_SITE", "candidates": []}

    known = set(sites)
    candidates: list[dict] = []
    for base in sites:
        for path in HH_PATHS:
            cand = probe(base, path, client)
            if cand and cand["url"] not in known:
                candidates.append(cand)
                known.add(cand["url"])
        for sm_url in sitemap_urls(base, client):
            if not KEYWORD_RE.search(sm_url):
                continue
            if sm_url.rstrip("/") in known:
                continue
            cand = probe(urlsplit(sm_url).scheme + "://" + urlsplit(sm_url).netloc,
                         urlsplit(sm_url).path, client)
            if cand:
                candidates.append(cand)
                known.add(cand["url"])

    candidates.sort(key=lambda c: -c["score"])
    return {"id": vid, "name": venue["name"], "status": "OK", "candidates": candidates}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--venue", action="append", dest="venues", help="venue id (repeatable)")
    parser.add_argument("--json", metavar="PATH", help="also write machine-readable results")
    parser.add_argument("--all", action="store_true", help="scan every venue, not just missing-specials ones")
    args = parser.parse_args()

    cfg = load_json(CONFIG_PATH)
    data = load_json(DATA_PATH)
    missing = {v["id"] for v in data["venues"] if not v.get("specials")}
    by_id = {v["id"]: v for v in cfg["venues"]}

    targets = by_id.values()
    if args.venues:
        targets = [by_id[i] for i in args.venues if i in by_id]
    elif not args.all:
        targets = [v for v in targets if v["id"] in missing]

    results: list[dict] = []
    with httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xml"},
        timeout=TIMEOUT,
        follow_redirects=True,
    ) as client:
        for venue in targets:
            print(f"== {venue['name']} ({venue['id']}) ==", file=sys.stderr)
            results.append(discover_venue(venue, client))
            time.sleep(0.3)

    # stdout: markdown table
    print("| Venue | Status | Candidates (score, title) |")
    print("|---|---|---|")
    for r in results:
        if r["status"] == "NEEDS_SITE":
            print(f"| {r['name']} | NEEDS_SITE | no own-site URL known — find it and add to scrape_urls |")
            continue
        cands = ", ".join(
            f"[{c['score']}] {c['url']} — {c['title']}" for c in r["candidates"]
        )
        print(f"| {r['name']} | OK | {cands or 'no candidates found'} |")

    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
