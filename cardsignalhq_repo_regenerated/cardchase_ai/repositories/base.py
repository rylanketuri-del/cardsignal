"""Generalized read interfaces for league intelligence storage."""

from __future__ import annotations

from typing import Any, Protocol

from cardchase_ai.models.nfl import NFLPerformanceSnapshot, NFLPlayerIdentity, NFLSignalDriver
from cardchase_ai.models.weekly import CardWeeklyIntelligenceSnapshot, PlayerWeeklySignalSnapshot


class WeeklySnapshotRepository(Protocol):
    def get_latest_official_run(self, league: str) -> dict[str, Any] | None:
        ...

    def get_player_weekly_history(self, league: str, player_id: str, limit: int = 12) -> list[dict[str, Any]]:
        ...

    def get_latest_player_snapshot(self, league: str, player_id: str) -> PlayerWeeklySignalSnapshot | None:
        ...

    def get_card_snapshots_for_player(self, league: str, player_id: str) -> list[CardWeeklyIntelligenceSnapshot]:
        ...


class PerformanceSnapshotRepository(Protocol):
    def get_latest_performance(self, league: str, player_id: str) -> NFLPerformanceSnapshot | dict[str, Any] | None:
        ...

    def get_performance_history(self, league: str, player_id: str, limit: int = 12) -> list[Any]:
        ...


class SignalDriverRepository(Protocol):
    def get_current_drivers(self, league: str, player_id: str) -> list[NFLSignalDriver | dict[str, Any]]:
        ...

    def get_driver_history(self, league: str, player_id: str, limit: int = 12) -> list[Any]:
        ...


class MarketSnapshotRepository(Protocol):
    def get_latest_player_market(self, league: str, player_id: str) -> dict[str, Any] | None:
        ...

    def get_player_market_history(self, league: str, player_id: str, limit: int = 12) -> list[dict[str, Any]]:
        ...


class PlayerRegistryRepository(Protocol):
    def get_player(self, league: str, player_id: str) -> NFLPlayerIdentity | dict[str, Any] | None:
        ...

    def search_players(self, leagues: list[str], query: str, limit: int = 10) -> list[dict[str, Any]]:
        ...
