"""Population import validation and loading — Sprint 8.6."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cardchase_ai.card_registry import get_enriched_player_cards
from cardchase_ai.models.population import SOURCE_METHODS

ALLOWED_SOURCE_METHODS = SOURCE_METHODS


class ImportValidationError(ValueError):
    pass


def _known_cs_card_ids() -> set[str]:
    from cardchase_ai.pipeline import _build_market_universe
    from cardchase_ai.clients.mlb import MLBClient
    from cardchase_ai.identity import enrich_player_entry
    from cardchase_ai.config import get_settings

    settings = get_settings()
    mlb_client = MLBClient()
    candidates = _build_market_universe(mlb_client, settings)
    known: set[str] = set()
    for candidate in candidates[: settings.card_market_player_limit]:
        player = enrich_player_entry(candidate)
        for card in get_enriched_player_cards(player):
            card_id = str(card.get("cs_card_id") or "")
            if card_id:
                known.add(card_id)
    return known


def validate_import_row(row: dict[str, Any], *, known_card_ids: set[str] | None = None) -> tuple[dict[str, Any] | None, str | None]:
    cs_card_id = str(row.get("cs_card_id") or "").strip()
    if not cs_card_id:
        return None, "Missing cs_card_id"

    known = known_card_ids if known_card_ids is not None else _known_cs_card_ids()
    if cs_card_id not in known:
        return None, f"Unknown cs_card_id: {cs_card_id}"

    source_method = str(row.get("source_method") or "approved_import").strip()
    if source_method not in ALLOWED_SOURCE_METHODS:
        return None, f"Invalid source_method: {source_method}"

    total_population = row.get("total_population")
    if total_population is not None and int(total_population) < 0:
        return None, "Negative total_population"

    population_by_grade = row.get("population_by_grade") or {}
    if isinstance(population_by_grade, dict):
        for value in population_by_grade.values():
            if value is not None and int(value) < 0:
                return None, "Negative grade population count"

    psa_10 = row.get("psa_10_population")
    psa_9 = row.get("psa_9_population")
    if total_population is not None:
        total = int(total_population)
        grade_sum = 0
        has_grade = False
        if isinstance(population_by_grade, dict):
            for value in population_by_grade.values():
                if value is not None:
                    has_grade = True
                    grade_sum += int(value)
        if psa_10 is not None:
            has_grade = True
            grade_sum = max(grade_sum, int(psa_10))
        if has_grade and grade_sum > total and not row.get("notes"):
            return None, "Grade totals exceed total_population without explanatory notes"

    clean = dict(row)
    clean["cs_card_id"] = cs_card_id
    clean["source_method"] = source_method
    return clean, None


def validate_import_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    known = _known_cs_card_ids()
    accepted: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for index, row in enumerate(rows, start=1):
        clean, error = validate_import_row(row, known_card_ids=known)
        if error:
            errors.append({"row": index, "cs_card_id": row.get("cs_card_id"), "error": error})
            continue
        accepted.append(clean)

    return accepted, errors


def load_import_file(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
        return payload["rows"]
    raise ImportValidationError("Import file must be a JSON array or {\"rows\": [...]} object.")
