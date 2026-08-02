"""Unit tests for venue truth pipeline (observation → claim → decision)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from harness import TempDir, run_script  # noqa: E402
from adapters.overture import (  # noqa: E402
    load_fixture,
    match_venues_to_candidates,
    observations_from_matches,
)
from adapters.overpass import diff_snapshots, match_removed_to_venues  # noqa: E402
from adapters.scrape_bridge import observation_from_scrape  # noqa: E402
from truth.agreement import agree_venue, venue_has_primary  # noqa: E402
from truth.budget import rank_uncertain  # noqa: E402
from truth import depen, llm_fusion  # noqa: E402
from adapters import social  # noqa: E402
from truth.identity import page_matches_venue, venue_matches_candidate  # noqa: E402
from truth.schema import (  # noqa: E402
    DecisionKind,
    ExtractionMethod,
    FactField,
    Observation,
    ObservationStore,
)
from truth.synthesize import apply_decisions_to_record  # noqa: E402


class IdentityTests(unittest.TestCase):
    def test_page_matches_aggregator(self):
        venue = {"name": "Ale Works", "address": "611 E Main St"}
        self.assertTrue(
            page_matches_venue(
                "Ale Works happy hour — 611 E Main St, Bozeman",
                venue,
                require_address=True,
            )
        )
        self.assertFalse(
            page_matches_venue(
                "Old Chicago — 2107 N 7th Ave",
                venue,
                require_address=True,
            )
        )

    def test_namesake_wrong_address_rejected(self):
        venue = {"name": "Main Street Grill", "address": "1 Main St, Bozeman", "phone": ""}
        self.assertFalse(
            venue_matches_candidate(
                venue,
                name="Main Street Grill",
                address="999 Other Ave, Belgrade",
            )
        )


class SantaFeAgreement(unittest.TestCase):
    def test_closed_prior_suppresses_aggregator_hh(self):
        obs = [
            Observation(
                venue_id="santa-fe-reds",
                observed_at="2026-08-01T00:00:00Z",
                source_url="overture:x",
                source_type="overture",
                source_family="overture",
                extraction_method=ExtractionMethod.PRIOR,
                evidence_excerpt="permanently_closed",
                payload={"business_status": "permanently_closed", "overture_confidence": 0.0},
            ),
            Observation(
                venue_id="santa-fe-reds",
                observed_at="2026-07-01T00:00:00Z",
                source_url="https://mthappyhour.com/locations/santa-fe-reds/",
                source_type="aggregator",
                source_family="mthappyhour",
                extraction_method=ExtractionMethod.LLM,
                evidence_excerpt="hours=Daily 3-6pm",
                payload={
                    "business_status": "open",
                    "hours": "Daily 3-6pm, Fri-Sat 10pm-12am",
                    "specials": [
                        {"item": "$5 Marg", "price": 5, "category": "drinks", "description": ""}
                    ],
                },
            ),
        ]
        decisions = agree_venue("santa-fe-reds", obs, has_primary_source=False)
        status = decisions["business_status"]
        self.assertEqual(status.kind, DecisionKind.SUPPRESSED)
        self.assertIn(status.value, ("permanently_closed", "likely_closed"))
        self.assertEqual(decisions["specials"].kind, DecisionKind.SUPPRESSED)
        self.assertEqual(decisions["hours"].kind, DecisionKind.SUPPRESSED)

    def test_aggregator_only_open_is_unverified(self):
        obs = [
            Observation(
                venue_id="x",
                observed_at="2026-08-01T00:00:00Z",
                source_type="aggregator",
                source_family="mthappyhour",
                source_url="https://mthappyhour.com/x",
                payload={"business_status": "open", "hours": "Mon-Fri 4-6pm"},
            )
        ]
        d = agree_venue("x", obs, has_primary_source=False)
        self.assertEqual(d["business_status"].kind, DecisionKind.UNVERIFIED)
        self.assertEqual(d["business_status"].value, "open")


class SynthesizeSuppress(unittest.TestCase):
    def test_shadow_leaves_record_unchanged(self):
        from truth.schema import Decision

        rec = {"id": "x", "specials": [{"item": "Beer", "price": 5}], "hours": "4-6pm", "notes": ""}
        decisions = {
            "business_status": Decision(
                venue_id="x",
                field=FactField.BUSINESS_STATUS,
                kind=DecisionKind.SUPPRESSED,
                value="likely_closed",
            ),
            "specials": Decision(
                venue_id="x",
                field=FactField.SPECIALS,
                kind=DecisionKind.SUPPRESSED,
                value=None,
            ),
            "hours": Decision(
                venue_id="x",
                field=FactField.HOURS,
                kind=DecisionKind.SUPPRESSED,
                value=None,
            ),
        }
        out = apply_decisions_to_record(rec, decisions, suppress_enabled=False)
        self.assertEqual(out["specials"], rec["specials"])
        out2 = apply_decisions_to_record(rec, decisions, suppress_enabled=True)
        self.assertEqual(out2["specials"], [])
        self.assertEqual(out2["hours"], "")
        self.assertIn("suppressed", out2["notes"].lower())


class OvertureFixture(unittest.TestCase):
    def test_fixture_matches_santa_fe(self):
        places = load_fixture(ROOT / "data" / "eval" / "overture_fixture.json")
        venue = {
            "id": "santa-fe-reds",
            "name": "Santa Fe Reds",
            "address": "1235 N 7th Ave, Bozeman",
            "phone": "",
        }
        matches = match_venues_to_candidates([venue], places)
        self.assertIn("santa-fe-reds", matches)
        self.assertEqual(matches["santa-fe-reds"]["operating_status"], "permanently_closed")
        obs = observations_from_matches(matches)
        self.assertEqual(obs[0].payload["business_status"], "permanently_closed")


class OverpassDiff(unittest.TestCase):
    def test_removed_matched(self):
        prev = [{"osm_key": "node/1", "name": "Santa Fe Reds", "address": "1235 N 7th"}]
        curr = []
        diff = diff_snapshots(prev, curr)
        self.assertEqual(len(diff["removed"]), 1)
        venues = [{"id": "santa-fe-reds", "name": "Santa Fe Reds", "address": "1235 N 7th Ave"}]
        hits = match_removed_to_venues(diff["removed"], venues)
        self.assertEqual(hits[0][0], "santa-fe-reds")


class ObservationStoreRetention(unittest.TestCase):
    def test_compact_keeps_last_n(self):
        with TempDir() as tmp:
            store = ObservationStore(tmp / "evidence", retain_per_family=2)
            for i in range(4):
                store.write(
                    Observation(
                        venue_id="v1",
                        observed_at=f"2026-08-0{i+1}T00:00:00Z",
                        source_type="overture",
                        source_family="overture",
                        payload={"business_status": "open", "n": i},
                        content_hash=f"hash{i}",
                    )
                )
            remaining = store.list_for_venue("v1")
            self.assertEqual(len(remaining), 2)


class BudgetRank(unittest.TestCase):
    def test_top_n(self):
        from truth.schema import Decision

        venues = [
            {"id": "a", "scrape_urls": ["https://example.com"], "website": "https://example.com"},
            {"id": "b", "scrape_urls": ["https://mthappyhour.com/x"], "website": ""},
        ]
        decisions = {
            "a": {
                "business_status": Decision(
                    venue_id="a",
                    field=FactField.BUSINESS_STATUS,
                    kind=DecisionKind.VERIFIED,
                    value="open",
                )
            },
            "b": {
                "business_status": Decision(
                    venue_id="b",
                    field=FactField.BUSINESS_STATUS,
                    kind=DecisionKind.CONFLICTED,
                    value="unknown",
                )
            },
        }
        top = rank_uncertain(venues, decisions, venue_has_primary, top_n=1)
        self.assertEqual(top, ["b"])


class DeferredExtensionPoints(unittest.TestCase):
    def test_depen_llm_social_not_available(self):
        self.assertFalse(depen.available())
        self.assertFalse(llm_fusion.available())
        self.assertFalse(social.available())
        with self.assertRaises(NotImplementedError):
            depen.agree_depen([])
        with self.assertRaises(NotImplementedError):
            llm_fusion.fuse_claims([])
        with self.assertRaises(NotImplementedError):
            social.fetch_observations({})


class ScrapeBridge(unittest.TestCase):
    def test_builds_observation(self):
        venue = {
            "id": "x",
            "name": "X",
            "address": "1 Main",
            "scrape_urls": ["https://mthappyhour.com/x"],
        }
        extract = {
            "status": "ok",
            "hours": "Mon-Fri 4-6pm",
            "specials": [{"item": "Beer", "price": 5, "category": "drinks", "description": ""}],
        }
        obs = observation_from_scrape(venue, extract, venue["scrape_urls"])
        self.assertIsNotNone(obs)
        self.assertEqual(obs.source_type, "aggregator")
        self.assertEqual(obs.payload["hours"], "Mon-Fri 4-6pm")


class GoldenEvalScript(unittest.TestCase):
    def test_eval_script_passes(self):
        proc = run_script(ROOT / "scripts" / "eval_venue_truth.py")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
