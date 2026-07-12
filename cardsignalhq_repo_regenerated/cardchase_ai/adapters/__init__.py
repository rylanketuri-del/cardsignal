"""Sport adapter framework — centralized league registration."""

from cardchase_ai.adapters.base import (
    CardReportAdapter,
    CardSignalAdapter,
    LeagueAdapter,
    PerformanceAdapter,
    PlayerSnapshotAdapter,
    SeasonAdapter,
    SignalDriverAdapter,
    SportAdapter,
)
from cardchase_ai.adapters.metadata import LeagueMetadata, RecentWindow, SeasonPhaseRules, SportMetadata
from cardchase_ai.adapters.registry import (
    get_league_adapter,
    get_sport_adapter,
    list_registered_leagues,
    list_searchable_leagues,
    register_league,
    register_sport,
    search_players,
)

__all__ = [
    "CardReportAdapter",
    "CardSignalAdapter",
    "LeagueAdapter",
    "LeagueMetadata",
    "PerformanceAdapter",
    "PlayerSnapshotAdapter",
    "RecentWindow",
    "SeasonAdapter",
    "SeasonPhaseRules",
    "SignalDriverAdapter",
    "SportAdapter",
    "SportMetadata",
    "get_league_adapter",
    "get_sport_adapter",
    "list_registered_leagues",
    "list_searchable_leagues",
    "register_league",
    "register_sport",
    "search_players",
]


def _bootstrap_registrations() -> None:
    from cardchase_ai.adapters.mlb import MlbLeagueAdapter, MlbSportAdapter
    from cardchase_ai.adapters.nfl import NflLeagueAdapter, NflSportAdapter

    register_sport(MlbSportAdapter())
    register_sport(NflSportAdapter())
    register_league(MlbLeagueAdapter())
    register_league(NflLeagueAdapter())


_bootstrap_registrations()
