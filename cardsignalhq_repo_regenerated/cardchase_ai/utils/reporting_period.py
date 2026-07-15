"""Timezone-aware reporting period helpers for weekly intelligence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

LeagueCode = Literal["MLB", "NBA", "NFL"]

DEFAULT_TIMEZONE = "America/New_York"
DEFAULT_REFRESH_DAY = 1  # Tuesday (Monday=0)
DEFAULT_REFRESH_HOUR = 6

# weekday: Monday=0 .. Sunday=6
LEAGUE_PERIOD_RULES: dict[str, dict[str, int | tuple[int, ...]]] = {
    "MLB": {"period_start_weekday": 0, "period_end_weekday": 6},
    "NBA": {"period_start_weekday": 0, "period_end_weekday": 6},
    "NFL": {"period_start_weekday": 3, "period_end_weekday": 0},  # Thu–Mon (future)
}


@dataclass(frozen=True)
class ReportingPeriod:
    league: str
    sport: str
    season: int
    year: int
    week_number: int
    period_start: datetime
    period_end: datetime


def _league_tz(timezone_name: str) -> ZoneInfo:
    return ZoneInfo(timezone_name or DEFAULT_TIMEZONE)


def _period_bounds_for_date(
    league: str,
    anchor: datetime,
    timezone_name: str = DEFAULT_TIMEZONE,
) -> tuple[datetime, datetime]:
    """Return period_start and period_end (inclusive end-of-day) for the period containing anchor."""
    tz = _league_tz(timezone_name)
    local = anchor.astimezone(tz)
    rules = LEAGUE_PERIOD_RULES.get(league.upper(), LEAGUE_PERIOD_RULES["MLB"])
    start_wd = int(rules["period_start_weekday"])
    end_wd = int(rules["period_end_weekday"])

    # Walk back to period_start at 00:00:00 local
    days_back = (local.weekday() - start_wd) % 7
    period_start = (local - timedelta(days=days_back)).replace(hour=0, minute=0, second=0, microsecond=0)

    # Walk forward to period_end at 23:59:59.999999 local
    if start_wd <= end_wd:
        days_forward = end_wd - start_wd
    else:
        # Wrap-around week (NFL Thu–Mon)
        days_forward = (end_wd - start_wd) % 7
        if local.weekday() <= end_wd and days_back > 0:
            days_forward = (end_wd - local.weekday()) % 7
        elif local.weekday() < start_wd:
            days_forward = (end_wd - local.weekday()) % 7

    period_end_day = period_start + timedelta(days=days_forward)
    period_end = period_end_day.replace(hour=23, minute=59, second=59, microsecond=999999)
    return period_start, period_end


def _iso_week_number(dt: datetime) -> int:
    return dt.isocalendar()[1]


def _season_for_league(league: str, period_start: datetime, explicit_season: int | None = None) -> int:
    if explicit_season is not None:
        return explicit_season
    league_upper = league.upper()
    if league_upper == "MLB":
        # MLB season year aligns with calendar year for beta
        return period_start.year
    return period_start.year


def build_reporting_period(
    league: str = "MLB",
    sport: str | None = None,
    *,
    anchor: datetime | None = None,
    timezone_name: str = DEFAULT_TIMEZONE,
    season: int | None = None,
) -> ReportingPeriod:
    """Build the reporting period containing anchor (default: now)."""
    tz = _league_tz(timezone_name)
    anchor_dt = (anchor or datetime.now(tz)).astimezone(tz)
    period_start, period_end = _period_bounds_for_date(league, anchor_dt, timezone_name)
    resolved_season = _season_for_league(league, period_start, season)
    return ReportingPeriod(
        league=league.upper(),
        sport=(sport or league).upper(),
        season=resolved_season,
        year=period_start.year,
        week_number=_iso_week_number(period_start),
        period_start=period_start,
        period_end=period_end,
    )


def current_reporting_period(
    league: str = "MLB",
    timezone_name: str = DEFAULT_TIMEZONE,
    season: int | None = None,
) -> ReportingPeriod:
    return build_reporting_period(league=league, timezone_name=timezone_name, season=season)


def previous_reporting_period(
    league: str = "MLB",
    timezone_name: str = DEFAULT_TIMEZONE,
    season: int | None = None,
) -> ReportingPeriod:
    current = current_reporting_period(league, timezone_name, season)
    tz = _league_tz(timezone_name)
    anchor = current.period_start.astimezone(tz) - timedelta(days=1)
    return build_reporting_period(league=league, anchor=anchor, timezone_name=timezone_name, season=season)


def next_scheduled_refresh(
    league: str = "MLB",
    timezone_name: str = DEFAULT_TIMEZONE,
    refresh_day: int = DEFAULT_REFRESH_DAY,
    refresh_hour: int = DEFAULT_REFRESH_HOUR,
) -> datetime:
    """Next Tuesday (or configured day) refresh at refresh_hour in league timezone."""
    tz = _league_tz(timezone_name)
    now = datetime.now(tz)
    days_ahead = (refresh_day - now.weekday()) % 7
    candidate = now.replace(hour=refresh_hour, minute=0, second=0, microsecond=0) + timedelta(days=days_ahead)
    if candidate <= now:
        candidate += timedelta(days=7)
    return candidate


def refresh_datetime_for_period(
    period: ReportingPeriod,
    *,
    refresh_day: int = DEFAULT_REFRESH_DAY,
    refresh_hour: int = DEFAULT_REFRESH_HOUR,
) -> datetime:
    """Scheduled refresh instant belonging to a reporting period (e.g. Tuesday 06:00)."""
    days_from_start = (refresh_day - period.period_start.weekday()) % 7
    return period.period_start.replace(
        hour=refresh_hour,
        minute=0,
        second=0,
        microsecond=0,
    ) + timedelta(days=days_from_start)


def is_weekly_refresh_window_open(
    period: ReportingPeriod,
    *,
    now: datetime | None = None,
    timezone_name: str = DEFAULT_TIMEZONE,
    refresh_day: int = DEFAULT_REFRESH_DAY,
    refresh_hour: int = DEFAULT_REFRESH_HOUR,
) -> tuple[bool, datetime]:
    """Return whether the configured weekly refresh window has opened for this period."""
    tz = _league_tz(timezone_name)
    current = (now or datetime.now(tz)).astimezone(tz)
    refresh_at = refresh_datetime_for_period(period, refresh_day=refresh_day, refresh_hour=refresh_hour)
    return current >= refresh_at, refresh_at


def official_run_key(period: ReportingPeriod) -> str:
    return f"{period.league}:{period.year}:W{period.week_number:02d}"
