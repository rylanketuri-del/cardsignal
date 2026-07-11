"""Tests for Data Confidence Layer (Sprint 10.0 / v0.14.0)."""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from cardchase_ai.data_confidence import (
    build_card_confidence,
    build_player_confidence,
    compute_freshness_bucket,
    confidence_response_to_public_dict,
)
from cardchase_ai.models.weekly import CardWeeklyIntelligenceSnapshot, PlayerWeeklySignalSnapshot

REPO_ROOT = Path(__file__).resolve().parents[1]


def _now() -> datetime:
    return datetime(2026, 7, 11, 12, 0, 0, tzinfo=timezone.utc)


def _player_entry(**overrides) -> dict:
    base = {
        "player_id": 592450,
        "player_name": "Aaron Judge",
        "stats_7d": {"games": 6, "avg": 0.310, "ops": 1.050, "home_runs": 3},
        "stats_30d": {"games": 28, "avg": 0.285, "ops": 0.980},
        "market_snapshots": {
            "broad": {"listings_count": 12, "query_name": "broad"},
            "auto": {"listings_count": 8, "query_name": "auto"},
        },
        "generated_at": _now().isoformat(),
    }
    base.update(overrides)
    return base


def _weekly_snap(**overrides) -> PlayerWeeklySignalSnapshot:
    data = {
        "snapshot_id": "snap-1",
        "run_id": "run-1",
        "cs_player_id": "mlb:592450",
        "source_player_id": "592450",
        "league": "MLB",
        "sport": "MLB",
        "season": 2026,
        "year": 2026,
        "week_number": 28,
        "period_start": _now() - timedelta(days=7),
        "period_end": _now(),
        "performance_score": 82.0,
        "market_score": 74.0,
        "collector_score": 68.0,
        "momentum_score": 71.0,
        "scarcity_score": 55.0,
        "recommendation": "BUY",
        "conviction": "High",
        "missing_inputs": [],
        "evidence": {
            "performance_reasons": ["elite 7-day OPS"],
            "collector_evidence": ["premium_listings=4"],
            "momentum_evidence": ["ops_delta=0.070"],
        },
        "captured_at": _now() - timedelta(minutes=42),
        "algorithm_version": "MLB_PLAYER_SIGNAL_V1",
    }
    data.update(overrides)
    return PlayerWeeklySignalSnapshot.model_validate(data)


def _card_snap(**overrides) -> CardWeeklyIntelligenceSnapshot:
    data = {
        "snapshot_id": "csnap-1",
        "run_id": "run-1",
        "cs_card_id": "mlb:592450:card:broad",
        "cs_player_id": "mlb:592450",
        "league": "MLB",
        "year": 2026,
        "week_number": 28,
        "period_start": _now() - timedelta(days=7),
        "period_end": _now(),
        "card_signal_score": 72.0,
        "recommendation": "HOLD",
        "missing_inputs": [],
        "evidence": {
            "listings_count": 18,
            "tags": {"psa10_count": 3, "premium_count": 5},
        },
        "captured_at": _now() - timedelta(hours=3),
        "card_label": "2024 Topps Chrome",
        "algorithm_version": "MLB_PLAYER_SIGNAL_V1",
    }
    data.update(overrides)
    return CardWeeklyIntelligenceSnapshot.model_validate(data)


class FreshnessBucketTests(unittest.TestCase):
    def test_live_bucket(self):
        latest = _now() - timedelta(minutes=30)
        info = compute_freshness_bucket(latest, now=_now())
        self.assertEqual(info.bucket, "LIVE")
        self.assertLess(info.freshness_minutes, 60)

    def test_recent_bucket(self):
        latest = _now() - timedelta(hours=5)
        info = compute_freshness_bucket(latest, now=_now())
        self.assertEqual(info.bucket, "RECENT")

    def test_current_bucket(self):
        latest = _now() - timedelta(days=3)
        info = compute_freshness_bucket(latest, now=_now())
        self.assertEqual(info.bucket, "CURRENT")

    def test_stale_bucket(self):
        latest = _now() - timedelta(days=10)
        info = compute_freshness_bucket(latest, now=_now())
        self.assertEqual(info.bucket, "STALE")

    def test_unknown_when_no_timestamp(self):
        info = compute_freshness_bucket(None, now=_now())
        self.assertEqual(info.bucket, "UNKNOWN")
        self.assertIsNone(info.freshness_minutes)


class PlayerConfidenceTests(unittest.TestCase):
    def test_confidence_not_derived_from_recommendation(self):
        entry = _player_entry()
        snap_buy = _weekly_snap(recommendation="BUY")
        snap_sell = _weekly_snap(recommendation="SELL")

        conf_buy = build_player_confidence("592450", entry, snap_buy, [snap_buy.model_dump(mode="json")])
        conf_sell = build_player_confidence("592450", entry, snap_sell, [snap_sell.model_dump(mode="json")])

        self.assertEqual(conf_buy.confidence.confidence_level, conf_sell.confidence.confidence_level)
        self.assertEqual(conf_buy.confidence.confidence_score, conf_sell.confidence.confidence_score)

    def test_missing_evidence_lowers_confidence(self):
        entry = _player_entry(market_snapshots={})
        rich_snap = _weekly_snap(missing_inputs=[])
        sparse_snap = _weekly_snap(missing_inputs=["stats_7d", "market_snapshots", "listing_volume"])

        rich = build_player_confidence("592450", entry, rich_snap, [])
        sparse = build_player_confidence("592450", entry, sparse_snap, [])

        self.assertGreater(rich.confidence.confidence_score, sparse.confidence.confidence_score)
        self.assertTrue(sparse.missing_inputs)

    def test_evidence_summary_uses_stored_data_only(self):
        entry = _player_entry()
        snap = _weekly_snap()
        history = [snap.model_dump(mode="json"), snap.model_dump(mode="json")]
        response = build_player_confidence("592450", entry, snap, history)

        self.assertEqual(response.evidence_summary.player_snapshots, 2)
        self.assertEqual(response.evidence_summary.market_snapshots, 2)
        self.assertGreater(response.evidence_summary.signal_drivers, 0)

    def test_missing_inputs_surfaced_honestly(self):
        snap = _weekly_snap(missing_inputs=["population", "market_snapshots"])
        response = build_player_confidence("592450", _player_entry(), snap, [])
        self.assertTrue(any("Population" in msg for msg in response.missing_inputs))
        self.assertTrue(any("Market activity" in msg for msg in response.missing_inputs))


class CardConfidenceTests(unittest.TestCase):
    def test_card_confidence_independent_of_recommendation(self):
        snap_hold = _card_snap(recommendation="HOLD")
        snap_buy = _card_snap(recommendation="BUY")
        hold = build_card_confidence(snap_hold.cs_card_id, snap_hold, [snap_hold.model_dump(mode="json")], registry_linked=True)
        buy = build_card_confidence(snap_buy.cs_card_id, snap_buy, [snap_buy.model_dump(mode="json")], registry_linked=True)
        self.assertEqual(hold.confidence.confidence_level, buy.confidence.confidence_level)


class ApiSerializationTests(unittest.TestCase):
    def test_no_weighting_percentages_exposed(self):
        response = build_player_confidence("592450", _player_entry(), _weekly_snap(), [])
        payload = confidence_response_to_public_dict(response)
        serialized = json.dumps(payload)
        self.assertNotIn("confidence_multiplier", serialized)
        self.assertNotIn("weight", serialized.lower())
        self.assertNotIn("percent", serialized.lower())

    def test_api_payload_includes_confidence_without_formulas(self):
        response = build_player_confidence("592450", _player_entry(), _weekly_snap(), [])
        payload = confidence_response_to_public_dict(response)
        self.assertIn("confidence", payload)
        self.assertIn("freshness", payload)
        self.assertIn("evidence_summary", payload)
        self.assertIn("missing_inputs", payload)
        self.assertNotIn("_compute_confidence_score", json.dumps(payload))


class ConfidenceEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from api.main import app

        cls.client = TestClient(app)

    def test_player_confidence_endpoint(self):
        response = self.client.get("/api/confidence/player/592450")
        if response.status_code == 404:
            self.skipTest("No player data in test environment")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["entity_type"], "player")
        self.assertIn("confidence", body)
        self.assertIn("freshness", body)
        self.assertNotIn("confidence_multiplier", json.dumps(body))

    def test_card_confidence_endpoint(self):
        response = self.client.get("/api/confidence/card/mlb:592450:card:broad")
        self.assertIn(response.status_code, {200, 404})
        if response.status_code == 200:
            body = response.json()
            self.assertEqual(body["entity_type"], "card")


class FrontendGuardTests(unittest.TestCase):
    def test_data_confidence_script_loaded(self):
        index_html = (REPO_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
        self.assertIn("data-confidence.js", index_html)
        metrics_pos = index_html.find("data-confidence.js")
        app_pos = index_html.find("app.js")
        self.assertGreater(app_pos, metrics_pos)

    def test_scouting_report_uses_evidence_not_confidence_in_header(self):
        app_js = (REPO_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
        dc_js = (REPO_ROOT / "frontend" / "data-confidence.js").read_text(encoding="utf-8")
        header_fn = app_js.split("function renderScoutingReportHeader")[1].split("function ")[0]
        self.assertIn("dcRenderHeaderBadges", header_fn)
        self.assertIn("Evidence", dc_js)
        self.assertIn("Freshness", dc_js)
        self.assertNotIn('"Confidence"', header_fn)

    def test_why_this_report_section_present(self):
        dc_js = (REPO_ROOT / "frontend" / "data-confidence.js").read_text(encoding="utf-8")
        self.assertIn("Why this report?", dc_js)


if __name__ == "__main__":
    unittest.main()
