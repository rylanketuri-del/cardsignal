"""Card Intelligence public API helpers — Sprint 8.7."""

from __future__ import annotations

import time
from typing import Any

from cardchase_ai.intelligence.constants import CARD_INTELLIGENCE_ALGORITHM_VERSION, DISCLAIMER
from cardchase_ai.intelligence.synthesis import build_player_intelligence_summary, synthesize_card_intelligence
from cardchase_ai.market.movement import calculate_card_market_movement, movement_to_public_dict, sort_snapshots_asc
from cardchase_ai.market.player_market import format_public_market_snapshot
from cardchase_ai.models.intelligence import CardIntelligence

_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_CACHE_TTL_SECONDS = 60


def _cache_get(key: str) -> dict[str, Any] | None:
    entry = _CACHE.get(key)
    if not entry:
        return None
    expires_at, payload = entry
    if time.time() > expires_at:
        _CACHE.pop(key, None)
        return None
    return payload


def _cache_set(key: str, payload: dict[str, Any]) -> None:
    _CACHE[key] = (time.time() + _CACHE_TTL_SECONDS, payload)


def card_intelligence_to_public_dict(card: CardIntelligence) -> dict[str, Any]:
    payload = card.model_dump(mode="json")
    payload["has_full_score"] = card.card_signal_score is not None
    return payload


def build_player_card_intelligence_response(
    *,
    player: dict[str, Any],
    registry_cards: list[dict[str, Any]],
    market_snapshots_by_card: dict[str, dict[str, Any]],
    market_history_by_card: dict[str, list[dict[str, Any]]],
    population_snapshots_by_card: dict[str, dict[str, Any]],
    population_history_by_card: dict[str, list[dict[str, Any]]],
    psa_matches_by_card: dict[str, dict[str, Any]],
    movement_config: Any,
    data_source: str | None = None,
    use_cache: bool = True,
) -> dict[str, Any]:
    player_id = player.get("player_id")
    cs_player_id = player.get("cs_player_id")
    cache_key = f"{cs_player_id}:{len(registry_cards)}"
    if use_cache:
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

    synthesized: list[CardIntelligence] = []
    for card in registry_cards:
        card_id = str(card.get("cs_card_id") or "")
        market_snapshot_raw = market_snapshots_by_card.get(card_id)
        market_snapshot = format_public_market_snapshot(market_snapshot_raw) if market_snapshot_raw else None

        card_history = sort_snapshots_asc(market_history_by_card.get(card_id, []))
        movement_7d = calculate_card_market_movement(card_history, window="7d", config=movement_config)
        movement_30d = calculate_card_market_movement(card_history, window="30d", config=movement_config)

        population_snapshot = population_snapshots_by_card.get(card_id)
        population_history = population_history_by_card.get(card_id, [])
        psa_match = psa_matches_by_card.get(card_id)

        synthesized.append(
            synthesize_card_intelligence(
                card=card,
                market_snapshot=market_snapshot,
                movement_7d=movement_7d,
                movement_30d=movement_30d,
                population_snapshot=population_snapshot,
                population_history=population_history,
                psa_match=psa_match,
            )
        )

    summary = build_player_intelligence_summary(synthesized)
    response = {
        "player_id": player_id,
        "cs_player_id": cs_player_id,
        "algorithm_version": CARD_INTELLIGENCE_ALGORITHM_VERSION,
        "cards": [card_intelligence_to_public_dict(card) for card in synthesized],
        "summary": summary.model_dump(mode="json"),
        "disclaimer": DISCLAIMER,
        "data_source": data_source,
    }

    if use_cache:
        _cache_set(cache_key, response)
    return response
