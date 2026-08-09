"""Entity matching — shared contamination / identity guard."""

from __future__ import annotations

import re
from typing import Any


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def street_token(address: str) -> str | None:
    """Street number + first street word, normalized (e.g. 1235n)."""
    addr = _norm(address)
    m = re.match(r"(\d+[a-z]+?)", addr)
    return m.group(1) if m else None


def names_match(a: str, b: str) -> bool:
    """Loose name equality after stripping leading articles."""
    na = _norm(a.replace("The ", "").replace("the ", ""))
    nb = _norm(b.replace("The ", "").replace("the ", ""))
    if not na or not nb:
        return False
    return na == nb or na in nb or nb in na


def phones_match(a: str, b: str) -> bool:
    da = re.sub(r"\D", "", a or "")
    db = re.sub(r"\D", "", b or "")
    if len(da) < 7 or len(db) < 7:
        return False
    return da[-10:] == db[-10:]


def page_matches_venue(text: str, venue: dict, require_address: bool) -> bool:
    """Contamination guard (lifted from scraper.fetch for shared use).

    Aggregator pages must contain name AND street token. Own-site: name only.
    """
    t = _norm(text)
    name = _norm((venue.get("name") or "").replace("The ", "").replace("the ", ""))
    if not name or name not in t:
        return False
    if require_address:
        tok = street_token(venue.get("address") or "")
        if not tok:
            return True
        return tok in t
    return True


def venue_matches_candidate(
    venue: dict,
    *,
    name: str | None = None,
    address: str | None = None,
    phone: str | None = None,
) -> bool:
    """Match a curated venue to an external POI candidate (Overture, etc.)."""
    if name and not names_match(venue.get("name") or "", name):
        return False
    if not name:
        return False

    v_phone = venue.get("phone") or ""
    if phone and v_phone and phones_match(v_phone, phone):
        return True

    v_addr = venue.get("address") or ""
    if address and v_addr:
        vt = street_token(v_addr)
        ct = street_token(address)
        if vt and ct and vt == ct:
            return True
        # Fallback: street number alone if both have it
        vn = re.match(r"(\d+)", _norm(v_addr))
        cn = re.match(r"(\d+)", _norm(address))
        if vn and cn and vn.group(1) == cn.group(1):
            return True

    # Name-only match is allowed when venue has no address/phone to corroborate
    # (still risky — callers should prefer address). Used as last resort.
    if not (v_addr or v_phone):
        return True
    # Name matched but address/phone present without corroboration → reject
    return False


def match_score(venue: dict, candidate: dict[str, Any]) -> float:
    """0–1 score for ranking Overture candidates."""
    score = 0.0
    if names_match(venue.get("name") or "", candidate.get("name") or ""):
        score += 0.5
    else:
        return 0.0
    if venue_matches_candidate(
        venue,
        name=candidate.get("name"),
        address=candidate.get("address"),
        phone=candidate.get("phone"),
    ):
        score += 0.3
    if phones_match(venue.get("phone") or "", candidate.get("phone") or ""):
        score += 0.2
    return min(1.0, score)
