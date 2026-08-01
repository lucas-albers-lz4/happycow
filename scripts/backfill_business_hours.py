#!/usr/bin/env python3
"""Backfill business_hours for venues from their mthappyhour pages.

mthappyhour venue pages have a "Business Hours" section laid out as:
    Business Hours | Monday | 4pm-10pm | Tuesday | ... | Sunday | ...
This parses that section directly (no LLM), compresses identical
consecutive days ("Mon-Wed 11am-10pm"), and writes the result into
data/happy_hour_data.json as venue["business_hours"].

Venues without an mthappyhour scrape_url or without a parseable section
are left unchanged ("" stays "").

Usage: python scripts/backfill_business_hours.py
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "happy_hour_data.json"
CONFIG_PATH = ROOT / "config" / "venues.json"

USER_AGENT = "happycow-backfill/1.0 (+https://github.com/lucas-albers-lz4/happycow)"
REQUEST_TIMEOUT = 30.0
INTER_REQUEST_SLEEP = 0.5

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DAY_ABBR = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def fetch(client: httpx.Client, url: str) -> str | None:
    try:
        resp = client.get(url)
        if resp.status_code >= 400:
            return None
        return resp.text
    except Exception:
        return None


def parse_business_hours(html: str) -> str:
    """Return compressed 'Mon-Thu 11am-12am, Fri 11am-2am' style string."""
    soup = BeautifulSoup(html, "lxml")
    heading = None
    for tag in soup.find_all(["h1", "h2", "h3", "h4"]):
        if re.search(r"business\s+hours", tag.get_text(strip=True), re.I):
            heading = tag
            break
    if not heading:
        return ""

    # Collect day -> hours from the heading's container text
    container = heading.find_parent()
    text = container.get_text(" | ", strip=True) if container else ""
    # Tokenize on '|'
    tokens = [t.strip() for t in text.split("|") if t.strip()]

    daily: dict[str, str] = {}
    for i, tok in enumerate(tokens):
        if tok in DAYS and i + 1 < len(tokens):
            # hours token: may be "4pm-10pm" or "Closed" or "4:00pm - 10:00pm"
            h = tokens[i + 1]
            h = re.sub(r"\s*–\s*|\s*—\s*", "-", h)
            h = re.sub(r"\s+to\s+", "-", h, flags=re.I)
            h = re.sub(r"\s+", " ", h).strip()
            h = re.sub(r"-+$", "", h)  # trailing dangling dash ("11:00am-")
            if h.lower().startswith("closed") or not h:
                h = "Closed" if h.lower().startswith("closed") else ""
            daily[tok] = h

    if not daily:
        return ""

    # Build day list, compress runs of equal hours
    hours_list = [daily.get(d, "") for d in DAYS]
    parts: list[str] = []
    i = 0
    while i < 7:
        h = hours_list[i]
        if not h:
            i += 1
            continue
        j = i
        while j + 1 < 7 and hours_list[j + 1] == h:
            j += 1
        day_range = DAY_ABBR[i] if i == j else f"{DAY_ABBR[i]}-{DAY_ABBR[j]}"
        parts.append(f"{day_range} {h}")
        i = j + 1
    return ", ".join(parts)


def main() -> int:
    config = json.load(open(CONFIG_PATH))
    cfg_by_id = {v["id"]: v for v in config.get("venues", [])}
    data = json.load(open(DATA_PATH))
    if "venues" not in data:
        data = {"venues": data}

    updated = 0
    with httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
        follow_redirects=True,
        timeout=REQUEST_TIMEOUT,
    ) as client:
        for venue in data["venues"]:
            if venue.get("business_hours"):
                continue  # already filled
            cfg = cfg_by_id.get(venue["id"], {})
            urls = [u for u in (cfg.get("scrape_urls") or []) if "mthappyhour.com" in u]
            if not urls:
                continue
            html = fetch(client, urls[0])
            time.sleep(INTER_REQUEST_SLEEP)
            if not html:
                continue
            bh = parse_business_hours(html)
            if bh:
                venue["business_hours"] = bh
                updated += 1
                print(f"  {venue['name']}: {bh}")

    json.dump(data, open(DATA_PATH, "w"), indent=2)
    with open(DATA_PATH, "a") as f:
        f.write("\n")
    print(f"\nUpdated {updated} venues with business_hours")
    return 0


if __name__ == "__main__":
    sys.exit(main())
