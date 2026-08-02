"""Social / search connectors — deferred until uncertainty escalation is needed."""

from __future__ import annotations

from truth.schema import Observation


def available() -> bool:
    return False


def fetch_observations(venue: dict) -> list[Observation]:
    """Instagram / Reddit / search-snippet adapters — not enabled in v1."""
    raise NotImplementedError(
        "Social connectors deferred — escalate only after Overture + rules + Overpass"
    )
