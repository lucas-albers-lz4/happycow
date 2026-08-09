"""Source adapter protocol — I/O only; never decide publish policy."""

from __future__ import annotations

from typing import Protocol

from truth.schema import Observation


class SourceAdapter(Protocol):
    name: str

    def discover(self, venue: dict) -> list[str]:
        """Return candidate URLs or signal ids for the venue."""

    def fetch_observations(self, venue: dict) -> list[Observation]:
        """Fetch and return observations (may be empty)."""
