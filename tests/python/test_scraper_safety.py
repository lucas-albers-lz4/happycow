"""Issue #44: scraper safety and normalization unit tests.

Covers:
  - common.is_aggregator
  - fetch.page_matches_venue (aggregator match/reject, own-site soft)
  - merge.venue_to_site_record (carry-through, scrape_urls exclusion, falsy config keeps prev)
  - extract.normalize_hours
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from common import is_aggregator  # noqa: E402
from scraper.extract import normalize_hours  # noqa: E402
from scraper.fetch import page_matches_venue  # noqa: E402
from scraper.merge import venue_to_site_record  # noqa: E402


class IsAggregator(unittest.TestCase):
    def test_known_aggregator_hosts(self):
        for url in [
            "https://mthappyhour.com/bozeman/ale-works",
            "https://www.yelp.com/biz/ale-works-bozeman",
            "https://facebook.com/aleworks",
            "https://menupix.com/bozeman/ale-works",
            "https://sellout.io/bozeman",
            "https://google.com/maps/place/aleworks",
            "https://visit-bozeman.com/eat/happy-hours",
            "https://bozemanmagazine.com/dining/happy-hour",
        ]:
            with self.subTest(url=url):
                self.assertTrue(is_aggregator(url))

    def test_own_site_not_aggregator(self):
        for url in [
            "https://www.montanaaleworks.com/happy-hour",
            "https://bozemangrill.com/specials",
            "https://theexample.biz/hh",
        ]:
            with self.subTest(url=url):
                self.assertFalse(is_aggregator(url))

    def test_empty_and_junk(self):
        self.assertFalse(is_aggregator(""))
        self.assertFalse(is_aggregator("not a url"))


class PageMatchesVenue(unittest.TestCase):
    VENUE = {"id": "ale-works", "name": "Ale Works", "address": "611 E Main St"}

    def test_aggregator_match_name_and_street_number(self):
        text = "Ale Works happy hour — 611 E Main St, Bozeman MT"
        self.assertTrue(page_matches_venue(text, self.VENUE, require_address=True))

    def test_aggregator_reject_wrong_venue_entirely(self):
        text = "Old Chicago happy hour — 2107 N 7th Ave, Bozeman MT"
        self.assertFalse(page_matches_venue(text, self.VENUE, require_address=True))

    def test_aggregator_reject_right_name_wrong_address(self):
        text = "Ale Works is located at 999 Other Rd, Bozeman MT"
        self.assertFalse(page_matches_venue(text, self.VENUE, require_address=True))

    def test_own_site_passes_on_name_alone(self):
        text = "Welcome to Ale Works — happy hour 4-6pm daily!"
        self.assertTrue(page_matches_venue(text, self.VENUE, require_address=False))

    def test_own_site_fails_when_name_absent(self):
        text = "Welcome to our restaurant — happy hour 4-6pm daily!"
        self.assertFalse(page_matches_venue(text, self.VENUE, require_address=False))

    def test_venue_with_no_address_soft_pass(self):
        venue_no_addr = {"id": "no-addr", "name": "No Addr Bar", "address": ""}
        text = "No Addr Bar happy hour 4-6pm"
        self.assertTrue(page_matches_venue(text, venue_no_addr, require_address=True))


class VenueToSiteRecord(unittest.TestCase):
    BASE_VENUE = {
        "id": "test-venue",
        "name": "Test Venue",
        "nickname": "TV",
        "nickname_alts": [],
        "address": "123 Main St",
        "phone": "555-1234",
        "website": "https://test.example.com",
        "maps": "https://maps.google.com/test",
        "tags": ["downtown"],
        "noise_level": "moderate",
        "mood": "casual",
        "scrape_urls": ["https://mthappyhour.com/test-venue"],
    }

    def test_scrape_urls_never_in_record(self):
        record = venue_to_site_record(self.BASE_VENUE, {}, None)
        self.assertNotIn("scrape_urls", record)

    def test_config_fields_carry_through(self):
        record = venue_to_site_record(self.BASE_VENUE, {}, None)
        self.assertEqual(record["name"], "Test Venue")
        self.assertEqual(record["address"], "123 Main St")
        self.assertEqual(record["tags"], ["downtown"])

    def test_falsy_website_keeps_prev(self):
        venue = {**self.BASE_VENUE, "website": ""}
        prev = {**self.BASE_VENUE, "website": "https://old.example.com", "hours": "", "specials": [], "notes": ""}
        record = venue_to_site_record(venue, {}, prev)
        self.assertEqual(record["website"], "https://old.example.com")

    def test_falsy_tags_keeps_prev(self):
        venue = {**self.BASE_VENUE, "tags": []}
        prev = {**self.BASE_VENUE, "tags": ["sports", "dive"], "hours": "", "specials": [], "notes": ""}
        record = venue_to_site_record(venue, {}, prev)
        self.assertEqual(record["tags"], ["sports", "dive"])

    def test_non_empty_tags_overrides_prev(self):
        venue = {**self.BASE_VENUE, "tags": ["downtown"]}
        prev = {**self.BASE_VENUE, "tags": ["old-tag"], "hours": "", "specials": [], "notes": ""}
        record = venue_to_site_record(venue, {}, prev)
        self.assertEqual(record["tags"], ["downtown"])

    def test_extract_hours_win_over_prev(self):
        extract = {"hours": "Mon-Fri 4-6pm", "business_hours": "", "specials": [], "notes": ""}
        prev = {**self.BASE_VENUE, "hours": "Old hours 5-7pm", "specials": [], "notes": ""}
        record = venue_to_site_record(self.BASE_VENUE, extract, prev)
        self.assertEqual(record["hours"], "Mon-Fri 4-6pm")

    def test_empty_extract_hours_falls_back_to_prev(self):
        extract = {"hours": "", "business_hours": "", "specials": [], "notes": ""}
        prev = {**self.BASE_VENUE, "hours": "Daily 4-6pm", "specials": [], "notes": ""}
        record = venue_to_site_record(self.BASE_VENUE, extract, prev)
        self.assertEqual(record["hours"], "Daily 4-6pm")

    def test_extract_specials_win(self):
        new_special = {"item": "Draft", "price": 4.0, "category": "drinks", "description": ""}
        extract = {"hours": "", "business_hours": "", "specials": [new_special], "notes": ""}
        prev = {**self.BASE_VENUE, "hours": "", "specials": [], "notes": ""}
        record = venue_to_site_record(self.BASE_VENUE, extract, prev)
        self.assertEqual(record["specials"][0]["item"], "Draft")

    def test_no_prev_no_extract_runtime_fields_empty(self):
        record = venue_to_site_record(self.BASE_VENUE, None, None)
        self.assertEqual(record["hours"], "")
        self.assertEqual(record["specials"], [])


class NormalizeHours(unittest.TestCase):
    def test_empty_returns_empty(self):
        self.assertEqual(normalize_hours(""), "")

    def test_everyday_to_daily(self):
        self.assertIn("Daily", normalize_hours("everyday 4pm-6pm"))

    def test_every_day_to_daily(self):
        self.assertIn("Daily", normalize_hours("every day 4pm-6pm"))

    def test_day_range_collapses_spaces(self):
        self.assertIn("Mon-Fri", normalize_hours("Mon - Fri 4pm-6pm"))

    def test_pm_space_stripped(self):
        result = normalize_hours("Daily 4 PM-6 PM")
        self.assertIn("4pm", result.lower())
        self.assertIn("6pm", result.lower())
        self.assertNotIn(" PM", result)

    def test_to_becomes_dash(self):
        self.assertIn("4pm-6pm", normalize_hours("Daily 4pm to 6pm"))

    def test_em_dash_to_hyphen(self):
        result = normalize_hours("Mon-Fri 4pm\u20136pm")
        self.assertNotIn("\u2013", result)

    def test_en_dash_to_hyphen(self):
        result = normalize_hours("Mon-Fri 4pm\u20146pm")
        self.assertNotIn("\u2014", result)

    def test_day_case_title(self):
        self.assertIn("Mon-Fri", normalize_hours("mon-fri 4pm-6pm"))

    def test_daily_prefix_preserved(self):
        self.assertTrue(normalize_hours("DAILY 4pm-6pm").startswith("Daily "))

    def test_collapse_extra_spaces(self):
        result = normalize_hours("Daily  4pm-6pm")
        self.assertNotIn("  ", result)


if __name__ == "__main__":
    unittest.main()
