"""Population scarcity calculations — Sprint 8.6."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from cardchase_ai.models.population import CardPopulationMovement, CardPopulationSnapshot, CardScarcityMetrics
from cardchase_ai.population.movement import calculate_population_movement

SCARCITY_ALGORITHM_VERSION = "psa-population-scarcity-v1"


def _inverse_population_score(population: int | None, *, scale: int = 10000) -> float | None:
    if population is None or population < 0:
        return None
    if population == 0:
        return 100.0
    score = 100.0 * (1.0 - min(population / scale, 1.0))
    return round(max(0.0, min(100.0, score)), 2)


def _growth_scarcity_adjustment(movement: CardPopulationMovement | None) -> float | None:
    if movement is None or not movement.has_movement:
        return None
    change_pct = movement.population_change_pct
    if change_pct is None:
        return None
    if change_pct >= 25:
        return 20.0
    if change_pct >= 10:
        return 35.0
    if change_pct <= -10:
        return 80.0
    return 50.0


def calculate_card_scarcity_metrics(
    snapshot: CardPopulationSnapshot,
    *,
    prior_snapshots: list[dict[str, Any]] | None = None,
    active_listing_count: int | None = None,
) -> CardScarcityMetrics:
    now = datetime.now(timezone.utc)
    inputs: list[str] = []

    population_score = _inverse_population_score(snapshot.total_population)
    if population_score is not None:
        inputs.append("total_population")

    grade_scarcity_score = _inverse_population_score(snapshot.psa_10_population, scale=5000)
    if grade_scarcity_score is not None:
        inputs.append("psa_10_population")

    listing_scarcity_score = None
    if active_listing_count is not None:
        listing_scarcity_score = _inverse_population_score(active_listing_count, scale=50)
        inputs.append("active_listings")

    movement = None
    if prior_snapshots:
        movement = calculate_population_movement([*prior_snapshots, snapshot.model_dump(mode="json")])

    population_growth_score = _growth_scarcity_adjustment(movement)
    if population_growth_score is not None:
        inputs.append("population_growth")

    weighted_scores: list[tuple[float, float]] = []
    if population_score is not None:
        weighted_scores.append((population_score, 0.35))
    if grade_scarcity_score is not None:
        weighted_scores.append((grade_scarcity_score, 0.35))
    if listing_scarcity_score is not None:
        weighted_scores.append((listing_scarcity_score, 0.15))
    if population_growth_score is not None:
        weighted_scores.append((population_growth_score, 0.15))

    overall = None
    if weighted_scores:
        total_weight = sum(weight for _, weight in weighted_scores)
        overall = round(sum(score * weight for score, weight in weighted_scores) / total_weight, 2)

    if len(inputs) >= 2 and snapshot.data_quality in {"HIGH", "MEDIUM"}:
        confidence = "HIGH"
    elif inputs:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    return CardScarcityMetrics(
        cs_card_id=snapshot.cs_card_id,
        cs_player_id=snapshot.cs_player_id,
        population_score=population_score,
        grade_scarcity_score=grade_scarcity_score,
        listing_scarcity_score=listing_scarcity_score,
        population_growth_score=population_growth_score,
        overall_scarcity_score=overall,
        confidence=confidence,
        inputs_available=inputs,
        algorithm_version=SCARCITY_ALGORITHM_VERSION,
        calculated_at=now,
        label="PSA Population Scarcity",
    )
