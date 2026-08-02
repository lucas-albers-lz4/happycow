"""Unit tests for venue truth pipeline (observation → claim → decision)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from harness import TempDir, run_script, write_json  # noqa: E402
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

    def test_overture_alone_open_is_unverified(self):
        obs = [
            Observation(
                venue_id="x",
                observed_at="2026-08-01T00:00:00Z",
                source_type="overture",
                source_family="overture",
                source_url="overture:x",
                payload={"business_status": "open", "overture_confidence": 0.9},
            )
        ]
        d = agree_venue("x", obs, has_primary_source=True)
        self.assertEqual(d["business_status"].kind, DecisionKind.UNVERIFIED)
        self.assertEqual(d["business_status"].value, "open")

    def test_overture_plus_own_site_is_verified(self):
        obs = [
            Observation(
                venue_id="x",
                observed_at="2026-08-01T00:00:00Z",
                source_type="overture",
                source_family="overture",
                source_url="overture:x",
                payload={"business_status": "open", "overture_confidence": 0.9},
            ),
            Observation(
                venue_id="x",
                observed_at="2026-08-01T00:00:00Z",
                source_type="own_site",
                source_family="own_site",
                source_url="https://example.com/hh",
                payload={"business_status": "open", "hours": "4-6pm"},
            ),
        ]
        d = agree_venue("x", obs, has_primary_source=True)
        self.assertEqual(d["business_status"].kind, DecisionKind.VERIFIED)
        self.assertEqual(d["business_status"].value, "open")


class SynthesizeSuppress(unittest.TestCase):
    def test_shadow_leaves_record_unchanged(self):
        from truth.schema import Decision

        rec = {
            "id": "x",
            "specials": [{"item": "Beer", "price": 5}],
            "hours": "4-6pm",
            "business_hours": "Daily 11am-10pm",
            "notes": "",
        }
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
            "business_hours": Decision(
                venue_id="x",
                field=FactField.BUSINESS_HOURS,
                kind=DecisionKind.SUPPRESSED,
                value=None,
            ),
        }
        out = apply_decisions_to_record(rec, decisions, suppress_enabled=False)
        self.assertEqual(out["specials"], rec["specials"])
        out2 = apply_decisions_to_record(rec, decisions, suppress_enabled=True)
        self.assertEqual(out2["specials"], [])
        self.assertEqual(out2["hours"], "")
        self.assertEqual(out2["business_hours"], "")
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

    def test_confidence_zero_does_not_force_closed(self):
        matches = {
            "open-low-conf": {
                "id": "ov-1",
                "name": "Open Pub",
                "address": "1 Main",
                "operating_status": "open",
                "confidence": 0.0,
            }
        }
        obs = observations_from_matches(matches)
        self.assertEqual(obs[0].payload["business_status"], "open")

    def test_namesake_fallback_path_removed(self):
        venue = {
            "id": "main-street",
            "name": "Main Street Grill",
            "address": "1 Main St, Bozeman",
            "phone": "",
        }
        cand = {
            "id": "wrong",
            "name": "Main Street Grill",
            "address": "999 Other Ave, Belgrade",
            "operating_status": "permanently_closed",
            "confidence": 0.0,
        }
        matches = match_venues_to_candidates([venue], [cand], min_score=0.5)
        self.assertNotIn("main-street", matches)


class OvertureLocalParquet(unittest.TestCase):
    def test_query_local_parquet(self):
        try:
            import duckdb
        except ImportError:
            self.skipTest("duckdb not installed")
        from adapters.overture import query_overture_bbox

        with TempDir() as tmp:
            parquet = tmp / "places.parquet"
            con = duckdb.connect()
            con.execute(
                """
                COPY (
                  SELECT
                    'id-1' AS id,
                    {'primary': 'Test Brewery'} AS names,
                    [{'freeform': '100 Test St', 'locality': 'Bozeman'}] AS addresses,
                    ['4065551212'] AS phones,
                    'open' AS operating_status,
                    0.88::DOUBLE AS confidence,
                    {'primary': 'brewery'} AS categories
                ) TO ? (FORMAT PARQUET)
                """,
                [str(parquet)],
            )
            con.close()
            rows = query_overture_bbox(
                {"xmin": 0, "xmax": 1, "ymin": 0, "ymax": 1},
                parquet_glob=str(parquet),
            )
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["name"], "Test Brewery")
            self.assertEqual(rows[0]["operating_status"], "open")


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

    def test_prefers_own_site_url_over_aggregator(self):
        venue = {
            "id": "ale",
            "name": "Ale Works",
            "address": "611 E Main",
            "scrape_urls": [
                "https://mthappyhour.com/locations/ale-works/",
                "https://www.montanaaleworks.com/happy-hour",
            ],
        }
        extract = {
            "status": "ok",
            "hours": "Mon-Fri 3-6pm",
            "specials": [{"item": "Beer", "price": 5, "category": "drinks", "description": ""}],
        }
        obs = observation_from_scrape(venue, extract, venue["scrape_urls"])
        self.assertIsNotNone(obs)
        self.assertEqual(obs.source_type, "own_site")
        self.assertIn("montanaaleworks.com", obs.source_url)


class GoldenEvalScript(unittest.TestCase):
    def test_eval_script_passes(self):
        proc = run_script(ROOT / "scripts" / "eval_venue_truth.py")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


class ShadowCliIntegration(unittest.TestCase):
    """CLI wiring: dry-run, --suppress gate, --force-suppress clear path."""

    def test_dry_run_exits_zero(self):
        proc = run_script(ROOT / "scripts" / "run_venue_truth.py", ["--dry-run"])
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("Overture:", proc.stdout)

    def test_suppress_gate_and_force_clear(self):
        import run_venue_truth as rvt

        fixture = ROOT / "data" / "eval" / "overture_fixture.json"
        santa = {
            "id": "santa-fe-reds",
            "name": "Santa Fe Reds",
            "address": "1235 N 7th Ave, Bozeman",
            "phone": "",
            "website": "",
            "scrape_urls": ["https://mthappyhour.com/locations/santa-fe-reds/"],
        }
        site_venue = {
            "id": "santa-fe-reds",
            "name": "Santa Fe Reds",
            "hours": "Daily 3-6pm",
            "business_hours": "Mon-Sun 11am-10pm",
            "specials": [
                {"item": "$5 Marg", "price": 5, "category": "drinks", "description": ""}
            ],
            "notes": "Source: mthappyhour.com",
        }

        with TempDir() as tmp:
            venues_path = tmp / "venues.json"
            data_path = tmp / "happy_hour_data.json"
            state = tmp / "state"
            evidence = tmp / "evidence"
            state.mkdir()
            evidence.mkdir()
            write_json(venues_path, {"venues": [santa]})
            write_json(data_path, {"last_updated": "2026-08-01T00:00:00Z", "venues": [site_venue]})
            write_json(state / "truth_config.json", {"suppress_enabled": False, "top_n_uncertain": 5})

            patches = {
                "VENUES_PATH": venues_path,
                "DATA_PATH": data_path,
                "EVIDENCE_DIR": evidence,
                "TRUTH_CONFIG_PATH": state / "truth_config.json",
                "SHADOW_DECISIONS_PATH": state / "shadow_decisions.json",
                "REVIEW_QUEUE_PATH": state / "review_queue.json",
                "COST_COUNTERS_PATH": state / "cost_counters.json",
                "OVERTURE_CACHE_PATH": state / "overture_priors.json",
                "OVERPASS_CACHE_PATH": state / "overpass_snapshot.json",
            }
            orig = {name: getattr(rvt, name) for name in patches}
            try:
                for name, value in patches.items():
                    setattr(rvt, name, value)

                # --suppress alone must NOT mutate site data when config is false
                before = data_path.read_text(encoding="utf-8")
                rc = rvt.run(fixture=fixture, suppress=True, write=True)
                self.assertEqual(rc, 0)
                self.assertEqual(data_path.read_text(encoding="utf-8"), before)

                shadow = json.loads((state / "shadow_decisions.json").read_text(encoding="utf-8"))
                status = shadow["venues"]["santa-fe-reds"]["business_status"]
                self.assertEqual(status["kind"], "suppressed")
                self.assertIn(status["value"], ("permanently_closed", "likely_closed"))

                # --force-suppress clears HH fields for suppressed venues
                rc = rvt.run(fixture=fixture, force_suppress=True, write=True)
                self.assertEqual(rc, 0)
                after = json.loads(data_path.read_text(encoding="utf-8"))
                rec = after["venues"][0]
                self.assertEqual(rec["specials"], [])
                self.assertEqual(rec["hours"], "")
                self.assertEqual(rec["business_hours"], "")
                self.assertIn("suppressed", (rec.get("notes") or "").lower())
            finally:
                for name, value in orig.items():
                    setattr(rvt, name, value)

if __name__ == "__main__":
    unittest.main()
