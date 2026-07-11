"""Tests for Card Report model and API builder."""

from __future__ import annotations

import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from cardchase_ai.card_outlook import format_evidence_tier
from cardchase_ai.card_report import (
    build_card_report,
    parse_cs_card_id,
)
from cardchase_ai.models.card_report import CardReport


def _sample_snapshot(cs_card_id: str = "mlb:660271:card:psa10") -> dict:
    now = datetime(2026, 7, 8, 12, 0, tzinfo=ZoneInfo("UTC"))
    return {
        "snapshot_id": "snap-1",
        "run_id": "run-1",
        "cs_card_id": cs_card_id,
        "cs_player_id": "mlb:660271",
        "league": "MLB",
        "year": 2026,
        "week_number": 28,
        "period_start": now.isoformat(),
        "period_end": now.isoformat(),
        "card_signal_score": 72.5,
        "recommendation": "BUY",
        "conviction": "Medium",
        "risk": "Low",
        "time_horizon": "2-4 weeks",
        "market_activity_score": 68.0,
        "demand_score": 74.0,
        "momentum_score": 55.0,
        "scarcity_score": 61.0,
        "missing_inputs": [],
        "algorithm_version": "WEEKLY_INTELLIGENCE_V1",
        "captured_at": now.isoformat(),
        "card_label": "PSA 10",
        "player_name": "Aaron Judge",
        "evidence": {
            "query_name": "psa10",
            "listings_count": 12,
            "avg_price": 145.0,
            "tags": {"psa10_count": 8, "premium_count": 3, "numbered_count": 1},
        },
    }


class ParseCsCardIdTests(unittest.TestCase):
    def test_valid_cs_card_id(self):
        parsed = parse_cs_card_id("mlb:660271:card:psa10")
        self.assertEqual(parsed["league"], "MLB")
        self.assertEqual(parsed["player_id"], "660271")
        self.assertEqual(parsed["query_name"], "psa10")
        self.assertEqual(parsed["cs_player_id"], "mlb:660271")

    def test_invalid_cs_card_id_raises(self):
        with self.assertRaises(ValueError):
            parse_cs_card_id("invalid-id")


class EvidenceTierTests(unittest.TestCase):
    def test_conviction_mapping(self):
        self.assertEqual(format_evidence_tier("High"), "HIGH")
        self.assertEqual(format_evidence_tier("Medium"), "MEDIUM")
        self.assertEqual(format_evidence_tier(None), "INSUFFICIENT")


class BuildCardReportTests(unittest.TestCase):
    def test_builds_card_report_from_snapshot(self):
        snapshot = _sample_snapshot()
        snapshot["evidence"]["outlook_reasons"] = ["listing volume increased"]
        report = build_card_report(snapshot, [snapshot])
        self.assertIsInstance(report, CardReport)
        self.assertEqual(report.cs_card_id, "mlb:660271:card:psa10")
        self.assertEqual(report.player_id, "660271")
        self.assertEqual(report.league, "MLB")
        self.assertEqual(report.player_name, "Aaron Judge")
        self.assertEqual(report.card_score, 72.5)
        self.assertEqual(report.recommendation, "BUY")
        self.assertEqual(report.evidence, "MEDIUM")
        self.assertEqual(report.outlook_evidence, ["listing volume increased"])

    def test_no_heuristic_outlook_evidence_without_stored_items(self):
        snapshot = _sample_snapshot()
        report = build_card_report(snapshot, [snapshot])
        for phrase in (
            "improving demand",
            "tight listing supply",
            "positive price momentum",
            "premium listing activity",
        ):
            self.assertNotIn(phrase, [item.lower() for item in report.outlook_evidence])

    def test_no_stored_outlook_evidence_marks_insufficient(self):
        snapshot = _sample_snapshot()
        snapshot["recommendation"] = "BUY"
        report = build_card_report(snapshot, [snapshot])
        self.assertEqual(report.evidence, "INSUFFICIENT")
        self.assertEqual(report.outlook_evidence, [])
        self.assertEqual(
            report.outlook_summary,
            "Supporting evidence is not available in the current snapshot.",
        )

    def test_market_drivers_from_stored_evidence(self):
        snapshot = _sample_snapshot()
        report = build_card_report(snapshot, [snapshot])
        self.assertTrue(len(report.market_drivers) > 0)
        labels = [d.label for d in report.market_drivers]
        self.assertIn("Active Listings", labels)

    def test_scarcity_drivers_from_stored_evidence(self):
        snapshot = _sample_snapshot()
        report = build_card_report(snapshot, [snapshot])
        self.assertTrue(len(report.scarcity_drivers) > 0)

    def test_price_history_foundation(self):
        snapshot = _sample_snapshot()
        report = build_card_report(snapshot, [snapshot])
        self.assertEqual(report.price_history.chart_adapter, "pending")
        self.assertEqual(report.price_history.status, "coming_soon")
        self.assertEqual(len(report.price_history.series), 1)

    def test_signal_drivers_empty_for_card_report(self):
        snapshot = _sample_snapshot()
        report = build_card_report(snapshot, [snapshot])
        self.assertEqual(report.signal_drivers, [])

    def test_extensions_architecture(self):
        snapshot = _sample_snapshot()
        report = build_card_report(snapshot, [snapshot])
        self.assertFalse(report.extensions.comments["enabled"])
        self.assertFalse(report.extensions.price_charts["enabled"])

    def test_card_identity_from_registry(self):
        snapshot = _sample_snapshot()
        snapshot["identity"] = {
            "year": 2023,
            "brand": "Bowman",
            "set": "Chrome",
            "parallel": "Refractor",
            "card_number": "BCP-1",
            "grade": "10",
            "grading_company": "PSA",
        }
        report = build_card_report(snapshot, [snapshot])
        self.assertIsNotNone(report.card_identity)
        self.assertEqual(report.card_identity.brand, "Bowman")
        self.assertEqual(report.card_identity.grade, "10")

    def test_no_fabricated_card_score(self):
        snapshot = _sample_snapshot()
        snapshot["card_signal_score"] = None
        report = build_card_report(snapshot, [snapshot])
        self.assertIsNone(report.card_score)


if __name__ == "__main__":
    unittest.main()
