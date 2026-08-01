#!/usr/bin/env python3
"""
Happy Cow — generalized venue discovery.

The scraper (scrape_happy_hours.py) only processes venues hand-listed in
config/venues.json. Nothing ever grows that list, so bars like The Filling
Station or The Molly Brown — which no directory indexes — stay missing.

This script implements the `discovery_seeds` + `curated_venues` sections of
config/venues.json:

  1. Directory sources (discovery_seeds): fetch index pages, parse venue
     cards (name / address / city / HH summary / URL), paginate.
  2. Curated venue pages (curated_venues): single known venue pages that
     directories miss (dive bars, live-music rooms). Parses name, address,
     phone, categories from the page.

Everything is deduped against the existing venue list (normalized name +
address) and filtered to the target city, then new venue stubs are appended
to config/venues.json with scrape_urls for the normal scraper to enrich.

Usage:
  python scripts/discover_venues.py             # dry-run report
  python scripts/discover_venues.py --write     # append new venues to config
  python scripts/discover_venues.py --source mthappyhour-dir   # limit sources
  python scripts/discover_venues.py --verbose   # per-card detail
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
VENUES_PATH = ROOT / "config" / "venues.json"

USER_AGENT = "happycow-discovery/1.0 (+https://github.com/lucas-albers-lz4/happycow)"
REQUEST_TIMEOUT = 30.0
INTER_REQUEST_SLEEP = 0.7

CITY_KEYWORDS = {"bozeman"}  # matched against lowercased address text


# ─── Data ───

@dataclass
class Candidate:
    name: str
    address: str = ""
    city: str = ""
    url: str = ""
    hh_summary: str = ""
    tags: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    phone: str = ""
    website: str = ""


# ─── Normalization / dedup ───

def norm_name(name: str) -> str:
    """'The Filling Station' -> 'filling station' (strip articles/punct)."""
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()
    for art in ("the ", "a ", "an "):
        if s.startswith(art) and len(s) > len(art):
            s = s[len(art):]
    return re.sub(r"\s+", " ", s).strip()


def norm_address(addr: str) -> str:
    s = addr.lower()
    s = re.sub(r"[,.\-]+", " ", s)
    s = re.sub(r"\b(mt|montana)\b", "", s)
    s = re.sub(r"\b\d{5}\b", "", s)  # zip
    return re.sub(r"\s+", " ", s).strip()


def street_number(addr: str) -> str:
    m = re.search(r"^\s*(\d+)", addr or "")
    return m.group(1) if m else ""


def is_city_match(candidate: Candidate, cities: list[str]) -> bool:
    """Match if the address mentions ANY target city (Bozeman/Belgrade/Four Corners...)."""
    if not cities:
        return True
    haystack = f"{candidate.address} {candidate.city}".lower()
    # "four corners" is two words; also handle "4 corners"
    for c in cities:
        ck = c.strip().lower()
        if ck in haystack:
            return True
        if ck == "four corners" and ("four corners" in haystack or "4 corners" in haystack):
            return True
    return False


def existing_lookup(venues: list[dict]) -> tuple[dict, dict]:
    by_name = {}
    by_addr = {}
    for v in venues:
        by_name.setdefault(norm_name(v.get("name", "")), []).append(v)
        if v.get("address"):
            by_addr.setdefault(norm_address(v["address"]), []).append(v)
    return by_name, by_addr


def is_duplicate(cand: Candidate, by_name: dict, by_addr: dict) -> bool:
    """Match by normalized name, or by shared street number + address tokens."""
    if norm_name(cand.name) in by_name:
        return True
    num = street_number(cand.address)
    naddr = norm_address(cand.address)
    if num:
        for existing in by_addr.get(naddr, []):
            if num and street_number(existing.get("address", "")) == num:
                return True
    return False


# ─── HTTP ───

def fetch(client: httpx.Client, url: str) -> str | None:
    try:
        resp = client.get(url)
        if resp.status_code >= 400:
            print(f"  WARN fetch skipped HTTP {resp.status_code} {url}", file=sys.stderr)
            return None
        return resp.text
    except Exception as e:
        print(f"  WARN fetch failed {url}: {e}", file=sys.stderr)
        return None


def next_page_url(soup: BeautifulSoup, base: str) -> str | None:
    """Follow rel=next, or 'Older posts'/'Next' style pagination links."""
    for a in soup.find_all("a", href=True):
        label = a.get_text(strip=True).lower()
        if a.get("rel") and "next" in a.get("rel"):
            return urllib.parse.urljoin(base, a["href"])
        if label in ("older posts", "next", "next »", "›", "»"):
            return urllib.parse.urljoin(base, a["href"])
        if label.startswith(("next", "older posts")):
            return urllib.parse.urljoin(base, a["href"])
    return None


# ─── Source parsers ───

def parse_mthappyhour_dir(html: str, source_url: str) -> list[Candidate]:
    """MT directory cards (article OR div based): heading + Address/Happy Hour spans + /locations/ link."""
    soup = BeautifulSoup(html, "lxml")
    out = []
    seen_names: set[str] = set()
    for h in soup.find_all(["h1", "h2", "h3", "h4"]):
        name = h.get_text(strip=True)
        if len(name) < 2 or name.lower() in ("happy hours nearbozeman", "happy hours near bozeman"):
            continue
        if name in seen_names:
            continue
        # Find the nearest container that also holds a /locations/ link
        card = h.find_parent(["article", "div"])
        link = None
        container = card
        for _ in range(3):
            if container is None:
                break
            link = container.find("a", href=lambda x: x and "/locations/" in x)
            if link:
                break
            container = container.parent
        if not link:
            continue
        # A real venue card has exactly one heading; nav/pagination blocks
        # contain several (or none). Reject anything else.
        if container is None or len(container.find_all(["h1", "h2", "h3", "h4"])) != 1:
            continue
        if name.lower() in ("posts navigation", "find yourhappy hour", "find your happy hour"):
            continue
        seen_names.add(name)
        txt = h.find_parent(["article", "div"]).get_text(" ", strip=True) if h.find_parent(["article", "div"]) else ""
        if not txt:
            txt = card.get_text(" ", strip=True) if card else ""
        addr = re.search(r"Address:\s*([^|]+)", txt)
        hh = re.search(r"Happy Hour:\s*([^|]+)", txt)
        url = urllib.parse.urljoin(source_url, link["href"])
        addr_text = (addr.group(1).strip() if addr else "")
        # Strip trailing link labels that end up in the card text
        addr_text = re.sub(r"\s+(More Info|Details|View)\s*$", "", addr_text, flags=re.I)
        cand = Candidate(
            name=name,
            address=addr_text,
            hh_summary=(hh.group(1).strip() if hh else ""),
            url=url,
            sources=[source_url],
        )
        # city from address tail, e.g. "515 W Aspen St, Bozeman"
        if cand.address:
            parts = [p.strip() for p in cand.address.split(",")]
            if len(parts) >= 2:
                cand.city = parts[1]
        out.append(cand)
    return out


def parse_page(html: str, source_url: str, seed_name: str | None = None) -> list[Candidate]:
    """Generic single-page parse: h1 name, address/phone lines, category labels.

    Works for Bozeman Magazine bar/location pages and similar static pages.
    Falls back to <title> for the name when no h1 is present.
    """
    soup = BeautifulSoup(html, "lxml")
    h1 = soup.find(["h1", "h2"])
    title = soup.find("title")
    name = None
    if h1 and len(h1.get_text(strip=True)) > 2:
        name = h1.get_text(strip=True)
    elif title:
        t = title.get_text(strip=True)
        name = re.split(r"\s*[|–—-]\s*", t)[0].strip()
    if not name or len(name) < 2:
        return []

    main = soup.find("main") or soup.find("article") or soup
    text = main.get_text(" | ", strip=True)

    address = ""
    # Street-suffixed addresses first ("703 W Babcock St, Bozeman, MT 59715")
    m = re.search(
        r"(\d+\s+[NSEW]?\.?\s*[A-Z][A-Za-z0-9 .]+"
        r"(?:Ave|St|Street|Avenue|Rd|Road|Dr|Drive|Ln|Lane|Blvd|Boulevard|Hwy|Highway|Ct|Court|Way)\b[^|]*)",
        text,
    )
    if not m:
        # Fallback: bare street names with no suffix ("703 W. Babcock | Bozeman, MT")
        m = re.search(
            r"(\d+\s+[NSEW]?\.?\s*[A-Z][A-Za-z0-9 .]+?)(?=\s*\|?\s*Bozeman\b|$)",
            text,
        )
    if m:
        address = re.sub(r"\s*\|\s*$", "", m.group(1)).strip()
        # keep only up to "Bozeman, MT 59715"
        am = re.search(r"^(.*?Bozeman[^|]*?)", address)
        if am:
            address = am.group(1).strip()

    phone = ""
    pm = re.search(r"\(?(\d{3})\)?[.\s-]?(\d{3})[.\s-]?(\d{4})", text)
    if pm:
        phone = f"({pm.group(1)}) {pm.group(2)}-{pm.group(3)}"

    website = ""
    wm = soup.find(
        "a",
        href=re.compile(
            r"^https?://(?!.*(?:facebook|instagram|twitter|t\.me|x\.com|yelp|magazine|mthappyhour|visitmt|visit-bozeman))"
        ),
    )
    if wm:
        website = wm["href"]

    cats = []
    for c in soup.find_all("a", href=True):
        if "/bars/categories/" in c["href"]:
            cats.append(c.get_text(strip=True))

    return [
        Candidate(
            name=name,
            address=address,
            city="Bozeman",
            url=source_url,
            tags=cats,
            sources=[source_url],
            phone=phone,
            website=website,
        )
    ]


PARSERS = {
    "mthappyhour-dir": parse_mthappyhour_dir,
    "page": parse_page,
}


# ─── Main ───

def slugify(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s or "venue"


def to_config_entry(cand: Candidate) -> dict:
    city_hint = cand.city.split(",")[0].strip() if cand.city else "Bozeman"
    maps_q = urllib.parse.quote(f"{cand.name} {city_hint} MT")
    scrape_urls = [cand.url] if cand.url else []
    if cand.website and cand.website not in scrape_urls:
        scrape_urls.append(cand.website)
    return {
        "id": slugify(cand.name),
        "name": cand.name,
        "address": cand.address,
        "phone": cand.phone,
        "website": cand.website,
        "scrape_urls": scrape_urls,
        "maps": f"https://www.google.com/maps/search/?api=1&query={maps_q}",
        "tags": cand.tags,
        "noise_level": "",
        "mood": "",
    }


def run(write: bool, only_sources: list[str] | None, verbose: bool) -> int:
    config = load_json(VENUES_PATH)
    # Multi-city support: config "cities" list (e.g. Bozeman/Belgrade/Four Corners),
    # falling back to the legacy single "city" string.
    cities = [c.strip() for c in (config.get("cities") or [config.get("city", "Bozeman, MT")]) if c.strip()]
    venues = config.get("venues", [])
    by_name, by_addr = existing_lookup(venues)

    seeds = list(config.get("discovery_seeds") or [])
    curated = list(config.get("curated_venues") or [])

    candidates: list[Candidate] = []
    seen_keys: set[str] = set()

    def absorb(cands: list[Candidate], source_id: str) -> None:
        for c in cands:
            # Dedup candidates by name+address: two different venues can share a
            # name (e.g. Plonk in Missoula vs Plonk in Bozeman), so name alone is
            # not enough. Two candidates match only if BOTH name and street
            # number (when present) agree.
            name_key = norm_name(c.name)
            num = street_number(c.address)
            key = name_key if not num else f"{name_key}|{num}"
            if not name_key or key in seen_keys:
                continue
            # Also skip if a same-named candidate with a different street
            # number already exists (keeps the first city's venue, allows the
            # second city's venue through).
            seen_keys.add(key)
            c.sources.append(source_id)
            candidates.append(c)

    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/json"}
    with httpx.Client(headers=headers, follow_redirects=True, timeout=REQUEST_TIMEOUT) as client:
        for seed in seeds:
            sid = seed.get("id", seed.get("url"))
            kind = seed.get("kind", "mthappyhour-dir")
            if only_sources and kind not in only_sources:
                continue
            if kind not in PARSERS:
                print(f"  SKIP unknown kind '{kind}' for seed {sid}", file=sys.stderr)
                continue
            url = seed["url"]
            print(f"\n== Source: {sid} ({kind}) ==")
            page_no = 0
            while url:
                page_no += 1
                if page_no > 1:
                    print(f"  page {page_no}")
                html = fetch(client, url)
                if not html:
                    break
                soup = BeautifulSoup(html, "lxml")
                found = PARSERS[kind](html, url)
                absorb(found, sid)
                print(f"  {len(found)} cards on page {page_no} ({len(candidates)} unique so far)")
                nxt = next_page_url(soup, url)
                if not nxt or nxt == url:
                    break
                url = nxt
                time.sleep(INTER_REQUEST_SLEEP)

        for entry in curated:
            name = entry.get("name")
            url = entry.get("url")
            kind = entry.get("kind", "page")
            print(f"\n== Curated: {name} ==")
            html = fetch(client, url)
            if not html:
                continue
            found = PARSERS.get(kind, parse_page)(html, url, seed_name=name)
            if not found:
                print(f"  WARN could not parse curated venue page {url}", file=sys.stderr)
                continue
            cand = found[0]
            cand.name = name  # trust the curated name over page parsing
            cand.tags = list(dict.fromkeys(list(entry.get("tags") or []) + cand.tags))
            absorb([cand], f"curated:{name}")

    # City filter + dedup against existing
    new: list[Candidate] = []
    for c in candidates:
        if not is_city_match(c, cities):
            if verbose:
                print(f"  skip (not in {cities}): {c.name} — {c.address}")
            continue
        if is_duplicate(c, by_name, by_addr):
            if verbose:
                print(f"  dup: {c.name}")
            continue
        new.append(c)

    new.sort(key=lambda c: norm_name(c.name))

    print(f"\n=== Summary ===")
    print(f"City filter: {', '.join(cities)}")
    print(f"Existing venues: {len(venues)}")
    print(f"Discovered unique candidates: {len(candidates)}")
    print(f"New venues after dedup+city filter: {len(new)}")

    for c in new:
        print(f"  + {c.name} | {c.address} | {c.hh_summary[:70]} | {c.url}")

    if not write:
        print("\nDry run — pass --write to append these to config/venues.json")
        return 0

    if not new:
        return 0

    entries = [to_config_entry(c) for c in new]
    venues.extend(entries)
    config["venues"] = venues
    save_json(VENUES_PATH, config)
    print(f"\nAppended {len(entries)} venues to {VENUES_PATH}")
    return 0


def load_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def main():
    parser = argparse.ArgumentParser(description="Discover new Bozeman venues")
    parser.add_argument("--write", action="store_true", help="Append new venues to config")
    parser.add_argument("--source", action="append", dest="sources", help="Only run this source kind (repeatable)")
    parser.add_argument("--verbose", action="store_true", help="Show skip/dup reasons")
    args = parser.parse_args()
    sys.exit(run(write=args.write, only_sources=args.sources, verbose=args.verbose))


if __name__ == "__main__":
    main()
