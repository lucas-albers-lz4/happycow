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
                {
                    "id": "good",
                    "hours": "",
                    "specials": [],
                    "notes": "Site probed — no HH page",
                },
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
        self.assertIn("Site probed — no HH page", good["notes"])
        self.assertIn("from own site", good["notes"])
        self.assertIn("enriched", good["notes"])
        low = next(v for v in data["venues"] if v["id"] == "low")
        self.assertEqual(low["specials"], [])

        cfg_good = next(v for v in cfg["venues"] if v["id"] == "good")
        self.assertIn("https://good.example/specials", cfg_good["scrape_urls"])
        self.assertTrue(cfg_good["website"].startswith("https://good.example"))
        self.assertEqual(good.get("website"), cfg_good["website"])

    def test_apply_sets_data_website_with_config(self):
        cfg = {
            "venues": [
                {"id": "w", "name": "W", "scrape_urls": [], "website": ""}
            ]
        }
        data = {
            "venues": [
                {"id": "w", "hours": "", "specials": [], "notes": "", "website": ""},
            ]
        }
        candidates = {
            "w": {
                "status": "ok",
                "confidence": "high",
                "hours": "",
                "specials": [
                    {"item": "Beer", "price": 4, "category": "drinks", "description": ""}
                ],
                "source_urls": ["https://w.example/hh"],
                "notes": "",
            }
        }
        applied, _, _ = enrich.apply_candidates(cfg, data, candidates)
        self.assertEqual(applied, 1)
        self.assertEqual(cfg["venues"][0]["website"], "https://w.example/")
        self.assertEqual(data["venues"][0]["website"], "https://w.example/")

    def test_apply_skips_venues_that_already_have_specials(self):
        cfg = {
            "venues": [
                {"id": "filled", "name": "Filled", "scrape_urls": [], "website": "https://f.example/"}
            ]
        }
        data = {
            "venues": [
                {
                    "id": "filled",
                    "hours": "Daily 3-5pm",
                    "specials": [
                        {"item": "Beer", "price": 4, "category": "drinks", "description": ""}
                    ],
                    "notes": "from weekly scrape",
                }
            ]
        }
        candidates = {
            "filled": {
                "status": "ok",
                "confidence": "high",
                "hours": "Mon-Fri 4-6pm",
                "specials": [
                    {"item": "Stale", "price": 1, "category": "drinks", "description": ""}
                ],
                "source_urls": ["https://f.example/hh"],
                "notes": "stale candidate",
            }
        }
        applied, skipped, needs_site = enrich.apply_candidates(cfg, data, candidates)
        self.assertEqual(applied, 0)
        self.assertEqual(skipped, 1)
        self.assertEqual(needs_site, 0)
        filled = data["venues"][0]
        self.assertEqual(filled["specials"][0]["item"], "Beer")
        self.assertEqual(filled["hours"], "Daily 3-5pm")
        self.assertEqual(filled["notes"], "from weekly scrape")

    def test_apply_only_ids_filters_store(self):
        cfg = {
            "venues": [
                {"id": "a", "name": "A", "scrape_urls": [], "website": "https://a.example/"},
                {"id": "b", "name": "B", "scrape_urls": [], "website": "https://b.example/"},
            ]
        }
        data = {
            "venues": [
                {"id": "a", "hours": "", "specials": [], "notes": ""},
                {"id": "b", "hours": "", "specials": [], "notes": ""},
            ]
        }
        candidates = {
            "a": {
                "status": "ok",
                "confidence": "high",
                "hours": "",
                "specials": [
                    {"item": "A deal", "price": 3, "category": "drinks", "description": ""}
                ],
                "source_urls": ["https://a.example/"],
                "notes": "",
            },
            "b": {
                "status": "ok",
                "confidence": "high",
                "hours": "",
                "specials": [
                    {"item": "B deal", "price": 3, "category": "drinks", "description": ""}
                ],
                "source_urls": ["https://b.example/"],
                "notes": "",
            },
        }
        applied, skipped, _ = enrich.apply_candidates(
            cfg, data, candidates, only_ids={"a"}
        )
        self.assertEqual(applied, 1)
        self.assertEqual(len(next(v for v in data["venues"] if v["id"] == "a")["specials"]), 1)
        self.assertEqual(next(v for v in data["venues"] if v["id"] == "b")["specials"], [])


    def test_apply_rejects_price0_without_wording(self):
        cfg = {
            "venues": [
                {"id": "bad", "name": "Bad", "scrape_urls": [], "website": "https://bad.example/"}
            ]
        }
        data = {
            "venues": [
                {"id": "bad", "hours": "", "specials": [], "notes": ""},
            ]
        }
        candidates = {
            "bad": {
                "status": "ok",
                "confidence": "high",
                "hours": "",
                "specials": [
                    {"item": "Mystery", "price": 0, "category": "drinks", "description": "house pour"}
                ],
                "source_urls": ["https://bad.example/"],
                "notes": "",
            }
        }
        applied, skipped, _ = enrich.apply_candidates(cfg, data, candidates)
        self.assertEqual(applied, 0)
        self.assertEqual(skipped, 1)
        self.assertEqual(data["venues"][0]["specials"], [])

    def test_apply_accepts_price0_with_half_off(self):
        cfg = {
            "venues": [
                {"id": "ok0", "name": "Ok", "scrape_urls": [], "website": "https://ok.example/"}
            ]
        }
        data = {
            "venues": [
                {"id": "ok0", "hours": "", "specials": [], "notes": ""},
            ]
        }
        candidates = {
            "ok0": {
                "status": "ok",
                "confidence": "high",
                "hours": "",
                "specials": [
                    {
                        "item": "Well",
                        "price": 0,
                        "category": "drinks",
                        "description": "half off wells",
                    }
                ],
                "source_urls": ["https://ok.example/"],
                "notes": "",
            }
        }
        applied, skipped, _ = enrich.apply_candidates(cfg, data, candidates)
        self.assertEqual(applied, 1)
        self.assertEqual(len(data["venues"][0]["specials"]), 1)


class Price0Helpers(unittest.TestCase):
    def test_price0_context(self):
        self.assertFalse(
            enrich.price0_has_context(
                {"item": "X", "price": 0, "description": "house pour"}, ""
            )
        )
        self.assertTrue(
            enrich.price0_has_context(
                {"item": "X", "price": 0, "description": "half off"}, ""
            )
        )
        self.assertTrue(
            enrich.price0_has_context({"item": "X", "price": 4, "description": ""}, "")
        )


class PageTextCap(unittest.TestCase):
    def test_cap_matches_scraper(self):
        from scraper.fetch import MAX_PAGE_CHARS

        self.assertEqual(enrich.PAGE_TEXT_CAP, MAX_PAGE_CHARS * 2)


class MergeNotes(unittest.TestCase):
    def test_preserves_existing(self):
        out = enrich.merge_notes("Site probed — no HH", "Wing Wednesday", "medium")
        self.assertTrue(out.startswith("Site probed — no HH"))
        self.assertIn("Wing Wednesday", out)
        self.assertIn("conf=medium", out)

    def test_avoids_duplicate_enrich_note(self):
        once = enrich.merge_notes("keep", "same note", "high")
        twice = enrich.merge_notes(once, "same note", "high")
        self.assertEqual(once.count("same note"), 1)
        self.assertEqual(twice.count("same note"), 1)


if __name__ == "__main__":
    unittest.main()
