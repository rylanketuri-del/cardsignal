"""Public population API helpers — Sprint 8.6."""

from __future__ import annotations

from typing import Any

from cardchase_ai.card_registry import get_enriched_player_cards
from cardchase_ai.models.population import CardPopulationSnapshot, CardScarcityMetrics, PSACardMatch
from cardchase_ai.population.movement import calculate_population_movement
from cardchase_ai.population.scarcity import calculate_card_scarcity_metrics


def normalize_population_snapshot_row(row: dict[str, Any]) -> dict[str, Any]:
    metrics = row.get("metrics") or {}
    if metrics.get("total_population") is None and row.get("total_population") is not None:
        metrics = row

    payload = {
        "cs_card_id": row["cs_card_id"],
        "cs_player_id": row["cs_player_id"],
        "provider": row.get("provider", "PSA"),
        "source_method": row.get("source_method", "manual_beta_seed"),
        "captured_at": row.get("captured_at") or row.get("created_at"),
        "psa_card_id": row.get("psa_card_id") or metrics.get("psa_card_id"),
        "algorithm_version": row.get("algorithm_version", ""),
        "match_confidence": row.get("match_confidence", metrics.get("match_confidence", "LOW")),
        "data_quality": row.get("data_quality", metrics.get("data_quality", "INSUFFICIENT")),
        **metrics,
    }
    return payload


def normalize_psa_match_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    payload = row.get("match_payload") if isinstance(row.get("match_payload"), dict) else row
    return {
        "cs_card_id": row.get("cs_card_id") or payload.get("cs_card_id"),
        "cs_player_id": row.get("cs_player_id") or payload.get("cs_player_id"),
        "provider": row.get("provider") or payload.get("provider") or "PSA",
        "psa_card_id": row.get("psa_card_id") or payload.get("psa_card_id"),
        "match_status": row.get("match_status") or payload.get("match_status") or "UNMATCHED",
        "match_confidence": row.get("match_confidence") or payload.get("match_confidence") or "LOW",
        "source_method": row.get("source_method") or payload.get("source_method") or "manual_beta_seed",
        "matched_at": row.get("matched_at") or payload.get("matched_at"),
        "notes": row.get("notes") or payload.get("notes") or "",
    }


def source_method_label(source_method: str) -> str:
    mapping = {
        "official_api": "Live PSA data",
        "approved_import": "Imported PSA snapshot",
        "manual_beta_seed": "Beta seed data",
    }
    return mapping.get(str(source_method or "").strip(), "PSA population pending")


def build_card_population_latest_response(
    *,
    card_identity: dict[str, Any],
    snapshot: dict[str, Any] | None,
    match: dict[str, Any] | None,
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    scarcity_payload = None
    movement_payload = None

    if snapshot:
        try:
            snapshot_model = CardPopulationSnapshot.model_validate(snapshot)
            scarcity = calculate_card_scarcity_metrics(snapshot_model, prior_snapshots=history)
            scarcity_payload = scarcity.model_dump(mode="json")
        except Exception:
            scarcity_payload = snapshot.get("scarcity")

        if history and len(history) >= 2:
            movement = calculate_population_movement([*history, snapshot])
            if movement:
                movement_payload = movement.model_dump(mode="json")

    return {
        "card": {
            "cs_card_id": card_identity.get("cs_card_id"),
            "cs_player_id": card_identity.get("cs_player_id"),
            "year": card_identity.get("year"),
            "manufacturer": card_identity.get("manufacturer"),
            "set_name": card_identity.get("set_name"),
            "card_name": card_identity.get("card_name"),
            "parallel": card_identity.get("parallel"),
            "player_name": card_identity.get("player_name"),
        },
        "psa_match": normalize_psa_match_row(match),
        "population_snapshot": snapshot,
        "scarcity": scarcity_payload,
        "population_movement": movement_payload,
        "source_method": snapshot.get("source_method") if snapshot else None,
        "source_method_label": source_method_label(snapshot.get("source_method") if snapshot else ""),
        "captured_at": snapshot.get("captured_at") if snapshot else None,
        "data_quality": snapshot.get("data_quality") if snapshot else None,
    }


def find_registry_card(cards: list[dict[str, Any]], cs_card_id: str) -> dict[str, Any] | None:
    for card in cards:
        if str(card.get("cs_card_id")) == str(cs_card_id):
            return card
    return None
