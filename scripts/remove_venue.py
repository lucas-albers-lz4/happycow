#!/usr/bin/env python3
"""Remove a venue from the dataset (use when closure is confirmed).

Removes the venue from BOTH `config/venues.json` (source of truth) and
`data/happy_hour_data.json` (site data), and records a tombstone in
`data/removed_venues.json` so `discover_venues.py` does not re-add it.

Usage:
  python scripts/remove_venue.py open-range --reason "closed June 2026, Meson Frailes taking over 241 E Main"
  python scripts/remove_venue.py broken-spoke-bar-grill the-bay   # multiple ids

Run with --dry-run to preview what would change.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "venues.json"
DATA_PATH = ROOT / "data" / "happy_hour_data.json"
REMOVED_PATH = ROOT / "data" / "removed_venues.json"


def norm_name(name: str) -> str:
    return " ".join(name.lower().split())


def norm_address(addr: str) -> str:
    return " ".join(addr.lower().split())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("venue_ids", nargs="+", help="venue id(s) to remove")
    ap.add_argument("--reason", default="", help="why (e.g. 'closed June 2026')")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cfg = json.loads(CONFIG_PATH.read_text())
    data = json.loads(DATA_PATH.read_text())
    removed = json.loads(REMOVED_PATH.read_text()) if REMOVED_PATH.exists() else {"venues": []}

    cfg_by_id = {v["id"]: v for v in cfg["venues"]}
    missing = [i for i in args.venue_ids if i not in cfg_by_id]
    if missing:
        print(f"ERROR: unknown venue id(s): {missing}", file=sys.stderr)
        return 2

    for vid in args.venue_ids:
        v = cfg_by_id[vid]
        tombstone = {
            "id": vid,
            "name": v["name"],
            "norm_name": norm_name(v["name"]),
            "norm_address": norm_address(v.get("address", "")),
            "removed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "reason": args.reason,
        }
        cfg["venues"] = [x for x in cfg["venues"] if x["id"] != vid]
        data["venues"] = [x for x in data["venues"] if x["id"] != vid]
        removed["venues"] = [x for x in removed["venues"] if x["id"] != vid] + [tombstone]
        print(f"removed {vid} ({v['name']})" + (f" — {args.reason}" if args.reason else ""))

    if args.dry_run:
        print("(dry run — nothing written)")
        return 0

    CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")
    DATA_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    REMOVED_PATH.write_text(json.dumps(removed, indent=2, ensure_ascii=False) + "\n")
    print(f"config: {len(cfg['venues'])} venues | data: {len(data['venues'])} venues")
    print(f"tombstones: {len(removed['venues'])} -> {REMOVED_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
