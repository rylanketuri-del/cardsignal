"""Centralized NBA Scouting Report payload mapping."""

from __future__ import annotations

from typing import Any

from cardchase_ai.models.nba import NBAPerformanceSnapshot, NBASeasonPhase, NBASignalDriver, recent_window_value


def _window_payload(snapshot: NBAPerformanceSnapshot | None) -> dict[str, Any] | None:
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
        "recent_window_type": "COMPLETED_GAMES",
        "recent_window_value": recent_window_value(),
    }


def resolve_nba_season_phase(
    *,
    active_status: str | None = None,
    computed_phase: NBASeasonPhase | None = None,
    explicit_phase: NBASeasonPhase | None = None,
) -> NBASeasonPhase:
    """Resolve stored season phase without browser recomputation."""
    if explicit_phase:
        return explicit_phase
    status = str(active_status or "ACTIVE").upper()
    if status in {"INACTIVE", "INJURED_RESERVE", "RETIRED"}:
        return "INACTIVE"
    if computed_phase:
        return computed_phase
    return "UNKNOWN"


def build_nba_scouting_evidence(
    *,
    nba_season_phase: NBASeasonPhase,
    season: int,
    recent_snap: NBAPerformanceSnapshot | None,
    season_snap: NBAPerformanceSnapshot | None,
    drivers: list[NBASignalDriver],
    performance_reasons: list[str] | None = None,
    collector_evidence: list[str] | None = None,
    scarcity_evidence: list[str] | None = None,
    confidence_multiplier: float | None = None,
    tag: str | None = None,
) -> dict[str, Any]:
    """Build stable NBA scouting evidence stored on weekly snapshots."""
    return {
        "nba_season_phase": nba_season_phase,
        "nba_season": season,
        "nba_recent_window": _window_payload(recent_snap),
        "nba_season_window": _window_payload(season_snap),
        "nba_recent_stats": recent_snap.stats if recent_snap else {},
        "nba_season_stats": season_snap.stats if season_snap else {},
        "nba_data_quality": recent_snap.data_quality if recent_snap else "INSUFFICIENT",
        "nba_signal_drivers": [d.model_dump(mode="json") for d in drivers],
        "performance_reasons": performance_reasons or [],
        "collector_evidence": collector_evidence or [],
        "scarcity_evidence": scarcity_evidence or [],
        "confidence_multiplier": confidence_multiplier,
        "tag": tag,
    }


def build_nba_player_detail_payload(
    *,
    player: dict[str, Any],
    nba_season_phase: NBASeasonPhase | None = None,
    recent_snap: NBAPerformanceSnapshot | None = None,
    season_snap: NBAPerformanceSnapshot | None = None,
    drivers: list[NBASignalDriver] | None = None,
) -> dict[str, Any]:
    """Enrich NBA player API responses with scouting context."""
    payload = dict(player)
    evidence = payload.get("evidence") or {}
    phase = nba_season_phase or evidence.get("nba_season_phase") or "UNKNOWN"
    payload["player_id"] = payload.get("source_player_id") or payload.get("player_id")
    payload["nba_season_phase"] = phase
    payload["nba_season"] = evidence.get("nba_season") or payload.get("season")
    payload["nba_recent_window"] = evidence.get("nba_recent_window") or _window_payload(recent_snap)
    payload["nba_season_window"] = evidence.get("nba_season_window") or _window_payload(season_snap)
    payload["nba_signal_drivers"] = evidence.get("nba_signal_drivers") or [
        d.model_dump(mode="json") for d in (drivers or [])
    ]
    return payload


def build_nba_performance_payload(
    *,
    cs_player_id: str,
    nba_season_phase: NBASeasonPhase | None,
    recent_snap: NBAPerformanceSnapshot | None,
    season_snap: NBAPerformanceSnapshot | None,
    drivers: list[NBASignalDriver] | None = None,
) -> dict[str, Any]:
    if not recent_snap and not season_snap:
        return {
            "cs_player_id": cs_player_id,
            "available": False,
            "recent_5_games": None,
            "season": None,
            "pending": True,
            "nba_season_phase": nba_season_phase or "UNKNOWN",
            "nba_recent_window": None,
            "nba_season_window": None,
            "nba_signal_drivers": [],
        }
    return {
        "cs_player_id": cs_player_id,
        "available": True,
        "pending": False,
        "nba_season_phase": nba_season_phase or "UNKNOWN",
        "recent_5_games": recent_snap.model_dump(mode="json") if recent_snap else None,
        "season": season_snap.model_dump(mode="json") if season_snap else None,
        "nba_recent_window": _window_payload(recent_snap),
        "nba_season_window": _window_payload(season_snap),
        "nba_signal_drivers": [d.model_dump(mode="json") for d in (drivers or [])],
    }
