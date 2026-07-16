"""Shared season-phase helper for the CardSignal engine.

The engine receives only IN_SEASON / OFFSEASON / PRESEASON.
League-specific calendars (NFL, NBA, MLB) map into that vocabulary here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

EngineSeasonPhase = Literal["IN_SEASON", "OFFSEASON", "PRESEASON"]

# League-native phases that count as "in season" for the engine.
_IN_SEASON_NATIVE = frozenset({"REGULAR_SEASON", "POSTSEASON", "IN_SEASON"})
_PRESEASON_NATIVE = frozenset({"PRESEASON"})
_OFFSEASON_NATIVE = frozenset({"OFFSEASON"})

DEFAULT_TIMEZONE = "America/New_York"


@dataclass(frozen=True)
class PerformanceWindow:
    """Inclusive calendar window used for in-season weekly performance."""

    period_start: datetime
    period_end: datetime
    label: str = "Previous Tuesday → Current Tuesday"


def resolve_engine_season_phase(native_phase: str | None) -> EngineSeasonPhase:
    """Map a league-native phase string onto the engine's three-phase model."""
    phase = str(native_phase or "").upper()
    if phase in _PRESEASON_NATIVE:
        return "PRESEASON"
    if phase in _OFFSEASON_NATIVE:
        return "OFFSEASON"
    if phase in _IN_SEASON_NATIVE:
        return "IN_SEASON"
    # Unknown / empty → treat as offseason so we never fabricate recent form.
    return "OFFSEASON"


def season_phase_for_league(
    league: str,
    *,
    today: date | None = None,
    has_active_season_games: bool = False,
    is_preseason: bool = False,
    is_postseason: bool = False,
) -> EngineSeasonPhase:
    """Determine engine season phase for a league using shared calendar rules."""
    league_upper = str(league or "").upper()
    today = today or date.today()

    if league_upper == "NFL":
        from cardchase_ai.nfl_season import nfl_season_phase

        native = nfl_season_phase(
            today=today,
            has_active_season_games=has_active_season_games,
            is_preseason=is_preseason,
            is_postseason=is_postseason,
        )
        return resolve_engine_season_phase(native)

    if league_upper == "NBA":
        from cardchase_ai.nba_season import nba_season_phase

        native = nba_season_phase(
            today=today,
            has_active_season_games=has_active_season_games,
            is_preseason=is_preseason,
            is_postseason=is_postseason,
        )
        return resolve_engine_season_phase(native)

    # MLB: treat the active baseball calendar as in-season; winter as offseason.
    month = today.month
    if month in {3, 4, 5, 6, 7, 8, 9, 10}:
        return "IN_SEASON"
    if month == 2:
        return "PRESEASON"
    return "OFFSEASON"


def in_season_tuesday_window(
    *,
    anchor: datetime | None = None,
    timezone_name: str = DEFAULT_TIMEZONE,
) -> PerformanceWindow:
    """Return the previous-Tuesday → current-Tuesday performance window.

    At/after Tuesday local midnight, "current Tuesday" is today's Tuesday and
    "previous Tuesday" is seven days earlier. Before Tuesday in the local week,
    the window ends on the most recent Tuesday and starts the Tuesday before that.
    """
    tz = ZoneInfo(timezone_name or DEFAULT_TIMEZONE)
    local = (anchor or datetime.now(tz)).astimezone(tz)

    days_since_tuesday = (local.weekday() - 1) % 7
    current_tuesday = (local - timedelta(days=days_since_tuesday)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    previous_tuesday = current_tuesday - timedelta(days=7)
    # Window ends at the start of current Tuesday (exclusive end → last instant prior).
    period_end = current_tuesday - timedelta(microseconds=1)
    return PerformanceWindow(
        period_start=previous_tuesday,
        period_end=period_end,
        label="Previous Tuesday → Current Tuesday",
    )


def uses_previous_season_baseline(phase: EngineSeasonPhase) -> bool:
    """Offseason (and preseason) use completed previous-season performance."""
    return phase in {"OFFSEASON", "PRESEASON"}
