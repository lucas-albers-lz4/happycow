"""LLM extraction layer: schema, prompt, DeepSeek call, cache.

Phase 5 of issue #30 — extracted from scripts/scrape_happy_hours.py.
The pydantic schema is the contract for what the LLM may return; extraction
results are cached by content hash so unchanged pages skip the model.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from typing import Literal

import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from common import is_aggregator

from .fetch import TRANSIENT_HTTP, _is_transient_http_error, gather_page_text

ANTHROPIC_API_KEY = (
    os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
)
ANTHROPIC_BASE_URL = os.environ.get(
    "ANTHROPIC_BASE_URL", "https://api.deepseek.com/anthropic"
).rstrip("/")
MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash")


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

    def day_case(m):
        tok = m.group(0)
        if tok.lower() == "daily":
            return "Daily"
        return tok[0].upper() + tok[1:].lower()

    h = re.sub(r"\b(daily|mon|tue|wed|thu|fri|sat|sun)\b", day_case, h, flags=re.I)
    return h


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


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
        dedicated = [u for u in (venue.get("scrape_urls") or []) if not is_aggregator(u)]
        website = venue.get("website") or ""
        if not dedicated and not website:
            print(f"  SKIP {venue['id']}: no page text (no_own_site)")
        else:
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
