"""Explicit league capability declarations — frontend must not infer from missing fields."""

from __future__ import annotations

from cardchase_ai.models.intelligence import CapabilityStatus, LEAGUE_CAPABILITIES


def _base_capabilities() -> dict[str, CapabilityStatus]:
    return {key: "UNAVAILABLE" for key in LEAGUE_CAPABILITIES}


def declare_mlb_capabilities(
    *,
    has_market_history: bool = False,
    has_weekly_history: bool = True,
) -> dict[str, CapabilityStatus]:
    """MLB capability map based on real implementation paths."""
    caps = _base_capabilities()
    caps.update({
        "live_performance": "SUPPORTED",
        "recent_form": "SUPPORTED",
        "season_stats": "SUPPORTED",
        "signal_drivers": "SUPPORTED",
        "momentum": "SUPPORTED",
        "market_snapshots": "SUPPORTED",
        "market_movement": "SUPPORTED" if has_market_history else "PENDING",
        "card_intelligence": "SUPPORTED",
        "population": "PENDING",
        "alerts": "SUPPORTED",
        "legacy_supabase": "SUPPORTED",
        "weekly_history": "SUPPORTED" if has_weekly_history else "PENDING",
        "imported_performance": "UNAVAILABLE",
        "previous_season_stats": "UNAVAILABLE",
    })
    return caps


def declare_nfl_capabilities(
    *,
    has_prior_weekly_snapshot: bool = False,
    has_market_history: bool = False,
    has_import_data: bool = True,
) -> dict[str, CapabilityStatus]:
    """NFL capability map — no MLB legacy paths, alerts disabled until implemented."""
    caps = _base_capabilities()
    caps.update({
        "imported_performance": "SUPPORTED" if has_import_data else "UNAVAILABLE",
        "recent_form": "SUPPORTED" if has_import_data else "UNAVAILABLE",
        "season_stats": "SUPPORTED" if has_import_data else "UNAVAILABLE",
        "signal_drivers": "SUPPORTED" if has_import_data else "UNAVAILABLE",
        "market_snapshots": "SUPPORTED",
        "card_intelligence": "SUPPORTED",
        "weekly_history": "SUPPORTED",
        "population": "PENDING",
        "alerts": "DISABLED",
        "legacy_supabase": "UNAVAILABLE",
        "live_performance": "UNAVAILABLE",
        "previous_season_stats": "PENDING",
        "momentum": "SUPPORTED" if has_prior_weekly_snapshot else "PENDING",
        "market_movement": "SUPPORTED" if has_market_history else "UNAVAILABLE",
    })
    return caps


def capability_allows(capabilities: dict[str, CapabilityStatus], key: str) -> bool:
    return capabilities.get(key) == "SUPPORTED"
