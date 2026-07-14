"""MLB Signal Driver generation from stored performance evidence only."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from cardchase_ai.models.intelligence import SignalDriverPayload
from cardchase_ai.models.schemas import RollingHitterStats


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def generate_mlb_signal_drivers(
    *,
    stats_7d: RollingHitterStats,
    stats_30d: RollingHitterStats,
    developments: list[dict[str, Any]] | None = None,
    season_phase: str = "REGULAR_SEASON",
) -> list[SignalDriverPayload]:
    """Generate MLB signal drivers from stored stats and verified developments."""
    drivers: list[SignalDriverPayload] = []
    now = _utcnow().isoformat()
    source = "mlb_stats_api"

    if stats_7d.games >= 3:
        if stats_7d.ops >= 1.000:
            drivers.append(SignalDriverPayload(
                driver_type="RECENT_BATTING_SURGE",
                label="Recent Batting Surge",
                description=f"OPS {stats_7d.ops:.3f} over last {stats_7d.games} games.",
                evidence={"ops_7d": round(stats_7d.ops, 3), "games": stats_7d.games},
                source_method=source,
                season_phase=season_phase,
                captured_at=now,
            ))

        if stats_7d.home_runs >= 3:
            drivers.append(SignalDriverPayload(
                driver_type="POWER_PRODUCTION",
                label="Power Production",
                description=f"{stats_7d.home_runs} home runs in last {stats_7d.games} games.",
                evidence={"home_runs_7d": stats_7d.home_runs},
                source_method=source,
                season_phase=season_phase,
                captured_at=now,
            ))

        if stats_30d.games > 0 and stats_7d.ops - stats_30d.ops >= 0.100:
            drivers.append(SignalDriverPayload(
                driver_type="IMPROVED_OPS",
                label="Improved OPS",
                description="OPS improved versus 30-day baseline.",
                evidence={
                    "ops_7d": round(stats_7d.ops, 3),
                    "ops_30d": round(stats_30d.ops, 3),
                    "ops_delta": round(stats_7d.ops - stats_30d.ops, 3),
                },
                source_method=source,
                season_phase=season_phase,
                captured_at=now,
            ))

        if stats_7d.stolen_bases >= 2:
            drivers.append(SignalDriverPayload(
                driver_type="STOLEN_BASE_ACTIVITY",
                label="Stolen-Base Activity",
                description=f"{stats_7d.stolen_bases} stolen bases in recent window.",
                evidence={"stolen_bases_7d": stats_7d.stolen_bases},
                source_method=source,
                season_phase=season_phase,
                captured_at=now,
            ))

    dev_types = {
        "CALL_UP": "Call-Up",
        "TRADE": "Trade",
        "INJURY_RETURN": "Injury Return",
    }
    for dev in developments or []:
        driver_type = str(dev.get("driver_type", "")).upper()
        if driver_type not in dev_types:
            continue
        if dev.get("verified") is False:
            continue
        drivers.append(SignalDriverPayload(
            driver_type=driver_type,
            label=dev.get("label", dev_types[driver_type]),
            description=dev.get("description", ""),
            evidence=dev.get("evidence") or {},
            source_method=dev.get("source_method", source),
            season_phase=season_phase,
            captured_at=now,
        ))

    return drivers


def driver_data_quality(drivers: list[SignalDriverPayload], games: int) -> str:
    if not drivers:
        return "INSUFFICIENT"
    if games >= 5 and len(drivers) >= 2:
        return "HIGH"
    if games >= 3:
        return "MEDIUM"
    return "LOW"
