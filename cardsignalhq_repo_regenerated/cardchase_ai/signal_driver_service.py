"""Read-only Signal Driver API payload builder."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from cardchase_ai.development_provider import StoredDevelopmentProvider
from cardchase_ai.models.schemas import MarketSnapshot, RollingHitterStats
from cardchase_ai.models.signal_driver import (
    SIGNAL_DRIVERS_V1,
    SignalDriverDataQuality,
    SignalDriversResponse,
)
from cardchase_ai.season_state import resolve_season_state
from cardchase_ai.signal_driver_storage import SignalDriverStorage
from cardchase_ai.signal_drivers import filter_current_drivers, group_drivers_by_category
from cardchase_ai.weekly_scoring import cs_player_id


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _build_data_quality(drivers: list) -> SignalDriverDataQuality:
    quality = SignalDriverDataQuality(
        total_drivers=len(drivers),
        current_drivers=len(drivers),
    )
    for driver in drivers:
        eq = driver.evidence_quality
        if eq == "HIGH":
            quality.high_evidence += 1
        elif eq == "MEDIUM":
            quality.medium_evidence += 1
        elif eq == "LOW":
            quality.low_evidence += 1
        else:
            quality.insufficient_evidence += 1
    return quality


def _parse_stats(payload: dict[str, Any] | None) -> RollingHitterStats:
    if not payload:
        return RollingHitterStats()
    return RollingHitterStats.model_validate(payload)


def _parse_market_snapshots(payload: dict[str, Any] | None) -> dict[str, MarketSnapshot]:
    if not payload:
        return {}
    result: dict[str, MarketSnapshot] = {}
    for key, value in payload.items():
        if isinstance(value, dict):
            result[key] = MarketSnapshot.model_validate(value)
    return result


def build_signal_drivers_response(
    *,
    player_payload: dict[str, Any],
    storage: SignalDriverStorage,
    league: str = "MLB",
    season: int | None = None,
    current_only: bool = True,
    category: str | None = None,
    limit: int = 50,
) -> SignalDriversResponse:
    """Build read-only API response from stored drivers and player context."""
    source_player_id = str(player_payload.get("player_id", ""))
    cs_id = cs_player_id(source_player_id, league) if source_player_id else player_payload.get("cs_player_id", "")
    resolved_season = season or player_payload.get("season") or 0

    metadata = storage.fetch_league_metadata(league, int(resolved_season))
    stats_7d = _parse_stats(player_payload.get("stats_7d"))
    season_state = resolve_season_state(
        league,
        season=int(resolved_season),
        metadata=metadata,
        player_games_recent=stats_7d.games,
    )

    all_drivers = storage.fetch_drivers(cs_id, league=league, limit=limit)
    if current_only:
        all_drivers = filter_current_drivers(all_drivers)

    if category:
        cat_upper = category.upper()
        all_drivers = [d for d in all_drivers if d.category == cat_upper]

    groups = group_drivers_by_category(all_drivers, season_state.state)
    previous_context: dict[str, Any] = {
        "season": resolved_season,
        "stats_30d": player_payload.get("stats_30d"),
        "label": "Previous Season Snapshot" if season_state.state in {"OFFSEASON", "INACTIVE", "UNKNOWN"} else "Season Snapshot",
        "driver_groups": {k: [d.model_dump(mode="json") for d in v] for k, v in groups.items() if v},
    }

    return SignalDriversResponse(
        cs_player_id=cs_id,
        source_player_id=source_player_id,
        player_name=player_payload.get("player_name"),
        league=league.upper(),
        sport=player_payload.get("sport", league).upper(),
        season_state=season_state,
        current_drivers=all_drivers,
        previous_season_context=previous_context,
        data_quality=_build_data_quality(all_drivers),
        algorithm_version=SIGNAL_DRIVERS_V1,
    )


def persist_pipeline_signal_drivers(
    *,
    player_name: str,
    source_player_id: str | int,
    league: str,
    stats_7d: RollingHitterStats,
    stats_30d: RollingHitterStats,
    market_snapshots: dict[str, MarketSnapshot],
    season: int,
    storage: SignalDriverStorage,
    season_state_value: str | None = None,
) -> list:
    """Generate and persist drivers during pipeline — not called from GET handlers."""
    from cardchase_ai.signal_drivers import build_player_signal_drivers

    developments = storage.fetch_developments(cs_player_id(source_player_id, league))
    provider = StoredDevelopmentProvider(developments)

    metadata = storage.fetch_league_metadata(league, season)
    season_state = resolve_season_state(
        league,
        season=season,
        metadata=metadata,
        player_games_recent=stats_7d.games,
    )
    state = season_state_value or season_state.state

    drivers = build_player_signal_drivers(
        player_name=player_name,
        source_player_id=source_player_id,
        league=league,
        stats_7d=stats_7d,
        stats_30d=stats_30d,
        market_snapshots=market_snapshots,
        season=season,
        season_state=state,  # type: ignore[arg-type]
        development_provider=provider,
    )
    return storage.append_drivers(drivers)
