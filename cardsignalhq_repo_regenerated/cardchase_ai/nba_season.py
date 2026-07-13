"""NBA season phase and presentation rules."""

from __future__ import annotations

from datetime import date
from typing import Literal

from cardchase_ai.models.nba import NBASeasonPhase, recent_window_value

NBASeasonPresentation = Literal[
    "RECENT_AND_SEASON",
    "PRESEASON_MIX",
    "OFFSEASON_PREVIOUS",
]


def nba_season_phase(
    *,
    today: date | None = None,
    has_active_season_games: bool = False,
    is_preseason: bool = False,
    is_postseason: bool = False,
) -> NBASeasonPhase:
    """Determine NBA season phase for presentation rules."""
    today = today or date.today()
    month = today.month

    if is_postseason:
        return "POSTSEASON"
    if is_preseason or month in {10} and today.day < 15:
        return "PRESEASON"
    if has_active_season_games or month in {10, 11, 12, 1, 2, 3, 4}:
        if month in {7, 8, 9}:
            return "OFFSEASON"
        if month == 6 and today.day > 25:
            return "OFFSEASON"
        return "REGULAR_SEASON"
    if month in {5, 6, 7, 8, 9}:
        return "OFFSEASON"
    return "REGULAR_SEASON"


def nba_presentation_mode(phase: NBASeasonPhase) -> NBASeasonPresentation:
    if phase in {"REGULAR_SEASON", "POSTSEASON"}:
        return "RECENT_AND_SEASON"
    if phase == "PRESEASON":
        return "PRESEASON_MIX"
    return "OFFSEASON_PREVIOUS"


def recent_window_label(phase: NBASeasonPhase) -> str:
    window = recent_window_value()
    if phase in {"REGULAR_SEASON", "POSTSEASON"}:
        return f"Recent {window} Games"
    if phase == "PRESEASON":
        return "Preseason Performance"
    return "Previous Season Performance"


def season_snapshot_label(phase: NBASeasonPhase) -> str:
    if phase == "OFFSEASON":
        return "Previous Season Performance"
    if phase == "PRESEASON":
        return "Previous Season Performance"
    return "Season Performance"


def should_show_recent_window(phase: NBASeasonPhase) -> bool:
    return phase in {"REGULAR_SEASON", "POSTSEASON"}
