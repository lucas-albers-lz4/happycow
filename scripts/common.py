"""Shared constants + small helpers for the happycow pipeline scripts.

Phase 2 of issue #30: AGGREGATOR_HOSTS was copy-pasted in three scripts
(scrape_happy_hours, discover_hh_pages, check_venue_status) and had already
drifted (an extra `maps.google.com` — redundant, since is_aggregator()'s
suffix match covers it via google.com). This module is the single source.

Run scripts as `python scripts/<name>.py` from the repo root; the script's
own directory is on sys.path, so `from common import ...` works.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
VENUES_PATH = ROOT / "config" / "venues.json"
DATA_PATH = ROOT / "data" / "happy_hour_data.json"
CACHE_PATH = ROOT / "data" / "scrape_cache.json"
TOMBSTONES_PATH = ROOT / "data" / "removed_venues.json"
PROMPT_PATH = ROOT / "prompts" / "extract_happy_hour.txt"

# Directory/aggregator hosts — curated venue pages (own site, HH subpages)
# outrank these in gather_page_text so their boilerplate can't starve the
# dedicated sources that actually hold the deals.
AGGREGATOR_HOSTS = {
    "mthappyhour.com",
    "bozemanmagazine.com",
    "visit-bozeman.com",
    "menupix.com",
    "sellout.io",
    "google.com",
    "yelp.com",
    "facebook.com",
}


def host_of(url: str) -> str:
    """Hostname without scheme/port, leading www. stripped ('' for junk)."""
    h = urlsplit(url or "").hostname or ""
    return h[4:] if h.startswith("www.") else h


def is_aggregator(url: str) -> bool:
    """True for aggregator/directory hosts (suffix match; www handled)."""
    host = host_of(url)
    return bool(host) and any(host == a or host.endswith("." + a) for a in AGGREGATOR_HOSTS)
