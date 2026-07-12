"""NBA Signal Driver generation from stored evidence only."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from cardchase_ai.models.nba import NBASeasonPhase, NBASignalDriver

ACTIVE_SEASON_DRIVERS = frozenset({
    "HOT_STREAK",
    "ROLE_EXPANSION",
    "STARTER_CHANGE",
    "MINUTES_SURGE",
    "TRADE",
    "CONTRACT",
    "INJURY",
    "INJURY_RETURN",
    "ALL_STAR_SELECTION",
    "PLAYOFF_PERFORMANCE",
})

OFFSEASON_DRIVERS = frozenset({
    "TRADE",
    "CONTRACT",
    "INJURY_RECOVERY",
    "ROLE_EXPANSION",
})


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def generate_nba_signal_drivers(
    *,
    recent_stats: dict[str, Any],
    season_stats: dict[str, Any] | None,
    developments: list[dict[str, Any]] | None = None,
    season_phase: NBASeasonPhase = "REGULAR_SEASON",
    source_method: str = "APPROVED_IMPORT",
) -> list[NBASignalDriver]:
    """Generate signal drivers from stored evidence. Never from rumors or projections."""
    drivers: list[NBASignalDriver] = []
    now = _utcnow()
    games = int(recent_stats.get("games_played", 0))

    if season_phase in {"REGULAR_SEASON", "POSTSEASON"} and games >= 3:
        ppg = recent_stats.get("points_per_game")
        if ppg is not None and ppg >= 22:
            drivers.append(NBASignalDriver(
                driver_type="HOT_STREAK",
                label="Hot Streak",
                description="Scoring production elevated in recent completed games.",
                evidence={"points_per_game": ppg, "games_in_window": games},
                source_method=source_method,  # type: ignore[arg-type]
                captured_at=now,
                season_phase=season_phase,
            ))

        mpg = recent_stats.get("minutes_per_game")
        if mpg is not None and mpg >= 34:
            drivers.append(NBASignalDriver(
                driver_type="MINUTES_SURGE",
                label="Minutes Surge",
                description="Playing time increased in recent completed games.",
                evidence={"minutes_per_game": mpg},
                source_method=source_method,  # type: ignore[arg-type]
                captured_at=now,
                season_phase=season_phase,
            ))

        apg = recent_stats.get("assists_per_game")
        if apg is not None and apg >= 7:
            drivers.append(NBASignalDriver(
                driver_type="ROLE_EXPANSION",
                label="Role Expansion",
                description="Playmaking role expanded in recent completed games.",
                evidence={"assists_per_game": apg},
                source_method=source_method,  # type: ignore[arg-type]
                captured_at=now,
                season_phase=season_phase,
            ))

    for dev in developments or []:
        driver_type = str(dev.get("driver_type", "")).upper()
        if not driver_type:
            continue
        allowed = ACTIVE_SEASON_DRIVERS if season_phase in {"REGULAR_SEASON", "POSTSEASON"} else OFFSEASON_DRIVERS
        if driver_type not in allowed:
            continue
        if dev.get("verified") is False:
            continue
        drivers.append(NBASignalDriver(
            driver_type=driver_type,
            label=dev.get("label", driver_type.replace("_", " ").title()),
            description=dev.get("description", ""),
            evidence=dev.get("evidence") or {},
            source_method=dev.get("source_method", source_method),  # type: ignore[arg-type]
            captured_at=now,
            season_phase=season_phase,
        ))

    return drivers


def driver_alone_recommendation_allowed() -> bool:
    """Signal drivers alone must not issue recommendations."""
    return False
