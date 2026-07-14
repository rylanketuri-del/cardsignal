"""NFL season phase and presentation rules."""

from __future__ import annotations

from datetime import date
from typing import Literal

from cardchase_ai.models.nfl import NFLSeasonPhase

NFLSeasonPresentation = Literal[
    "RECENT_AND_SEASON",
    "PRESEASON_MIX",
    "OFFSEASON_PREVIOUS",
]


def nfl_season_phase(
    *,
    today: date | None = None,
    has_active_season_games: bool = False,
    is_preseason: bool = False,
    is_postseason: bool = False,
) -> NFLSeasonPhase:
    """Determine NFL season phase for presentation rules."""
    today = today or date.today()
    month = today.month

    if is_postseason:
        return "POSTSEASON"
    if is_preseason or month in {8}:
        return "PRESEASON"
    if has_active_season_games or month in {9, 10, 11, 12, 1}:
        if month == 1 and today.day > 15:
            return "OFFSEASON"
        if month in {2, 3, 4, 5, 6, 7}:
            return "OFFSEASON"
        return "REGULAR_SEASON"
    if month in {2, 3, 4, 5, 6, 7}:
        return "OFFSEASON"
    return "REGULAR_SEASON"


def nfl_presentation_mode(phase: NFLSeasonPhase) -> NFLSeasonPresentation:
    if phase in {"REGULAR_SEASON", "POSTSEASON"}:
        return "RECENT_AND_SEASON"
    if phase == "PRESEASON":
        return "PRESEASON_MIX"
    return "OFFSEASON_PREVIOUS"


def recent_window_label(phase: NFLSeasonPhase) -> str:
    if phase in {"REGULAR_SEASON", "POSTSEASON"}:
        return "Recent 3 Games"
    if phase == "PRESEASON":
        return "Preseason Performance"
    return "Previous Season Performance"


def season_snapshot_label(phase: NFLSeasonPhase) -> str:
    if phase == "OFFSEASON":
        return "Previous Season Performance"
    if phase == "PRESEASON":
        return "Previous Season Performance"
    return "Season Performance"


def should_show_recent_window(phase: NFLSeasonPhase) -> bool:
    return phase in {"REGULAR_SEASON", "POSTSEASON"}
