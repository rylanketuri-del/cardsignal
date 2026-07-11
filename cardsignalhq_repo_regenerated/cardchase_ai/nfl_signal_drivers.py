"""NFL Signal Driver generation from stored evidence only."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from cardchase_ai.models.nfl import NFLSignalDriver, NFLSeasonPhase

ACTIVE_SEASON_DRIVERS = frozenset({
    "THREE_GAME_FORM",
    "PASSING_SURGE",
    "TOUCHDOWN_STREAK",
    "TARGET_VOLUME",
    "RECEIVING_SURGE",
    "RUSHING_SURGE",
    "ROLE_EXPANSION",
    "STARTER_CHANGE",
    "INJURY",
    "INJURY_RETURN",
    "DEPTH_CHART_CHANGE",
    "CONTRACT_EXTENSION",
    "TRADE",
    "MILESTONE",
    "PLAYOFF_PERFORMANCE",
})

OFFSEASON_DRIVERS = frozenset({
    "FREE_AGENT_SIGNING",
    "TRADE",
    "CONTRACT_EXTENSION",
    "DRAFT_SELECTION",
    "DEPTH_CHART_CHANGE",
    "TRAINING_CAMP_ROLE",
    "INJURY_RECOVERY",
    "VERIFIED_TEAM_DEVELOPMENT",
})


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def generate_nfl_signal_drivers(
    *,
    recent_stats: dict[str, Any],
    season_stats: dict[str, Any] | None,
    position_group: str,
    developments: list[dict[str, Any]] | None = None,
    season_phase: NFLSeasonPhase = "REGULAR_SEASON",
    source_method: str = "APPROVED_IMPORT",
) -> list[NFLSignalDriver]:
    """Generate signal drivers from stored evidence. Never from rumors or projections."""
    drivers: list[NFLSignalDriver] = []
    now = _utcnow()
    group = position_group.upper()
    games = int(recent_stats.get("games_played", 0))

    if season_phase in {"REGULAR_SEASON", "POSTSEASON"} and games >= 2:
        drivers.append(NFLSignalDriver(
            driver_type="THREE_GAME_FORM",
            label="Three-Game Form",
            description=f"Recent form window includes {games} completed games.",
            evidence={"games_in_window": games},
            source_method=source_method,
            captured_at=now,
            season_phase=season_phase,
        ))

    if group == "QB":
        pass_yds = recent_stats.get("passing_yards")
        if games and pass_yds and (pass_yds / games) >= 250:
            drivers.append(NFLSignalDriver(
                driver_type="PASSING_SURGE",
                label="Passing Surge",
                description="Passing production elevated in recent window.",
                evidence={"passing_yards_per_game": round(pass_yds / games, 1)},
                source_method=source_method,
                captured_at=now,
                season_phase=season_phase,
            ))
        tds = recent_stats.get("passing_touchdowns", 0)
        if tds and tds >= 3:
            drivers.append(NFLSignalDriver(
                driver_type="TOUCHDOWN_STREAK",
                label="Touchdown Production",
                description="Multiple passing touchdowns in recent window.",
                evidence={"passing_touchdowns": tds},
                source_method=source_method,
                captured_at=now,
                season_phase=season_phase,
            ))

    if group == "RB":
        rush_yds = recent_stats.get("rushing_yards")
        if games and rush_yds and (rush_yds / games) >= 80:
            drivers.append(NFLSignalDriver(
                driver_type="RUSHING_SURGE",
                label="Rushing Surge",
                description="Rushing production elevated in recent window.",
                evidence={"rushing_yards_per_game": round(rush_yds / games, 1)},
                source_method=source_method,
                captured_at=now,
                season_phase=season_phase,
            ))

    if group in {"WR", "TE"}:
        targets = recent_stats.get("targets")
        if games and targets and (targets / games) >= 8:
            drivers.append(NFLSignalDriver(
                driver_type="TARGET_VOLUME",
                label="Target Volume",
                description="High target volume in recent window.",
                evidence={"targets_per_game": round(targets / games, 1)},
                source_method=source_method,
                captured_at=now,
                season_phase=season_phase,
            ))
        rec_yds = recent_stats.get("receiving_yards")
        if games and rec_yds and (rec_yds / games) >= 70:
            drivers.append(NFLSignalDriver(
                driver_type="RECEIVING_SURGE",
                label="Receiving Surge",
                description="Receiving production elevated in recent window.",
                evidence={"receiving_yards_per_game": round(rec_yds / games, 1)},
                source_method=source_method,
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
        drivers.append(NFLSignalDriver(
            driver_type=driver_type,
            label=dev.get("label", driver_type.replace("_", " ").title()),
            description=dev.get("description", ""),
            evidence=dev.get("evidence") or {},
            source_method=dev.get("source_method", source_method),
            captured_at=now,
            season_phase=season_phase,
        ))

    return drivers


def driver_alone_recommendation_allowed() -> bool:
    """Signal drivers alone must not issue recommendations."""
    return False
