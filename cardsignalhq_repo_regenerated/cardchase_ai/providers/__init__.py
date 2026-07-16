"""League performance providers (retrieval + normalization only)."""

from __future__ import annotations

__all__ = [
    "MLBProvider",
    "NBAProvider",
    "NFLProvider",
    "get_mlb_provider",
    "get_nba_provider",
    "get_nfl_provider",
    "get_provider",
]


def __getattr__(name: str):
    # Lazy exports avoid circular imports with clients.*_import modules.
    if name in {"MLBProvider", "get_mlb_provider"}:
        from cardchase_ai.providers.mlb_provider import MLBProvider, get_mlb_provider

        return {"MLBProvider": MLBProvider, "get_mlb_provider": get_mlb_provider}[name]
    if name in {"NFLProvider", "get_nfl_provider"}:
        from cardchase_ai.providers.nfl_provider import NFLProvider, get_nfl_provider

        return {"NFLProvider": NFLProvider, "get_nfl_provider": get_nfl_provider}[name]
    if name in {"NBAProvider", "get_nba_provider"}:
        from cardchase_ai.providers.nba_provider import NBAProvider, get_nba_provider

        return {"NBAProvider": NBAProvider, "get_nba_provider": get_nba_provider}[name]
    if name == "get_provider":
        return get_provider
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def get_provider(league: str, settings=None):
    """Return the performance provider for a league."""
    league_upper = str(league or "").upper()
    if league_upper == "MLB":
        from cardchase_ai.providers.mlb_provider import get_mlb_provider

        return get_mlb_provider(settings)
    if league_upper == "NFL":
        from cardchase_ai.providers.nfl_provider import get_nfl_provider

        return get_nfl_provider(settings)
    if league_upper == "NBA":
        from cardchase_ai.providers.nba_provider import get_nba_provider

        return get_nba_provider(settings)
    raise ValueError(f"Unsupported league: {league}")
