"""Uncertainty ranking and cost counters for budgeted expensive work."""

from __future__ import annotations

from typing import Any

from truth.schema import Decision, DecisionKind, FactField


def uncertainty_score(
    venue: dict,
    decisions: dict[str, Decision],
    *,
    has_primary: bool,
) -> float:
    """Higher = more worth spending LLM / deep scrape / social on."""
    score = 0.0
    status = decisions.get(FactField.BUSINESS_STATUS.value)
    if not has_primary:
        score += 2.0
    if status:
        if status.kind in (DecisionKind.CONFLICTED, DecisionKind.NEEDS_REVIEW):
            score += 3.0
        elif status.kind == DecisionKind.UNVERIFIED:
            score += 1.5
        elif status.kind == DecisionKind.STALE:
            score += 1.5
        elif status.kind == DecisionKind.SUPPRESSED:
            score += 0.5  # already decided; less need to burn LLM
        if status.value == "unknown":
            score += 1.0
    else:
        score += 2.0

    for key in (FactField.HOURS.value, FactField.SPECIALS.value):
        d = decisions.get(key)
        if d and d.kind in (DecisionKind.CONFLICTED, DecisionKind.STALE):
            score += 1.0
        if d is None and has_primary:
            score += 0.5

    scrape_urls = venue.get("scrape_urls") or []
    if len(scrape_urls) <= 1:
        score += 0.5
    return score


def rank_uncertain(
    venues: list[dict],
    decisions_by_venue: dict[str, dict[str, Decision]],
    has_primary_fn,
    *,
    top_n: int,
) -> list[str]:
    scored = []
    for v in venues:
        vid = v["id"]
        scored.append(
            (
                uncertainty_score(
                    v,
                    decisions_by_venue.get(vid) or {},
                    has_primary=has_primary_fn(v),
                ),
                vid,
            )
        )
    scored.sort(reverse=True)
    return [vid for _, vid in scored[: max(0, top_n)]]


def empty_counters() -> dict[str, Any]:
    return {
        "fetches": 0,
        "llm_calls": 0,
        "tokens": 0,
        "cache_hits": 0,
        "cache_misses": 0,
        "escalations": 0,
        "overture_matches": 0,
        "overpass_signals": 0,
        "venues_processed": 0,
        "top_n_selected": [],
    }
