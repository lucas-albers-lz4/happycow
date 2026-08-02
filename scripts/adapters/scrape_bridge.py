"""Bridge scrape extracts into truth observations (provenance)."""

from __future__ import annotations

from typing import Any

from common import host_of, is_aggregator
from truth.agreement import source_family_for
from truth.schema import ExtractionMethod, Observation, utc_now_iso


def _primary_source_url(source_urls: list[str]) -> str:
    """Prefer first non-aggregator URL so own-site evidence is visible to agreement."""
    urls = [u for u in (source_urls or []) if u]
    if not urls:
        return ""
    for url in urls:
        if not is_aggregator(url):
            return url
    return urls[0]


def observation_from_scrape(
    venue: dict,
    extract: dict[str, Any] | None,
    source_urls: list[str],
    *,
    content_hash: str = "",
    observed_at: str | None = None,
) -> Observation | None:
    """Build an observation from a successful scrape extract."""
    if not extract or extract.get("status") not in (None, "ok"):
        # Some extracts may omit status
        if not extract:
            return None
        if extract.get("status") and extract.get("status") != "ok":
            return None
    if not (extract.get("hours") or extract.get("specials") or extract.get("business_hours")):
        return None

    primary_url = _primary_source_url(source_urls)
    agg = bool(primary_url) and is_aggregator(primary_url)
    source_type = "aggregator" if agg else "own_site"
    family = source_family_for(host_of(primary_url) or primary_url, source_type)

    payload: dict[str, Any] = {
        "business_status": "open",  # scrape success implies still advertising
        "hours": extract.get("hours") or "",
        "business_hours": extract.get("business_hours") or "",
        "specials": extract.get("specials") or [],
        "notes": extract.get("notes") or "",
        "source_urls": source_urls,
    }
    excerpt_bits = []
    if payload["hours"]:
        excerpt_bits.append(f"hours={payload['hours']}")
    if payload["specials"]:
        excerpt_bits.append(f"specials={len(payload['specials'])} items")
    return Observation(
        venue_id=venue["id"],
        observed_at=observed_at or utc_now_iso(),
        source_url=primary_url,
        source_type=source_type,
        source_family=family,
        content_hash=content_hash,
        extraction_method=ExtractionMethod.LLM,
        evidence_excerpt="; ".join(excerpt_bits)[:500],
        matched_name=venue.get("name"),
        matched_address=venue.get("address"),
        payload=payload,
    )
