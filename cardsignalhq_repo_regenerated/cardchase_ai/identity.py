"""CardSignal player and card identity helpers."""

from __future__ import annotations


def cs_nfl_player_id(source_player_id: str | int) -> str:
    """Deterministic NFL player ID: CS-NFL-P-{STABLE_SOURCE_PLAYER_ID}."""
    stable = str(source_player_id).strip()
    return f"CS-NFL-P-{stable}"


def cs_nba_player_id(source_player_id: str | int) -> str:
    """Deterministic NBA player ID: CS-NBA-P-{STABLE_SOURCE_PLAYER_ID}."""
    stable = str(source_player_id).strip()
    return f"CS-NBA-P-{stable}"


def cs_player_id(source_player_id: str | int, league: str = "MLB") -> str:
    """Build a league-specific CardSignal player ID."""
    league_upper = league.upper()
    if league_upper == "NFL":
        return cs_nfl_player_id(source_player_id)
    if league_upper == "NBA":
        return cs_nba_player_id(source_player_id)
    return f"{league.lower()}:{source_player_id}"


def cs_card_id(source_player_id: str | int, query_name: str, league: str = "MLB") -> str:
    """Build a league-specific CardSignal card ID."""
    return f"{cs_player_id(source_player_id, league)}:card:{query_name}"


def parse_cs_player_id(cs_id: str) -> tuple[str, str]:
    """Return (league, source_player_id) from a CardSignal player ID."""
    if cs_id.startswith("CS-NFL-P-"):
        return "NFL", cs_id.removeprefix("CS-NFL-P-")
    if cs_id.startswith("CS-NBA-P-"):
        return "NBA", cs_id.removeprefix("CS-NBA-P-")
    if ":" in cs_id:
        league, source_id = cs_id.split(":", 1)
        return league.upper(), source_id
    return "MLB", cs_id


def normalize_api_player_id(player_id: str, league: str = "MLB") -> str:
    """Normalize API path player_id to cs_player_id format."""
    if player_id.startswith("CS-NFL-P-") or player_id.startswith("CS-NBA-P-"):
        return player_id
    if ":" in player_id:
        return player_id
    if league.upper() == "NFL":
        return cs_nfl_player_id(player_id)
    if league.upper() == "NBA":
        return cs_nba_player_id(player_id)
    return cs_player_id(player_id, league)
