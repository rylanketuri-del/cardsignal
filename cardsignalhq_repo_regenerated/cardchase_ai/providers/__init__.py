"""League performance providers (retrieval + normalization only)."""

from cardchase_ai.providers.mlb_provider import MLBProvider, get_mlb_provider
from cardchase_ai.providers.nba_provider import NBAProvider, get_nba_provider
from cardchase_ai.providers.nfl_provider import NFLProvider, get_nfl_provider


def get_provider(league: str, settings=None):
    """Return the performance provider for a league."""
    league_upper = str(league or "").upper()
    if league_upper == "MLB":
        return get_mlb_provider(settings)
    if league_upper == "NFL":
        return get_nfl_provider(settings)
    if league_upper == "NBA":
        return get_nba_provider(settings)
    raise ValueError(f"Unsupported league: {league}")


__all__ = [
    "MLBProvider",
    "NBAProvider",
    "NFLProvider",
    "get_mlb_provider",
    "get_nba_provider",
    "get_nfl_provider",
    "get_provider",
]
