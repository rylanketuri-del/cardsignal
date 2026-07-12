"""Shared Sport Adapter Framework contracts.

League-specific adapters (MLB, NFL, NBA) implement these protocols without
modifying shared framework contracts. MLB retains its existing client path;
NFL and NBA implement PerformanceAdapter via import providers.
"""

from __future__ import annotations

from typing import Any, Protocol


class SportAdapter(Protocol):
    """Sport-level metadata and availability."""

    sport: str

    def is_available(self) -> bool:
        ...


class LeagueAdapter(Protocol):
    """League identity, search, and universe access."""

    league: str
    sport: str

    def is_available(self) -> bool:
        ...

    def search_players(self, query: str, limit: int = 10) -> list[Any]:
        ...

    def fetch_player_universe(self, limit: int = 100) -> list[Any]:
        ...


class PerformanceAdapter(Protocol):
    """Provider-neutral performance data interface."""

    source_method: str

    def is_available(self) -> bool:
        ...

    def fetch_recent_games(self, source_player_id: str, limit: int) -> list[Any]:
        ...

    def fetch_season_stats(self, source_player_id: str, season: int) -> dict[str, Any] | None:
        ...


class SeasonAdapter(Protocol):
    """League season phase and presentation rules."""

    def season_phase(self, **kwargs: Any) -> str:
        ...

    def recent_window_label(self, phase: str) -> str:
        ...


class SignalDriverAdapter(Protocol):
    """Evidence-backed signal driver generation."""

    def generate_drivers(self, **kwargs: Any) -> list[Any]:
        ...
