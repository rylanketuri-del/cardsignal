"""Population calculation tests — Sprint 8.6."""

from __future__ import annotations

from datetime import datetime, timezone

from cardchase_ai.models.population import CardPopulationSnapshot
from cardchase_ai.population.movement import calculate_population_movement
from cardchase_ai.population.scarcity import calculate_card_scarcity_metrics
from cardchase_ai.population.snapshot import build_card_population_snapshot


def test_build_snapshot_gem_rate_safe():
    card = {
        "cs_card_id": "CS-MLB-C-test",
        "cs_player_id": "CS-MLB-P-test",
        "league": "MLB",
    }
    snapshot = build_card_population_snapshot(
        card,
        source_method="manual_beta_seed",
        total_population=100,
        population_by_grade={"10": 25, "9": 40},
    )
    assert snapshot.gem_rate == 0.25
    assert snapshot.psa_10_population == 25


def test_build_snapshot_zero_total_no_divide_by_zero():
    card = {
        "cs_card_id": "CS-MLB-C-test",
        "cs_player_id": "CS-MLB-P-test",
        "league": "MLB",
    }
    snapshot = build_card_population_snapshot(
        card,
        source_method="manual_beta_seed",
        total_population=0,
        population_by_grade={"10": 0},
    )
    assert snapshot.gem_rate is None


def test_scarcity_uses_available_inputs_only():
    snapshot = CardPopulationSnapshot(
        cs_card_id="CS-MLB-C-test",
        cs_player_id="CS-MLB-P-test",
        league="MLB",
        source_method="manual_beta_seed",
        captured_at=datetime.now(timezone.utc),
        total_population=500,
        psa_10_population=50,
        data_quality="MEDIUM",
        algorithm_version="test",
    )
    metrics = calculate_card_scarcity_metrics(snapshot)
    assert metrics.label == "PSA Population Scarcity"
    assert "total_population" in metrics.inputs_available
    assert "psa_10_population" in metrics.inputs_available
    assert metrics.listing_scarcity_score is None


def test_population_movement_requires_history():
    rows = [
        {
            "cs_card_id": "CS-MLB-C-test",
            "cs_player_id": "CS-MLB-P-test",
            "captured_at": "2026-01-01T00:00:00+00:00",
            "total_population": 100,
            "psa_10_population": 20,
            "data_quality": "MEDIUM",
        },
        {
            "cs_card_id": "CS-MLB-C-test",
            "cs_player_id": "CS-MLB-P-test",
            "captured_at": "2026-02-01T00:00:00+00:00",
            "total_population": 120,
            "psa_10_population": 24,
            "data_quality": "MEDIUM",
        },
    ]
    movement = calculate_population_movement(rows)
    assert movement is not None
    assert movement.has_movement is True
    assert movement.population_change == 20
