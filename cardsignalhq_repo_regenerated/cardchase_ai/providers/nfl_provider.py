"""NFL performance provider — approved import retrieval and normalization only."""

from __future__ import annotations

from typing import Any

from cardchase_ai.config import Settings, get_settings
from cardchase_ai.providers.nfl_performance import NFLPerformanceProvider


class NFLProvider:
    """Thin wrapper over the NFL import provider. No CardSignal scoring."""

    league = "NFL"

    def __init__(self, inner: NFLPerformanceProvider | None = None, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        if inner is not None:
            self._inner = inner
        else:
            from cardchase_ai.clients.nfl_import import get_nfl_provider as _get_import_provider

            self._inner = _get_import_provider(self._settings)

    @property
    def source_method(self) -> str:
        return getattr(self._inner, "source_method", "UNAVAILABLE")

    @property
    def inner(self) -> NFLPerformanceProvider:
        return self._inner

    def is_available(self) -> bool:
        return bool(self._inner.is_available())

    def search_players(self, query: str, limit: int = 10) -> list[Any]:
        return self._inner.search_players(query, limit=limit)

    def fetch_player_universe(self, limit: int = 100) -> list[Any]:
        return self._inner.fetch_player_universe(limit=limit)

    def fetch_recent_games(self, source_player_id: str, limit: int = 3) -> list[Any]:
        return self._inner.fetch_recent_games(source_player_id, limit=limit)

    def fetch_season_stats(self, source_player_id: str, season: int) -> dict[str, Any] | None:
        return self._inner.fetch_season_stats(source_player_id, season)

    def fetch_player_profile(self, source_player_id: str) -> Any:
        return self._inner.fetch_player_profile(source_player_id)

    def fetch_team_roster(self, team_id: str, season: int) -> list[Any]:
        return self._inner.fetch_team_roster(team_id, season)

    def fetch_league_schedule(self, season: int) -> list[dict[str, Any]]:
        return self._inner.fetch_league_schedule(season)

    def fetch_player_status(self, source_player_id: str) -> dict[str, Any] | None:
        return self._inner.fetch_player_status(source_player_id)


def get_nfl_provider(settings: Settings | None = None) -> NFLProvider:
    return NFLProvider(settings=settings or get_settings())
