#!/usr/bin/env python3
"""Data regression gate: compare candidate data against the HEAD baseline.

Runs AFTER scrape + validate and BEFORE git commit in scrape.yml.  A failed
gate means the pipeline writes nothing — bad data never reaches GitHub Pages.

Hard-fail conditions (exit 1):
  1. VENUE_COUNT_DROP   — candidate has fewer venues than baseline
  2. MISSING_IDS        — baseline venue ids absent from candidate (unexplained removal)
  3. SPECIALS_COVERAGE  — more than SPECIALS_DROP_THRESHOLD venues lost ALL specials
  4. HOURS_WIPE         — more than HOURS_WIPE_THRESHOLD venues lost non-empty hours
  5. COVERAGE_BROKEN    — venues with no specials AND no notes (should be 0)

Report (always printed):
  - Total changed-venues count (hours+specials hash changed) and their ids.
    This output feeds issue #46 (change attribution / changelog).

Mode precedence / PR mode note (#46):
  When this script is wired into a future PR-check workflow the intention is
  that hard-fail conditions should be surfaced as PR review comments rather
  than a bare exit 1.  Until then (PR mode off) exit 1 is the only signal.
  Add --pr-mode / $PR_MODE=1 to switch once the PR annotation step exists.
  Document the escape hatch: --allow-regression skips the hard-fail exit but
  still prints the regression report so the log is never silent.

Usage:
  python scripts/check_data_regression.py [--candidate PATH] [--baseline PATH]
                                           [--allow-regression]

Defaults:
  --candidate  data/happy_hour_data.json   (output of this scrape run)
  --baseline   git show HEAD:data/happy_hour_data.json  (piped in automatically)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ─── Thresholds (adjust here; keep as named constants so diffs are auditable)
SPECIALS_DROP_THRESHOLD = 2   # more than this many venues losing all specials = fail
HOURS_WIPE_THRESHOLD = 1      # more than this many venues losing hours entirely = fail

CANDIDATE_DEFAULT = ROOT / "data" / "happy_hour_data.json"


def _venue_hash(venue: dict) -> str:
    """Stable hash of a venue's runtime content (hours + specials)."""
    payload = json.dumps(
        {"hours": venue.get("hours") or "", "specials": venue.get("specials") or []},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _load_json_from_path(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: cannot read {path}: {exc}", file=sys.stderr)
        sys.exit(1)


def _load_baseline_from_git() -> dict | None:
    """Load HEAD version of data/happy_hour_data.json via git show."""
    try:
        proc = subprocess.run(
            ["git", "show", "HEAD:data/happy_hour_data.json"],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
            check=False,
        )
        if proc.returncode != 0:
            return None
        return json.loads(proc.stdout)
    except Exception:  # noqa: BLE001
        return None


def _check(failures: list[str], cond: bool, msg: str) -> None:
    if not cond:
        failures.append(msg)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--candidate", type=Path, default=CANDIDATE_DEFAULT,
                    help="Path to candidate data file (default: data/happy_hour_data.json)")
    ap.add_argument("--baseline", type=Path, default=None,
                    help="Path to baseline data file (default: git show HEAD:…)")
    ap.add_argument("--allow-regression", action="store_true",
                    help="Print regression report but exit 0 (CI escape hatch)")
    args = ap.parse_args()

    candidate_data = _load_json_from_path(args.candidate)
    candidate_venues = candidate_data.get("venues") or []

    if args.baseline:
        baseline_data = _load_json_from_path(args.baseline)
    else:
        baseline_data = _load_baseline_from_git()

    if baseline_data is None:
        print("INFO: no HEAD baseline found (first run or git unavailable) — skipping regression check")
        return 0

    baseline_venues = baseline_data.get("venues") or []
    baseline_by_id: dict[str, dict] = {v["id"]: v for v in baseline_venues if v.get("id")}
    candidate_by_id: dict[str, dict] = {v["id"]: v for v in candidate_venues if v.get("id")}

    failures: list[str] = []

    # 1. Venue count must not drop
    _check(failures,
           len(candidate_venues) >= len(baseline_venues),
           f"VENUE_COUNT_DROP: {len(baseline_venues)} -> {len(candidate_venues)} venues")

    # 2. Baseline ids must all be present in candidate
    missing_ids = sorted(set(baseline_by_id) - set(candidate_by_id))
    _check(failures, not missing_ids, f"MISSING_IDS: baseline venue ids absent from candidate: {missing_ids}")

    # 3. Specials coverage: count venues that lost ALL specials
    specials_lost = [
        vid for vid, bv in baseline_by_id.items()
        if bv.get("specials") and not (candidate_by_id.get(vid) or {}).get("specials")
    ]
    _check(failures,
           len(specials_lost) <= SPECIALS_DROP_THRESHOLD,
           f"SPECIALS_COVERAGE: {len(specials_lost)} venues lost all specials "
           f"(threshold {SPECIALS_DROP_THRESHOLD}): {specials_lost}")

    # 4. Hours retention: count venues that had hours and now have none
    hours_wiped = [
        vid for vid, bv in baseline_by_id.items()
        if (bv.get("hours") or "").strip()
        and not ((candidate_by_id.get(vid) or {}).get("hours") or "").strip()
    ]
    _check(failures,
           len(hours_wiped) <= HOURS_WIPE_THRESHOLD,
           f"HOURS_WIPE: {len(hours_wiped)} venues lost hours "
           f"(threshold {HOURS_WIPE_THRESHOLD}): {hours_wiped}")

    # 5. Coverage invariant: every venue must have specials OR a non-empty notes
    uncovered = [
        v.get("id") for v in candidate_venues
        if not v.get("specials") and not (v.get("notes") or "").strip()
    ]
    _check(failures, not uncovered,
           f"COVERAGE_BROKEN: venues with no specials AND no notes: {uncovered}")

    # ─── Content-hash report (always printed; feeds issue #46 attribution) ───
    changed_ids: list[str] = []
    for vid, cv in candidate_by_id.items():
        bv = baseline_by_id.get(vid)
        if bv is None:
            changed_ids.append(vid)  # new venue
            continue
        if _venue_hash(cv) != _venue_hash(bv):
            changed_ids.append(vid)

    print(f"REGRESSION CHECK: {len(candidate_venues)} venues | "
          f"{len(changed_ids)} changed (hours/specials): {changed_ids}")

    if failures:
        print("REGRESSION FAILURES:")
        for f in failures:
            print(f"  - {f}")
        if args.allow_regression:
            print("INFO: --allow-regression set — exiting 0 despite failures")
            return 0
        return 1

    print("OK: no regressions detected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
