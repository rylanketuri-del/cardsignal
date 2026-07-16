"""Shared scheduling helpers for MLB and weekly (NFL/NBA) pipelines.

Target schedules:
  - MLB: every 3 days
  - NFL / NBA: Tuesday 06:00 America/New_York

Duplicated cron/weekday logic should live here rather than in each pipeline.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from cardchase_ai.config import Settings, get_settings
from cardchase_ai.utils import reporting_period as reporting_period_mod

MLB_INTERVAL_DAYS = 3
WEEKLY_TIMEZONE = "America/New_York"
WEEKLY_REFRESH_DAY = 1  # Tuesday
WEEKLY_REFRESH_HOUR = 6


def _tz(settings: Settings | None = None) -> ZoneInfo:
    settings = settings or get_settings()
    return ZoneInfo(settings.weekly_timezone or WEEKLY_TIMEZONE)


def mlb_marker_path(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    return Path(settings.output_dir) / ".mlb_pipeline_last_run"


def record_mlb_pipeline_run(
    settings: Settings | None = None,
    *,
    when: datetime | None = None,
) -> None:
    """Persist a local marker used by the 3-day MLB due-check (debug/cron only)."""
    settings = settings or get_settings()
    path = mlb_marker_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = (when or datetime.now(_tz(settings))).isoformat()
    path.write_text(stamp, encoding="utf-8")


def last_mlb_pipeline_run(settings: Settings | None = None) -> datetime | None:
    path = mlb_marker_path(settings)
    if not path.exists():
        return None
    try:
        return datetime.fromisoformat(path.read_text(encoding="utf-8").strip())
    except ValueError:
        return None


def is_mlb_pipeline_due(
    settings: Settings | None = None,
    *,
    now: datetime | None = None,
    interval_days: int = MLB_INTERVAL_DAYS,
    force: bool = False,
) -> bool:
    """Return True when the MLB leaderboard pipeline should run."""
    if force:
        return True
    settings = settings or get_settings()
    tz = _tz(settings)
    current = (now or datetime.now(tz)).astimezone(tz)
    last = last_mlb_pipeline_run(settings)
    if last is None:
        return True
    if last.tzinfo is None:
        last = last.replace(tzinfo=tz)
    return current >= last.astimezone(tz) + timedelta(days=interval_days)


def is_weekly_pipeline_due(
    league: str,
    settings: Settings | None = None,
    *,
    now: datetime | None = None,
    storage=None,
) -> tuple[bool, str]:
    """Return (due, reason) for NFL/NBA Tuesday weekly refresh.

    Due when:
      1) no official completed run for the current reporting week, AND
      2) the Tuesday 06:00 Eastern refresh window has opened.
    """
    settings = settings or get_settings()
    from cardchase_ai.sports.registry import season_for_league
    from cardchase_ai.storage.supabase import build_weekly_storage

    storage = storage or build_weekly_storage(settings)
    # Look up via module so tests can patch reporting_period helpers.
    period = reporting_period_mod.build_reporting_period(
        league=league,
        timezone_name=settings.weekly_timezone or WEEKLY_TIMEZONE,
        season=season_for_league(league, settings),
    )
    existing = storage.find_official_completed_run(league, period.year, period.week_number)
    if existing:
        return False, (
            f"Official weekly run already completed for "
            f"{league.upper()} {period.year} W{period.week_number:02d}"
        )

    window_open, refresh_at = reporting_period_mod.is_weekly_refresh_window_open(
        period,
        now=now,
        timezone_name=settings.weekly_timezone or WEEKLY_TIMEZONE,
        refresh_day=settings.weekly_refresh_day if settings.weekly_refresh_day is not None else WEEKLY_REFRESH_DAY,
        refresh_hour=settings.weekly_refresh_hour if settings.weekly_refresh_hour is not None else WEEKLY_REFRESH_HOUR,
    )
    if not window_open:
        return False, (
            f"Weekly refresh not yet due until {refresh_at.isoformat()} "
            f"({league.upper()} {period.year} W{period.week_number:02d})"
        )
    return True, f"Weekly refresh due for {league.upper()} {period.year} W{period.week_number:02d}"
