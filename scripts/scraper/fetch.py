"""Page acquisition layer: fetch, trim, and the contamination guard.

Phase 5 of issue #30 — extracted from scripts/scrape_happy_hours.py.
Own-site pages are fetched before aggregators; aggregator pages are only
accepted when they match the venue (name + street number/word).
"""

from __future__ import annotations

import re
import sys
import time

import httpx
import trafilatura
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from common import is_aggregator

# Re-export for tests / callers that imported from scraper.fetch
__all__ = [
    "fetch_html",
    "trim_happy_hour_section",
    "html_section_by_heading",
    "html_to_trimmed_text",
    "page_matches_venue",
    "gather_page_text",
]


def page_matches_venue(text: str, venue: dict, require_address: bool) -> bool:
    """Lazy-import truth.identity so scrape works without the truth package."""
    from truth.identity import page_matches_venue as _match

    return _match(text, venue, require_address)

INTER_REQUEST_SLEEP = 1.0
MAX_PAGE_CHARS = 8000  # post-trim budget for the model
TRANSIENT_HTTP = {429, 500, 502, 503, 504}


def _is_transient_http_error(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TransportError, httpx.TimeoutException)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in TRANSIENT_HTTP
    return False


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception(_is_transient_http_error),
)
def _http_get(client: httpx.Client, url: str) -> httpx.Response:
    resp = client.get(url)
    if resp.status_code in TRANSIENT_HTTP:
        resp.raise_for_status()  # retry via tenacity
    return resp


def fetch_html(client: httpx.Client, url: str) -> str | None:
    try:
        resp = _http_get(client, url)
        if resp.status_code >= 400:
            # Permanent client/server errors (403/404/etc): skip, do not retry
            print(
                f"  WARN fetch skipped HTTP {resp.status_code} {url}",
                file=sys.stderr,
            )
            return None
        return resp.text
    except Exception as e:
        print(f"  WARN fetch failed {url}: {e}", file=sys.stderr)
        return None


def trim_happy_hour_section(text: str) -> str:
    """Keep this venue's happy-hour block; drop nav / other-locations noise."""
    if not text:
        return ""

    # Drop sibling venue lists first (mthappyhour puts these after the main entry)
    cut = re.split(
        r"\n\s*(?:OTHER\s+LOCATIONS|Explore\s+\d+\s+Happy\s+Hours|Submit\s+Update|Claim\s+Location)\b",
        text,
        maxsplit=1,
        flags=re.I,
    )[0]

    m = re.search(
        r"(Happy\s*Hour\s*Specials?\b.*?)(?=\n\s*Business\s+Hours\b|$)",
        cut,
        flags=re.I | re.S,
    )
    if m:
        return m.group(1).strip()

    # Fallback: window around first "happy hour" in the trimmed doc
    lower = cut.lower()
    idx = lower.find("happy hour")
    if idx >= 0:
        start = max(0, idx - 120)
        return cut[start : start + 3500].strip()
    return cut.strip()


def html_section_by_heading(html: str, start_pat: str, end_pats: list[str]) -> str:
    """Pull text between two headings from raw HTML (mthappyhour-friendly)."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return ""
    soup = BeautifulSoup(html, "lxml")
    start = None
    for tag in soup.find_all(["h1", "h2", "h3", "h4"]):
        if re.search(start_pat, tag.get_text(" ", strip=True), re.I):
            start = tag
            break
    if not start:
        return ""
    parts: list[str] = []
    for sib in start.next_siblings:
        name = getattr(sib, "name", None)
        if name in ("h1", "h2", "h3", "h4"):
            heading = sib.get_text(" ", strip=True)
            if any(re.search(p, heading, re.I) for p in end_pats):
                break
        text = sib.get_text(" ", strip=True) if hasattr(sib, "get_text") else str(sib).strip()
        if text:
            parts.append(text)
    return (start.get_text(" ", strip=True) + "\n" + "\n".join(parts)).strip()


def html_to_trimmed_text(html: str) -> str:
    # 1) Prefer DOM-bounded happy hour section (avoids sibling venue lists)
    section = html_section_by_heading(
        html,
        start_pat=r"happy\s*hour\s*specials?",
        end_pats=[r"business\s+hours", r"other\s+locations", r"submit\s+update", r"business\s+details"],
    )
    if section and len(section) > 40:
        trimmed = trim_happy_hour_section(section)
        return re.sub(r"\n{3,}", "\n\n", trimmed).strip()[:MAX_PAGE_CHARS]

    # 2) trafilatura main-content extract + trim
    extracted = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=True,
        include_links=False,
        favor_recall=True,
    ) or ""
    trimmed = trim_happy_hour_section(extracted)
    trimmed = re.sub(r"\n{3,}", "\n\n", trimmed).strip()
    return trimmed[:MAX_PAGE_CHARS]


def gather_page_text(client: httpx.Client, venue: dict) -> tuple[str, list[str]]:
    # Dedicated venue pages first (own site, HH subpages) — that's where the
    # real deals live. Aggregator directories (mthappyhour et al.) are fetched
    # after, with an early-break once enough signal exists — so their
    # boilerplate can't starve the curated own-site URLs.
    urls = list(venue.get("scrape_urls") or [])
    dedicated = [u for u in urls if not is_aggregator(u)]
    aggregators = [u for u in urls if is_aggregator(u)]
    website = venue.get("website") or ""
    fallback = [website] if website and website not in urls else []

    chunks: list[str] = []
    used: list[str] = []

    def _ingest(url: str) -> bool:
        print(f"  fetch {url}")
        html = fetch_html(client, url)
        time.sleep(INTER_REQUEST_SLEEP)
        if not html:
            return False
        text = html_to_trimmed_text(html)
        if not text:
            print(f"  WARN empty extract for {url}", file=sys.stderr)
            return False
        # Contamination guard: aggregator pages must match this venue
        # (name + street address) or they're skipped — they've been caught
        # carrying other venues' content (Old Chicago <- Bozeman Spirits, …).
        if is_aggregator(url):
            if not page_matches_venue(text, venue, require_address=True):
                print(f"  SKIP {url}: aggregator page doesn't match venue (contamination guard)", file=sys.stderr)
                return False
        elif not page_matches_venue(text, venue, require_address=False):
            print(f"  WARN {url}: page text lacks venue name (soft check)", file=sys.stderr)
        chunks.append(f"[source: {url}]\n{text}")
        used.append(url)
        return True

    for url in dedicated:
        _ingest(url)
    for url in aggregators:
        _ingest(url)
        # Enough signal from curated sources — don't waste time on gated own-sites
        if chunks and sum(len(c) for c in chunks) >= 200:
            break

    if not chunks:
        for url in fallback:
            if _ingest(url):
                break

    page_text = "\n\n".join(chunks)[: MAX_PAGE_CHARS * 2]
    return page_text, used
