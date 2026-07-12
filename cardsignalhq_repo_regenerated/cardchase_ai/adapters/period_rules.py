"""Reporting period construction from registered league metadata.

Canonical league behavior (period bounds, refresh schedule, season resolution)
is defined on LeagueMetadata in each registered LeagueAdapter.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from cardchase_ai.utils.reporting_period import ReportingPeriod

if TYPE_CHECKING:
    from cardchase_ai.adapters.metadata import LeagueMetadata
    from cardchase_ai.config import Settings


def _league_tz(timezone_name: str) -> ZoneInfo:
    return ZoneInfo(timezone_name or "America/New_York")


def period_bounds_from_metadata(
    metadata: LeagueMetadata,
    anchor: datetime,
    timezone_name: str | None = None,
) -> tuple[datetime, datetime]:
    """Return period_start and period_end for the period containing anchor."""
    tz_name = timezone_name or metadata.timezone
    tz = _league_tz(tz_name)
    local = anchor.astimezone(tz)
    start_wd = int(metadata.period_start_weekday)
    end_wd = int(metadata.period_end_weekday)

    days_back = (local.weekday() - start_wd) % 7
    period_start = (local - timedelta(days=days_back)).replace(hour=0, minute=0, second=0, microsecond=0)

    if start_wd <= end_wd:
        days_forward = end_wd - start_wd
    else:
        days_forward = (end_wd - start_wd) % 7
        if local.weekday() <= end_wd and days_back > 0:
            days_forward = (end_wd - local.weekday()) % 7
        elif local.weekday() < start_wd:
            days_forward = (end_wd - local.weekday()) % 7

    period_end_day = period_start + timedelta(days=days_forward)
    period_end = period_end_day.replace(hour=23, minute=59, second=59, microsecond=999999)
    return period_start, period_end


def resolve_season_from_metadata(
    metadata: LeagueMetadata,
    period_start: datetime,
    settings: Settings | None = None,
    explicit_season: int | None = None,
) -> int:
    if explicit_season is not None:
        return explicit_season
    if metadata.season_settings_key and settings is not None:
        return int(getattr(settings, metadata.season_settings_key))
    return period_start.year


def build_reporting_period_from_metadata(
    metadata: LeagueMetadata,
    *,
    anchor: datetime | None = None,
    timezone_name: str | None = None,
    season: int | None = None,
    settings: Settings | None = None,
) -> ReportingPeriod:
    tz_name = timezone_name or metadata.timezone
    tz = _league_tz(tz_name)
    anchor_dt = (anchor or datetime.now(tz)).astimezone(tz)
    period_start, period_end = period_bounds_from_metadata(metadata, anchor_dt, tz_name)
    resolved_season = resolve_season_from_metadata(metadata, period_start, settings, season)
    return ReportingPeriod(
        league=metadata.league.upper(),
        sport=metadata.sport.upper(),
        season=resolved_season,
        year=period_start.year,
        week_number=period_start.isocalendar()[1],
        period_start=period_start,
        period_end=period_end,
    )


def next_refresh_from_metadata(
    metadata: LeagueMetadata,
    *,
    timezone_name: str | None = None,
) -> datetime:
    tz_name = timezone_name or metadata.timezone
    tz = _league_tz(tz_name)
    now = datetime.now(tz)
    days_ahead = (metadata.refresh_day - now.weekday()) % 7
    candidate = now.replace(hour=metadata.refresh_hour, minute=0, second=0, microsecond=0) + timedelta(days=days_ahead)
    if candidate <= now:
        candidate += timedelta(days=7)
    return candidate
