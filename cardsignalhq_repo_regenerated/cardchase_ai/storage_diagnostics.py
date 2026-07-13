"""Storage backend diagnostics for admin/health-protected endpoints."""

from __future__ import annotations

from typing import Any

from cardchase_ai.config import Settings, get_settings
from cardchase_ai.performance_storage import build_performance_storage
from cardchase_ai.sports.registry import is_league_available
from cardchase_ai.weekly_intelligence import build_weekly_storage


def build_storage_diagnostics(settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    weekly_storage = build_weekly_storage(settings)
    performance_storage = build_performance_storage(settings)

    weekly_backend = "supabase" if weekly_storage.uses_supabase else "local_json"
    performance_backend = "supabase" if performance_storage.uses_supabase else "local_json"
    durable = weekly_storage.uses_supabase and performance_storage.uses_supabase

    league_performance: dict[str, Any] = {}
    for league in ("NFL", "NBA", "MLB"):
        summary = performance_storage.league_summary(league)
        summary["league_available"] = is_league_available(league, settings)
        league_performance[league] = summary

    weekly_leagues: dict[str, Any] = {}
    for league in ("MLB", "NFL", "NBA"):
        payload = weekly_storage.fetch_latest_completed_payload(league)
        weekly_leagues[league] = {
            "has_completed_run": payload is not None,
            "player_snapshot_count": len(payload.get("player_snapshots", [])) if payload else 0,
            "run_status": (payload.get("run") or {}).get("status") if payload else None,
        }

    warnings: list[str] = []
    if not durable:
        warnings.append(
            "Local JSON storage is ephemeral on Render — configure Supabase for durable persistence across redeploys."
        )

    return {
        "performance_storage_backend": performance_backend,
        "weekly_storage_backend": weekly_backend,
        "storage_is_durable": durable,
        "league_performance": league_performance,
        "weekly_intelligence": weekly_leagues,
        "warnings": warnings,
    }
