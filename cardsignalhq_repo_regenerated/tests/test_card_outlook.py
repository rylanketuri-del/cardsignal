"""Tests for centralized Card Outlook builder — stored evidence only."""

from __future__ import annotations

import unittest

from cardchase_ai.card_outlook import (
    HEURISTIC_EVIDENCE_PHRASES,
    NO_EVIDENCE_SUMMARY,
    NO_SUPPORT_SUMMARY,
    build_card_outlook,
)


class CardOutlookHeuristicGuardTests(unittest.TestCase):
    def _outlook_with_high_scores_no_stored_evidence(self):
        return build_card_outlook(
            stored_recommendation="BUY",
            stored_evidence_tier="High",
            evidence_data={
                "listings_count": 3,
                "tags": {"premium_count": 5},
            },
            stored_risk="Low",
            stored_time_horizon="2-4 weeks",
            missing_inputs=[],
            algorithm_version="WEEKLY_INTELLIGENCE_V1",
        )

    def test_score_thresholds_do_not_generate_evidence_text(self):
        outlook = self._outlook_with_high_scores_no_stored_evidence()
        for phrase in HEURISTIC_EVIDENCE_PHRASES:
            self.assertNotIn(
                phrase,
                [item.lower() for item in outlook.supporting_evidence],
                msg=f"Heuristic phrase leaked: {phrase}",
            )

    def test_listing_count_does_not_generate_tight_supply(self):
        outlook = self._outlook_with_high_scores_no_stored_evidence()
        joined = " ".join(outlook.supporting_evidence).lower()
        self.assertNotIn("tight listing supply", joined)
        self.assertNotIn("tight supply", joined)

    def test_demand_score_context_does_not_generate_improving_demand(self):
        outlook = build_card_outlook(
            stored_recommendation="BUY",
            stored_evidence_tier="High",
            evidence_data={"demand_score": 90},
            stored_risk=None,
            stored_time_horizon=None,
            missing_inputs=[],
            algorithm_version="WEEKLY_INTELLIGENCE_V1",
        )
        self.assertNotIn("improving demand", [s.lower() for s in outlook.supporting_evidence])

    def test_momentum_score_does_not_generate_positive_price_momentum(self):
        outlook = build_card_outlook(
            stored_recommendation="BUY",
            stored_evidence_tier="High",
            evidence_data={"momentum_score": 80},
            stored_risk=None,
            stored_time_horizon=None,
            missing_inputs=[],
            algorithm_version="WEEKLY_INTELLIGENCE_V1",
        )
        self.assertNotIn("positive price momentum", [s.lower() for s in outlook.supporting_evidence])

    def test_premium_tags_do_not_generate_premium_listing_activity(self):
        outlook = build_card_outlook(
            stored_recommendation="BUY",
            stored_evidence_tier="High",
            evidence_data={"tags": {"premium_count": 10}},
            stored_risk=None,
            stored_time_horizon=None,
            missing_inputs=[],
            algorithm_version="WEEKLY_INTELLIGENCE_V1",
        )
        self.assertNotIn("premium listing activity", [s.lower() for s in outlook.supporting_evidence])


class CardOutlookStoredEvidenceTests(unittest.TestCase):
    def test_stored_outlook_reasons_rendered(self):
        outlook = build_card_outlook(
            stored_recommendation="BUY",
            stored_evidence_tier="High",
            evidence_data={"outlook_reasons": ["strong player performance", "tight listing supply"]},
            stored_risk="Low",
            stored_time_horizon="2-4 weeks",
            missing_inputs=[],
            algorithm_version="WEEKLY_INTELLIGENCE_V1",
        )
        self.assertEqual(outlook.supporting_evidence, ["strong player performance", "tight listing supply"])
        self.assertEqual(outlook.evidence, "HIGH")

    def test_structured_evidence_items_rendered(self):
        outlook = build_card_outlook(
            stored_recommendation="HOLD",
            stored_evidence_tier="Medium",
            evidence_data={
                "evidence_items": [
                    {
                        "type": "market",
                        "label": "Listing velocity increased week-over-week",
                        "source_reference": "weekly_intelligence:run-1",
                    }
                ]
            },
            stored_risk="Medium",
            stored_time_horizon="2-4 weeks",
            missing_inputs=["population"],
            algorithm_version="WEEKLY_INTELLIGENCE_V1",
        )
        self.assertEqual(outlook.supporting_evidence, ["Listing velocity increased week-over-week"])
        self.assertIn("population", outlook.missing_inputs)

    def test_invalid_structured_evidence_excluded(self):
        outlook = build_card_outlook(
            stored_recommendation="BUY",
            stored_evidence_tier="High",
            evidence_data={
                "evidence_items": [
                    {"type": "unsupported", "label": "should not appear"},
                    {"type": "market", "label": "valid stored signal", "source_reference": "run-1"},
                ]
            },
            stored_risk=None,
            stored_time_horizon=None,
            missing_inputs=[],
            algorithm_version="WEEKLY_INTELLIGENCE_V1",
        )
        self.assertEqual(outlook.supporting_evidence, ["valid stored signal"])


class CardOutlookFallbackTests(unittest.TestCase):
    def test_no_stored_evidence_produces_watch_insufficient(self):
        outlook = build_card_outlook(
            stored_recommendation=None,
            stored_evidence_tier="High",
            evidence_data={},
            stored_risk=None,
            stored_time_horizon=None,
            missing_inputs=["listings"],
            algorithm_version="WEEKLY_INTELLIGENCE_V1",
        )
        self.assertEqual(outlook.recommendation, "WATCH")
        self.assertEqual(outlook.evidence, "INSUFFICIENT")
        self.assertEqual(outlook.summary, NO_EVIDENCE_SUMMARY)
        self.assertEqual(outlook.supporting_evidence, [])

    def test_stored_recommendation_without_evidence_keeps_rec_insufficient(self):
        outlook = build_card_outlook(
            stored_recommendation="BUY",
            stored_evidence_tier="High",
            evidence_data={},
            stored_risk="Low",
            stored_time_horizon="2-4 weeks",
            missing_inputs=[],
            algorithm_version="WEEKLY_INTELLIGENCE_V1",
        )
        self.assertEqual(outlook.recommendation, "BUY")
        self.assertEqual(outlook.evidence, "INSUFFICIENT")
        self.assertEqual(outlook.summary, NO_SUPPORT_SUMMARY)
        self.assertEqual(outlook.supporting_evidence, [])

    def test_algorithm_version_present(self):
        outlook = build_card_outlook(
            stored_recommendation="WATCH",
            stored_evidence_tier=None,
            evidence_data={},
            stored_risk=None,
            stored_time_horizon=None,
            missing_inputs=[],
            algorithm_version="WEEKLY_INTELLIGENCE_V1",
        )
        self.assertEqual(outlook.algorithm_version, "WEEKLY_INTELLIGENCE_V1")


if __name__ == "__main__":
    unittest.main()
