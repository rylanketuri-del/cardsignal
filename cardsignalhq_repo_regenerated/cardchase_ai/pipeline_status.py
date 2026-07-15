"""Admin pipeline health diagnostics — lightweight readiness summary."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cardchase_ai.config import Settings, get_settings
from cardchase_ai.storage import SupabaseStorage
from cardchase_ai.utils.reporting_period import (
    build_reporting_period,
    next_scheduled_refresh,
    refresh_datetime_for_period,
)
from cardchase_ai.weekly_intelligence import (
    build_latest_weekly_api_payload,
    build_weekly_storage,
    card_intelligence_from_homepage,
)
from cardchase_ai.sports.registry import season_for_league


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    text = str(value).strip()
    return text or None


def _file_mtime_iso(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def _card_sections_ready(card_intelligence: dict[str, Any] | None) -> bool:
    if not isinstance(card_intelligence, dict):
        return False
    sections = ("trending_cards", "biggest_movers", "buy_low_watch", "most_chased")
    return any(isinstance(card_intelligence.get(key), list) and len(card_intelligence[key]) > 0 for key in sections)


def _trend_history_available(payload: dict[str, Any] | None, weekly_storage) -> bool:
    """True when at least one stored weekly_change exists or 2+ official weekly runs."""
    if not payload:
        return False

    leaders = payload.get("todays_leaders") or []
    if any(leader.get("weekly_change") is not None for leader in leaders if isinstance(leader, dict)):
        return True

    player_snaps = payload.get("player_snapshots") or []
    if any(snap.get("weekly_change") is not None for snap in player_snaps if isinstance(snap, dict)):
        return True

    # Cheap depth check: two completed official weekly runs implies prior history can exist.
    run = payload.get("run") or {}
    league = str(run.get("league") or "MLB").upper()
    try:
        if weekly_storage.supabase:
            rows = weekly_storage.supabase._get(
                weekly_storage.RUNS_TABLE,
                {
                    "select": "run_id",
                    "league": f"eq.{league}",
                    "status": "in.(COMPLETED,PARTIAL)",
                    "force": "eq.false",
                    "triggered_by": "neq.test",
                    "limit": "2",
                },
            )
            return len(rows or []) >= 2
        index = weekly_storage.json._load_index()
        completed = [
            e for e in index
            if e.get("league") == league
            and e.get("status") in {"COMPLETED", "PARTIAL"}
            and not e.get("force")
            and e.get("triggered_by") != "test"
        ]
        return len(completed) >= 2
    except Exception:
        return False


def _derive_status(
    *,
    leaderboard_players: int,
    homepage_intelligence_ready: bool,
    weekly_snapshot_exists: bool,
    weekly_due: bool,
) -> str:
    if leaderboard_players <= 0:
        return "unhealthy"
    if weekly_due and (not weekly_snapshot_exists or not homepage_intelligence_ready):
        return "degraded"
    return "healthy"


def build_pipeline_status(
    settings: Settings | None = None,
    *,
    league: str = "MLB",
    leaderboard_items: list[dict[str, Any]] | None = None,
    supabase: SupabaseStorage | None = None,
) -> dict[str, Any]:
    """Build GET /api/admin/pipeline/status payload from stored data only."""
    settings = settings or get_settings()
    league_upper = (league or "MLB").upper()
    weekly_storage = build_weekly_storage(settings)

    # --- Leaderboard / daily pipeline ---
    last_pipeline_run: str | None = None
    if supabase is None and settings.supabase_url and settings.supabase_service_role_key:
        try:
            supabase = SupabaseStorage(settings.supabase_url, settings.supabase_service_role_key)
        except Exception:
            supabase = None

    if supabase:
        try:
            latest_run = supabase.fetch_latest_run()
            if latest_run:
                last_pipeline_run = _iso(latest_run.get("created_at"))
                if leaderboard_items is None:
                    leaderboard_items = supabase.fetch_latest_leaderboard()
        except Exception:
            pass

    latest_path = Path(settings.output_dir) / "latest_leaderboard.json"
    if last_pipeline_run is None:
        last_pipeline_run = _file_mtime_iso(latest_path)

    if leaderboard_items is None:
        leaderboard_items = []
        if latest_path.exists():
            try:
                import json

                raw = json.loads(latest_path.read_text(encoding="utf-8"))
                if isinstance(raw, list):
                    leaderboard_items = raw
            except Exception:
                leaderboard_items = []

    leaderboard_players = len(leaderboard_items or [])

    # --- Weekly intelligence ---
    try:
        weekly_payload = weekly_storage.fetch_latest_completed_payload(league_upper)
    except Exception:
        weekly_payload = None

    try:
        api_payload = build_latest_weekly_api_payload(league_upper, weekly_storage, settings)
    except Exception:
        api_payload = {
            "todays_leaders": [],
            "card_intelligence": card_intelligence_from_homepage(
                weekly_payload.get("homepage") if weekly_payload else None
            ),
        }

    run = None
    if weekly_payload:
        run = weekly_payload.get("run")
        if hasattr(run, "model_dump"):
            run = run.model_dump(mode="json")

    last_weekly_snapshot = None
    latest_snapshot_week = None
    latest_snapshot_year = None
    if isinstance(run, dict):
        last_weekly_snapshot = _iso(run.get("completed_at") or run.get("started_at"))
        latest_snapshot_week = run.get("week_number")
        latest_snapshot_year = run.get("year")

    card_intel = api_payload.get("card_intelligence")
    if not _card_sections_ready(card_intel):
        # Fall back to raw homepage payload sections if API assembly returned empty arrays.
        card_intel = card_intelligence_from_homepage(
            weekly_payload.get("homepage") if weekly_payload else None
        )

    homepage_intelligence_ready = _card_sections_ready(card_intel)
    trend_history_available = _trend_history_available(
        {
            "todays_leaders": api_payload.get("todays_leaders") or [],
            "player_snapshots": (weekly_payload or {}).get("player_snapshots") or [],
            "run": run or {"league": league_upper},
        },
        weekly_storage,
    )

    next_due = next_scheduled_refresh(
        league=league_upper,
        timezone_name=settings.weekly_timezone,
        refresh_day=settings.weekly_refresh_day,
        refresh_hour=settings.weekly_refresh_hour,
    )

    period = build_reporting_period(
        league=league_upper,
        timezone_name=settings.weekly_timezone,
        season=season_for_league(league_upper, settings),
    )
    existing = weekly_storage.find_official_completed_run(league_upper, period.year, period.week_number)
    refresh_at = refresh_datetime_for_period(
        period,
        refresh_day=settings.weekly_refresh_day,
        refresh_hour=settings.weekly_refresh_hour,
    )
    weekly_due = existing is None and datetime.now(refresh_at.tzinfo) >= refresh_at

    status = _derive_status(
        leaderboard_players=leaderboard_players,
        homepage_intelligence_ready=homepage_intelligence_ready,
        weekly_snapshot_exists=weekly_payload is not None,
        weekly_due=weekly_due,
    )

    return {
        "last_pipeline_run": last_pipeline_run,
        "last_weekly_snapshot": last_weekly_snapshot,
        "next_weekly_snapshot_due": next_due.isoformat(),
        "leaderboard_players": leaderboard_players,
        "homepage_intelligence_ready": homepage_intelligence_ready,
        "trend_history_available": trend_history_available,
        "latest_snapshot_week": latest_snapshot_week,
        "latest_snapshot_year": latest_snapshot_year,
        "status": status,
        "league": league_upper,
    }
