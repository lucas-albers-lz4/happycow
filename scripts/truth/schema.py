"""Observation / claim / decision schemas for the venue truth pipeline."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from common import save_text


class ExtractionMethod(str, Enum):
    REGEX = "regex"
    HEURISTIC = "heuristic"
    LLM = "llm"
    HUMAN = "human"
    PRIOR = "prior"


class FactField(str, Enum):
    BUSINESS_STATUS = "business_status"
    BUSINESS_HOURS = "business_hours"
    HOURS = "hours"
    SPECIALS = "specials"
    ADDRESS = "address"
    PHONE = "phone"


class DecisionKind(str, Enum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    STALE = "stale"
    SUPPRESSED = "suppressed"
    CONFLICTED = "conflicted"
    NEEDS_REVIEW = "needs_review"


BusinessStatusValue = Literal[
    "open",
    "permanently_closed",
    "temporarily_closed",
    "likely_closed",
    "unknown",
]


class Observation(BaseModel):
    """Immutable evidence from one source at one time."""

    venue_id: str
    observed_at: str  # ISO-8601 UTC
    source_url: str = ""
    source_type: str  # own_site | aggregator | overture | overpass | human | social
    source_family: str  # collapsed family for independence (e.g. mthappyhour)
    content_hash: str = ""
    http_status: int | None = None
    extraction_method: ExtractionMethod = ExtractionMethod.HEURISTIC
    evidence_excerpt: str = ""
    # Optional identity signals used for matching
    matched_name: str | None = None
    matched_address: str | None = None
    matched_phone: str | None = None
    matched_overture_id: str | None = None
    # Raw payload for claim extraction (small, structured)
    payload: dict[str, Any] = Field(default_factory=dict)

    def filename_stem(self) -> str:
        stamp = self.observed_at.replace(":", "").replace("-", "")[:15]
        h = (self.content_hash or self.stable_hash())[:12]
        return f"{stamp}-{h}"

    def stable_hash(self) -> str:
        blob = json.dumps(
            {
                "venue_id": self.venue_id,
                "source_url": self.source_url,
                "source_family": self.source_family,
                "payload": self.payload,
                "evidence_excerpt": self.evidence_excerpt[:500],
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha256(blob.encode()).hexdigest()


class Claim(BaseModel):
    """Normalized interpretation of one or more observations for one field."""

    venue_id: str
    field: FactField
    value: Any
    observed_at: str
    source_url: str = ""
    source_type: str = ""
    source_family: str = ""
    evidence_excerpt: str = ""
    weight: float = 1.0  # field-specific source strength × freshness
    expires_at: str | None = None


class Decision(BaseModel):
    """Publish-facing assessment for one field on one venue."""

    venue_id: str
    field: FactField
    kind: DecisionKind
    value: Any = None
    rationale: str = ""
    cited_sources: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    decided_at: str = ""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ObservationStore:
    """Filesystem store under data/evidence/<venue-id>/."""

    def __init__(self, root: Path, retain_per_family: int = 5):
        self.root = root
        self.retain_per_family = retain_per_family

    def venue_dir(self, venue_id: str) -> Path:
        return self.root / venue_id

    def write(self, obs: Observation) -> Path:
        if not obs.content_hash:
            obs = obs.model_copy(update={"content_hash": obs.stable_hash()})
        d = self.venue_dir(obs.venue_id)
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"{obs.filename_stem()}.json"
        save_text(path, obs.model_dump_json(indent=2) + "\n")
        self.compact(obs.venue_id)
        return path

    def list_for_venue(self, venue_id: str) -> list[Observation]:
        d = self.venue_dir(venue_id)
        if not d.is_dir():
            return []
        out: list[Observation] = []
        for p in sorted(d.glob("*.json")):
            try:
                out.append(Observation.model_validate_json(p.read_text(encoding="utf-8")))
            except Exception:  # noqa: BLE001
                continue
        return out

    def compact(self, venue_id: str) -> None:
        """Keep last N observations per source_family; drop older files."""
        by_family: dict[str, list[tuple[Path, Observation]]] = {}
        d = self.venue_dir(venue_id)
        if not d.is_dir():
            return
        for p in d.glob("*.json"):
            try:
                obs = Observation.model_validate_json(p.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                continue
            by_family.setdefault(obs.source_family, []).append((p, obs))
        for _fam, items in by_family.items():
            items.sort(key=lambda t: t[1].observed_at, reverse=True)
            for path, _ in items[self.retain_per_family :]:
                try:
                    path.unlink()
                except OSError:
                    pass
