"""Deterministic NFL beta player-population rules for previous-season seeds.

Skill-position only: the current scoring engine supports QB/RB/WR/TE
(FB maps to RB via map_nfl_position). Defensive and specialist positions
are excluded until dedicated scoring exists.
"""

from __future__ import annotations

from typing import Any

INCLUDED_RAW_POSITIONS = frozenset({"QB", "RB", "WR", "TE", "FB"})
TARGET_POPULATION_SIZE = 180
MIN_GAMES_PLAYED = 6

# Minimum statistical activity by raw position (season totals).
MIN_QB_ATTEMPTS = 100
MIN_QB_PASSING_YARDS = 500
MIN_RB_CARRIES = 40
MIN_RB_RUSHING_YARDS = 200
MIN_RB_RECEPTIONS = 15
MIN_WR_TARGETS = 40
MIN_WR_RECEIVING_YARDS = 300
MIN_TE_TARGETS = 25
MIN_TE_RECEIVING_YARDS = 200

SEED_SCRIPT_VERSION = "NFL_PREVIOUS_SEASON_SEED_V1"
NFLVERSE_STATS_RELEASE = "stats_player"
NFLVERSE_STATS_ASSET = "stats_player_reg_{season}.csv"
NFLVERSE_DOWNLOAD_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/"
    f"{NFLVERSE_STATS_RELEASE}/{NFLVERSE_STATS_ASSET}"
)
NFLVERSE_LICENSE = "CC-BY-4.0"
NFLVERSE_LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
NFLVERSE_ATTRIBUTION = (
    "Player statistics adapted from nflverse (https://github.com/nflverse/nflverse-data), "
    "licensed under CC BY 4.0. Modifications: skill-position filtering, CardSignal "
    "previous-season schema mapping, derived rate metrics (completion_percentage, "
    "yards_per_attempt, passer_rating, yards_per_carry, yards_per_reception, catch_rate)."
)


def num(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def meets_activity_threshold(row: dict[str, Any]) -> bool:
    position = str(row.get("position") or "").upper()
    games = int(num(row.get("games")))
    if games < MIN_GAMES_PLAYED:
        return False
    if position == "QB":
        return num(row.get("attempts")) >= MIN_QB_ATTEMPTS or num(row.get("passing_yards")) >= MIN_QB_PASSING_YARDS
    if position in {"RB", "FB"}:
        return (
            num(row.get("carries")) >= MIN_RB_CARRIES
            or num(row.get("rushing_yards")) >= MIN_RB_RUSHING_YARDS
            or num(row.get("receptions")) >= MIN_RB_RECEPTIONS
        )
    if position == "WR":
        return num(row.get("targets")) >= MIN_WR_TARGETS or num(row.get("receiving_yards")) >= MIN_WR_RECEIVING_YARDS
    if position == "TE":
        return num(row.get("targets")) >= MIN_TE_TARGETS or num(row.get("receiving_yards")) >= MIN_TE_RECEIVING_YARDS
    return False


def activity_rank_key(row: dict[str, Any]) -> tuple:
    """Descending sort key (negate numerics for standard ascending sort)."""
    fantasy = num(row.get("fantasy_points_ppr"))
    if fantasy <= 0:
        fantasy = num(row.get("fantasy_points"))
    total_yards = (
        num(row.get("passing_yards"))
        + max(0.0, num(row.get("rushing_yards")))
        + max(0.0, num(row.get("receiving_yards")))
    )
    games = num(row.get("games"))
    player_id = str(row.get("player_id") or "")
    return (-fantasy, -total_yards, -games, player_id)


def selection_rules_dict() -> dict[str, Any]:
    return {
        "included_positions": sorted(INCLUDED_RAW_POSITIONS),
        "excluded_positions_reason": "Scoring engine supports QB/RB/WR/TE only (FB→RB)",
        "min_games_played": MIN_GAMES_PLAYED,
        "activity_thresholds": {
            "QB": {"min_attempts": MIN_QB_ATTEMPTS, "or_min_passing_yards": MIN_QB_PASSING_YARDS},
            "RB/FB": {
                "min_carries": MIN_RB_CARRIES,
                "or_min_rushing_yards": MIN_RB_RUSHING_YARDS,
                "or_min_receptions": MIN_RB_RECEPTIONS,
            },
            "WR": {"min_targets": MIN_WR_TARGETS, "or_min_receiving_yards": MIN_WR_RECEIVING_YARDS},
            "TE": {"min_targets": MIN_TE_TARGETS, "or_min_receiving_yards": MIN_TE_RECEIVING_YARDS},
        },
        "target_population_size": TARGET_POPULATION_SIZE,
        "ranking": "fantasy_points_ppr desc, then total yards, games, player_id",
        "inactive_players": "Excluded when games < min_games_played or activity thresholds unmet",
        "traded_players": "Season aggregates use nflverse recent_team as team abbreviation",
        "rookies": "Included when thresholds met",
        "free_agents": "Rejected when recent_team is empty",
        "duplicate_resolution": "Unique by player_id; keep highest activity_rank_key",
    }
