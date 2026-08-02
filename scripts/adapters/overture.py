"""Overture Maps Places prior adapter — DuckDB bbox query + local cache."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from truth.identity import match_score, venue_matches_candidate
from truth.schema import ExtractionMethod, Observation, utc_now_iso

# Default release — override via OVERTURE_RELEASE env if needed.
DEFAULT_OVERTURE_RELEASE = "2026-07-22.0"
OVERTURE_S3 = (
    "s3://overturemaps-us-west-2/release/{release}/theme=places/type=place/*"
)


def _row_to_candidate(row: dict[str, Any]) -> dict[str, Any]:
    names = row.get("names") or {}
    if isinstance(names, str):
        try:
            names = json.loads(names)
        except json.JSONDecodeError:
            names = {"primary": names}
    primary = names.get("primary") if isinstance(names, dict) else None

    addresses = row.get("addresses") or []
    if isinstance(addresses, str):
        try:
            addresses = json.loads(addresses)
        except json.JSONDecodeError:
            addresses = []
    addr0 = addresses[0] if addresses else {}
    freeform = ""
    if isinstance(addr0, dict):
        freeform = addr0.get("freeform") or ""
        locality = addr0.get("locality") or ""
        if locality and locality not in freeform:
            freeform = f"{freeform}, {locality}".strip(", ")

    phones = row.get("phones") or []
    if isinstance(phones, str):
        try:
            phones = json.loads(phones)
        except json.JSONDecodeError:
            phones = []
    phone = phones[0] if phones else ""

    return {
        "id": row.get("id") or "",
        "name": primary or "",
        "address": freeform,
        "phone": phone or "",
        "operating_status": row.get("operating_status") or "open",
        "confidence": float(row.get("confidence") or 0.0),
        "categories": row.get("categories"),
    }


def query_overture_bbox(
    bbox: dict[str, float],
    *,
    release: str = DEFAULT_OVERTURE_RELEASE,
    limit: int = 5000,
    parquet_glob: str | None = None,
) -> list[dict[str, Any]]:
    """Query Overture Places for a bbox. Requires duckdb + network/S3 access.

    ``parquet_glob`` overrides the remote S3 path (used for local unit tests).
    """
    try:
        import duckdb
    except ImportError as e:
        raise RuntimeError("duckdb is required for Overture queries") from e

    path = parquet_glob or OVERTURE_S3.format(release=release)
    remote = parquet_glob is None
    con = duckdb.connect()
    try:
        if remote:
            con.execute("INSTALL httpfs; LOAD httpfs;")
            con.execute("INSTALL spatial; LOAD spatial;")
            con.execute("SET s3_region='us-west-2';")
        # bbox bounds are floats from our config — never user input.
        xmin = float(bbox["xmin"])
        xmax = float(bbox["xmax"])
        ymin = float(bbox["ymin"])
        ymax = float(bbox["ymax"])
        hive = "filename=true, hive_partitioning=1" if remote else "filename=true"
        # Local test fixtures may omit bbox/categories nested structs.
        if remote:
            where = f"""
            WHERE bbox.xmin BETWEEN {xmin} AND {xmax}
              AND bbox.ymin BETWEEN {ymin} AND {ymax}
              AND (
                categories.primary ILIKE '%restaurant%'
                OR categories.primary ILIKE '%bar%'
                OR categories.primary ILIKE '%cafe%'
                OR categories.primary ILIKE '%pub%'
                OR categories.primary ILIKE '%brewery%'
                OR categories.primary ILIKE '%food%'
              )
            """
        else:
            where = ""
        sql = f"""
        SELECT
          id,
          names,
          addresses,
          phones,
          operating_status,
          confidence,
          categories
        FROM read_parquet('{path}', {hive})
        {where}
        LIMIT {int(limit)}
        """
        cur = con.execute(sql)
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        con.close()
    return [_row_to_candidate(r) for r in rows]


def load_fixture(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return data.get("places") or data.get("candidates") or []
    return list(data)


def match_venues_to_candidates(
    venues: list[dict],
    candidates: list[dict[str, Any]],
    *,
    min_score: float = 0.5,
) -> dict[str, dict[str, Any]]:
    """Best candidate per venue_id. Requires venue_matches_candidate (namesake guard)."""
    matched: dict[str, dict[str, Any]] = {}
    for venue in venues:
        best = None
        best_score = 0.0
        for cand in candidates:
            if not venue_matches_candidate(
                venue,
                name=cand.get("name"),
                address=cand.get("address"),
                phone=cand.get("phone"),
            ):
                continue
            sc = match_score(venue, cand)
            if sc > best_score and sc >= min_score:
                best_score = sc
                best = cand
        if best:
            matched[venue["id"]] = {**best, "_match_score": best_score}
    return matched


def observations_from_matches(
    matches: dict[str, dict[str, Any]],
    *,
    observed_at: str | None = None,
) -> list[Observation]:
    """Build prior observations from Overture matches."""
    when = observed_at or utc_now_iso()
    out: list[Observation] = []
    for venue_id, cand in matches.items():
        # Trust operating_status as-is. confidence is a data-quality signal for
        # agreement weighting — never rewrite open → permanently_closed on conf=0.
        status = cand.get("operating_status") or "open"
        conf = float(cand.get("confidence") or 0.0)
        excerpt = (
            f"Overture id={cand.get('id')} name={cand.get('name')!r} "
            f"operating_status={status} confidence={conf}"
        )
        out.append(
            Observation(
                venue_id=venue_id,
                observed_at=when,
                source_url=f"overture:places:{cand.get('id')}",
                source_type="overture",
                source_family="overture",
                extraction_method=ExtractionMethod.PRIOR,
                evidence_excerpt=excerpt[:500],
                matched_name=cand.get("name"),
                matched_address=cand.get("address"),
                matched_phone=cand.get("phone") or None,
                matched_overture_id=cand.get("id"),
                payload={
                    "business_status": status,
                    "overture_confidence": conf,
                    "address": cand.get("address") or "",
                    "phone": cand.get("phone") or "",
                },
            )
        )
    return out


def fetch_or_cache(
    venues: list[dict],
    bbox: dict[str, float],
    cache_path: Path,
    *,
    fixture_path: Path | None = None,
    force_refresh: bool = False,
    release: str = DEFAULT_OVERTURE_RELEASE,
) -> tuple[list[Observation], dict[str, Any]]:
    """Return observations + meta. Prefer fixture, then cache, then live query."""
    meta: dict[str, Any] = {"source": None, "matches": 0, "candidates": 0}

    if fixture_path and fixture_path.exists():
        candidates = load_fixture(fixture_path)
        meta["source"] = f"fixture:{fixture_path}"
    elif cache_path.exists() and not force_refresh:
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        candidates = cached.get("candidates") or []
        meta["source"] = "cache"
    else:
        try:
            candidates = query_overture_bbox(bbox, release=release)
            meta["source"] = f"overture:{release}"
            if not candidates:
                meta["empty_live"] = True
                print(
                    "ERROR overture live query returned 0 candidates — "
                    "check release pin / S3 access / bbox filters",
                    file=sys.stderr,
                )
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(
                json.dumps(
                    {
                        "updated_at": utc_now_iso(),
                        "release": release,
                        "bbox": bbox,
                        "candidates": candidates,
                    },
                    indent=2,
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
        except Exception as e:  # noqa: BLE001
            meta["failed"] = True
            meta["error"] = str(e)
            print(f"ERROR overture live query failed: {e}", file=sys.stderr)
            if cache_path.exists():
                cached = json.loads(cache_path.read_text(encoding="utf-8"))
                candidates = cached.get("candidates") or []
                meta["source"] = "cache_fallback"
            else:
                candidates = []
                meta["source"] = "empty"

    meta["candidates"] = len(candidates)
    matches = match_venues_to_candidates(venues, candidates)
    meta["matches"] = len(matches)
    return observations_from_matches(matches), meta
