"""Provider-neutral NBA performance interface."""

from __future__ import annotations

from typing import Any, Protocol

from cardchase_ai.models.nba import (
    NBAGameLogRow,
    NBAPlayerIdentity,
    NBAPlayerSearchResult,
    NBASourceMethod,
)


class NBAPerformanceProvider(Protocol):
    """Neutral interface for NBA performance data sources (PerformanceAdapter)."""

    source_method: NBASourceMethod

    def is_available(self) -> bool:
        """Return True when the provider has loadable NBA data."""
        ...

    def search_players(self, query: str, limit: int = 10) -> list[NBAPlayerSearchResult]:
        ...

    def fetch_player_profile(self, source_player_id: str) -> NBAPlayerIdentity | None:
        ...

    def fetch_recent_games(self, source_player_id: str, limit: int) -> list[NBAGameLogRow]:
        ...

    def fetch_season_stats(self, source_player_id: str, season: int) -> dict[str, Any] | None:
        ...

    def fetch_team_roster(self, team_id: str, season: int) -> list[NBAPlayerIdentity]:
        ...

    def fetch_league_schedule(self, season: int) -> list[dict[str, Any]]:
        ...

    def fetch_player_status(self, source_player_id: str) -> dict[str, Any] | None:
        ...

    def fetch_player_universe(self, limit: int = 100) -> list[NBAPlayerIdentity]:
        ...
