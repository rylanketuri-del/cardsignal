"""Timezone-aware reporting period helpers for weekly intelligence.

All league-specific period rules are resolved through the adapter registry.
LeagueMetadata on each registered LeagueAdapter is the canonical configuration.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

DEFAULT_TIMEZONE = "America/New_York"
DEFAULT_REFRESH_DAY = 1  # Tuesday (Monday=0)
DEFAULT_REFRESH_HOUR = 6


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


def build_reporting_period(
    league: str,
    sport: str | None = None,
    *,
    anchor: datetime | None = None,
    timezone_name: str = DEFAULT_TIMEZONE,
    season: int | None = None,
    settings=None,
) -> ReportingPeriod:
    """Build the reporting period for a registered league."""
    from cardchase_ai.adapters import get_league_adapter

    adapter = get_league_adapter(league)
    return adapter.season.build_reporting_period(
        anchor=anchor,
        timezone_name=timezone_name,
        season=season,
        settings=settings,
    )


def current_reporting_period(
    league: str,
    timezone_name: str = DEFAULT_TIMEZONE,
    season: int | None = None,
    settings=None,
) -> ReportingPeriod:
    return build_reporting_period(
        league=league,
        timezone_name=timezone_name,
        season=season,
        settings=settings,
    )


def previous_reporting_period(
    league: str,
    timezone_name: str = DEFAULT_TIMEZONE,
    season: int | None = None,
    settings=None,
) -> ReportingPeriod:
    current = current_reporting_period(league, timezone_name, season, settings=settings)
    tz = _league_tz(timezone_name)
    anchor = current.period_start.astimezone(tz) - timedelta(days=1)
    return build_reporting_period(
        league=league,
        anchor=anchor,
        timezone_name=timezone_name,
        season=season,
        settings=settings,
    )


def next_scheduled_refresh(
    league: str,
    timezone_name: str = DEFAULT_TIMEZONE,
    refresh_day: int | None = None,
    refresh_hour: int | None = None,
) -> datetime:
    """Next scheduled refresh using registered league metadata."""
    from cardchase_ai.adapters import get_league_adapter
    from cardchase_ai.adapters.period_rules import next_refresh_from_metadata

    adapter = get_league_adapter(league)
    if refresh_day is not None or refresh_hour is not None:
        meta = adapter.metadata
        from dataclasses import replace

        meta = replace(
            meta,
            refresh_day=refresh_day if refresh_day is not None else meta.refresh_day,
            refresh_hour=refresh_hour if refresh_hour is not None else meta.refresh_hour,
        )
        return next_refresh_from_metadata(meta, timezone_name=timezone_name)
    return next_refresh_from_metadata(adapter.metadata, timezone_name=timezone_name)


def official_run_key(period: ReportingPeriod) -> str:
    return f"{period.league}:{period.year}:W{period.week_number:02d}"
