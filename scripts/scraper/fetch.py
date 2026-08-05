"""Page acquisition layer: fetch, trim, and the contamination guard.

Phase 5 of issue #30 — extracted from scripts/scrape_happy_hours.py.
Own-site pages are fetched before aggregators; aggregator pages are only
accepted when they match the venue (name + street number/word).

Fetch strategy:
  1. httpx with browser-like headers (many WAFs reject custom bot UAs)
  2. Classify failures (http403 / challenge / empty_body / empty_extract / …)
  3. Optional Playwright Chromium fallback for own-site URLs that look
     blocked or JS-empty (set HAPPYCOW_BROWSER_FETCH=0 to disable)
"""

from __future__ import annotations

import os
import re
import sys
import time
from dataclasses import dataclass

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
    "BROWSER_HEADERS",
    "FetchResult",
    "fetch_html",
    "html_to_trimmed_text",
    "html_section_by_heading",
    "is_challenge_page",
    "page_matches_venue",
    "gather_page_text",
    "trim_happy_hour_section",
]


def page_matches_venue(text: str, venue: dict, require_address: bool) -> bool:
    """Lazy-import truth.identity so scrape works without the truth package."""
    from truth.identity import page_matches_venue as _match

    return _match(text, venue, require_address)


# Desktop Chrome — custom bot UAs (happycow-scraper/1.0) trip Cloudflare/WAF.
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    # Omit br — avoids binary bodies when brotli isn't installed for httpx.
    "Accept-Encoding": "gzip, deflate",
    "Upgrade-Insecure-Requests": "1",
}

INTER_REQUEST_SLEEP = 1.0
MAX_PAGE_CHARS = 8000  # post-trim budget for the model
TRANSIENT_HTTP = {429, 500, 502, 503, 504}
BROWSER_FETCH_ENV = "HAPPYCOW_BROWSER_FETCH"
PLAYWRIGHT_TIMEOUT_MS = 25_000


@dataclass(frozen=True)
class FetchResult:
    html: str | None
    reason: str  # ok | httpNNN | challenge | empty_body | transport | disabled

    @property
    def ok(self) -> bool:
        return bool(self.html) and self.reason == "ok"


def browser_fetch_enabled() -> bool:
    raw = (os.environ.get(BROWSER_FETCH_ENV) or "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def is_challenge_page(html: str) -> bool:
    """True when the body is a bot interstitial rather than venue content.

    Avoids false positives on real pages that merely mention 'captcha' in
    third-party scripts (e.g. Gravity Forms / Cloudflare analytics).
    """
    if not html:
        return False
    low = html.lower()
    if re.search(r"<title[^>]*>\s*just a moment", low):
        return True
    if re.search(r"<title[^>]*>\s*attention required", low):
        return True
    if "cf-browser-verification" in low:
        return True
    # Challenge platform + thin / content-less shell
    if "cdn-cgi/challenge-platform" in low or "challenge-platform" in low:
        if len(html) < 20_000 and not re.search(
            r"happy\s*hour|daily\s+special|menu|hours", low
        ):
            return True
    if "enable javascript and cookies to continue" in low and len(html) < 15_000:
        return True
    return False


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


def fetch_html(client: httpx.Client, url: str) -> FetchResult:
    """httpx GET with classification. Returns usable HTML only when reason=ok."""
    try:
        resp = _http_get(client, url)
    except Exception as e:
        print(f"  WARN fetch failed transport {url}: {e}", file=sys.stderr)
        return FetchResult(None, "transport")

    status = resp.status_code
    html = resp.text or ""

    if status >= 400:
        reason = f"http{status}"
        print(f"  WARN fetch skipped {reason} {url}", file=sys.stderr)
        return FetchResult(None, reason)

    if not html.strip():
        print(f"  WARN fetch empty_body {url}", file=sys.stderr)
        return FetchResult(None, "empty_body")

    if is_challenge_page(html):
        print(f"  WARN fetch challenge {url}", file=sys.stderr)
        return FetchResult(None, "challenge")

    return FetchResult(html, "ok")


def fetch_html_playwright(url: str) -> FetchResult:
    """Headless Chromium fallback for own-site WAF / JS shells.

    No-op (reason=disabled) when Playwright isn't installed or
    HAPPYCOW_BROWSER_FETCH=0.
    """
    if not browser_fetch_enabled():
        return FetchResult(None, "disabled")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            f"  WARN browser fallback unavailable (install playwright) {url}",
            file=sys.stderr,
        )
        return FetchResult(None, "disabled")

    print(f"  browser fallback {url}")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                context = browser.new_context(
                    user_agent=BROWSER_HEADERS["User-Agent"],
                    locale="en-US",
                )
                page = context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=PLAYWRIGHT_TIMEOUT_MS)
                # Give SPA/hydration a short beat without waiting forever.
                page.wait_for_timeout(1500)
                html = page.content() or ""
            finally:
                browser.close()
    except Exception as e:
        print(f"  WARN browser fallback failed {url}: {e}", file=sys.stderr)
        return FetchResult(None, "transport")

    if not html.strip():
        print(f"  WARN browser empty_body {url}", file=sys.stderr)
        return FetchResult(None, "empty_body")
    if is_challenge_page(html):
        print(f"  WARN browser challenge {url}", file=sys.stderr)
        return FetchResult(None, "challenge")
    return FetchResult(html, "ok")


def _should_browser_fallback(url: str, result: FetchResult, trimmed: str) -> bool:
    if is_aggregator(url):
        return False
    if not browser_fetch_enabled():
        return False
    if result.reason in ("http403", "http401", "http429", "challenge", "empty_body"):
        return True
    if result.ok and not trimmed:
        return True
    return False


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
    miss_reasons: list[str] = []

    def _ingest(url: str) -> bool:
        print(f"  fetch {url}")
        result = fetch_html(client, url)
        time.sleep(INTER_REQUEST_SLEEP)
        text = html_to_trimmed_text(result.html) if result.ok and result.html else ""

        if _should_browser_fallback(url, result, text):
            why = result.reason if not (result.ok and not text) else "empty_extract"
            print(f"  WARN empty_extract {url}" if why == "empty_extract" else f"  NOTE retry via browser ({why})")
            result = fetch_html_playwright(url)
            time.sleep(INTER_REQUEST_SLEEP)
            text = html_to_trimmed_text(result.html) if result.ok and result.html else ""
            if result.ok and not text:
                print(f"  WARN empty_extract {url}", file=sys.stderr)
                miss_reasons.append(f"{url}:empty_extract")
                return False

        if not result.ok or not result.html:
            miss_reasons.append(f"{url}:{result.reason}")
            return False
        if not text:
            print(f"  WARN empty_extract {url}", file=sys.stderr)
            miss_reasons.append(f"{url}:empty_extract")
            return False

        # Contamination guard: aggregator pages must match this venue
        # (name + street address) or they're skipped — they've been caught
        # carrying other venues' content (Old Chicago <- Bozeman Spirits, …).
        if is_aggregator(url):
            if not page_matches_venue(text, venue, require_address=True):
                print(
                    f"  SKIP {url}: aggregator page doesn't match venue (contamination guard)",
                    file=sys.stderr,
                )
                miss_reasons.append(f"{url}:contamination")
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

    if not chunks:
        if not dedicated and not fallback:
            print(
                f"  NOTE no_own_site for {venue.get('id')} — only aggregators/none configured",
                file=sys.stderr,
            )
        elif miss_reasons:
            # Compact summary for the extract_venue SKIP line context
            summary = ", ".join(miss_reasons[:6])
            if len(miss_reasons) > 6:
                summary += f", +{len(miss_reasons) - 6} more"
            print(f"  NOTE fetch_misses: {summary}", file=sys.stderr)

    page_text = "\n\n".join(chunks)[: MAX_PAGE_CHARS * 2]
    return page_text, used
