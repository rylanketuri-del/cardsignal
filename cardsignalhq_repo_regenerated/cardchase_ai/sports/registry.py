"""Sport registry for league-specific performance providers."""

from __future__ import annotations

from cardchase_ai.config import Settings, get_settings
from cardchase_ai.providers import get_mlb_provider, get_nba_provider, get_nfl_provider

SUPPORTED_LEAGUES = frozenset({"MLB", "NFL", "NBA"})


def get_performance_client(league: str, settings: Settings | None = None):
    """Return the performance provider/client for a league.

    MLB returns the underlying MLBClient for backward compatibility with
    existing pipeline code; NFL/NBA return import providers via the new
    provider wrappers (``.inner``) so callers that expect the import API
    keep working.
    """
    league_upper = league.upper()
    if league_upper == "MLB":
        return get_mlb_provider(settings).client
    if league_upper == "NFL":
        return get_nfl_provider(settings).inner
    if league_upper == "NBA":
        return get_nba_provider(settings).inner
    raise ValueError(f"Unsupported league: {league}")


def is_league_available(league: str, settings: Settings | None = None) -> bool:
    """Return True when stored/provider data exists for the league."""
    league_upper = league.upper()
    if league_upper == "MLB":
        return True
    if league_upper == "NFL":
        provider = get_nfl_provider(settings)
        if provider.is_available():
            return True
        from cardchase_ai.performance_storage import build_performance_storage
        perf = build_performance_storage(settings)
        return perf.league_summary("NFL")["has_data"]
    if league_upper == "NBA":
        provider = get_nba_provider(settings)
        if provider.is_available():
            return True
        from cardchase_ai.performance_storage import build_performance_storage
        perf = build_performance_storage(settings)
        return perf.league_summary("NBA")["has_data"]
    return False


def season_for_league(league: str, settings: Settings | None = None) -> int:
    settings = settings or get_settings()
    league_upper = league.upper()
    if league_upper == "NFL":
        return settings.nfl_season
    if league_upper == "NBA":
        return settings.nba_season
    return settings.mlb_season
