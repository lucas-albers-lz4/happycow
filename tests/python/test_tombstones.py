"""Tombstone matching for discovery (removed_venues blocklist)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from common import norm_address, norm_name  # noqa: E402
from discover_venues import Candidate, is_removed  # noqa: E402

# Legacy Broken Spoke tombstone as written before shared normalizers (#49 regression).
LEGACY_BROKEN_SPOKE = {
    "id": "broken-spoke-bar-grill",
    "name": "Broken Spoke Bar & Grill",
    "norm_name": "broken spoke bar & grill",  # kept '&' — must still match
    "norm_address": "120 big pine dr, big sky, mt 59716 (meadow village)",
    "reason": "out of coverage",
}

OPEN_RANGE = {
    "id": "open-range",
    "name": "Open Range",
    "norm_name": "open range",
    "norm_address": "241 e main st bozeman",
    "reason": "closed",
}


class TestNormRoundTrip(unittest.TestCase):
    def test_ampersand_stripped(self):
        self.assertEqual(norm_name("Broken Spoke Bar & Grill"), "broken spoke bar grill")

    def test_address_strips_city_noise(self):
        self.assertEqual(
            norm_address("120 Big Pine Dr, Big Sky, MT 59716 (Meadow Village)"),
            "120 big pine dr big sky (meadow village)",
        )


class TestIsRemoved(unittest.TestCase):
    def test_broken_spoke_city_label_drift(self):
        """Aggregator lists Gallatin Gateway; tombstone says Big Sky — same street."""
        c = Candidate(name="Broken Spoke Bar & Grill", address="120 Big Pine Dr, Gallatin Gateway")
        self.assertTrue(is_removed(c, [LEGACY_BROKEN_SPOKE]))

    def test_broken_spoke_exact_legacy_address(self):
        c = Candidate(
            name="Broken Spoke Bar & Grill",
            address="120 Big Pine Dr, Big Sky, MT 59716 (Meadow Village)",
        )
        self.assertTrue(is_removed(c, [LEGACY_BROKEN_SPOKE]))

    def test_open_range_abbrev_vs_expanded_street(self):
        c = Candidate(name="Open Range", address="241 East Main Street, Bozeman, MT 59715")
        self.assertTrue(is_removed(c, [OPEN_RANGE]))

    def test_reopen_at_new_street_not_suppressed(self):
        """Issue #49: same name, different street → human review, not auto-skip."""
        c = Candidate(name="Open Range", address="500 N 7th Ave, Bozeman, MT")
        self.assertFalse(is_removed(c, [OPEN_RANGE]))

    def test_different_name_same_street_not_suppressed(self):
        c = Candidate(name="Meson Frailes", address="241 E Main St, Bozeman")
        self.assertFalse(is_removed(c, [OPEN_RANGE]))


if __name__ == "__main__":
    unittest.main()
