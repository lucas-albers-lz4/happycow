"""Issue #43: validate_data.py negative fixtures.

Each test class represents one failure class from validate_data.py.  The test
builds a minimal fixture (data + config), writes it to a temp dir, runs
validate_data.py --data … --config … via subprocess, and asserts:
  - exit code 1
  - expected error substring appears in stdout

A final smoke test asserts the live data/happy_hour_data.json exits 0.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "validate_data.py"
LIVE_DATA = ROOT / "data" / "happy_hour_data.json"
LIVE_CONFIG = ROOT / "config" / "venues.json"

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(ROOT / "scripts"))

from harness import TempDir, run_script, write_json  # noqa: E402

# ─── Minimal valid venue + config for fixture construction ───

_VALID_VENUE = {
    "id": "test-bar",
    "name": "Test Bar",
    "nickname": "The Tester",
    "nickname_alts": [],
    "address": "123 Main St",
    "phone": "406-555-0100",
    "website": "https://testbar.example.com",
    "maps": "https://maps.google.com/testbar",
    "hours": "Daily 4-6pm",
    "business_hours": "Daily 11am-10pm",
    "tags": ["downtown"],
    "noise_level": "moderate",
    "mood": "casual",
    "specials": [
        {"item": "Draft Beer", "price": 4.0, "category": "drinks", "description": "Select drafts"}
    ],
}

_VALID_CONFIG_VENUE = {
    "id": "test-bar",
    "name": "Test Bar",
    "nickname": "The Tester",
    "nickname_alts": [],
    "address": "123 Main St",
    "phone": "406-555-0100",
    "website": "https://testbar.example.com",
    "maps": "https://maps.google.com/testbar",
    "tags": ["downtown"],
    "noise_level": "moderate",
    "mood": "casual",
    "scrape_urls": ["https://mthappyhour.com/test-bar"],
}


def _make_data(venues: list) -> dict:
    return {"last_updated": "2026-08-01", "city": "Bozeman", "population": 53293, "venues": venues}


def _make_config(venues: list) -> dict:
    return {"venues": venues}


def _write_and_run(tmp: Path, data: dict | str, config: dict | None = None) -> "subprocess.CompletedProcess":
    data_path = tmp / "data.json"
    config_path = tmp / "config.json"
    if isinstance(data, str):
        data_path.write_text(data, encoding="utf-8")
    else:
        write_json(data_path, data)
    cfg = config if config is not None else _make_config([_VALID_CONFIG_VENUE])
    write_json(config_path, cfg)
    return run_script(SCRIPT, ["--data", str(data_path), "--config", str(config_path)])


class _FixtureBase(unittest.TestCase):
    """Base: run a fixture, assert exit 1 + expected substring."""

    def _assert_fail(self, result, expected_substr: str) -> None:
        self.assertEqual(result.returncode, 1,
                         f"Expected exit 1; got {result.returncode}\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}")
        combined = result.stdout + result.stderr
        self.assertIn(expected_substr, combined,
                      f"Expected {expected_substr!r} in output:\n{combined}")


class UnparseableJson(_FixtureBase):
    def test_bad_json_exits_1(self):
        with TempDir() as tmp:
            result = _write_and_run(tmp, "this is not json")
        self._assert_fail(result, "unparseable")


class VenuesNotList(_FixtureBase):
    def test_venues_not_list(self):
        with TempDir() as tmp:
            result = _write_and_run(tmp, _make_data("not-a-list"))
        self._assert_fail(result, "'venues' must be a list")


class VenueEntryNotDict(_FixtureBase):
    def test_venue_not_dict(self):
        with TempDir() as tmp:
            result = _write_and_run(tmp, _make_data(["just-a-string"]))
        self._assert_fail(result, "venue entries must be objects")


class BadVenueId(_FixtureBase):
    def test_id_with_uppercase(self):
        venue = {**_VALID_VENUE, "id": "Test-Bar"}
        with TempDir() as tmp:
            result = _write_and_run(tmp, _make_data([venue]))
        self._assert_fail(result, "bad id")

    def test_id_with_spaces(self):
        venue = {**_VALID_VENUE, "id": "test bar"}
        with TempDir() as tmp:
            result = _write_and_run(tmp, _make_data([venue]))
        self._assert_fail(result, "bad id")


class MissingRequiredKey(_FixtureBase):
    def test_missing_hours(self):
        venue = {k: v for k, v in _VALID_VENUE.items() if k != "hours"}
        with TempDir() as tmp:
            result = _write_and_run(tmp, _make_data([venue]))
        self._assert_fail(result, "missing required key 'hours'")

    def test_missing_specials(self):
        venue = {k: v for k, v in _VALID_VENUE.items() if k != "specials"}
        with TempDir() as tmp:
            result = _write_and_run(tmp, _make_data([venue]))
        self._assert_fail(result, "missing required key 'specials'")


class PipelineOnlyKeyLeaked(_FixtureBase):
    def test_scrape_urls_in_data(self):
        venue = {**_VALID_VENUE, "scrape_urls": ["https://example.com"]}
        with TempDir() as tmp:
            result = _write_and_run(tmp, _make_data([venue]))
        self._assert_fail(result, "pipeline-only key 'scrape_urls' leaked")


class EmptyNickname(_FixtureBase):
    def test_empty_nickname(self):
        venue = {**_VALID_VENUE, "nickname": ""}
        with TempDir() as tmp:
            result = _write_and_run(tmp, _make_data([venue]))
        self._assert_fail(result, "empty nickname")


class TagsNotList(_FixtureBase):
    def test_tags_is_string(self):
        venue = {**_VALID_VENUE, "tags": "downtown"}
        with TempDir() as tmp:
            result = _write_and_run(tmp, _make_data([venue]))
        self._assert_fail(result, "'tags' must be a list")


class TagsEmpty(_FixtureBase):
    def test_empty_tags_list(self):
        venue = {**_VALID_VENUE, "tags": []}
        with TempDir() as tmp:
            result = _write_and_run(tmp, _make_data([venue]))
        self._assert_fail(result, "'tags' must be non-empty")


class SpecialsNotList(_FixtureBase):
    def test_specials_is_string(self):
        venue = {**_VALID_VENUE, "specials": "Draft $4"}
        with TempDir() as tmp:
            result = _write_and_run(tmp, _make_data([venue]))
        self._assert_fail(result, "'specials' must be a list")


class SpecialEntryNotDict(_FixtureBase):
    def test_special_not_dict(self):
        venue = {**_VALID_VENUE, "specials": ["just a string"]}
        with TempDir() as tmp:
            result = _write_and_run(tmp, _make_data([venue]))
        self._assert_fail(result, "special entries must be objects")


class SpecialMissingKey(_FixtureBase):
    def test_special_missing_price(self):
        bad_special = {"item": "Draft", "category": "drinks", "description": "cold"}
        venue = {**_VALID_VENUE, "specials": [bad_special]}
        with TempDir() as tmp:
            result = _write_and_run(tmp, _make_data([venue]))
        self._assert_fail(result, "special missing 'price'")


class SpecialBadCategory(_FixtureBase):
    def test_category_not_drinks_or_food(self):
        bad_special = {"item": "Cocktail", "price": 5.0, "category": "booze", "description": ""}
        venue = {**_VALID_VENUE, "specials": [bad_special]}
        with TempDir() as tmp:
            result = _write_and_run(tmp, _make_data([venue]))
        self._assert_fail(result, "special category must be drinks|food")


class SpecialBadPrice(_FixtureBase):
    def test_negative_price(self):
        bad_special = {"item": "Draft", "price": -1.0, "category": "drinks", "description": ""}
        venue = {**_VALID_VENUE, "specials": [bad_special]}
        with TempDir() as tmp:
            result = _write_and_run(tmp, _make_data([venue]))
        self._assert_fail(result, "special price must be a number >= 0")

    def test_string_price(self):
        bad_special = {"item": "Draft", "price": "free", "category": "drinks", "description": ""}
        venue = {**_VALID_VENUE, "specials": [bad_special]}
        with TempDir() as tmp:
            result = _write_and_run(tmp, _make_data([venue]))
        self._assert_fail(result, "special price must be a number >= 0")


class PriceZeroNoContext(_FixtureBase):
    def test_price_0_no_wording(self):
        bad_special = {"item": "Snack", "price": 0, "category": "food", "description": "on the menu"}
        venue = {**_VALID_VENUE, "specials": [bad_special]}
        with TempDir() as tmp:
            result = _write_and_run(tmp, _make_data([venue]))
        self._assert_fail(result, "price-0 special")


class DuplicateVenueIds(_FixtureBase):
    def test_duplicate_ids(self):
        venue2 = {**_VALID_VENUE, "id": "test-bar"}  # same id
        config2 = _make_config([_VALID_CONFIG_VENUE, {**_VALID_CONFIG_VENUE, "id": "test-bar-2"}])
        data = _make_data([_VALID_VENUE, venue2])
        with TempDir() as tmp:
            result = _write_and_run(tmp, data, config2)
        self._assert_fail(result, "duplicate venue ids")


class NoCoverage(_FixtureBase):
    def test_no_specials_no_notes(self):
        venue = {**_VALID_VENUE, "specials": []}
        # no notes key → coverage fails
        with TempDir() as tmp:
            result = _write_and_run(tmp, _make_data([venue]))
        self._assert_fail(result, "no specials AND no note")


class ConfigMissingFromData(_FixtureBase):
    def test_config_id_absent_from_data(self):
        config = _make_config([_VALID_CONFIG_VENUE, {**_VALID_CONFIG_VENUE, "id": "ghost-venue"}])
        with TempDir() as tmp:
            result = _write_and_run(tmp, _make_data([_VALID_VENUE]), config)
        self._assert_fail(result, "config venues missing from data")


class DataMissingFromConfig(_FixtureBase):
    def test_data_id_absent_from_config(self):
        extra_venue = {**_VALID_VENUE, "id": "extra-bar"}
        config = _make_config([_VALID_CONFIG_VENUE])
        with TempDir() as tmp:
            result = _write_and_run(tmp, _make_data([_VALID_VENUE, extra_venue]), config)
        self._assert_fail(result, "data venues missing from config")


class DeepParityMismatch(_FixtureBase):
    def test_name_differs_from_config(self):
        data_venue = {**_VALID_VENUE, "name": "Different Name"}
        with TempDir() as tmp:
            result = _write_and_run(tmp, _make_data([data_venue]))
        self._assert_fail(result, "deep parity mismatch for 'name'")

    def test_tags_differs_from_config(self):
        data_venue = {**_VALID_VENUE, "tags": ["sports"]}
        with TempDir() as tmp:
            result = _write_and_run(tmp, _make_data([data_venue]))
        self._assert_fail(result, "deep parity mismatch for 'tags'")


class LiveDataSmoke(unittest.TestCase):
    def test_live_data_exits_0(self):
        result = run_script(SCRIPT, ["--data", str(LIVE_DATA), "--config", str(LIVE_CONFIG)])
        self.assertEqual(
            result.returncode, 0,
            f"Live data validation failed:\n{result.stdout}\n{result.stderr}",
        )
        self.assertIn("OK:", result.stdout)


if __name__ == "__main__":
    unittest.main()
