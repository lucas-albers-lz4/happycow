#!/usr/bin/env python3
"""Detect venues that may have closed — report only, never auto-removes.

Motivation: Open Range sat in the dataset for weeks after closing (June
2026) because nothing checked. This script runs in the same CI workflow as
the scraper (Sun + Thu) and produces a human-review report.

Signals:
1. SITE_DEAD — ALL of a venue's own-site URLs fail to load (conn error,
   DNS, 404, 401-auth like Open Range's parked site) in BOTH this run and
   the previous run. Consecutive-failure state lives in
   `data/state/closure_state.json` (kept separate from the scraper cache).
2. CLOSED_MARKER — the venue's mthappyhour entry contains closure wording
   (low confidence: mthappyhour pages are known to carry contamination).

Optional: `--with-yelp` also probes Yelp biz pages for "permanently closed"
(off by default — Yelp aggressively rate-limits bots).

Usage:
  python scripts/check_venue_status.py          # report to stdout + data/state/closure_report.md
  python scripts/check_venue_status.py --dry-run  # don't persist state

Exit code is always 0 — the report is for a human to review.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from common import CLOSURE_REPORT_PATH, CLOSURE_STATE_PATH, is_aggregator, save_json, save_text

import httpx

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "venues.json"
DATA_PATH = ROOT / "data" / "happy_hour_data.json"
STATE_PATH = CLOSURE_STATE_PATH
REPORT_PATH = CLOSURE_REPORT_PATH

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) HappyCowClosureCheck/1.0"
TIMEOUT = 10.0
FLAG_AFTER_CONSECUTIVE = 2

# Own-site URLs exclude aggregator hosts — single source: scripts/common.py.
CLOSED_RE = re.compile(
    r"permanently closed|has closed|has shut down|shuttered|closed its doors|"
    r"no longer (open|in business)|business closed|ceases? operations|"
    r"venue (is|has) closed|restaurant (is|has) closed",
    re.IGNORECASE,
)


def load_json(path: Path, fallback=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback if fallback is not None else {}


def own_site_urls(venue: dict) -> list[str]:
    out = []
    for u in venue.get("scrape_urls") or []:
        if not is_aggregator(u):
            out.append(u)
    return out


def site_ok(client: httpx.Client, url: str) -> bool:
    try:
        r = client.get(url)
        # 401/403 (auth-protected/parked — Open Range's case) counts as dead.
        return r.status_code < 400
    except Exception:
        return False


def probe_mthappyhour(client: httpx.Client, venue: dict) -> bool:
    """True if the venue's mthappyhour entry carries closure wording."""
    mthh = next((u for u in (venue.get("scrape_urls") or [])
                 if "mthappyhour.com" in (urlsplit(u).hostname or "")), None)
    if not mthh:
        return False
    try:
        r = client.get(mthh)
        if r.status_code != 200:
            return False
        text = re.sub(r"<script[^>]*>.*?</script>", " ", r.text, flags=re.DOTALL | re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        name = re.escape(venue["name"].split("(")[0].strip())
        for m in CLOSED_RE.finditer(text):
            window = text[max(0, m.start() - 200): m.end() + 200]
            if re.search(name, window, re.I):
                return True
    except Exception:
        return False
    return False


def probe_yelp(client: httpx.Client, venue: dict) -> bool:
    """Best-effort: True if the venue's Yelp page shows a permanent-closure badge."""
    slug = re.sub(r"[^a-z0-9]+", "-", venue["name"].lower()).strip("-")
    try:
        r = client.get(f"https://www.yelp.com/biz/{slug}", headers={"Accept-Language": "en-US"})
        if r.status_code != 200:
            return False
        return bool(re.search(r"permanently closed|closed", r.text, re.I))
    except Exception:
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="don't persist closure state")
    ap.add_argument("--with-yelp", action="store_true", help="also probe Yelp (rate-limited)")
    args = ap.parse_args()

    cfg = load_json(CONFIG_PATH)
    venues = cfg.get("venues", [])
    state = load_json(STATE_PATH)
    state_venues = state.setdefault("venues", {})

    rows: list[dict] = []
    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT,
                      follow_redirects=True) as client:
        for venue in venues:
            vid = venue["id"]
            st = state_venues.setdefault(vid, {"fail_count": 0, "last": "ok"})
            signals = []
            sites = own_site_urls(venue)
            site_dead = bool(sites) and not any(site_ok(client, u) for u in sites)
            if site_dead:
                st["fail_count"] += 1
                st["last"] = "site_dead"
                if st["fail_count"] >= FLAG_AFTER_CONSECUTIVE:
                    signals.append(f"SITE_DEAD x{st['fail_count']} ({', '.join(sites)})")
            else:
                st["fail_count"] = 0
                st["last"] = "ok"
            if probe_mthappyhour(client, venue):
                signals.append("CLOSED_MARKER (mthappyhour — low confidence)")
            if args.with_yelp and probe_yelp(client, venue):
                signals.append("YELP_CLOSED (best-effort)")
            st["checked_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            rows.append({"id": vid, "name": venue["name"], "sites": len(sites), "signals": signals})

    flagged = [r for r in rows if r["signals"]]
    checked = len(rows)

    # Report
    lines = [
        f"# Venue Closure Check — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        f"Checked {checked} venues. **{len(flagged)} flagged for review.**",
        "",
        "| Venue | Signal |",
        "|---|---|",
    ]
    for r in flagged:
        for sig in r["signals"]:
            lines.append(f"| {r['name']} | `{sig}` |")
    if not flagged:
        lines.append("| _none_ | |")
    lines += ["", "No venue is auto-removed — review the flags, then update data manually.",
              "To remove a confirmed-closed venue:",
              "  python scripts/remove_venue.py <id> --reason \"closed ...\"",
              "  (records a tombstone in data/state/removed_venues.json so discovery won't re-add it)"]
    report = "\n".join(lines) + "\n"
    print(report)

    if not args.dry_run:
        state["last_run"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        save_json(CLOSURE_STATE_PATH, state)
        save_text(CLOSURE_REPORT_PATH, report)
        print(f"state -> {CLOSURE_STATE_PATH}", file=sys.stderr)
        print(f"report -> {CLOSURE_REPORT_PATH}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
