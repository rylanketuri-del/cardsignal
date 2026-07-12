"""Centralized league and sport registration."""

from __future__ import annotations

from cardchase_ai.adapters.base import LeagueAdapter, SportAdapter

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
    """Return leagues with search support enabled."""
    return sorted(
        code
        for code, adapter in _LEAGUE_REGISTRY.items()
        if adapter.metadata.search_support
    )


def search_players(query: str, *, league: str | None = None, limit: int = 10) -> list[dict]:
    """Search players across one or all searchable leagues."""
    trimmed = (query or "").strip()
    if len(trimmed) < 2:
        return []

    if league:
        adapter = get_league_adapter(league)
        if not adapter.metadata.search_support:
            return []
        return adapter.search_players(trimmed, limit=limit)

    results: list[dict] = []
    for code in list_searchable_leagues():
        try:
            results.extend(get_league_adapter(code).search_players(trimmed, limit=limit))
        except Exception:
            continue
    return results[:limit]
