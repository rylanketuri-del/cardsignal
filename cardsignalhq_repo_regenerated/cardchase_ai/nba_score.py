"""Position-aware NBA performance scoring (NBA_PERFORMANCE_V1)."""

from __future__ import annotations

from typing import Any

from cardchase_ai.models.nba import (
    NBA_PERFORMANCE_V1,
    NBADataQuality,
    NBAGameLogRow,
    NBAPerformanceSnapshot,
    NBAPosition,
    SUPPORTED_POSITIONS,
)
from cardchase_ai.score import clamp_score
from cardchase_ai.utils.nba_rolling import (
    aggregate_basketball_stats,
    build_performance_window,
    evaluate_window_quality,
    recent_window_value,
    select_recent_games,
)


def _threshold_score(value: float | None, thresholds: list[tuple[float, float]]) -> float | None:
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


def score_nba_performance(
    position: NBAPosition,
    recent_stats: dict[str, Any],
    season_stats: dict[str, Any] | None,
    *,
    games_in_window: int,
) -> tuple[float | None, dict[str, float], list[str], NBADataQuality, list[str]]:
    """Score NBA performance from stored basketball metrics only."""
    missing: list[str] = []
    if position not in SUPPORTED_POSITIONS:
        return None, {}, [], "INSUFFICIENT", ["unsupported_position"]

    if games_in_window <= 0:
        missing.append("recent_games")
        return None, {}, [], "INSUFFICIENT", missing

    quality = evaluate_window_quality(games_in_window)

    games = int(recent_stats.get("games_played", 0))
    ppg = recent_stats.get("points_per_game")
    rpg = recent_stats.get("rebounds_per_game")
    apg = recent_stats.get("assists_per_game")
    spg = recent_stats.get("steals_per_game")
    bpg = recent_stats.get("blocks_per_game")
    mpg = recent_stats.get("minutes_per_game")
    fg_pct = recent_stats.get("field_goal_percentage")
    tp_pct = recent_stats.get("three_point_percentage")
    ft_pct = recent_stats.get("free_throw_percentage")
    turnovers = recent_stats.get("turnovers", 0)
    tpg = (turnovers / games) if games else None

    scoring = _threshold_score(ppg, [(12, 40), (18, 60), (22, 75), (28, 90)])
    playmaking = _threshold_score(apg, [(3, 40), (5, 60), (7, 75), (9, 90)])
    rebounding = _threshold_score(rpg, [(4, 40), (6, 60), (8, 75), (11, 90)])
    defense = _threshold_score(
        (spg + bpg) if spg is not None and bpg is not None else None,
        [(1.0, 40), (1.5, 60), (2.0, 75), (3.0, 90)],
    )
    efficiency = _threshold_score(fg_pct, [(42, 40), (45, 60), (48, 75), (52, 90)])
    if efficiency is None:
        efficiency = _threshold_score(tp_pct, [(32, 40), (36, 60), (38, 75), (42, 90)])
    free_throw = _threshold_score(ft_pct, [(70, 40), (78, 60), (85, 75), (90, 90)])
    ball_security = _threshold_score(
        max(0, 5 - (tpg or 0)),
        [(0, 30), (1, 50), (2, 70), (3, 90)],
    )
    workload = _threshold_score(mpg, [(20, 40), (28, 60), (32, 75), (36, 90)])
    momentum = _momentum_component(recent_stats, season_stats, "points")

    score, reasons = _weighted_score([
        (scoring, 0.25),
        (playmaking, 0.15),
        (rebounding, 0.12),
        (defense, 0.10),
        (efficiency, 0.12),
        (free_throw, 0.06),
        (ball_security, 0.08),
        (workload, 0.07),
        (momentum, 0.05),
    ])
    normalized = {
        k: v for k, v in {
            "scoring": scoring,
            "playmaking": playmaking,
            "rebounding": rebounding,
            "defense": defense,
            "efficiency": efficiency,
            "free_throw": free_throw,
            "ball_security": ball_security,
            "workload": workload,
            "momentum": momentum,
        }.items() if v is not None
    }

    if score is None:
        missing.append("performance_metrics")
        quality = "INSUFFICIENT"

    return score, normalized, reasons, quality, missing


def build_nba_performance_snapshot(
    *,
    cs_player_id: str,
    source_player_id: str,
    season: int,
    position: str | None,
    position_group: NBAPosition,
    period_type: str,
    games: list,
    season_stats: dict[str, Any] | None,
    source_method: str,
) -> NBAPerformanceSnapshot:
    game_rows = [g if isinstance(g, NBAGameLogRow) else NBAGameLogRow.model_validate(g) for g in games]
    window = build_performance_window(game_rows, source_method=source_method)  # type: ignore[arg-type]
    recent_games = select_recent_games(game_rows)
    recent_stats = aggregate_basketball_stats(recent_games)

    if period_type == "REGULAR_SEASON" and season_stats:
        stats = season_stats
        games_played = int(season_stats.get("games_played", 0))
    else:
        stats = recent_stats
        games_played = int(recent_stats.get("games_played", 0))

    score, normalized, reasons, quality, missing = score_nba_performance(
        position_group,
        recent_stats if period_type != "REGULAR_SEASON" else stats,
        season_stats,
        games_in_window=window.games_in_window,
    )

    explanation = None
    if position_group not in SUPPORTED_POSITIONS:
        explanation = "Position scoring is not available for this player."
        score = None
        quality = "INSUFFICIENT"

    dates = [g.game_date for g in recent_games if g.game_date]

    return NBAPerformanceSnapshot(
        cs_player_id=cs_player_id,
        source_player_id=source_player_id,
        season=season,
        position=position,
        position_group=position_group,
        period_type=period_type,  # type: ignore[arg-type]
        period_start=min(dates) if dates else None,
        period_end=max(dates) if dates else None,
        games_played=games_played,
        stats=stats,
        normalized_metrics=normalized,
        performance_score=score,
        data_quality=quality,
        missing_inputs=missing,
        source_method=source_method,  # type: ignore[arg-type]
        algorithm_version=NBA_PERFORMANCE_V1,
        explanation=explanation,
    )
