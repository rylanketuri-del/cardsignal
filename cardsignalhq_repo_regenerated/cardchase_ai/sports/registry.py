"""Sport registry for league-specific performance providers."""

from __future__ import annotations

from cardchase_ai.clients.nfl_import import NFLImportProvider, get_nfl_provider
from cardchase_ai.clients.mlb import MLBClient
from cardchase_ai.config import Settings, get_settings

SUPPORTED_LEAGUES = frozenset({"MLB", "NFL", "NBA"})


def get_performance_client(league: str, settings: Settings | None = None):
    """Return the performance client for a league."""
    league_upper = league.upper()
    if league_upper == "MLB":
        return MLBClient()
    if league_upper == "NFL":
        return get_nfl_provider(settings)
    raise ValueError(f"Unsupported league: {league}")


def is_league_available(league: str, settings: Settings | None = None) -> bool:
    """Return True when stored/provider data exists for the league."""
    league_upper = league.upper()
    if league_upper == "MLB":
        return True
    if league_upper == "NFL":
        provider = get_nfl_provider(settings)
        return provider.is_available()
    return False


def season_for_league(league: str, settings: Settings | None = None) -> int:
    settings = settings or get_settings()
    if league.upper() == "NFL":
        return settings.nfl_season
    return settings.mlb_season
