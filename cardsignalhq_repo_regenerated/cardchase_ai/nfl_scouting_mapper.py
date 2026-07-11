"""Centralized NFL Scouting Report payload mapping."""

from __future__ import annotations

from typing import Any

from cardchase_ai.models.nfl import NFLPerformanceSnapshot, NFLSignalDriver, NFLSeasonPhase


def _window_payload(snapshot: NFLPerformanceSnapshot | None) -> dict[str, Any] | None:
    if not snapshot:
        return None
    return {
        "period_start": snapshot.period_start,
        "period_end": snapshot.period_end,
        "games_in_window": snapshot.games_played,
        "season": snapshot.season,
        "period_type": snapshot.period_type,
        "data_quality": snapshot.data_quality,
        "captured_at": snapshot.captured_at.isoformat() if snapshot.captured_at else None,
    }


def resolve_nfl_season_phase(
    *,
    active_status: str | None = None,
    computed_phase: NFLSeasonPhase | None = None,
    explicit_phase: NFLSeasonPhase | None = None,
) -> NFLSeasonPhase:
    """Resolve stored season phase without browser recomputation."""
    if explicit_phase:
        return explicit_phase
    status = str(active_status or "ACTIVE").upper()
    if status in {"INACTIVE", "INJURED_RESERVE", "RETIRED"}:
        return "INACTIVE"
    if computed_phase:
        return computed_phase
    return "UNKNOWN"


def build_nfl_scouting_evidence(
    *,
    nfl_season_phase: NFLSeasonPhase,
    season: int,
    recent_snap: NFLPerformanceSnapshot | None,
    season_snap: NFLPerformanceSnapshot | None,
    drivers: list[NFLSignalDriver],
    performance_reasons: list[str] | None = None,
    collector_evidence: list[str] | None = None,
    scarcity_evidence: list[str] | None = None,
    confidence_multiplier: float | None = None,
    tag: str | None = None,
) -> dict[str, Any]:
    """Build stable NFL scouting evidence stored on weekly snapshots."""
    return {
        "nfl_season_phase": nfl_season_phase,
        "nfl_season": season,
        "nfl_recent_window": _window_payload(recent_snap),
        "nfl_season_window": _window_payload(season_snap),
        "nfl_recent_stats": recent_snap.stats if recent_snap else {},
        "nfl_season_stats": season_snap.stats if season_snap else {},
        "nfl_data_quality": recent_snap.data_quality if recent_snap else "INSUFFICIENT",
        "nfl_signal_drivers": [d.model_dump(mode="json") for d in drivers],
        "performance_reasons": performance_reasons or [],
        "collector_evidence": collector_evidence or [],
        "scarcity_evidence": scarcity_evidence or [],
        "confidence_multiplier": confidence_multiplier,
        "tag": tag,
    }


def build_nfl_player_detail_payload(
    *,
    player: dict[str, Any],
    nfl_season_phase: NFLSeasonPhase | None = None,
    recent_snap: NFLPerformanceSnapshot | None = None,
    season_snap: NFLPerformanceSnapshot | None = None,
    drivers: list[NFLSignalDriver] | None = None,
) -> dict[str, Any]:
    """Enrich NFL player API responses with scouting context."""
    payload = dict(player)
    evidence = payload.get("evidence") or {}
    phase = nfl_season_phase or evidence.get("nfl_season_phase") or "UNKNOWN"
    payload["player_id"] = payload.get("source_player_id") or payload.get("player_id")
    payload["nfl_season_phase"] = phase
    payload["nfl_season"] = evidence.get("nfl_season") or payload.get("season")
    payload["nfl_recent_window"] = evidence.get("nfl_recent_window") or _window_payload(recent_snap)
    payload["nfl_season_window"] = evidence.get("nfl_season_window") or _window_payload(season_snap)
    payload["nfl_signal_drivers"] = evidence.get("nfl_signal_drivers") or [
        d.model_dump(mode="json") for d in (drivers or [])
    ]
    return payload


def build_nfl_performance_payload(
    *,
    cs_player_id: str,
    nfl_season_phase: NFLSeasonPhase | None,
    recent_snap: NFLPerformanceSnapshot | None,
    season_snap: NFLPerformanceSnapshot | None,
    drivers: list[NFLSignalDriver] | None = None,
) -> dict[str, Any]:
    if not recent_snap and not season_snap:
        return {
            "cs_player_id": cs_player_id,
            "available": False,
            "recent_3_games": None,
            "season": None,
            "pending": True,
            "nfl_season_phase": nfl_season_phase or "UNKNOWN",
            "nfl_recent_window": None,
            "nfl_season_window": None,
            "nfl_signal_drivers": [],
        }
    return {
        "cs_player_id": cs_player_id,
        "available": True,
        "pending": False,
        "nfl_season_phase": nfl_season_phase or "UNKNOWN",
        "recent_3_games": recent_snap.model_dump(mode="json") if recent_snap else None,
        "season": season_snap.model_dump(mode="json") if season_snap else None,
        "nfl_recent_window": _window_payload(recent_snap),
        "nfl_season_window": _window_payload(season_snap),
        "nfl_signal_drivers": [d.model_dump(mode="json") for d in (drivers or [])],
    }
