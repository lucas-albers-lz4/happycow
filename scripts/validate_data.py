#!/usr/bin/env python3
"""Validate data/happy_hour_data.json against the venue contract.

Phase 3 of issue #30. Dependency-free mirror of schema/venue.schema.json
(the schema file is the documented contract; this checker enforces it without
needing jsonschema installed in CI).

Checks:
1. JSON parses; top-level shape right
2. Per-venue schema: required keys, types, id format + uniqueness,
   specials shape (category enum, price >= 0), no pipeline-only keys
   (scrape_urls), nickname present
3. Price-0 semantics (MCR rule): a price-0 special must carry free/discount
   wording in its description or the venue note — otherwise it's a data
   quality bug, not a free item
4. Hours strings parse — delegated to the SINGLE source of truth (the JS
   parser in assets/js/hours.js) via node scripts/validate_hours.mjs
5. Coverage invariant: every venue has specials OR a notes entry
6. Config/data parity: identical id sets between config and data

Exit 0 = pass, 1 = fail (details printed to stdout).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "happy_hour_data.json"
CONFIG_PATH = ROOT / "config" / "venues.json"
HOURS_VALIDATOR = ROOT / "scripts" / "validate_hours.mjs"

REQUIRED_KEYS = {
    "id", "name", "nickname", "address", "phone", "website", "maps",
    "tags", "noise_level", "mood", "hours", "business_hours", "specials",
}
PIPELINE_ONLY_KEYS = {"scrape_urls"}
SPECIAL_REQUIRED = {"item", "price", "category", "description"}
ID_RE = re.compile(r"^[a-z0-9-]+$")
# Words that give a price-0 special free/discount context (MCR rule).
PRICE0_CONTEXT = (
    "free", "complimentary", "no charge", "off", "discount", "half", "bogo",
    "special", "price", "deal", "cents", "$", "%", "2 for 1", "2-4-1",
)

errors: list[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        errors.append(msg)


def main() -> int:
    try:
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: data file unparseable: {exc}")
        return 1

    venues = data.get("venues")
    check(isinstance(venues, list), "top-level 'venues' must be a list")

    ids: list[str] = []
    for v in venues or []:
        if not isinstance(v, dict):
            check(False, "venue entries must be objects")
            continue
        vid = v.get("id")
        ids.append(vid or "")
        check(bool(vid) and bool(ID_RE.match(str(vid))), f"{vid}: bad id (want [a-z0-9-]+)")
        for k in REQUIRED_KEYS:
            check(k in v, f"{vid}: missing required key '{k}'")
        for k in PIPELINE_ONLY_KEYS:
            check(k not in v, f"{vid}: pipeline-only key '{k}' leaked into site data")
        check(bool(v.get("nickname")), f"{vid}: empty nickname")
        check(isinstance(v.get("tags"), list), f"{vid}: 'tags' must be a list")

        specs = v.get("specials")
        check(isinstance(specs, list), f"{vid}: 'specials' must be a list")
        for s in specs or []:
            if not isinstance(s, dict):
                check(False, f"{vid}: special entries must be objects")
                continue
            for k in SPECIAL_REQUIRED:
                check(k in s, f"{vid}: special missing '{k}'")
            check(s.get("category") in ("drinks", "food"), f"{vid}: special category must be drinks|food")
            price = s.get("price")
            check(isinstance(price, (int, float)) and not isinstance(price, bool) and price >= 0,
                  f"{vid}: special price must be a number >= 0")
            if price == 0:
                desc = (s.get("description") or "").lower()
                note = (v.get("notes") or "").lower()
                has_ctx = any(w in desc for w in PRICE0_CONTEXT) or "free" in note
                check(has_ctx, f"{vid}: price-0 special '{s.get('item')}' has no free/discount wording")

    dup = {x for x in ids if ids.count(x) > 1}
    check(not dup, f"duplicate venue ids: {sorted(dup)}")

    uncovered = [v.get("id") for v in venues or [] if not v.get("specials") and not (v.get("notes") or "").strip()]
    check(not uncovered, f"venues with no specials AND no note: {uncovered}")

    try:
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        cfg_ids = {v["id"] for v in cfg.get("venues", [])}
        data_ids = {x for x in ids if x}
        check(not (cfg_ids - data_ids), f"config venues missing from data: {sorted(cfg_ids - data_ids)}")
        check(not (data_ids - cfg_ids), f"data venues missing from config: {sorted(data_ids - cfg_ids)}")
    except Exception as exc:  # noqa: BLE001
        check(False, f"config parity check failed: {exc}")

    try:
        proc = subprocess.run(
            ["node", str(HOURS_VALIDATOR), str(DATA_PATH)],
            capture_output=True, text=True, timeout=60,
        )
        if proc.returncode != 0:
            errors.append(f"hours parse failures:\n{(proc.stdout + proc.stderr).strip()}")
    except FileNotFoundError:
        check(False, "node not found — cannot validate hours parsing (needs the JS parser)")
    except subprocess.TimeoutExpired:
        check(False, "hours validation timed out")

    if errors:
        print("VALIDATION FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"OK: {len(venues)} venues — schema, ids, price-0 semantics, hours grammar, coverage, config parity all valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
