"""Tests for centralized card intelligence synthesis."""

from __future__ import annotations

import unittest

from cardchase_ai.card_intelligence import (
    CARD_INTELLIGENCE_V1,
    build_card_intelligence,
    card_intelligence_from_snapshot,
)
from cardchase_ai.card_registry import card_report_path, get_card_identity, has_registry_identity
from cardchase_ai.models.schemas import ListingTagSummary, MarketSnapshot


def _snapshot(
    *,
    listings_count: int = 20,
    premium: int = 8,
    auto: int = 2,
    psa10: int = 3,
    rookie: int = 1,
    avg_price: float = 45.0,
) -> MarketSnapshot:
    return MarketSnapshot(
        query_name="broad",
        listings_count=listings_count,
        avg_price=avg_price,
        tags=ListingTagSummary(
            premium_count=premium,
            auto_count=auto,
            psa10_count=psa10,
            rookie_count=rookie,
        ),
    )


class CardIntelligenceTests(unittest.TestCase):
    def test_empty_listings_returns_watch_and_insufficient(self):
        snapshot = MarketSnapshot(query_name="broad", listings_count=0)
        result = build_card_intelligence(
            query_name="broad",
            snapshot=snapshot,
            card_label="Base Cards",
            player_name="Juan Soto",
        )
        self.assertIsNone(result["card_signal_score"])
        self.assertEqual(result["recommendation"], "WATCH")
        self.assertEqual(result["evidence"]["evidence_tier"], "INSUFFICIENT")
        self.assertEqual(result["evidence"]["factors"], [])

    def test_score_uses_available_components_only(self):
        result = build_card_intelligence(
            query_name="broad",
            snapshot=_snapshot(),
            card_label="Base Cards",
            player_name="Juan Soto",
            player_performance_score=88.0,
            player_momentum_score=72.0,
            price_change_pct=6.5,
            listings_change=-4,
        )
        self.assertIsNotNone(result["card_signal_score"])
        components = result["evidence"]["components"]
        self.assertIsNotNone(components["player_performance"])
        self.assertIsNotNone(components["collector_demand"])
        self.assertIsNone(components["population"])
        self.assertIn(result["evidence"]["evidence_tier"], {"HIGH", "MEDIUM", "LOW"})

    def test_recommendation_from_intelligence_not_score_only(self):
        strong = build_card_intelligence(
            query_name="broad",
            snapshot=_snapshot(listings_count=8, premium=6),
            player_performance_score=85.0,
            player_momentum_score=78.0,
            price_change_pct=8.0,
            listings_change=-5,
        )
        self.assertIn(strong["recommendation"], {"BUY", "HOLD", "WATCH"})
        self.assertNotEqual(strong["evidence"]["evidence_tier"], "INSUFFICIENT")

        weak = build_card_intelligence(
            query_name="broad",
            snapshot=_snapshot(listings_count=45, premium=1, avg_price=12.0),
            player_performance_score=35.0,
            price_change_pct=-8.0,
            listings_change=8,
        )
        self.assertIn(weak["recommendation"], {"SELL", "HOLD", "WATCH"})

    def test_explanation_uses_supported_or_limited_pattern(self):
        result = build_card_intelligence(
            query_name="auto",
            snapshot=_snapshot(auto=6, premium=10),
            card_label="Autographs",
            player_performance_score=82.0,
            price_change_pct=4.0,
            listings_change=-3,
        )
        explanation = result["evidence"]["explanation"]
        self.assertTrue(
            explanation.startswith("Supported by") or explanation.startswith("Limited by"),
            msg=explanation,
        )

    def test_factor_chips_only_from_stored_data(self):
        result = build_card_intelligence(
            query_name="bowman_chrome",
            snapshot=_snapshot(rookie=2, auto=1),
            player_performance_score=80.0,
        )
        factors = result["evidence"]["factors"]
        labels = {f["label"] for f in factors}
        self.assertIn("Rookie", labels)
        for factor in factors:
            self.assertIn("emoji", factor)
            self.assertIn("label", factor)

    def test_card_intelligence_version_stored(self):
        result = card_intelligence_from_snapshot("broad", _snapshot(), "Juan Soto")
        self.assertEqual(result["evidence"]["card_intelligence_version"], CARD_INTELLIGENCE_V1)

    def test_median_price_computed_from_listings(self):
        from cardchase_ai.models.schemas import ListingSummary

        snapshot = MarketSnapshot(
            query_name="broad",
            listings_count=3,
            avg_price=30.0,
            listings=[
                ListingSummary(item_id="1", title="Card A", price=20.0),
                ListingSummary(item_id="2", title="Card B", price=30.0),
                ListingSummary(item_id="3", title="Card C", price=40.0),
            ],
        )
        result = build_card_intelligence(query_name="broad", snapshot=snapshot)
        self.assertEqual(result["evidence"]["median_price"], 30.0)


class CardRegistryTests(unittest.TestCase):
    def test_registry_identity_detection(self):
        identity = get_card_identity(
            card_label="PSA 10",
            registry={"year": 2025, "brand": "Topps", "set": "Chrome Sapphire", "card_number": "184", "grade": "10", "grading_company": "PSA"},
        )
        self.assertTrue(has_registry_identity(identity))

    def test_card_report_path(self):
        self.assertEqual(card_report_path("mlb:682829:card:psa10"), "/cards/mlb:682829:card:psa10")


if __name__ == "__main__":
    unittest.main()
