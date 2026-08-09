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
import re
import contextlib
import tempfile
import unicodedata
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
CACHE_PATH = STATE_DIR / "scrape_cache.json"  # scraper page cache
TOMBSTONES_PATH = STATE_DIR / "removed_venues.json"  # removed-venue blocklist
CLOSURE_STATE_PATH = STATE_DIR / "closure_state.json"  # consecutive-failure flags
CLOSURE_REPORT_PATH = STATE_DIR / "closure_report.md"  # human-review report

# ─── Venue truth pipeline (observation → claim → decision) ───
EVIDENCE_DIR = ROOT / "data" / "evidence"
EVAL_DIR = ROOT / "data" / "eval"
SHADOW_DECISIONS_PATH = STATE_DIR / "shadow_decisions.json"
REVIEW_QUEUE_PATH = STATE_DIR / "review_queue.json"
TRUTH_CONFIG_PATH = STATE_DIR / "truth_config.json"
OVERTURE_CACHE_PATH = STATE_DIR / "overture_priors.json"
OVERPASS_CACHE_PATH = STATE_DIR / "overpass_snapshot.json"
COST_COUNTERS_PATH = STATE_DIR / "cost_counters.json"
ENRICHMENT_CANDIDATES_PATH = STATE_DIR / "enrichment_candidates.json"

# Gallatin Valley bbox for Overture / Overpass (approx Bozeman + Belgrade)
BOZEMAN_BBOX = {
    "xmin": -111.20,
    "xmax": -110.90,
    "ymin": 45.55,
    "ymax": 45.85,
}

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


def norm_name(name: str) -> str:
    """Normalize a venue name for dedup and tombstone matching.

    Strips leading articles (the, a, an), collapses punctuation to spaces,
    and lowercases. Shared by remove_venue.py and discover_venues.py so
    tombstone name keys stay consistent across both scripts.

    Note: a venue that reopens at a *different street number* will not
    auto-skip via tombstone (name + street# / norm address; issue #49).
    """
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()
    for art in ("the ", "a ", "an "):
        if s.startswith(art) and len(s) > len(art):
            s = s[len(art) :]
    return re.sub(r"\s+", " ", s).strip()


def norm_address(addr: str) -> str:
    """Normalize an address for dedup and tombstone matching.

    Shared by remove_venue.py (writer) and discover_venues.py (reader) so
    stored tombstone keys compare equal to live candidate addresses.
    """
    s = (addr or "").lower()
    s = re.sub(r"[,.\-]+", " ", s)
    s = re.sub(r"\b(mt|montana)\b", "", s)
    s = re.sub(r"\b\d{5}\b", "", s)  # zip
    # Normalize unit markers: "#1e" == "suite 1e" == "unit 1e" == "ste 1e"
    s = re.sub(r"\b(suite|unit|ste|apt)\b", "#", s)
    s = re.sub(r"#\s*", "#", s)
    # Collapse repeated city tokens ("bozeman bozeman" -> "bozeman").
    # Bound \w{1,24}: backref patterns can be super-linear on adversarial input;
    # curated venue addresses are short — bound keeps matching linear in practice
    # (regexproof/#115; recheck not available in CI).
    s = re.sub(r"\b(\w{1,24})\s+\1\b", r"\1", s)
    return re.sub(r"\s+", " ", s).strip()


def street_number(addr: str) -> str:
    """Leading street number from an address ('' if none)."""
    m = re.search(r"^\s*(\d+)", addr or "")
    return m.group(1) if m else ""


def host_of(url: str) -> str:
    """Hostname without scheme/port, leading www. stripped ('' for junk)."""
    h = urlsplit(url or "").hostname or ""
    return h[4:] if h.startswith("www.") else h


def is_aggregator(url: str) -> bool:
    """True for aggregator/directory hosts (suffix match; www handled)."""
    host = host_of(url)
    return bool(host) and any(
        host == a or host.endswith("." + a) for a in AGGREGATOR_HOSTS
    )


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
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise
