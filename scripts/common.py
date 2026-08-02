"""Shared constants + small helpers for the happycow pipeline scripts.

Phases 2–4 of issue #30:
- AGGREGATOR_HOSTS was copy-pasted in three scripts (already drifted) —
  this module is the single source.
- Runtime state lives under data/state/ (scrape cache, closure state,
  tombstones, closure report) — one directory, one writer convention
  (atomic: tmp + rename), so a crash can't truncate a state file.

Run scripts as `python scripts/<name>.py` from the repo root; the script's
own directory is on sys.path, so `from common import ...` works.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
VENUES_PATH = ROOT / "config" / "venues.json"
DATA_PATH = ROOT / "data" / "happy_hour_data.json"
PROMPT_PATH = ROOT / "prompts" / "extract_happy_hour.txt"

# ─── Runtime state (Phase 4: consolidated under data/state/) ───
# NOTE: this repo is served by GitHub Pages, so anything committed here is
# public by nature. State contains content hashes + flags only — no secrets.
STATE_DIR = ROOT / "data" / "state"
CACHE_PATH = STATE_DIR / "scrape_cache.json"          # scraper page cache
TOMBSTONES_PATH = STATE_DIR / "removed_venues.json"   # removed-venue blocklist
CLOSURE_STATE_PATH = STATE_DIR / "closure_state.json" # consecutive-failure flags
CLOSURE_REPORT_PATH = STATE_DIR / "closure_report.md" # human-review report

# Directory/aggregator hosts — curated venue pages (own site, HH subpages)
# outrank these in gather_page_text so their boilerplate can't starve the
# dedicated sources that actually hold the deals.
AGGREGATOR_HOSTS = {
    "mthappyhour.com",
    "bozemanmagazine.com",
    "visit-bozeman.com",
    "menupix.com",
    "sellout.io",
    "google.com",
    "yelp.com",
    "facebook.com",
}


def host_of(url: str) -> str:
    """Hostname without scheme/port, leading www. stripped ('' for junk)."""
    h = urlsplit(url or "").hostname or ""
    return h[4:] if h.startswith("www.") else h


def is_aggregator(url: str) -> bool:
    """True for aggregator/directory hosts (suffix match; www handled)."""
    host = host_of(url)
    return bool(host) and any(host == a or host.endswith("." + a) for a in AGGREGATOR_HOSTS)


def load_json(path: Path, fallback=None):
    """Tolerant load: missing/corrupt -> fallback (default None/{})."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return fallback if fallback is not None else {}


def save_json(path: Path, obj) -> None:
    """Atomic JSON write (tmp + rename) — a crash can't truncate state."""
    _atomic_write(path, json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def save_text(path: Path, content: str) -> None:
    """Atomic text write (tmp + rename)."""
    _atomic_write(path, content)


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
