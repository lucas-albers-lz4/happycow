"""Depen_Simple iterative truth discovery — deferred until agreement v1 plateaus.

Extension point only. Call `available()` before use; raise if not ready.
"""

from __future__ import annotations

from truth.schema import Claim, Decision


def available() -> bool:
    """Depen is not enabled until eval shows rules are the bottleneck."""
    return False


def agree_depen(claims: list[Claim]) -> dict[str, Decision]:
    """Placeholder for Dong-style iterative source reliability + claim truth.

    Implement when:
    - multi-run claim history exists under data/evidence/
    - agreement v1 precision plateaus on data/eval/golden_venues.json
    """
    raise NotImplementedError(
        "Depen_Simple deferred — use truth.agreement.agree_venue until eval plateaus"
    )
