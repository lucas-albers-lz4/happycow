"""Unit tests for scripts/tools/enrich_empty_specials.py."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

SPEC = importlib.util.spec_from_file_location(
    "enrich_empty_specials",
    ROOT / "scripts" / "tools" / "enrich_empty_specials.py",
)
assert SPEC and SPEC.loader
enrich = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(enrich)


class SelectTargets(unittest.TestCase):
    def test_empty_specials_only(self):
        cfg = {
            "venues": [
                {"id": "a", "name": "A", "scrape_urls": ["https://a.example/"]},
                {"id": "b", "name": "B", "scrape_urls": ["https://b.example/"]},
                {"id": "c", "name": "C", "scrape_urls": ["https://c.example/"]},
            ]
        }
        data = {
            "venues": [
                {"id": "a", "specials": []},
                {"id": "b", "specials": [{"item": "Beer", "price": 4, "category": "drinks", "description": ""}]},
                {"id": "c", "specials": []},
            ]
        }
        pairs = enrich.select_targets(cfg, data)
        ids = [c["id"] for c, _ in pairs]
        self.assertEqual(ids, ["a", "c"])

    def test_venue_filter(self):
        cfg = {"venues": [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}]}
        data = {"venues": [{"id": "a", "specials": []}, {"id": "b", "specials": []}]}
        pairs = enrich.select_targets(cfg, data, venue_ids=["b"])
        self.assertEqual([c["id"] for c, _ in pairs], ["b"])


class OwnSiteUrls(unittest.TestCase):
    def test_skips_aggregators_and_dedupes(self):
        cfg = {
            "id": "x",
            "scrape_urls": [
                "https://mthappyhour.com/locations/x/",
                "https://www.example.com/hh",
                "https://www.example.com/hh/",
            ],
            "website": "https://www.example.com/",
        }
        urls = enrich.own_site_urls(cfg, {"website": "https://www.example.com/"})
        self.assertEqual(urls, ["https://www.example.com/hh", "https://www.example.com/"])

    def test_needs_site_when_only_aggregator(self):
        cfg = {
            "id": "x",
            "scrape_urls": ["https://mthappyhour.com/locations/x/"],
            "website": "",
        }
        self.assertEqual(enrich.own_site_urls(cfg, {}), [])


class ShouldApply(unittest.TestCase):
    def test_medium_with_specials_applies(self):
        self.assertTrue(
            enrich.should_apply(
                {
                    "status": "ok",
                    "confidence": "medium",
                    "specials": [{"item": "Pint", "price": 0, "category": "drinks", "description": "half off"}],
                }
            )
        )

    def test_high_applies(self):
        self.assertTrue(
            enrich.should_apply(
                {
                    "status": "ok",
                    "confidence": "high",
                    "specials": [{"item": "Beer", "price": 3, "category": "drinks", "description": ""}],
                }
            )
        )

    def test_low_does_not_apply(self):
        self.assertFalse(
            enrich.should_apply(
                {
                    "status": "ok",
                    "confidence": "low",
                    "specials": [{"item": "Beer", "price": 3, "category": "drinks", "description": ""}],
                }
            )
        )

    def test_not_found_does_not_apply(self):
        self.assertFalse(
            enrich.should_apply({"status": "not_found", "confidence": "medium", "specials": []})
        )

    def test_ok_without_specials_does_not_apply(self):
        self.assertFalse(
            enrich.should_apply({"status": "ok", "confidence": "high", "specials": []})
        )


class EnrichResultShape(unittest.TestCase):
    def test_half_off_price_zero(self):
        result = enrich.validate_enrich(
            {
                "found": True,
                "confidence": "medium",
                "hours": "",
                "specials": [
                    {
                        "item": "Draft pour with wings",
                        "price": 0,
                        "category": "drinks",
                        "description": "half off — Wednesdays",
                    }
                ],
                "notes": "Wing Wednesday",
                "source_urls": ["https://example.com/food"],
            }
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertTrue(result.found)
        self.assertEqual(result.specials[0].price, 0.0)
        self.assertEqual(result.specials[0].category, "drinks")
        self.assertIn("half off", result.specials[0].description)

    def test_hours_normalized(self):
        result = enrich.validate_enrich(
            {
                "found": True,
                "confidence": "high",
                "hours": "mon - fri 3 PM to 6 PM",
                "specials": [{"item": "Beer", "price": 4, "category": "drinks", "description": ""}],
                "notes": "",
                "source_urls": [],
            }
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertIn("Mon-Fri", result.hours)
        self.assertIn("3pm", result.hours.lower())


class ApplyMerge(unittest.TestCase):
    def test_apply_merges_medium_skips_low(self):
        cfg = {
            "venues": [
                {
                    "id": "good",
                    "name": "Good",
                    "scrape_urls": ["https://mthappyhour.com/locations/good/"],
                    "website": "",
                },
                {
                    "id": "low",
                    "name": "Low",
                    "scrape_urls": ["https://low.example/"],
                    "website": "https://low.example/",
                },
            ]
        }
        data = {
            "venues": [
                {"id": "good", "hours": "", "specials": [], "notes": ""},
                {"id": "low", "hours": "", "specials": [], "notes": ""},
            ]
        }
        candidates = {
            "good": {
                "status": "ok",
                "confidence": "medium",
                "hours": "Mon-Fri 3-5pm",
                "specials": [
                    {"item": "Well drink", "price": 5, "category": "drinks", "description": ""}
                ],
                "source_urls": ["https://good.example/specials"],
                "notes": "from own site",
            },
            "low": {
                "status": "ok",
                "confidence": "low",
                "hours": "",
                "specials": [
                    {"item": "Maybe", "price": 1, "category": "drinks", "description": ""}
                ],
                "source_urls": ["https://low.example/"],
                "notes": "guessy",
            },
            "ghost": {
                "status": "needs_site",
                "confidence": None,
                "specials": [],
                "source_urls": [],
                "notes": "",
            },
        }
        applied, skipped, needs_site = enrich.apply_candidates(cfg, data, candidates)
        self.assertEqual(applied, 1)
        self.assertEqual(needs_site, 1)
        self.assertGreaterEqual(skipped, 2)

        good = next(v for v in data["venues"] if v["id"] == "good")
        self.assertEqual(len(good["specials"]), 1)
        self.assertEqual(good["hours"], "Mon-Fri 3-5pm")
        low = next(v for v in data["venues"] if v["id"] == "low")
        self.assertEqual(low["specials"], [])

        cfg_good = next(v for v in cfg["venues"] if v["id"] == "good")
        self.assertIn("https://good.example/specials", cfg_good["scrape_urls"])
        self.assertTrue(cfg_good["website"].startswith("https://good.example"))


if __name__ == "__main__":
    unittest.main()
