"""Rule-based agreement v1 — field weights, source families, closure asymmetry."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from truth.freshness import claim_weight, is_stale
from truth.schema import (
    Claim,
    Decision,
    DecisionKind,
    ExtractionMethod,
    FactField,
    Observation,
    utc_now_iso,
)

# Known copy-prone aggregator families collapse to one vote.
FAMILY_ALIASES = {
    "mthappyhour.com": "mthappyhour",
    "bozemanmagazine.com": "local_directory",
    "visit-bozeman.com": "local_directory",
    "menupix.com": "menupix",
    "yelp.com": "yelp",
    "sellout.io": "sellout",
    "google.com": "google",
    "facebook.com": "facebook",
}


def source_family_for(url_or_type: str, source_type: str) -> str:
    if source_type in ("overture", "overpass", "human", "own_site", "social"):
        return source_type
    host = url_or_type.lower()
    for suffix, fam in FAMILY_ALIASES.items():
        if suffix in host:
            return fam
    return source_type or "unknown"


CLOSED_VALUES = frozenset({"permanently_closed", "temporarily_closed", "likely_closed"})


def observations_to_claims(observations: list[Observation]) -> list[Claim]:
    """Extract claims from observation payloads."""
    claims: list[Claim] = []
    for obs in observations:
        payload = obs.payload or {}
        status = payload.get("business_status")
        if status:
            claims.append(
                Claim(
                    venue_id=obs.venue_id,
                    field=FactField.BUSINESS_STATUS,
                    value=status,
                    observed_at=obs.observed_at,
                    source_url=obs.source_url,
                    source_type=obs.source_type,
                    source_family=obs.source_family,
                    evidence_excerpt=obs.evidence_excerpt[:400],
                    weight=claim_weight(obs.source_type, FactField.BUSINESS_STATUS, obs.observed_at),
                )
            )
        for key, field in (
            ("hours", FactField.HOURS),
            ("business_hours", FactField.BUSINESS_HOURS),
            ("specials", FactField.SPECIALS),
            ("address", FactField.ADDRESS),
            ("phone", FactField.PHONE),
        ):
            if key in payload and payload[key] not in (None, "", []):
                claims.append(
                    Claim(
                        venue_id=obs.venue_id,
                        field=field,
                        value=payload[key],
                        observed_at=obs.observed_at,
                        source_url=obs.source_url,
                        source_type=obs.source_type,
                        source_family=obs.source_family,
                        evidence_excerpt=obs.evidence_excerpt[:400],
                        weight=claim_weight(obs.source_type, field, obs.observed_at),
                    )
                )
    return claims


def _collapse_by_family(claims: list[Claim]) -> list[Claim]:
    """Keep highest-weight claim per (family, value) for independence."""
    best: dict[tuple[str, str], Claim] = {}
    for c in claims:
        key = (c.source_family, _value_key(c.value))
        prev = best.get(key)
        if prev is None or c.weight > prev.weight:
            best[key] = c
    # One vote per family: if same family asserts multiple values, keep max weight
    by_fam: dict[str, Claim] = {}
    for c in best.values():
        prev = by_fam.get(c.source_family)
        if prev is None or c.weight > prev.weight:
            by_fam[c.source_family] = c
    return list(by_fam.values())


def _value_key(value: Any) -> str:
    if isinstance(value, (list, dict)):
        return repr(value)[:200]
    return str(value).strip().lower()


def _agree_status(claims: list[Claim], has_primary: bool) -> Decision:
    """business_status with closure asymmetry + aggregator-only cap."""
    now_iso = utc_now_iso()
    if not claims:
        return Decision(
            venue_id="",
            field=FactField.BUSINESS_STATUS,
            kind=DecisionKind.UNVERIFIED,
            value="unknown",
            rationale="no status claims",
            decided_at=now_iso,
        )

    collapsed = _collapse_by_family(claims)
    closed = [c for c in collapsed if str(c.value) in CLOSED_VALUES]
    open_c = [c for c in collapsed if str(c.value) == "open"]

    strong_closed = [
        c
        for c in closed
        if c.source_type in ("overture", "own_site", "human", "overpass") and c.weight >= 0.4
    ]
    weak_closed = [c for c in closed if c not in strong_closed]

    cited = [c.source_url or c.source_family for c in collapsed]

    if strong_closed:
        primary = max(strong_closed, key=lambda c: c.weight)
        kind = DecisionKind.SUPPRESSED
        if primary.source_type == "human" or (
            primary.source_type == "overture" and str(primary.value) == "permanently_closed"
        ):
            val = str(primary.value)
        else:
            val = "likely_closed"
        return Decision(
            venue_id=primary.venue_id,
            field=FactField.BUSINESS_STATUS,
            kind=kind,
            value=val,
            rationale=f"strong closed signal from {primary.source_type}/{primary.source_family}",
            cited_sources=cited,
            confidence=min(1.0, primary.weight + 0.2 * (len(strong_closed) - 1)),
            decided_at=now_iso,
        )

    if len(weak_closed) >= 2 or (weak_closed and open_c):
        vid = (weak_closed or open_c)[0].venue_id
        return Decision(
            venue_id=vid,
            field=FactField.BUSINESS_STATUS,
            kind=DecisionKind.NEEDS_REVIEW if len(weak_closed) == 1 and not open_c else DecisionKind.CONFLICTED,
            value="likely_closed" if len(weak_closed) >= 2 else "unknown",
            rationale="weak/conflicting closed signals",
            cited_sources=cited,
            confidence=0.4,
            decided_at=now_iso,
        )

    if len(weak_closed) == 1 and not open_c:
        c = weak_closed[0]
        return Decision(
            venue_id=c.venue_id,
            field=FactField.BUSINESS_STATUS,
            kind=DecisionKind.NEEDS_REVIEW,
            value="unknown",
            rationale=f"single weak closed signal from {c.source_family}",
            cited_sources=cited,
            confidence=0.3,
            decided_at=now_iso,
        )

    # Open path
    if open_c:
        best = max(open_c, key=lambda c: c.weight)
        primary_open = any(c.source_type in ("own_site", "overture", "human") for c in open_c)
        only_agg = all(c.source_type == "aggregator" for c in open_c)
        if only_agg or (not has_primary and not primary_open):
            return Decision(
                venue_id=best.venue_id,
                field=FactField.BUSINESS_STATUS,
                kind=DecisionKind.UNVERIFIED,
                value="open",
                rationale="aggregator-only open — cannot verified:open",
                cited_sources=cited,
                confidence=0.35,
                decided_at=now_iso,
            )
        if is_stale(best.observed_at, FactField.BUSINESS_STATUS):
            return Decision(
                venue_id=best.venue_id,
                field=FactField.BUSINESS_STATUS,
                kind=DecisionKind.STALE,
                value="open",
                rationale="open claim past TTL",
                cited_sources=cited,
                confidence=0.4,
                decided_at=now_iso,
            )
        return Decision(
            venue_id=best.venue_id,
            field=FactField.BUSINESS_STATUS,
            kind=DecisionKind.VERIFIED,
            value="open",
            rationale="primary/open corroboration",
            cited_sources=cited,
            confidence=min(1.0, best.weight),
            decided_at=now_iso,
        )

    vid = claims[0].venue_id
    return Decision(
        venue_id=vid,
        field=FactField.BUSINESS_STATUS,
        kind=DecisionKind.UNVERIFIED,
        value="unknown",
        rationale="no open/closed consensus",
        cited_sources=cited,
        decided_at=now_iso,
    )


def _agree_generic(claims: list[Claim], field: FactField) -> Decision:
    now_iso = utc_now_iso()
    if not claims:
        return Decision(
            venue_id="",
            field=field,
            kind=DecisionKind.UNVERIFIED,
            value=None,
            rationale="no claims",
            decided_at=now_iso,
        )
    collapsed = _collapse_by_family(claims)
    by_val: dict[str, list[Claim]] = defaultdict(list)
    for c in collapsed:
        by_val[_value_key(c.value)].append(c)

    if len(by_val) > 1:
        top = sorted(by_val.values(), key=lambda cs: sum(c.weight for c in cs), reverse=True)
        if abs(sum(c.weight for c in top[0]) - sum(c.weight for c in top[1])) < 0.15:
            return Decision(
                venue_id=claims[0].venue_id,
                field=field,
                kind=DecisionKind.CONFLICTED,
                value=top[0][0].value,
                rationale="conflicting values across independent families",
                cited_sources=[c.source_url or c.source_family for c in collapsed],
                confidence=0.4,
                decided_at=now_iso,
            )

    best_group = max(by_val.values(), key=lambda cs: sum(c.weight for c in cs))
    best = max(best_group, key=lambda c: c.weight)
    weight_sum = sum(c.weight for c in best_group)
    if is_stale(best.observed_at, field):
        kind = DecisionKind.STALE
    elif weight_sum >= 0.7 and any(c.source_type in ("own_site", "human") for c in best_group):
        kind = DecisionKind.VERIFIED
    elif weight_sum >= 0.5:
        kind = DecisionKind.UNVERIFIED
    else:
        kind = DecisionKind.UNVERIFIED

    return Decision(
        venue_id=best.venue_id,
        field=field,
        kind=kind,
        value=best.value,
        rationale=f"agreement weight={weight_sum:.2f}",
        cited_sources=[c.source_url or c.source_family for c in collapsed],
        confidence=min(1.0, weight_sum),
        decided_at=now_iso,
    )


def agree_venue(
    venue_id: str,
    observations: list[Observation],
    *,
    has_primary_source: bool = False,
) -> dict[str, Decision]:
    """Run agreement v1 for all fields present in observations.

    Returns map field.value → Decision. Santa Fe class: if status is
    suppressed/likely_closed and hours/specials exist from aggregators only,
    mark specials/hours suppressed too.
    """
    claims = observations_to_claims(observations)
    for c in claims:
        if not c.venue_id:
            c.venue_id = venue_id

    by_field: dict[FactField, list[Claim]] = defaultdict(list)
    for c in claims:
        by_field[c.field].append(c)

    decisions: dict[str, Decision] = {}
    status_claims = by_field.get(FactField.BUSINESS_STATUS, [])
    status_dec = _agree_status(status_claims, has_primary_source)
    status_dec.venue_id = venue_id
    decisions[FactField.BUSINESS_STATUS.value] = status_dec

    for field, flist in by_field.items():
        if field == FactField.BUSINESS_STATUS:
            continue
        d = _agree_generic(flist, field)
        d.venue_id = venue_id
        decisions[field.value] = d

    # Santa Fe class: closed/suppressed status suppresses HH publish fields
    if status_dec.kind in (DecisionKind.SUPPRESSED, DecisionKind.CONFLICTED) or (
        status_dec.value in CLOSED_VALUES
    ):
        for f in (FactField.HOURS, FactField.SPECIALS, FactField.BUSINESS_HOURS):
            key = f.value
            existing = decisions.get(key)
            decisions[key] = Decision(
                venue_id=venue_id,
                field=f,
                kind=DecisionKind.SUPPRESSED,
                value=None if f == FactField.SPECIALS else (existing.value if existing else None),
                rationale=f"suppressed due to business_status={status_dec.value}",
                cited_sources=status_dec.cited_sources,
                confidence=status_dec.confidence,
                decided_at=utc_now_iso(),
            )

    return decisions


def venue_has_primary(venue: dict) -> bool:
    """True if venue has a non-aggregator website or scrape_url."""
    from common import is_aggregator  # local import — truth may run under scripts/

    website = venue.get("website") or ""
    if website and not is_aggregator(website):
        return True
    for u in venue.get("scrape_urls") or []:
        if u and not is_aggregator(u):
            return True
    return False
