"""Shared provider contracts.

Providers retrieve and normalize data only — they never calculate CardSignal.
"""

from __future__ import annotations

from typing import Any, Protocol


class PerformanceProvider(Protocol):
    """Neutral performance data interface shared by MLB, NFL, and NBA."""

    league: str
    source_method: str

    def is_available(self) -> bool:
        ...

    def search_players(self, query: str, limit: int = 10) -> list[Any]:
        ...

    def fetch_player_universe(self, limit: int = 100) -> list[Any]:
        ...

    def fetch_recent_games(self, source_player_id: str, limit: int) -> list[Any]:
        ...

    def fetch_season_stats(self, source_player_id: str, season: int) -> dict[str, Any] | None:
        ...
