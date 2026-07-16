#!/usr/bin/env python3
"""Tuesday cron entry point for NFL and NBA weekly intelligence.

Production schedule (Render, UTC):
  0 10 * * 2

Eastern mapping (Render cannot express TZ-aware cron):
  - EDT (UTC-4): 10:00 UTC == 06:00 America/New_York
  - EST (UTC-5): 10:00 UTC == 05:00 America/New_York

Beta anchors to 06:00 Eastern Daylight Time. This is the single production
entry point for NFL and NBA weekly refresh (see also render.yaml).
"""

from __future__ import annotations

from cardchase_ai.config import get_settings
from cardchase_ai.pipelines.schedule import is_weekly_pipeline_due
from cardchase_ai.pipelines.weekly_pipeline import run_weekly_pipeline
from cardchase_ai.sports.registry import is_league_available
from cardchase_ai.storage.supabase import build_weekly_storage, production_storage_configured


def main() -> None:
    settings = get_settings()
    storage = build_weekly_storage(settings)
    print(f"Supabase configured: {production_storage_configured(settings)}")

    for league in ("NFL", "NBA"):
        if not is_league_available(league, settings):
            print(f"Weekly {league}: SKIPPED (league data unavailable)")
            continue
        due, reason = is_weekly_pipeline_due(league, settings, storage=storage)
        if not due:
            print(f"Weekly {league}: SKIPPED ({reason})")
            continue
        summary = run_weekly_pipeline(
            league,
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
