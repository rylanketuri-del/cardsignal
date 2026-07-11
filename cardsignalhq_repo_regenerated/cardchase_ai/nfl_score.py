"""Position-aware NFL performance scoring."""

from __future__ import annotations

from typing import Any

from cardchase_ai.models.nfl import (
    NFL_PERFORMANCE_V1,
    NFLDataQuality,
    NFLPerformanceSnapshot,
    NFLPositionGroup,
    OFFENSIVE_POSITIONS,
)
from cardchase_ai.score import clamp_score
from cardchase_ai.utils.nfl_rolling import aggregate_position_stats, evaluate_window_quality


def _threshold_score(value: float | None, thresholds: list[tuple[float, float]]) -> float | None:
    """Map a raw stat to 0-100 using deterministic thresholds (beta, not percentile)."""
    if value is None:
        return None
    score = 0.0
    for threshold, points in thresholds:
        if value >= threshold:
            score = points
    return clamp_score(score)


def _weighted_score(components: list[tuple[float | None, float]]) -> tuple[float | None, list[str]]:
    available = [(score, weight) for score, weight in components if score is not None]
    if not available:
        return None, []
    total_weight = sum(w for _, w in available)
    if total_weight <= 0:
        return None, []
    score = sum(s * w for s, w in available) / total_weight
    reasons = [f"component_{i}" for i, (s, _) in enumerate(available) if s >= 70]
    return round(clamp_score(score), 2), reasons


def score_qb_performance(recent_stats: dict[str, Any], season_stats: dict[str, Any] | None) -> tuple[float | None, dict[str, float], list[str]]:
    passing_yards = recent_stats.get("passing_yards")
    pass_tds = recent_stats.get("passing_touchdowns")
    ints = recent_stats.get("interceptions")
    ypa = recent_stats.get("yards_per_attempt")
    rating = recent_stats.get("passer_rating")
    rush_yds = recent_stats.get("rushing_yards")
    fumbles = recent_stats.get("fumbles")
    games = recent_stats.get("games_played", 0)

    passing_prod = _threshold_score(
        (passing_yards / games) if games else None,
        [(150, 40), (200, 60), (250, 75), (300, 90)],
    )
    td_prod = _threshold_score(
        (pass_tds / games) if games else None,
        [(1, 50), (2, 70), (3, 85), (4, 95)],
    )
    efficiency = _threshold_score(ypa, [(6.0, 40), (7.0, 60), (7.5, 75), (8.5, 90)])
    if efficiency is None and rating is not None:
        efficiency = _threshold_score(rating, [(80, 40), (90, 60), (100, 80), (110, 95)])
    ball_security = _threshold_score(
        max(0, 3 - (ints or 0) - (fumbles or 0)),
        [(0, 30), (1, 50), (2, 70), (3, 90)],
    )
    rushing = _threshold_score(
        (rush_yds / games) if games else None,
        [(10, 40), (25, 60), (40, 75), (60, 90)],
    )
    momentum = _momentum_component(recent_stats, season_stats, "passing_yards")

    score, reasons = _weighted_score([
        (passing_prod, 0.25),
        (td_prod, 0.20),
        (efficiency, 0.20),
        (ball_security, 0.15),
        (rushing, 0.10),
        (momentum, 0.10),
    ])
    normalized = {
        k: v for k, v in {
            "passing_production": passing_prod,
            "touchdown_production": td_prod,
            "efficiency": efficiency,
            "ball_security": ball_security,
            "rushing_contribution": rushing,
            "momentum": momentum,
        }.items() if v is not None
    }
    return score, normalized, reasons


def score_rb_performance(recent_stats: dict[str, Any], season_stats: dict[str, Any] | None) -> tuple[float | None, dict[str, float], list[str]]:
    games = recent_stats.get("games_played", 0)
    rush_yds = recent_stats.get("rushing_yards")
    rush_tds = recent_stats.get("rushing_touchdowns")
    ypc = recent_stats.get("yards_per_carry")
    rec_yds = recent_stats.get("receiving_yards")
    total_tds = recent_stats.get("total_touchdowns")
    fumbles = recent_stats.get("fumbles")

    rushing_prod = _threshold_score(
        (rush_yds / games) if games else None,
        [(50, 40), (75, 60), (100, 75), (125, 90)],
    )
    receiving = _threshold_score(
        (rec_yds / games) if games else None,
        [(15, 40), (30, 60), (50, 75), (75, 90)],
    )
    td_prod = _threshold_score(
        (total_tds / games) if games else None,
        [(0.5, 50), (1, 70), (1.5, 85), (2, 95)],
    )
    efficiency = _threshold_score(ypc, [(3.5, 40), (4.0, 60), (4.5, 75), (5.5, 90)])
    ball_security = _threshold_score(
        max(0, 2 - (fumbles or 0)),
        [(0, 40), (1, 65), (2, 90)],
    )
    momentum = _momentum_component(recent_stats, season_stats, "rushing_yards")

    score, reasons = _weighted_score([
        (rushing_prod, 0.30),
        (receiving, 0.15),
        (td_prod, 0.20),
        (efficiency, 0.15),
        (ball_security, 0.10),
        (momentum, 0.10),
    ])
    normalized = {
        k: v for k, v in {
            "rushing_production": rushing_prod,
            "receiving_contribution": receiving,
            "touchdown_production": td_prod,
            "efficiency": efficiency,
            "ball_security": ball_security,
            "momentum": momentum,
        }.items() if v is not None
    }
    return score, normalized, reasons


def score_receiver_performance(recent_stats: dict[str, Any], season_stats: dict[str, Any] | None) -> tuple[float | None, dict[str, float], list[str]]:
    games = recent_stats.get("games_played", 0)
    targets = recent_stats.get("targets")
    receptions = recent_stats.get("receptions")
    rec_yds = recent_stats.get("receiving_yards")
    rec_tds = recent_stats.get("receiving_touchdowns")
    ypr = recent_stats.get("yards_per_reception")
    catch_rate = recent_stats.get("catch_rate")
    fumbles = recent_stats.get("fumbles")

    receiving_prod = _threshold_score(
        (rec_yds / games) if games else None,
        [(40, 40), (60, 60), (80, 75), (100, 90)],
    )
    activity = _threshold_score(
        (targets / games) if games else None,
        [(5, 40), (7, 60), (9, 75), (12, 90)],
    )
    td_prod = _threshold_score(
        (rec_tds / games) if games else None,
        [(0.5, 50), (1, 75), (1.5, 90)],
    )
    efficiency = _threshold_score(ypr, [(10, 40), (12, 60), (14, 75), (16, 90)])
    if efficiency is None and catch_rate is not None:
        efficiency = _threshold_score(catch_rate, [(60, 40), (70, 60), (75, 75), (80, 90)])
    ball_security = _threshold_score(
        max(0, 2 - (fumbles or 0)),
        [(0, 40), (1, 65), (2, 90)],
    )
    momentum = _momentum_component(recent_stats, season_stats, "receiving_yards")

    score, reasons = _weighted_score([
        (receiving_prod, 0.30),
        (activity, 0.15),
        (td_prod, 0.20),
        (efficiency, 0.15),
        (ball_security, 0.10),
        (momentum, 0.10),
    ])
    normalized = {
        k: v for k, v in {
            "receiving_production": receiving_prod,
            "target_activity": activity,
            "touchdown_production": td_prod,
            "efficiency": efficiency,
            "ball_security": ball_security,
            "momentum": momentum,
        }.items() if v is not None
    }
    return score, normalized, reasons


def _momentum_component(
    recent: dict[str, Any],
    season: dict[str, Any] | None,
    key: str,
) -> float | None:
    if not season:
        return None
    recent_games = recent.get("games_played", 0)
    season_games = season.get("games_played", 0)
    if recent_games <= 0 or season_games <= 0:
        return None
    recent_pace = recent.get(key, 0) / recent_games
    season_pace = season.get(key, 0) / season_games
    if season_pace <= 0:
        return None
    ratio = recent_pace / season_pace
    return clamp_score(50 + (ratio - 1) * 40)


def score_nfl_performance(
    position_group: NFLPositionGroup,
    recent_stats: dict[str, Any],
    season_stats: dict[str, Any] | None,
    *,
    games_in_window: int,
) -> tuple[float | None, dict[str, float], list[str], NFLDataQuality, list[str]]:
    """Score NFL performance from stored football metrics only."""
    missing: list[str] = []
    if position_group not in OFFENSIVE_POSITIONS:
        return None, {}, [], "INSUFFICIENT", ["unsupported_position"]

    if games_in_window <= 0:
        missing.append("recent_games")
        return None, {}, [], "INSUFFICIENT", missing

    quality = evaluate_window_quality(games_in_window)

    if position_group == "QB":
        score, normalized, reasons = score_qb_performance(recent_stats, season_stats)
    elif position_group == "RB":
        score, normalized, reasons = score_rb_performance(recent_stats, season_stats)
    elif position_group in {"WR", "TE"}:
        score, normalized, reasons = score_receiver_performance(recent_stats, season_stats)
    else:
        return None, {}, [], "INSUFFICIENT", ["unsupported_position"]

    if score is None:
        missing.append("performance_metrics")
        quality = "INSUFFICIENT"

    return score, normalized, reasons, quality, missing


def build_nfl_performance_snapshot(
    *,
    cs_player_id: str,
    source_player_id: str,
    season: int,
    position: str | None,
    position_group: NFLPositionGroup,
    period_type: str,
    games: list,
    season_stats: dict[str, Any] | None,
    source_method: str,
) -> NFLPerformanceSnapshot:
    from cardchase_ai.models.nfl import NFLGameLogRow
    from cardchase_ai.utils.nfl_rolling import build_performance_window, select_recent_games

    game_rows = [g if isinstance(g, NFLGameLogRow) else NFLGameLogRow.model_validate(g) for g in games]
    window = build_performance_window(game_rows, source_method=source_method)
    recent_games = select_recent_games(game_rows, limit=3)
    recent_stats = aggregate_position_stats(position_group, recent_games)

    if period_type == "REGULAR_SEASON" and season_stats:
        stats = season_stats
        games_played = int(season_stats.get("games_played", 0))
    else:
        stats = recent_stats
        games_played = int(recent_stats.get("games_played", 0))

    score, normalized, reasons, quality, missing = score_nfl_performance(
        position_group,
        recent_stats if period_type != "REGULAR_SEASON" else stats,
        season_stats,
        games_in_window=window.games_in_window,
    )

    explanation = None
    if position_group not in OFFENSIVE_POSITIONS:
        explanation = "Position scoring is not available yet."
        score = None
        quality = "INSUFFICIENT"

    dates = [g.game_date for g in recent_games if g.game_date]

    return NFLPerformanceSnapshot(
        cs_player_id=cs_player_id,
        source_player_id=source_player_id,
        season=season,
        position=position,
        position_group=position_group,
        period_type=period_type,
        period_start=min(dates) if dates else None,
        period_end=max(dates) if dates else None,
        games_played=games_played,
        stats=stats,
        normalized_metrics=normalized,
        performance_score=score,
        data_quality=quality,
        missing_inputs=missing,
        source_method=source_method,
        algorithm_version=NFL_PERFORMANCE_V1,
        explanation=explanation,
    )
