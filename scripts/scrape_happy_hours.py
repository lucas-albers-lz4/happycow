#!/usr/bin/env python3
"""
Happy Cow scraper — fetch venue pages, extract happy hours via DeepSeek,
merge into data/happy_hour_data.json for GitHub Pages.

Stack:
  1. trafilatura + happy-hour section trim (cheaper / cleaner LLM input)
  2. httpx + tenacity (reliable fetches & API calls)
  3. content-hash cache (skip LLM when page text unchanged)
  4. pydantic validation + one retry (accurate structured extracts)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

import httpx
import trafilatura
from pydantic import BaseModel, Field, ValidationError, field_validator
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

ROOT = Path(__file__).resolve().parent.parent
VENUES_PATH = ROOT / "config" / "venues.json"
DATA_PATH = ROOT / "data" / "happy_hour_data.json"
CACHE_PATH = ROOT / "data" / "scrape_cache.json"
PROMPT_PATH = ROOT / "prompts" / "extract_happy_hour.txt"

ANTHROPIC_API_KEY = (
    os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
)
ANTHROPIC_BASE_URL = os.environ.get(
    "ANTHROPIC_BASE_URL", "https://api.deepseek.com/anthropic"
).rstrip("/")
MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash")

USER_AGENT = "happycow-scraper/1.0 (+https://github.com/lucas-albers-lz4/happycow)"
REQUEST_TIMEOUT = 30.0
INTER_REQUEST_SLEEP = 1.0
MAX_PAGE_CHARS = 8000  # post-trim budget for the model

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


# ─── Pydantic schema ───

class Special(BaseModel):
    item: str = Field(min_length=1)
    price: float = 0.0
    category: Literal["drinks", "food"] = "drinks"
    description: str = ""

    @field_validator("item", "description", mode="before")
    @classmethod
    def strip_str(cls, v):
        return str(v or "").strip()

    @field_validator("price", mode="before")
    @classmethod
    def coerce_price(cls, v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0

    @field_validator("category", mode="before")
    @classmethod
    def coerce_category(cls, v):
        c = str(v or "drinks").lower().strip()
        return c if c in ("drinks", "food") else "drinks"


class ExtractResult(BaseModel):
    status: Literal["ok", "not_found", "unclear"] = "ok"
    hours: str = ""
    business_hours: str = ""
    specials: list[Special] = Field(default_factory=list)
    notes: str | None = None

    @field_validator("hours", "business_hours", mode="before")
    @classmethod
    def normalize_hours_fields(cls, v):
        return normalize_hours(str(v or ""))

    def is_usable(self) -> bool:
        if self.status == "not_found":
            return False
        return bool(self.hours or self.specials)


# ─── IO helpers ───

def load_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


# ─── Fetch + trim ───

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
    # Find heading whose text matches start_pat
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
    # Include the start heading itself
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


# ─── Hours normalize ───

def normalize_hours(hours: str) -> str:
    if not hours:
        return ""
    h = " ".join(hours.strip().split())
    h = re.sub(r"\bevery\s*day\b", "Daily", h, flags=re.I)
    h = re.sub(r"\beveryday\b", "Daily", h, flags=re.I)
    # Collapse day-range spaces: "Mon - Fri" → "Mon-Fri"
    h = re.sub(
        r"\b(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s*-\s*(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\b",
        r"\1-\2",
        h,
        flags=re.I,
    )
    # Lowercase am/pm, drop spaces before them: "3 PM" → "3pm"
    h = re.sub(r"\s*(a\.?m\.?|p\.?m\.?)\b", lambda m: m.group(1)[0].lower() + "m", h, flags=re.I)
    # "3:00pm-6:00pm" → keep; "3:00pm to 6:00pm" → "3:00pm-6:00pm"
    h = re.sub(r"\s+to\s+", "-", h, flags=re.I)
    h = re.sub(r"\s*–\s*|\s*—\s*", "-", h)
    # "4pm - 6pm" → "4pm-6pm"
    h = re.sub(r"(\d(?:am|pm)?)\s+-\s+(\d)", r"\1-\2", h, flags=re.I)
    if h.lower().startswith("daily "):
        h = "Daily " + h[6:]
    # Title-case weekday tokens
    def day_case(m):
        tok = m.group(0)
        if tok.lower() == "daily":
            return "Daily"
        return tok[0].upper() + tok[1:].lower()

    h = re.sub(r"\b(daily|mon|tue|wed|thu|fri|sat|sun)\b", day_case, h, flags=re.I)
    return h


# ─── DeepSeek ───

def extract_message_text(payload: dict) -> str:
    blocks = payload.get("content") or []
    texts = []
    for block in blocks:
        if isinstance(block, str):
            texts.append(block)
            continue
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text" and block.get("text"):
            texts.append(block["text"])
        elif isinstance(block.get("text"), str) and block.get("type") in (None, "text"):
            texts.append(block["text"])
    if texts:
        return "\n".join(texts).strip()
    if isinstance(payload.get("text"), str):
        return payload["text"].strip()
    return ""


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=20),
    retry=retry_if_exception(_is_transient_http_error),
)
def _post_messages(client: httpx.Client, prompt: str) -> dict:
    resp = client.post(
        f"{ANTHROPIC_BASE_URL}/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY or "",
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": MODEL,
            "max_tokens": 2048,
            "thinking": {"type": "disabled"},
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=90.0,
    )
    if resp.status_code in TRANSIENT_HTTP:
        resp.raise_for_status()
    resp.raise_for_status()
    return resp.json()


def call_deepseek(client: httpx.Client, prompt: str) -> str | None:
    if not ANTHROPIC_API_KEY:
        print("ERROR: DEEPSEEK_API_KEY (or ANTHROPIC_API_KEY) not set", file=sys.stderr)
        return None
    try:
        payload = _post_messages(client, prompt)
        text = extract_message_text(payload)
        if not text:
            types = [
                (b.get("type") if isinstance(b, dict) else type(b).__name__)
                for b in (payload.get("content") or [])
            ]
            print(f"  ERROR DeepSeek empty text (content types={types})", file=sys.stderr)
            return None
        return text
    except Exception as e:
        print(f"  ERROR DeepSeek call: {e}", file=sys.stderr)
        return None


def parse_raw_json(raw: str) -> dict | None:
    if not raw:
        return None
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None


def validate_extract(data: dict | None) -> ExtractResult | None:
    if not data:
        return None
    try:
        return ExtractResult.model_validate(data)
    except ValidationError as e:
        print(f"  WARN pydantic validation: {e.error_count()} error(s)", file=sys.stderr)
        return None


def llm_extract(
    client: httpx.Client,
    venue: dict,
    city: str,
    prompt_tmpl: str,
    page_text: str,
    urls: list[str],
) -> ExtractResult | None:
    prompt = (
        prompt_tmpl
        .replace("{name}", venue["name"])
        .replace("{city}", city)
        .replace("{urls}", ", ".join(urls))
        .replace("{page_text}", page_text)
    )
    print(f"  extract via {MODEL}")
    raw = call_deepseek(client, prompt)
    result = validate_extract(parse_raw_json(raw or ""))
    if result:
        return result

    # One retry with a stricter nudge
    print("  retry extract (validation/parse failed)")
    retry_prompt = (
        prompt
        + "\n\nIMPORTANT: Previous reply was invalid. Return ONLY a single JSON object, "
        "no markdown fences, matching the schema exactly."
    )
    raw2 = call_deepseek(client, retry_prompt)
    result2 = validate_extract(parse_raw_json(raw2 or ""))
    if not result2 and raw2:
        print(f"  raw[:300]={raw2[:300]!r}", file=sys.stderr)
    return result2


# ─── Venue pipeline ───

def gather_page_text(client: httpx.Client, venue: dict) -> tuple[str, list[str]]:
    # Dedicated venue pages first (own site, HH subpages) — that's where the
    # real deals live. Aggregator directories (mthappyhour et al.) are fetched
    # after, with an early-break once enough signal exists — so their
    # boilerplate can't starve the curated own-site URLs.
    urls = list(venue.get("scrape_urls") or [])
    def _host(u: str) -> str:
        return urlsplit(u).hostname or ""
    dedicated = [u for u in urls if _host(u) not in AGGREGATOR_HOSTS]
    aggregators = [u for u in urls if _host(u) in AGGREGATOR_HOSTS]
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


def extract_venue(
    client: httpx.Client,
    venue: dict,
    city: str,
    prompt_tmpl: str,
    cache: dict,
    force: bool = False,
) -> tuple[dict | None, bool]:
    """Returns (extract_dict_or_None, cache_hit)."""
    page_text, urls = gather_page_text(client, venue)
    if not page_text:
        print(f"  SKIP {venue['id']}: no page text")
        return None, False

    digest = content_hash(page_text)
    cached = cache.get(venue["id"]) or {}
    if (
        not force
        and cached.get("content_hash") == digest
        and cached.get("extract")
        and cached["extract"].get("status") == "ok"
        and (cached["extract"].get("hours") or cached["extract"].get("specials"))
    ):
        print(f"  cache hit ({digest}) — skip LLM")
        return cached["extract"], True

    result = llm_extract(client, venue, city, prompt_tmpl, page_text, urls)
    if not result:
        print(f"  SKIP {venue['id']}: bad/empty model JSON")
        return None, False

    extract = {
        "status": result.status,
        "hours": result.hours,
        "business_hours": result.business_hours,
        "specials": [s.model_dump() for s in result.specials],
        "notes": result.notes,
    }

    cache[venue["id"]] = {
        "content_hash": digest,
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": urls,
        "extract": extract,
    }
    if result.status == "not_found" or not result.is_usable():
        print(f"  not_found for {venue['id']}")

    return extract, False


def venue_to_site_record(venue: dict, extract: dict | None, previous: dict | None) -> dict:
    prev = previous or {}
    hours = (extract or {}).get("hours") or prev.get("hours") or ""
    business_hours = (extract or {}).get("business_hours") or prev.get("business_hours") or ""
    specials = (extract or {}).get("specials")
    if not specials:
        specials = prev.get("specials") or []

    return {
        "id": venue["id"],
        "name": venue["name"],
        "nickname": venue.get("nickname") or prev.get("nickname") or "",
        "nickname_alts": venue.get("nickname_alts") or prev.get("nickname_alts") or [],
        "address": venue.get("address") or prev.get("address") or "",
        "phone": venue.get("phone") or prev.get("phone") or "",
        "website": venue.get("website") or prev.get("website") or "",
        "maps": venue.get("maps") or prev.get("maps") or "",
        "hours": hours,
        "business_hours": business_hours,
        "tags": venue.get("tags") or prev.get("tags") or [],
        "noise_level": venue.get("noise_level") or prev.get("noise_level") or "",
        "mood": venue.get("mood") or prev.get("mood") or "",
        "specials": specials,
    }


def run(
    dry_run: bool = False,
    venue_ids: list[str] | None = None,
    force: bool = False,
) -> int:
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
    results = []
    ok = fail = kept = cache_hits = 0

    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/json"}
    with httpx.Client(headers=headers, follow_redirects=True, timeout=REQUEST_TIMEOUT) as client:
        for venue in venues:
            print(f"\n== {venue['name']} ({venue['id']}) ==")
            extract, from_cache = extract_venue(
                client, venue, city, prompt_tmpl, cache_venues, force=force
            )
            if from_cache:
                cache_hits += 1

            prev = prev_by_id.get(venue["id"])
            usable = (
                extract
                and extract.get("status") == "ok"
                and (extract.get("hours") or extract.get("specials"))
            )
            if usable:
                ok += 1
                record = venue_to_site_record(venue, extract, prev)
            elif prev:
                kept += 1
                print(f"  keeping previous data for {venue['id']}")
                record = venue_to_site_record(venue, None, prev)
            else:
                fail += 1
                record = venue_to_site_record(venue, {"hours": "", "specials": []}, None)
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

    save_json(DATA_PATH, out)
    save_json(CACHE_PATH, cache_out)
    print(f"Wrote {DATA_PATH}")
    print(f"Wrote {CACHE_PATH}")
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
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore content-hash cache and always call the LLM",
    )
    args = parser.parse_args()
    sys.exit(run(dry_run=args.dry_run, venue_ids=args.venues, force=args.force))


if __name__ == "__main__":
    main()
