#!/usr/bin/env python3
"""Issue #41: unparseable hours rejected; specials still apply; prev hours kept.

Stdlib unittest only — normalize_hours cases live in #44, not here.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from scraper.merge import reject_unparseable_hours, venue_to_site_record  # noqa: E402


class RejectUnparseableHours(unittest.TestCase):
    def test_bad_hours_cleared_specials_kept_prev_hours(self) -> None:
        extracts = {
            "venue-a": {
                "status": "ok",
                "hours": "not a real hours string",
                "business_hours": "",
                "specials": [
                    {
                        "item": "Well drinks",
                        "price": 5.0,
                        "category": "drinks",
                        "description": "",
                    }
                ],
                "notes": "",
            },
            "venue-b": {
                "status": "ok",
                "hours": "Daily 3-5pm & 8-9pm",
                "business_hours": "",
                "specials": [],
                "notes": "",
            },
        }
        bad = reject_unparseable_hours(extracts)
        self.assertEqual(bad, ["venue-a"])
        self.assertEqual(extracts["venue-a"]["hours"], "")
        self.assertEqual(len(extracts["venue-a"]["specials"]), 1)
        self.assertEqual(extracts["venue-b"]["hours"], "Daily 3-5pm & 8-9pm")

        venue = {
            "id": "venue-a",
            "name": "Venue A",
            "nickname": "A",
            "address": "1 Main",
            "phone": "",
            "website": "",
            "maps": "",
            "tags": [],
            "noise_level": "",
            "mood": "",
            "scrape_urls": ["https://example.com"],
        }
        prev = {
            "id": "venue-a",
            "hours": "Mon-Fri 4-6pm",
            "business_hours": "Daily 11am-10pm",
            "specials": [{"item": "Old", "price": 1, "category": "drinks", "description": ""}],
            "notes": "",
        }
        record = venue_to_site_record(venue, extracts["venue-a"], prev)
        self.assertEqual(record["hours"], "Mon-Fri 4-6pm")
        self.assertEqual(record["specials"][0]["item"], "Well drinks")
        self.assertNotIn("scrape_urls", record)

    def test_empty_candidates_no_node_needed(self) -> None:
        extracts = {"x": {"status": "ok", "hours": "", "specials": [{"item": "A", "price": 0, "category": "drinks", "description": "free"}]}}
        self.assertEqual(reject_unparseable_hours(extracts), [])


if __name__ == "__main__":
    unittest.main()
