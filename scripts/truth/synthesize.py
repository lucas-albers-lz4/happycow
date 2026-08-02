"""Apply decisions to site records (suppress path)."""

from __future__ import annotations

from typing import Any

from truth.schema import Decision, DecisionKind, FactField


def apply_decisions_to_record(
    record: dict[str, Any],
    decisions: dict[str, Decision],
    *,
    suppress_enabled: bool,
) -> dict[str, Any]:
    """Return a copy of record with suppress/conflict policy applied.

    When suppress_enabled is False, record is returned unchanged (shadow mode).
    When True and business_status is suppressed/likely_closed, clear specials
    and annotate notes — do not present old HH as current fact.
    """
    out = dict(record)
    if not suppress_enabled:
        return out

    status = decisions.get(FactField.BUSINESS_STATUS.value)
    if not status:
        return out

    if status.kind == DecisionKind.SUPPRESSED or status.value in (
        "permanently_closed",
        "temporarily_closed",
        "likely_closed",
    ):
        out["specials"] = []
        note = (
            f"(verification: business_status={status.value}; "
            f"happy hour suppressed pending human review)"
        )
        existing = (out.get("notes") or "").strip()
        if "happy hour suppressed" not in existing.lower():
            out["notes"] = f"{existing}; {note}".strip("; ").strip()
        # Clear hours so client doesn't show live HH / biz hours for a closed place
        hours_dec = decisions.get(FactField.HOURS.value)
        if hours_dec and hours_dec.kind == DecisionKind.SUPPRESSED:
            out["hours"] = ""
        biz_dec = decisions.get(FactField.BUSINESS_HOURS.value)
        if biz_dec and biz_dec.kind == DecisionKind.SUPPRESSED:
            out["business_hours"] = ""
    elif status.kind == DecisionKind.CONFLICTED:
        note = "(verification: status conflicted — treat hours/specials as unverified)"
        existing = (out.get("notes") or "").strip()
        if "status conflicted" not in existing.lower():
            out["notes"] = f"{existing}; {note}".strip("; ").strip()

    return out


def decisions_needing_review(decisions: dict[str, Decision]) -> list[Decision]:
    return [
        d
        for d in decisions.values()
        if d.kind
        in (
            DecisionKind.SUPPRESSED,
            DecisionKind.CONFLICTED,
            DecisionKind.NEEDS_REVIEW,
        )
    ]
