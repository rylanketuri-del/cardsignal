"""Read-only player intelligence API — stored data only, no provider refreshes."""

from __future__ import annotations

from typing import Any

from cardchase_ai.identity import cs_player_id, normalize_api_player_id
from cardchase_ai.intelligence_serializer import serialize_player_intelligence
from cardchase_ai.models.weekly import CardWeeklyIntelligenceSnapshot, PlayerWeeklySignalSnapshot
from cardchase_ai.weekly_storage import WeeklyStorage


def resolve_cs_player_id(league: str, player_id: str) -> str:
    league_upper = league.upper()
    if player_id.startswith("CS-NFL-P-") or player_id.startswith("CS-NBA-P-") or ":" in player_id:
        return player_id
    return normalize_api_player_id(player_id, league_upper)


def fetch_latest_player_snapshot(
    storage: WeeklyStorage,
    cs_id: str,
    league: str,
) -> tuple[PlayerWeeklySignalSnapshot | None, list[CardWeeklyIntelligenceSnapshot], bool]:
    """Return latest snapshot, related card snapshots, and whether a prior weekly exists."""
    history = storage.fetch_player_weekly_history(cs_id, limit=12)
    league_history = [h for h in history if str(h.get("league", "")).upper() == league.upper()]
    if not league_history:
        return None, [], False

    latest_raw = league_history[-1]
    snapshot = PlayerWeeklySignalSnapshot.model_validate(latest_raw)
    has_prior = len(league_history) >= 2

    card_snapshots: list[CardWeeklyIntelligenceSnapshot] = []
    payload = storage.fetch_latest_completed_payload(league)
    if payload:
        for raw in payload.get("card_snapshots", []):
            card = CardWeeklyIntelligenceSnapshot.model_validate(raw)
            if card.cs_player_id == cs_id:
                card_snapshots.append(card)

    return snapshot, card_snapshots, has_prior


def fetch_player_intelligence_payload(
    league: str,
    player_id: str,
    storage: WeeklyStorage,
) -> dict[str, Any] | None:
    """Build normalized PlayerIntelligencePayload from stored weekly intelligence."""
    cs_id = resolve_cs_player_id(league, player_id)
    snapshot, cards, has_prior = fetch_latest_player_snapshot(storage, cs_id, league)
    if not snapshot:
        return None

    movements = (snapshot.evidence or {}).get("market_movements")
    has_market_history = bool(movements)

    payload = serialize_player_intelligence(
        snapshot,
        card_snapshots=cards,
        market_movements=movements,
        has_prior_weekly=has_prior,
        has_market_history=has_market_history,
    )
    return payload.model_dump(mode="json")
