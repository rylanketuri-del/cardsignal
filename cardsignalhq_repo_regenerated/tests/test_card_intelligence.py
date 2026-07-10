"""Card Intelligence synthesis tests — Sprint 8.7."""

from __future__ import annotations

from datetime import datetime, timezone

from cardchase_ai.intelligence.constants import CARD_INTELLIGENCE_ALGORITHM_VERSION
from cardchase_ai.intelligence.synthesis import (
    build_player_intelligence_summary,
    meets_minimum_evidence,
    synthesize_card_intelligence,
)
from cardchase_ai.models.schemas import CardMarketMovement


def _base_card() -> dict:
    return {
        "cs_card_id": "CS-MLB-C-test",
        "cs_player_id": "CS-MLB-P-test",
        "league": "MLB",
        "player_name": "Test Player",
        "year": "2023",
        "manufacturer": "Topps",
        "set_name": "Topps Chrome",
        "card_name": "Base Rookie",
        "parallel": "Base",
        "grade": "Raw",
    }


def _market_snapshot(**overrides) -> dict:
    payload = {
        "active_listing_count": 12,
        "auction_count": 4,
        "buy_it_now_count": 8,
        "listings_with_bids": 3,
        "total_bid_count": 9,
        "median_price": 45.0,
        "average_price": 48.0,
        "sample_size": 10,
        "data_quality": "MEDIUM",
        "currency": "USD",
        "captured_at": "2026-07-01T12:00:00+00:00",
    }
    payload.update(overrides)
    return payload


def _movement(window: str = "7d", pct: float = 8.4, quality: str = "MEDIUM") -> CardMarketMovement:
    return CardMarketMovement(
        cs_card_id="CS-MLB-C-test",
        cs_player_id="CS-MLB-P-test",
        current_captured_at=datetime(2026, 7, 8, tzinfo=timezone.utc),
        comparison_captured_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        comparison_window=window,
        current_median_price=48.0,
        previous_median_price=44.28,
        median_price_change=3.72,
        median_price_change_pct=pct,
        sample_size_current=10,
        sample_size_previous=9,
        current_data_quality="MEDIUM",
        previous_data_quality="MEDIUM",
        movement_quality=quality,
        algorithm_version="card-market-movement-v1",
    )


def test_algorithm_version_present():
    result = synthesize_card_intelligence(
        card=_base_card(),
        market_snapshot=_market_snapshot(),
        movement_7d=_movement(),
    )
    assert result.algorithm_version == CARD_INTELLIGENCE_ALGORITHM_VERSION


def test_insufficient_data_fallback():
    result = synthesize_card_intelligence(card=_base_card())
    assert result.card_signal_score is None
    assert result.recommendation == "WATCH"
    assert result.conviction == "INSUFFICIENT"
    assert "minimum_evidence_requirement" in result.missing_inputs


def test_watch_fallback_when_only_market_snapshot():
    result = synthesize_card_intelligence(
        card=_base_card(),
        market_snapshot=_market_snapshot(listings_with_bids=0, total_bid_count=0),
    )
    assert result.card_signal_score is None
    assert result.recommendation == "WATCH"
    assert result.conviction == "INSUFFICIENT"


def test_no_buy_from_active_prices_alone():
    result = synthesize_card_intelligence(
        card=_base_card(),
        market_snapshot=_market_snapshot(
            listings_with_bids=0,
            total_bid_count=0,
            auction_count=0,
            active_listing_count=25,
            median_price=120.0,
            sample_size=20,
            data_quality="HIGH",
        ),
        movement_7d=None,
        movement_30d=None,
        population_snapshot=None,
    )
    assert result.recommendation != "BUY"


def test_no_buy_from_scarcity_alone():
    result = synthesize_card_intelligence(
        card=_base_card(),
        market_snapshot=_market_snapshot(
            listings_with_bids=0,
            total_bid_count=0,
            auction_count=0,
            sample_size=8,
            data_quality="MEDIUM",
        ),
        population_snapshot={
            "cs_card_id": "CS-MLB-C-test",
            "cs_player_id": "CS-MLB-P-test",
            "league": "MLB",
            "source_method": "manual_beta_seed",
            "captured_at": "2026-07-01T00:00:00+00:00",
            "total_population": 120,
            "psa_10_population": 18,
            "psa_9_population": 40,
            "gem_rate": 0.15,
            "data_quality": "HIGH",
            "algorithm_version": "test",
        },
    )
    assert result.recommendation != "BUY"


def test_full_score_when_minimum_evidence_met():
    result = synthesize_card_intelligence(
        card=_base_card(),
        market_snapshot=_market_snapshot(),
        movement_7d=_movement(),
    )
    assert result.card_signal_score is not None
    assert 0 <= result.card_signal_score <= 100
    assert result.recommendation in {"BUY", "HOLD", "SELL", "WATCH"}


def test_score_bounds():
    result = synthesize_card_intelligence(
        card=_base_card(),
        market_snapshot=_market_snapshot(active_listing_count=200, total_bid_count=80),
        movement_7d=_movement(pct=25.0, quality="HIGH"),
        population_snapshot={
            "cs_card_id": "CS-MLB-C-test",
            "cs_player_id": "CS-MLB-P-test",
            "league": "MLB",
            "source_method": "manual_beta_seed",
            "captured_at": "2026-07-01T00:00:00+00:00",
            "total_population": 50,
            "psa_10_population": 8,
            "data_quality": "HIGH",
            "algorithm_version": "test",
        },
    )
    for attr in ("market_activity_score", "demand_score", "momentum_score", "card_signal_score"):
        value = getattr(result, attr)
        if value is not None:
            assert 0 <= value <= 100


def test_evidence_generation():
    result = synthesize_card_intelligence(
        card=_base_card(),
        market_snapshot=_market_snapshot(),
        movement_7d=_movement(),
        population_snapshot={
            "cs_card_id": "CS-MLB-C-test",
            "cs_player_id": "CS-MLB-P-test",
            "league": "MLB",
            "source_method": "manual_beta_seed",
            "captured_at": "2026-07-01T00:00:00+00:00",
            "total_population": 184,
            "psa_10_population": 184,
            "gem_rate": 0.22,
            "data_quality": "HIGH",
            "algorithm_version": "test",
        },
    )
    assert result.evidence
    labels = {item.label for item in result.evidence}
    assert "Bid activity" in labels
    assert "7-day active price movement" in labels
    assert "PSA 10 population" in labels


def test_missing_input_reporting():
    result = synthesize_card_intelligence(
        card=_base_card(),
        market_snapshot=_market_snapshot(),
        movement_7d=_movement(),
    )
    assert "psa_population" in result.missing_inputs


def test_null_handling_in_player_summary():
    cards = [
        synthesize_card_intelligence(card=_base_card()),
        synthesize_card_intelligence(
            card={**_base_card(), "cs_card_id": "CS-MLB-C-test-2"},
            market_snapshot=_market_snapshot(),
            movement_7d=_movement(),
        ),
    ]
    summary = build_player_intelligence_summary(cards)
    assert summary.cards_pending_evidence >= 1
    assert summary.cards_with_sufficient_evidence >= 1
    assert summary.highest_card_signal is not None


def test_deterministic_scoring():
    kwargs = {
        "card": _base_card(),
        "market_snapshot": _market_snapshot(),
        "movement_7d": _movement(),
        "calculated_at": datetime(2026, 7, 10, tzinfo=timezone.utc),
    }
    first = synthesize_card_intelligence(**kwargs)
    second = synthesize_card_intelligence(**kwargs)
    assert first.card_signal_score == second.card_signal_score
    assert first.recommendation == second.recommendation
    assert first.conviction == second.conviction


def test_meets_minimum_evidence_helper():
    assert meets_minimum_evidence(
        card=_base_card(),
        market_snapshot=_market_snapshot(sample_size=1, data_quality="INSUFFICIENT"),
        movement_7d=None,
        movement_30d=None,
        population_snapshot=None,
    ) is False
    assert meets_minimum_evidence(
        card=_base_card(),
        market_snapshot=_market_snapshot(),
        movement_7d=_movement(),
        movement_30d=None,
        population_snapshot=None,
    ) is True


def test_recommendation_thresholds_hold_on_moderate_signal():
    result = synthesize_card_intelligence(
        card=_base_card(),
        market_snapshot=_market_snapshot(
            listings_with_bids=1,
            total_bid_count=2,
            active_listing_count=8,
            sample_size=8,
            data_quality="MEDIUM",
        ),
        movement_7d=_movement(pct=1.5, quality="LOW"),
    )
    if result.card_signal_score is not None and 43 <= result.card_signal_score <= 64:
        assert result.recommendation in {"HOLD", "WATCH"}
