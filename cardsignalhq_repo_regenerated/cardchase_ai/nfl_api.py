"""NFL API route helpers."""

from __future__ import annotations

from typing import Any

from cardchase_ai.clients.nfl_import import get_nfl_provider
from cardchase_ai.config import Settings, get_settings
from cardchase_ai.identity import cs_nfl_player_id, normalize_api_player_id
from cardchase_ai.nfl_scouting_mapper import build_nfl_performance_payload, build_nfl_player_detail_payload
from cardchase_ai.nfl_storage import build_nfl_storage
from cardchase_ai.sports.registry import is_league_available


def nfl_availability_payload(settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    available = is_league_available("NFL", settings)
    provider = get_nfl_provider(settings)
    return {
        "available": available,
        "source_method": provider.source_method if available else "UNAVAILABLE",
        "season": settings.nfl_season,
        "player_limit": settings.nfl_player_limit,
    }


def search_nfl_players(query: str, limit: int = 10, settings: Settings | None = None) -> list[dict[str, Any]]:
    settings = settings or get_settings()
    if not is_league_available("NFL", settings):
        return []
    provider = get_nfl_provider(settings)
    results = provider.search_players(query, limit=limit)
    serialized = []
    for result in results:
        payload = result.model_dump()
        payload["player_id"] = result.player_id
        serialized.append(payload)
    return serialized


def fetch_nfl_player(player_id: str, settings: Settings | None = None) -> dict[str, Any] | None:
    settings = settings or get_settings()
    if not is_league_available("NFL", settings):
        return None
    storage = build_nfl_storage(settings)
    cs_id = normalize_api_player_id(player_id, "NFL")
    player = storage.find_player(cs_id)
    if not player:
        return None
    recent = storage.fetch_latest_snapshot_by_period(cs_id, "RECENT_3_GAMES")
    season = storage.fetch_latest_snapshot_by_period(cs_id, "REGULAR_SEASON")
    drivers = storage.fetch_signal_drivers(cs_id)
    payload = build_nfl_player_detail_payload(
        player=player.model_dump(mode="json"),
        recent_snap=recent,
        season_snap=season,
        drivers=drivers,
    )
    payload["data_source"] = "stored"
    payload["player_id"] = player.source_player_id
    return payload


def fetch_nfl_leaderboard(settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    storage = build_nfl_storage(settings)
    if not is_league_available("NFL", settings):
        return {"available": False, "items": [], "data_source": "unavailable"}
    items = storage.fetch_leaderboard()
    weekly_payload = None
    from cardchase_ai.weekly_intelligence import build_latest_weekly_api_payload, build_weekly_storage
    weekly_storage = build_weekly_storage(settings)
    weekly_payload = build_latest_weekly_api_payload("NFL", weekly_storage, settings)
    if weekly_payload.get("todays_leaders"):
        items = weekly_payload["todays_leaders"]
    return {
        "available": True,
        "items": items,
        "data_source": "stored",
        "run": weekly_payload.get("run") if weekly_payload else None,
    }


def fetch_nfl_performance(player_id: str, settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    cs_id = normalize_api_player_id(player_id, "NFL")
    storage = build_nfl_storage(settings)
    recent = storage.fetch_latest_snapshot_by_period(cs_id, "RECENT_3_GAMES")
    season = storage.fetch_latest_snapshot_by_period(cs_id, "REGULAR_SEASON")
    drivers = storage.fetch_signal_drivers(cs_id)
    phase = None
    if recent and recent.stats:
        phase = None
    weekly_items = []
    from cardchase_ai.weekly_intelligence import build_weekly_storage
    weekly_storage = build_weekly_storage(settings)
    weekly_items = weekly_storage.fetch_player_weekly_history(cs_id, 1)
    if weekly_items:
        evidence = weekly_items[0].get("evidence") or {}
        phase = evidence.get("nfl_season_phase")
    return build_nfl_performance_payload(
        cs_player_id=cs_id,
        nfl_season_phase=phase,
        recent_snap=recent,
        season_snap=season,
        drivers=drivers,
    )


def fetch_nfl_signal_drivers(player_id: str, settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    cs_id = normalize_api_player_id(player_id, "NFL")
    storage = build_nfl_storage(settings)
    drivers = storage.fetch_signal_drivers(cs_id)
    phase = "UNKNOWN"
    from cardchase_ai.weekly_intelligence import build_weekly_storage
    weekly_storage = build_weekly_storage(settings)
    weekly_items = weekly_storage.fetch_player_weekly_history(cs_id, 1)
    if weekly_items:
        evidence = weekly_items[0].get("evidence") or {}
        phase = evidence.get("nfl_season_phase") or "UNKNOWN"
    return {
        "cs_player_id": cs_id,
        "nfl_season_phase": phase,
        "drivers": [d.model_dump(mode="json") for d in drivers],
        "count": len(drivers),
    }
