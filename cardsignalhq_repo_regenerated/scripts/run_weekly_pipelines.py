#!/usr/bin/env python3
"""Tuesday cron entry point for NFL and NBA weekly intelligence.

Schedule (Render): 0 10 * * 2  →  Tuesday 10:00 UTC (~06:00 America/New_York)

Uses the existing weekly intelligence pipeline. Idempotent: skips when an
official completed run already exists for the current reporting week, or when
the Tuesday refresh window has not opened yet.
"""

from __future__ import annotations

from cardchase_ai.config import get_settings
from cardchase_ai.sports.registry import is_league_available, season_for_league
from cardchase_ai.utils.reporting_period import (
    build_reporting_period,
    is_weekly_refresh_window_open,
)
from cardchase_ai.weekly_intelligence import build_weekly_storage, run_weekly_intelligence


def _is_due(league: str, settings, storage) -> tuple[bool, str]:
    period = build_reporting_period(
        league=league,
        timezone_name=settings.weekly_timezone,
        season=season_for_league(league, settings),
    )
    existing = storage.find_official_completed_run(league, period.year, period.week_number)
    if existing:
        return False, (
            f"Official weekly run already completed for "
            f"{league} {period.year} W{period.week_number:02d}"
        )

    window_open, refresh_at = is_weekly_refresh_window_open(
        period,
        timezone_name=settings.weekly_timezone,
        refresh_day=settings.weekly_refresh_day,
        refresh_hour=settings.weekly_refresh_hour,
    )
    if not window_open:
        return False, (
            f"Weekly refresh not yet due until {refresh_at.isoformat()} "
            f"({league} {period.year} W{period.week_number:02d})"
        )
    return True, f"Weekly refresh due for {league} {period.year} W{period.week_number:02d}"


def main() -> None:
    settings = get_settings()
    storage = build_weekly_storage(settings)
    supabase_ready = bool(settings.supabase_url and settings.supabase_service_role_key)
    print(f"Supabase configured: {supabase_ready}")

    for league in ("NFL", "NBA"):
        if not is_league_available(league, settings):
            print(f"Weekly {league}: SKIPPED (league data unavailable)")
            continue
        due, reason = _is_due(league, settings, storage)
        if not due:
            print(f"Weekly {league}: SKIPPED ({reason})")
            continue
        summary = run_weekly_intelligence(
            league=league,
            force=False,
            triggered_by="scheduler",
            settings=settings,
            storage=storage,
        )
        detail = summary.skipped_reason or (
            f"{summary.run.players_processed} players / {summary.run.cards_processed} cards"
        )
        print(f"Weekly {league}: {summary.run.status} ({detail})")


if __name__ == "__main__":
    main()
