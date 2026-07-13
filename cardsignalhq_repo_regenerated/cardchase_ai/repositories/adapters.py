"""Adapters that hide league-specific physical storage behind read repositories."""

from __future__ import annotations

from typing import Any

from cardchase_ai.identity import normalize_api_player_id, parse_cs_player_id
from cardchase_ai.models.nfl import NFLPerformanceSnapshot, NFLPlayerIdentity, NFLSignalDriver
from cardchase_ai.models.weekly import CardWeeklyIntelligenceSnapshot, PlayerWeeklySignalSnapshot
from cardchase_ai.nfl_storage import NFLStorage
from cardchase_ai.weekly_storage import WeeklyStorage


def _resolve_cs_id(league: str, player_id: str) -> str:
    if player_id.startswith("CS-NFL-P-") or player_id.startswith("CS-NBA-P-") or ":" in player_id:
        return player_id
    return normalize_api_player_id(player_id, league)


class WeeklySnapshotRepositoryAdapter:
    def __init__(self, weekly_storage: WeeklyStorage) -> None:
        self._storage = weekly_storage

    def get_latest_official_run(self, league: str) -> dict[str, Any] | None:
        return self._storage.fetch_latest_completed_payload(league)

    def get_player_weekly_history(self, league: str, player_id: str, limit: int = 12) -> list[dict[str, Any]]:
        cs_id = _resolve_cs_id(league, player_id)
        history = self._storage.fetch_player_weekly_history(cs_id, limit)
        return [item for item in history if str(item.get("league", "")).upper() == league.upper()]

    def get_latest_player_snapshot(self, league: str, player_id: str) -> PlayerWeeklySignalSnapshot | None:
        history = self.get_player_weekly_history(league, player_id, limit=12)
        if not history:
            return None
        return PlayerWeeklySignalSnapshot.model_validate(history[-1])

    def get_card_snapshots_for_player(self, league: str, player_id: str) -> list[CardWeeklyIntelligenceSnapshot]:
        cs_id = _resolve_cs_id(league, player_id)
        payload = self.get_latest_official_run(league)
        if not payload:
            return []
        cards: list[CardWeeklyIntelligenceSnapshot] = []
        for raw in payload.get("card_snapshots", []):
            card = CardWeeklyIntelligenceSnapshot.model_validate(raw)
            if card.cs_player_id == cs_id:
                cards.append(card)
        return cards


class PerformanceSnapshotRepositoryAdapter:
    def __init__(self, nfl_storage: NFLStorage | None = None) -> None:
        self._nfl = nfl_storage

    def get_latest_performance(self, league: str, player_id: str) -> NFLPerformanceSnapshot | dict[str, Any] | None:
        league_upper = league.upper()
        if league_upper != "NFL" or not self._nfl:
            return None
        cs_id = _resolve_cs_id(league, player_id)
        return self._nfl.fetch_latest_snapshot_by_period(cs_id, "RECENT_3_GAMES")

    def get_performance_history(self, league: str, player_id: str, limit: int = 12) -> list[Any]:
        league_upper = league.upper()
        if league_upper != "NFL" or not self._nfl:
            return []
        cs_id = _resolve_cs_id(league, player_id)
        return self._nfl.fetch_latest_snapshots(cs_id)[-limit:]


class SignalDriverRepositoryAdapter:
    def __init__(self, nfl_storage: NFLStorage | None = None) -> None:
        self._nfl = nfl_storage

    def get_current_drivers(self, league: str, player_id: str) -> list[NFLSignalDriver | dict[str, Any]]:
        league_upper = league.upper()
        if league_upper == "NFL" and self._nfl:
            cs_id = _resolve_cs_id(league, player_id)
            return self._nfl.fetch_signal_drivers(cs_id)
        return []

    def get_driver_history(self, league: str, player_id: str, limit: int = 12) -> list[Any]:
        return self.get_current_drivers(league, player_id)[:limit]


class MarketSnapshotRepositoryAdapter:
    def __init__(self, weekly_storage: WeeklyStorage) -> None:
        self._weekly = WeeklySnapshotRepositoryAdapter(weekly_storage)

    def get_latest_player_market(self, league: str, player_id: str) -> dict[str, Any] | None:
        snapshot = self._weekly.get_latest_player_snapshot(league, player_id)
        if not snapshot:
            return None
        evidence = snapshot.evidence or {}
        market = evidence.get("market_snapshots")
        if isinstance(market, dict) and market:
            return market
        return None

    def get_player_market_history(self, league: str, player_id: str, limit: int = 12) -> list[dict[str, Any]]:
        history = self._weekly.get_player_weekly_history(league, player_id, limit)
        results: list[dict[str, Any]] = []
        for item in history:
            evidence = item.get("evidence") or {}
            market = evidence.get("market_snapshots")
            if isinstance(market, dict):
                results.append(market)
        return results


class PlayerRegistryRepositoryAdapter:
    def __init__(self, nfl_storage: NFLStorage | None = None) -> None:
        self._nfl = nfl_storage

    def get_player(self, league: str, player_id: str) -> NFLPlayerIdentity | dict[str, Any] | None:
        if league.upper() == "NFL" and self._nfl:
            return self._nfl.find_player(player_id)
        return None

    def search_players(self, leagues: list[str], query: str, limit: int = 10) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        if "NFL" in [league.upper() for league in leagues] and self._nfl:
            from cardchase_ai.nfl_api import search_nfl_players

            results.extend(search_nfl_players(query, limit=limit))
        return results[:limit]


class RepositoryBundle:
    """Grouped repositories consumed by the normalized intelligence read service."""

    def __init__(
        self,
        weekly: WeeklySnapshotRepositoryAdapter,
        performance: PerformanceSnapshotRepositoryAdapter,
        drivers: SignalDriverRepositoryAdapter,
        market: MarketSnapshotRepositoryAdapter,
        registry: PlayerRegistryRepositoryAdapter,
    ) -> None:
        self.weekly = weekly
        self.performance = performance
        self.drivers = drivers
        self.market = market
        self.registry = registry
