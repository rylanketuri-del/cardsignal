"""Provider-neutral NFL performance interface."""

from __future__ import annotations

from typing import Any, Protocol

from cardchase_ai.models.nfl import (
    NFLGameLogRow,
    NFLPlayerIdentity,
    NFLPlayerSearchResult,
    NFLSourceMethod,
)


class NFLPerformanceProvider(Protocol):
    """Neutral interface for NFL performance data sources."""

    source_method: NFLSourceMethod

    def is_available(self) -> bool:
        """Return True when the provider has loadable NFL data."""
        ...

    def search_players(self, query: str, limit: int = 10) -> list[NFLPlayerSearchResult]:
        ...

    def fetch_player_profile(self, source_player_id: str) -> NFLPlayerIdentity | None:
        ...

    def fetch_recent_games(self, source_player_id: str, limit: int = 3) -> list[NFLGameLogRow]:
        ...

    def fetch_season_stats(self, source_player_id: str, season: int) -> dict[str, Any] | None:
        ...

    def fetch_team_roster(self, team_id: str, season: int) -> list[NFLPlayerIdentity]:
        ...

    def fetch_league_schedule(self, season: int) -> list[dict[str, Any]]:
        ...

    def fetch_player_status(self, source_player_id: str) -> dict[str, Any] | None:
        ...

    def fetch_player_universe(self, limit: int = 100) -> list[NFLPlayerIdentity]:
        ...
