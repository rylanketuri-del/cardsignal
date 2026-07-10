"""Population snapshot calculations — Sprint 8.6."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from cardchase_ai.models.population import CardPopulationSnapshot

POPULATION_SNAPSHOT_ALGORITHM_VERSION = "psa-population-snapshot-v1"

PSA_GRADE_KEYS = [str(grade) for grade in range(1, 11)] + ["Auth", "Q"]


def _round_rate(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 4)


def _safe_rate(numerator: int | None, denominator: int | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return _round_rate(numerator / denominator)


def _sum_grade_population(population_by_grade: dict[str, Any]) -> int | None:
    total = 0
    seen = False
    for value in population_by_grade.values():
        if value is None:
            continue
        seen = True
        total += int(value)
    return total if seen else None


def _classify_data_quality(total_population: int | None, population_by_grade: dict[str, Any]) -> str:
    if total_population is None or total_population <= 0:
        return "INSUFFICIENT"
    grade_count = sum(1 for value in population_by_grade.values() if value is not None)
    if total_population >= 500 and grade_count >= 5:
        return "HIGH"
    if total_population >= 100 and grade_count >= 3:
        return "MEDIUM"
    if total_population > 0:
        return "LOW"
    return "INSUFFICIENT"


def normalize_population_by_grade(raw: dict[str, Any] | None) -> dict[str, int | None]:
    normalized: dict[str, int | None] = {key: None for key in PSA_GRADE_KEYS}
    if not raw:
        return normalized

    alias_map = {
        "10": "10",
        "psa10": "10",
        "psa_10": "10",
        "9": "9",
        "psa9": "9",
        "psa_9": "9",
        "8": "8",
        "psa8": "8",
        "psa_8": "8",
        "auth": "Auth",
        "qualifier": "Q",
        "q": "Q",
    }

    for key, value in raw.items():
        if value is None:
            continue
        normalized_key = alias_map.get(str(key).strip().lower(), str(key).strip())
        if normalized_key in normalized:
            normalized[normalized_key] = int(value)
        elif normalized_key.isdigit() and normalized_key in normalized:
            normalized[normalized_key] = int(value)

    return normalized


def build_card_population_snapshot(
    card_identity: dict[str, Any],
    *,
    source_method: str,
    population_by_grade: dict[str, Any] | None = None,
    total_population: int | None = None,
    psa_card_id: str | None = None,
    match_confidence: str = "LOW",
    provider_updated_at: datetime | None = None,
    grade_requested: str | None = None,
    notes: str = "",
    captured_at: datetime | None = None,
) -> CardPopulationSnapshot:
    moment = captured_at or datetime.now(timezone.utc)
    by_grade = normalize_population_by_grade(population_by_grade)

    psa_10 = by_grade.get("10")
    psa_9 = by_grade.get("9")
    psa_8 = by_grade.get("8")

    if total_population is None:
        total_population = _sum_grade_population(by_grade)

    higher_grade = None
    lower_grade = None
    if total_population is not None and psa_10 is not None:
        higher_grade = psa_10
        lower_grade = max(total_population - psa_10, 0) if total_population >= psa_10 else None

    requested_grade_population = None
    if grade_requested:
        key = str(grade_requested).replace("PSA", "").strip()
        requested_grade_population = by_grade.get(key)

    gem_rate = _safe_rate(psa_10, total_population)
    top_grade_rate = gem_rate

    return CardPopulationSnapshot(
        cs_card_id=str(card_identity["cs_card_id"]),
        cs_player_id=str(card_identity["cs_player_id"]),
        league=str(card_identity.get("league") or "MLB"),
        source_method=source_method,
        captured_at=moment,
        psa_card_id=psa_card_id,
        total_population=total_population,
        population_by_grade=by_grade,
        psa_10_population=psa_10,
        psa_9_population=psa_9,
        psa_8_population=psa_8,
        higher_grade_population=higher_grade,
        lower_grade_population=lower_grade,
        grade_requested=grade_requested,
        requested_grade_population=requested_grade_population,
        gem_rate=gem_rate,
        top_grade_rate=top_grade_rate,
        data_quality=_classify_data_quality(total_population, by_grade),
        match_confidence=match_confidence,
        algorithm_version=POPULATION_SNAPSHOT_ALGORITHM_VERSION,
        provider_updated_at=provider_updated_at,
        notes=notes,
    )
