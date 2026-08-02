"""LLM data fusion fallback — deferred for residual high-uncertainty conflicts."""

from __future__ import annotations

from typing import Any

from truth.schema import Claim, Decision


def available() -> bool:
    return False


def fuse_claims(claims: list[Claim], *, model: str | None = None) -> Decision:
    """Structured LLM fusion over conflicting claims (2026 single/multi-truth style).

    Only invoke for residual conflicts after agreement v1 (and optional Depen).
    """
    raise NotImplementedError(
        "LLM fusion deferred — escalate via review queue until enabled"
    )


def should_fuse(decisions: dict[str, Decision]) -> bool:
    """Heuristic gate — True when a conflict remains unresolved."""
    from truth.schema import DecisionKind

    return any(d.kind == DecisionKind.CONFLICTED for d in decisions.values())
