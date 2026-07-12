"""Centralized league and sport registration."""

from __future__ import annotations

from cardchase_ai.adapters.base import LeagueAdapter, SportAdapter
from cardchase_ai.weekly_scoring import cs_player_id

_LEAGUE_REGISTRY: dict[str, LeagueAdapter] = {}
_SPORT_REGISTRY: dict[str, SportAdapter] = {}


def register_league(adapter: LeagueAdapter) -> None:
    """Register a league adapter by league code."""
    code = adapter.league_code.upper()
    _LEAGUE_REGISTRY[code] = adapter


def register_sport(adapter: SportAdapter) -> None:
    """Register a sport adapter by sport code."""
    code = adapter.sport_code.upper()
    _SPORT_REGISTRY[code] = adapter


def get_league_adapter(league: str) -> LeagueAdapter:
    """Return the registered adapter for a league code."""
    code = league.upper()
    adapter = _LEAGUE_REGISTRY.get(code)
    if adapter is None:
        supported = ", ".join(sorted(_LEAGUE_REGISTRY)) or "none"
        raise KeyError(f"League '{code}' is not registered. Supported: {supported}")
    return adapter


def get_sport_adapter(sport: str) -> SportAdapter:
    """Return the registered adapter for a sport code."""
    code = sport.upper()
    adapter = _SPORT_REGISTRY.get(code)
    if adapter is None:
        supported = ", ".join(sorted(_SPORT_REGISTRY)) or "none"
        raise KeyError(f"Sport '{code}' is not registered. Supported: {supported}")
    return adapter


def list_registered_leagues() -> list[str]:
    """Return all registered league codes."""
    return sorted(_LEAGUE_REGISTRY.keys())


def list_searchable_leagues() -> list[str]:
    """Return leagues with search enabled and live status."""
    return sorted(
        code
        for code, adapter in _LEAGUE_REGISTRY.items()
        if adapter.metadata.search_enabled and adapter.metadata.live_status == "live"
    )


def league_api_payload(adapter: LeagueAdapter) -> dict:
    """Serialize league metadata for API consumers."""
    meta = adapter.metadata
    return {
        "league": meta.league,
        "sport": meta.sport,
        "display_name": meta.display_name,
        "search_enabled": meta.search_enabled,
        "live_status": meta.live_status,
        "card_support": meta.card_support,
        "recent_window": {
            "kind": meta.recent_window.kind,
            "value": meta.recent_window.value,
        },
        "supported_positions": list(meta.supported_positions),
        "scoring_algorithm_version": meta.scoring_algorithm_version,
    }


def normalize_search_result(raw: dict, adapter: LeagueAdapter) -> dict:
    """Normalize adapter search output to the universal search contract."""
    league = adapter.league_code
    source_id = str(raw.get("player_id") or raw.get("source_player_id") or "")
    return {
        "player_id": raw.get("player_id"),
        "source_player_id": source_id,
        "cs_player_id": raw.get("cs_player_id") or cs_player_id(source_id, league),
        "player_name": raw.get("player_name"),
        "league": league,
        "sport": adapter.metadata.sport,
        "team": raw.get("team"),
        "position": raw.get("position"),
        "headshot_url": raw.get("headshot_url"),
        "team_logo_url": raw.get("team_logo_url"),
        "team_id": raw.get("team_id"),
    }


def search_players(query: str, *, league: str | None = None, limit: int = 10) -> list[dict]:
    """Search players across one or all live, search-enabled registered leagues."""
    trimmed = (query or "").strip()
    if len(trimmed) < 2:
        return []

    if league:
        adapter = get_league_adapter(league)
        if not adapter.metadata.search_enabled:
            return []
        if adapter.metadata.live_status != "live":
            return []
        return [
            normalize_search_result(item, adapter)
            for item in adapter.search_players(trimmed, limit=limit)
        ]

    results: list[dict] = []
    for code in list_searchable_leagues():
        try:
            adapter = get_league_adapter(code)
            results.extend(
                normalize_search_result(item, adapter)
                for item in adapter.search_players(trimmed, limit=limit)
            )
        except Exception:
            continue
    return results[:limit]
