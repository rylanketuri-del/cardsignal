"""Historical PSA population movement helpers — Sprint 8.6."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from cardchase_ai.market.movement import parse_captured_at
from cardchase_ai.models.population import CardPopulationMovement

POPULATION_MOVEMENT_ALGORITHM_VERSION = "psa-population-movement-v1"


def _round_pct(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 2)


def sort_population_snapshots_asc(snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[tuple[datetime, dict[str, Any]]] = []
    for snapshot in snapshots:
        captured = parse_captured_at(snapshot.get("captured_at"))
        if captured is None:
            continue
        rows.append((captured, snapshot))
    rows.sort(key=lambda item: item[0])
    return [row for _, row in rows]


def calculate_population_movement(snapshots: list[dict[str, Any]]) -> CardPopulationMovement | None:
    ordered = sort_population_snapshots_asc(snapshots)
    if len(ordered) < 2:
        return None

    current = ordered[-1]
    previous = ordered[-2]
    current_total = current.get("total_population")
    previous_total = previous.get("total_population")
    current_psa_10 = current.get("psa_10_population")
    previous_psa_10 = previous.get("psa_10_population")

    population_change = None
    population_change_pct = None
    if current_total is not None and previous_total is not None:
        population_change = int(current_total) - int(previous_total)
        if previous_total > 0:
            population_change_pct = _round_pct((population_change / previous_total) * 100)

    psa_10_change = None
    if current_psa_10 is not None and previous_psa_10 is not None:
        psa_10_change = int(current_psa_10) - int(previous_psa_10)

    comparison_captured_at = parse_captured_at(previous.get("captured_at"))
    quality = "INSUFFICIENT"
    if current_total is not None and previous_total is not None:
        if current.get("data_quality") in {"HIGH", "MEDIUM"} and previous.get("data_quality") in {"HIGH", "MEDIUM"}:
            quality = "HIGH"
        elif current_total > 0 and previous_total > 0:
            quality = "MEDIUM"
        else:
            quality = "LOW"

    return CardPopulationMovement(
        cs_card_id=str(current.get("cs_card_id") or ""),
        cs_player_id=str(current.get("cs_player_id") or ""),
        current_population=current_total,
        previous_population=previous_total,
        population_change=population_change,
        population_change_pct=population_change_pct,
        current_psa_10_population=current_psa_10,
        previous_psa_10_population=previous_psa_10,
        psa_10_population_change=psa_10_change,
        comparison_captured_at=comparison_captured_at,
        movement_quality=quality,
        has_movement=True,
    )
