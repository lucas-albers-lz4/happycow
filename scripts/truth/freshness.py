"""Freshness / TTL policies for claims."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from truth.schema import FactField

# Soft TTL days by field — past TTL → stale unless refreshed.
TTL_DAYS: dict[FactField, int] = {
    FactField.BUSINESS_STATUS: 30,
    FactField.BUSINESS_HOURS: 21,
    FactField.HOURS: 14,
    FactField.SPECIALS: 14,
    FactField.ADDRESS: 90,
    FactField.PHONE: 90,
}

# Source strength multipliers by field (before freshness decay).
SOURCE_STRENGTH: dict[FactField, dict[str, float]] = {
    FactField.BUSINESS_STATUS: {
        "own_site": 1.0,
        "overture": 0.95,
        "overpass": 0.85,
        "human": 1.0,
        "aggregator": 0.25,
        "social": 0.2,
    },
    FactField.HOURS: {
        "own_site": 1.0,
        "overture": 0.4,
        "aggregator": 0.45,
        "human": 1.0,
        "social": 0.15,
        "overpass": 0.1,
    },
    FactField.BUSINESS_HOURS: {
        "own_site": 1.0,
        "overture": 0.5,
        "aggregator": 0.4,
        "human": 1.0,
        "social": 0.1,
        "overpass": 0.1,
    },
    FactField.SPECIALS: {
        "own_site": 1.0,
        "aggregator": 0.4,
        "human": 1.0,
        "social": 0.2,
        "overture": 0.05,
        "overpass": 0.0,
    },
}


def _parse_iso(s: str) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.strptime(s.replace("Z", "+0000"), "%Y-%m-%dT%H:%M:%S%z")
    except ValueError:
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return None


def age_days(observed_at: str, now: datetime | None = None) -> float:
    now = now or datetime.now(timezone.utc)
    t = _parse_iso(observed_at)
    if not t:
        return 999.0
    return max(0.0, (now - t).total_seconds() / 86400.0)


def freshness_factor(observed_at: str, field: FactField, now: datetime | None = None) -> float:
    """1.0 fresh → decays to 0 after 2× TTL."""
    ttl = TTL_DAYS.get(field, 30)
    age = age_days(observed_at, now)
    if age <= ttl:
        return 1.0
    if age >= ttl * 2:
        return 0.0
    return 1.0 - (age - ttl) / ttl


def is_stale(observed_at: str, field: FactField, now: datetime | None = None) -> bool:
    return age_days(observed_at, now) > TTL_DAYS.get(field, 30)


def claim_weight(
    source_type: str,
    field: FactField,
    observed_at: str,
    now: datetime | None = None,
) -> float:
    base = SOURCE_STRENGTH.get(field, {}).get(source_type, 0.3)
    return base * freshness_factor(observed_at, field, now)


def expires_at(observed_at: str, field: FactField) -> str | None:
    t = _parse_iso(observed_at)
    if not t:
        return None
    exp = t + timedelta(days=TTL_DAYS.get(field, 30))
    return exp.strftime("%Y-%m-%dT%H:%M:%SZ")
