"""NBA API route helpers."""

from __future__ import annotations

from typing import Any

from cardchase_ai.clients.nba_import import get_nba_provider
from cardchase_ai.config import Settings, get_settings
from cardchase_ai.identity import normalize_api_player_id
from cardchase_ai.nba_scouting_mapper import build_nba_performance_payload, build_nba_player_detail_payload
from cardchase_ai.nba_storage import build_nba_storage
from cardchase_ai.sports.registry import is_league_available


def nba_availability_payload(settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    available = is_league_available("NBA", settings)
    provider = get_nba_provider(settings)
    return {
        "available": available,
        "source_method": provider.source_method if available else "UNAVAILABLE",
        "season": settings.nba_season,
        "player_limit": settings.nba_player_limit,
    }


def search_nba_players(query: str, limit: int = 10, settings: Settings | None = None) -> list[dict[str, Any]]:
    settings = settings or get_settings()
    if not is_league_available("NBA", settings):
        return []
    provider = get_nba_provider(settings)
    results = provider.search_players(query, limit=limit)
    serialized = []
    for result in results:
        payload = result.model_dump()
        payload["player_id"] = result.player_id
        serialized.append(payload)
    return serialized


def fetch_nba_player(player_id: str, settings: Settings | None = None) -> dict[str, Any] | None:
    settings = settings or get_settings()
    if not is_league_available("NBA", settings):
        return None
    storage = build_nba_storage(settings)
    cs_id = normalize_api_player_id(player_id, "NBA")
    player = storage.find_player(cs_id)
    if not player:
        return None
    recent = storage.fetch_latest_snapshot_by_period(cs_id, "RECENT_5_GAMES")
    season = storage.fetch_latest_snapshot_by_period(cs_id, "REGULAR_SEASON")
    drivers = storage.fetch_signal_drivers(cs_id)
    payload = build_nba_player_detail_payload(
        player=player.model_dump(mode="json"),
        recent_snap=recent,
        season_snap=season,
        drivers=drivers,
    )
    payload["data_source"] = "stored"
    payload["player_id"] = player.source_player_id
    return payload


def fetch_nba_leaderboard(settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    storage = build_nba_storage(settings)
    if not is_league_available("NBA", settings):
        return {"available": False, "items": [], "data_source": "unavailable"}
    items = storage.fetch_leaderboard()
    weekly_payload = None
    from cardchase_ai.weekly_intelligence import build_latest_weekly_api_payload, build_weekly_storage
    weekly_storage = build_weekly_storage(settings)
    weekly_payload = build_latest_weekly_api_payload("NBA", weekly_storage, settings)
    if weekly_payload.get("todays_leaders"):
        items = weekly_payload["todays_leaders"]
    return {
        "available": True,
        "items": items,
        "data_source": "stored",
        "run": weekly_payload.get("run") if weekly_payload else None,
    }


def fetch_nba_performance(player_id: str, settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    cs_id = normalize_api_player_id(player_id, "NBA")
    storage = build_nba_storage(settings)
    recent = storage.fetch_latest_snapshot_by_period(cs_id, "RECENT_5_GAMES")
    season = storage.fetch_latest_snapshot_by_period(cs_id, "REGULAR_SEASON")
    drivers = storage.fetch_signal_drivers(cs_id)
    phase = None
    from cardchase_ai.weekly_intelligence import build_weekly_storage
    weekly_storage = build_weekly_storage(settings)
    weekly_items = weekly_storage.fetch_player_weekly_history(cs_id, 1)
    if weekly_items:
        evidence = weekly_items[0].get("evidence") or {}
        phase = evidence.get("nba_season_phase")
    return build_nba_performance_payload(
        cs_player_id=cs_id,
        nba_season_phase=phase,
        recent_snap=recent,
        season_snap=season,
        drivers=drivers,
    )


def fetch_nba_signal_drivers(player_id: str, settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    cs_id = normalize_api_player_id(player_id, "NBA")
    storage = build_nba_storage(settings)
    drivers = storage.fetch_signal_drivers(cs_id)
    phase = "UNKNOWN"
    from cardchase_ai.weekly_intelligence import build_weekly_storage
    weekly_storage = build_weekly_storage(settings)
    weekly_items = weekly_storage.fetch_player_weekly_history(cs_id, 1)
    if weekly_items:
        evidence = weekly_items[0].get("evidence") or {}
        phase = evidence.get("nba_season_phase") or "UNKNOWN"
    return {
        "cs_player_id": cs_id,
        "nba_season_phase": phase,
        "drivers": [d.model_dump(mode="json") for d in drivers],
        "count": len(drivers),
    }
