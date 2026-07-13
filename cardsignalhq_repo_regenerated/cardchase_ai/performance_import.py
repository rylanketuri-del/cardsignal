"""Validated previous-season performance import for NFL and NBA."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from cardchase_ai.identity import cs_nba_player_id, cs_nfl_player_id
from cardchase_ai.models.nba import map_nba_position
from cardchase_ai.models.nfl import map_nfl_position
from cardchase_ai.models.performance import PreviousSeasonPerformanceSnapshot
from cardchase_ai.performance_storage import PerformanceStorage

SUPPORTED_LEAGUES = frozenset({"NFL", "NBA"})

NFL_QB_STATS = frozenset({
    "games_played", "starts", "passing_yards", "passing_touchdowns", "interceptions",
    "completion_percentage", "yards_per_attempt", "passer_rating",
    "rushing_yards", "rushing_touchdowns", "fumbles",
})
NFL_RB_STATS = frozenset({
    "games_played", "starts", "rushing_attempts", "rushing_yards", "rushing_touchdowns",
    "yards_per_carry", "targets", "receptions", "receiving_yards", "receiving_touchdowns",
    "total_yards", "total_touchdowns", "fumbles",
})
NFL_WR_TE_STATS = frozenset({
    "games_played", "starts", "targets", "receptions", "receiving_yards", "receiving_touchdowns",
    "yards_per_reception", "catch_rate", "rushing_yards", "total_touchdowns", "fumbles",
})

NBA_PER_GAME_STATS = frozenset({
    "games_played", "games_started", "minutes_per_game", "points_per_game",
    "rebounds_per_game", "assists_per_game", "steals_per_game", "blocks_per_game",
    "turnovers_per_game", "field_goal_percentage", "three_point_percentage", "free_throw_percentage",
})

PERCENTAGE_FIELDS = frozenset({
    "completion_percentage", "catch_rate", "field_goal_percentage",
    "three_point_percentage", "free_throw_percentage",
})


class ImportRowError(BaseModel):
    row_index: int
    source_player_id: str | None = None
    error: str


class PerformanceImportSummary(BaseModel):
    league: str
    season: int
    period_type: str = "PREVIOUS_SEASON"
    source_method: str
    rows_received: int = 0
    rows_imported: int = 0
    rows_updated: int = 0
    rows_skipped: int = 0
    rows_failed: int = 0
    errors: list[ImportRowError] = Field(default_factory=list)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def resolve_cs_player_id(league: str, source_player_id: str) -> str:
    league_upper = league.upper()
    if league_upper == "NFL":
        return cs_nfl_player_id(source_player_id)
    if league_upper == "NBA":
        return cs_nba_player_id(source_player_id)
    raise ValueError(f"Unsupported league: {league}")


def _sport_for_league(league: str) -> str:
    return {"NFL": "FOOTBALL", "NBA": "BASKETBALL"}[league.upper()]


def _validate_nonnegative(value: Any, field: str) -> str | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return f"{field} must be numeric"
    if numeric < 0:
        return f"{field} must be nonnegative"
    return None


def _validate_percentage(value: Any, field: str) -> str | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return f"{field} must be numeric"
    if numeric < 0:
        return f"{field} must be nonnegative"
    if numeric > 1:
        return f"{field} must be between 0 and 1"
    return None


def _extract_stats(row: dict[str, Any]) -> dict[str, Any]:
    stats = row.get("stats")
    if isinstance(stats, dict):
        return dict(stats)
    known = {k: v for k, v in row.items() if k not in {
        "source_player_id", "player_name", "league", "season", "position", "team",
        "games_played", "starts", "games_started", "source_method", "source_reference",
        "provider_updated_at", "data_quality", "headshot_url", "team_logo_url", "cs_player_id",
        "period_type", "sport",
    }}
    return known


def _nfl_allowed_stats(position_group: str) -> frozenset[str]:
    if position_group == "QB":
        return NFL_QB_STATS
    if position_group == "RB":
        return NFL_RB_STATS
    if position_group in {"WR", "TE"}:
        return NFL_WR_TE_STATS
    return NFL_QB_STATS | NFL_RB_STATS | NFL_WR_TE_STATS


def validate_import_row(
    row: dict[str, Any],
    *,
    league: str,
    season: int,
    row_index: int = 0,
) -> tuple[PreviousSeasonPerformanceSnapshot | None, ImportRowError | None]:
    league_upper = league.upper()
    if league_upper not in SUPPORTED_LEAGUES:
        return None, ImportRowError(row_index=row_index, error=f"Unsupported league: {league}")

    source_id = str(row.get("source_player_id") or "").strip()
    if not source_id:
        return None, ImportRowError(row_index=row_index, error="source_player_id is required")

    row_season = row.get("season", season)
    try:
        row_season = int(row_season)
    except (TypeError, ValueError):
        return None, ImportRowError(row_index=row_index, source_player_id=source_id, error="Invalid season")

    if row_season != season:
        return None, ImportRowError(
            row_index=row_index,
            source_player_id=source_id,
            error=f"Season mismatch: row={row_season}, import={season}",
        )

    position = row.get("position")
    if league_upper == "NFL":
        position_group = map_nfl_position(position)
    else:
        position_group = map_nba_position(position)

    if not position:
        return None, ImportRowError(row_index=row_index, source_player_id=source_id, error="position is required")

    stats = _extract_stats(row)
    games_played = row.get("games_played", stats.get("games_played"))
    if games_played is None:
        return None, ImportRowError(row_index=row_index, source_player_id=source_id, error="games_played is required")
    try:
        games_played = int(games_played)
    except (TypeError, ValueError):
        return None, ImportRowError(row_index=row_index, source_player_id=source_id, error="games_played must be integer")

    if league_upper == "NFL":
        allowed = _nfl_allowed_stats(position_group)
    else:
        allowed = NBA_PER_GAME_STATS

    for key, value in stats.items():
        if key not in allowed and key != "games_played":
            continue
        err = _validate_nonnegative(value, key)
        if err:
            return None, ImportRowError(row_index=row_index, source_player_id=source_id, error=err)
        if key in PERCENTAGE_FIELDS:
            err = _validate_percentage(value, key)
            if err:
                return None, ImportRowError(row_index=row_index, source_player_id=source_id, error=err)

    starts = row.get("starts")
    if starts is not None:
        try:
            starts = int(starts)
            if starts < 0:
                return None, ImportRowError(row_index=row_index, source_player_id=source_id, error="starts must be nonnegative")
        except (TypeError, ValueError):
            return None, ImportRowError(row_index=row_index, source_player_id=source_id, error="starts must be integer")

    source_method = str(row.get("source_method") or "APPROVED_IMPORT").upper()
    if source_method not in {"OFFICIAL_API", "LICENSED_API", "APPROVED_IMPORT", "MANUAL_VERIFIED"}:
        return None, ImportRowError(row_index=row_index, source_player_id=source_id, error="Invalid source_method")

    data_quality = str(row.get("data_quality") or "MEDIUM").upper()
    if data_quality not in {"HIGH", "MEDIUM", "LOW", "INSUFFICIENT"}:
        data_quality = "MEDIUM"

    cs_id = row.get("cs_player_id") or resolve_cs_player_id(league_upper, source_id)

    snapshot = PreviousSeasonPerformanceSnapshot(
        cs_player_id=str(cs_id),
        source_player_id=source_id,
        league=league_upper,
        sport=_sport_for_league(league_upper),
        season=row_season,
        position=str(position) if position else None,
        team=row.get("team"),
        games_played=games_played,
        starts=int(starts) if starts is not None else None,
        stats={k: v for k, v in stats.items() if v is not None},
        data_quality=data_quality,  # type: ignore[arg-type]
        source_method=source_method,  # type: ignore[arg-type]
        source_reference=str(row.get("source_reference") or ""),
        provider_updated_at=row.get("provider_updated_at"),
        captured_at=_utcnow(),
        player_name=row.get("player_name"),
        headshot_url=row.get("headshot_url"),
        team_logo_url=row.get("team_logo_url"),
    )
    return snapshot, None


def import_performance_records(
    storage: PerformanceStorage,
    *,
    league: str,
    season: int,
    records: list[dict[str, Any]],
    source_method: str = "APPROVED_IMPORT",
    period_type: Literal["PREVIOUS_SEASON"] = "PREVIOUS_SEASON",
) -> PerformanceImportSummary:
    if period_type != "PREVIOUS_SEASON":
        raise ValueError("Only PREVIOUS_SEASON imports are supported in Sprint 11.3")

    summary = PerformanceImportSummary(
        league=league.upper(),
        season=season,
        source_method=source_method,
        rows_received=len(records),
    )

    for index, row in enumerate(records):
        merged = dict(row)
        if "source_method" not in merged:
            merged["source_method"] = source_method
        snapshot, error = validate_import_row(merged, league=league, season=season, row_index=index)
        if error:
            summary.rows_failed += 1
            summary.errors.append(error)
            continue

        assert snapshot is not None
        existing = storage.get_previous_season(league, snapshot.cs_player_id, season)
        storage.upsert_snapshot(snapshot)
        if existing:
            summary.rows_updated += 1
        else:
            summary.rows_imported += 1

    return summary


def parse_csv_records(content: str) -> list[dict[str, Any]]:
    """Parse simple CSV with header row into import records."""
    import csv
    import io

    reader = csv.DictReader(io.StringIO(content))
    records: list[dict[str, Any]] = []
    for row in reader:
        record: dict[str, Any] = {}
        stats: dict[str, Any] = {}
        stat_prefix = "stat_"
        for key, value in row.items():
            if not key or value is None or value == "":
                continue
            normalized_key = key.strip()
            if normalized_key.startswith(stat_prefix):
                stats[normalized_key[len(stat_prefix):]] = _coerce_value(value)
            else:
                record[normalized_key] = _coerce_value(value)
        if stats:
            record["stats"] = stats
        records.append(record)
    return records


def _coerce_value(value: str) -> Any:
    text = str(value).strip()
    if text.lower() in {"true", "false"}:
        return text.lower() == "true"
    try:
        if "." in text:
            return float(text)
        return int(text)
    except ValueError:
        return text
