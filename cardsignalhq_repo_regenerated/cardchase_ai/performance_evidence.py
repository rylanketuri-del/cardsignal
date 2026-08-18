"""Normalized performance evidence builders for MLB and NFL."""

from __future__ import annotations

from typing import Any

from cardchase_ai.models.intelligence import EvidenceImpact, EvidenceQuality, NormalizedPerformanceEvidence
from cardchase_ai.models.nfl import NFLPerformanceSnapshot, map_nfl_position
from cardchase_ai.models.performance import PreviousSeasonPerformanceSnapshot
from cardchase_ai.models.schemas import RollingHitterStats


def _impact_from_delta(delta: float, threshold: float = 0.0) -> EvidenceImpact:
    if delta > threshold:
        return "positive"
    if delta < -threshold:
        return "negative"
    return "neutral"


def _quality_from_games(games: int) -> EvidenceQuality:
    if games >= 5:
        return "HIGH"
    if games >= 3:
        return "MEDIUM"
    if games >= 1:
        return "LOW"
    return "INSUFFICIENT"


def build_mlb_recent_evidence(
    stats_7d: RollingHitterStats,
    stats_30d: RollingHitterStats,
    *,
    period_start: str | None = None,
    period_end: str | None = None,
) -> list[NormalizedPerformanceEvidence]:
    """Structured recent-performance evidence for MLB hitters."""
    if stats_7d.games == 0:
        return []

    quality = _quality_from_games(stats_7d.games)
    evidence: list[NormalizedPerformanceEvidence] = []

    ops_delta = stats_7d.ops - stats_30d.ops if stats_30d.games > 0 else 0.0
    evidence.append(NormalizedPerformanceEvidence(
        metric="ops",
        label="OPS (Last 7 Days)",
        value=round(stats_7d.ops, 3),
        comparison_value=round(stats_30d.ops, 3) if stats_30d.games > 0 else None,
        period_type="LAST_7_DAYS",
        period_start=period_start,
        period_end=period_end,
        impact=_impact_from_delta(ops_delta, 0.05),
        quality=quality,
        source_reference="mlb_stats_api:rolling_7d",
    ))

    if stats_7d.home_runs > 0:
        evidence.append(NormalizedPerformanceEvidence(
            metric="home_runs",
            label="Home Runs (Last 7 Days)",
            value=stats_7d.home_runs,
            comparison_value=stats_30d.home_runs if stats_30d.games > 0 else None,
            period_type="LAST_7_DAYS",
            period_start=period_start,
            period_end=period_end,
            impact="positive" if stats_7d.home_runs >= 2 else "neutral",
            quality=quality,
            source_reference="mlb_stats_api:rolling_7d",
        ))

    if stats_7d.stolen_bases > 0:
        evidence.append(NormalizedPerformanceEvidence(
            metric="stolen_bases",
            label="Stolen Bases (Last 7 Days)",
            value=stats_7d.stolen_bases,
            period_type="LAST_7_DAYS",
            period_start=period_start,
            period_end=period_end,
            impact="positive",
            quality=quality,
            source_reference="mlb_stats_api:rolling_7d",
        ))

    evidence.append(NormalizedPerformanceEvidence(
        metric="avg",
        label="Batting Average (Last 7 Days)",
        value=round(stats_7d.avg, 3),
        comparison_value=round(stats_30d.avg, 3) if stats_30d.games > 0 else None,
        period_type="LAST_7_DAYS",
        period_start=period_start,
        period_end=period_end,
        impact=_impact_from_delta(stats_7d.avg - stats_30d.avg, 0.02) if stats_30d.games > 0 else "neutral",
        quality=quality,
        source_reference="mlb_stats_api:rolling_7d",
    ))

    return evidence


def build_mlb_season_evidence(
    stats_season: RollingHitterStats | None,
    *,
    period_start: str | None = None,
    period_end: str | None = None,
) -> list[NormalizedPerformanceEvidence]:
    """Structured full-season evidence for MLB (unfiltered season gamelog)."""
    if not stats_season or stats_season.games == 0:
        return []

    quality = _quality_from_games(stats_season.games)
    return [
        NormalizedPerformanceEvidence(
            metric="avg",
            label="AVG (Season)",
            value=round(stats_season.avg, 3),
            period_type="REGULAR_SEASON",
            period_start=period_start,
            period_end=period_end,
            impact="neutral",
            quality=quality,
            source_reference="mlb_stats_api:season",
        ),
        NormalizedPerformanceEvidence(
            metric="home_runs",
            label="Home Runs (Season)",
            value=stats_season.home_runs,
            period_type="REGULAR_SEASON",
            period_start=period_start,
            period_end=period_end,
            impact="positive" if stats_season.home_runs >= 15 else "neutral",
            quality=quality,
            source_reference="mlb_stats_api:season",
        ),
        NormalizedPerformanceEvidence(
            metric="rbi",
            label="RBI (Season)",
            value=stats_season.rbi,
            period_type="REGULAR_SEASON",
            period_start=period_start,
            period_end=period_end,
            impact="neutral",
            quality=quality,
            source_reference="mlb_stats_api:season",
        ),
        NormalizedPerformanceEvidence(
            metric="ops",
            label="OPS (Season)",
            value=round(stats_season.ops, 3),
            period_type="REGULAR_SEASON",
            period_start=period_start,
            period_end=period_end,
            impact="neutral",
            quality=quality,
            source_reference="mlb_stats_api:season",
        ),
        NormalizedPerformanceEvidence(
            metric="games",
            label="Games (Season)",
            value=stats_season.games,
            period_type="REGULAR_SEASON",
            period_start=period_start,
            period_end=period_end,
            impact="neutral",
            quality=quality,
            source_reference="mlb_stats_api:season",
        ),
        NormalizedPerformanceEvidence(
            metric="obp",
            label="OBP (Season)",
            value=round(stats_season.obp, 3),
            period_type="REGULAR_SEASON",
            period_start=period_start,
            period_end=period_end,
            impact="neutral",
            quality=quality,
            source_reference="mlb_stats_api:season",
        ),
        NormalizedPerformanceEvidence(
            metric="slg",
            label="SLG (Season)",
            value=round(stats_season.slg, 3),
            period_type="REGULAR_SEASON",
            period_start=period_start,
            period_end=period_end,
            impact="neutral",
            quality=quality,
            source_reference="mlb_stats_api:season",
        ),
    ]


def _nfl_metric_evidence(
    metric: str,
    label: str,
    value: Any,
    *,
    snapshot: NFLPerformanceSnapshot,
    comparison: Any = None,
    impact: EvidenceImpact = "neutral",
) -> NormalizedPerformanceEvidence | None:
    if value is None:
        return None
    return NormalizedPerformanceEvidence(
        metric=metric,
        label=label,
        value=value,
        comparison_value=comparison,
        period_type=snapshot.period_type,
        period_start=snapshot.period_start,
        period_end=snapshot.period_end,
        impact=impact,
        quality=snapshot.data_quality,
        source_reference=f"nfl_import:{snapshot.period_type.lower()}",
    )


def build_nfl_performance_evidence(snapshot: NFLPerformanceSnapshot | None) -> list[NormalizedPerformanceEvidence]:
    """Position-aware NFL evidence from stored performance snapshots."""
    if not snapshot or snapshot.games_played == 0:
        return []

    stats = snapshot.stats
    group = snapshot.position_group
    evidence: list[NormalizedPerformanceEvidence] = []

    games = snapshot.games_played
    if group == "QB":
        for metric, label, key in [
            ("passing_yards_per_game", "Passing Yards/G", "passing_yards"),
            ("passing_touchdowns", "Passing TDs", "passing_touchdowns"),
            ("passer_rating", "Passer Rating", "passer_rating"),
        ]:
            raw = stats.get(key)
            if raw is None:
                continue
            val = round(raw / games, 1) if key == "passing_yards" and games else raw
            item = _nfl_metric_evidence(metric, label, val, snapshot=snapshot)
            if item:
                evidence.append(item)
    elif group == "RB":
        rush = stats.get("rushing_yards")
        if rush is not None and games:
            evidence.append(_nfl_metric_evidence(
                "rushing_yards_per_game",
                "Rushing Yards/G",
                round(rush / games, 1),
                snapshot=snapshot,
                impact="positive" if rush / games >= 80 else "neutral",
            ))
        tds = stats.get("rushing_touchdowns")
        if tds is not None:
            evidence.append(_nfl_metric_evidence("rushing_touchdowns", "Rushing TDs", tds, snapshot=snapshot))
    elif group in {"WR", "TE"}:
        rec = stats.get("receiving_yards")
        if rec is not None and games:
            evidence.append(_nfl_metric_evidence(
                "receiving_yards_per_game",
                "Receiving Yards/G",
                round(rec / games, 1),
                snapshot=snapshot,
                impact="positive" if rec / games >= 70 else "neutral",
            ))
        targets = stats.get("targets")
        if targets is not None and games:
            evidence.append(_nfl_metric_evidence(
                "targets_per_game",
                "Targets/G",
                round(targets / games, 1),
                snapshot=snapshot,
            ))

    if not evidence and stats:
        games_item = _nfl_metric_evidence("games_played", "Games Played", games, snapshot=snapshot)
        if games_item:
            evidence.append(games_item)

    return evidence


def _previous_season_metric(
    metric: str,
    label: str,
    value: Any,
    *,
    snapshot: PreviousSeasonPerformanceSnapshot,
    source_ref: str,
) -> NormalizedPerformanceEvidence | None:
    if value is None:
        return None
    return NormalizedPerformanceEvidence(
        metric=metric,
        label=label,
        value=value,
        period_type="PREVIOUS_SEASON",
        impact="neutral",
        quality=snapshot.data_quality,
        source_reference=source_ref or f"{snapshot.source_method.lower()}:previous_season",
    )


def build_nfl_previous_season_evidence(
    snapshot: PreviousSeasonPerformanceSnapshot | None,
) -> list[NormalizedPerformanceEvidence]:
    """Position-aware previous-season NFL evidence — never labeled as recent form."""
    if not snapshot or snapshot.games_played == 0:
        return []

    stats = snapshot.stats
    group = map_nfl_position(snapshot.position)
    games = snapshot.games_played
    source_ref = snapshot.source_reference or f"{snapshot.source_method}:nfl:{snapshot.season}"
    evidence: list[NormalizedPerformanceEvidence] = []

    metric_map: list[tuple[str, str, str]] = []
    if group == "QB":
        metric_map = [
            ("passing_yards", "Passing Yards", "passing_yards"),
            ("passing_touchdowns", "Passing TDs", "passing_touchdowns"),
            ("interceptions", "Interceptions", "interceptions"),
            ("completion_percentage", "Completion %", "completion_percentage"),
            ("passer_rating", "Passer Rating", "passer_rating"),
            ("rushing_yards", "Rushing Yards", "rushing_yards"),
        ]
    elif group == "RB":
        metric_map = [
            ("rushing_yards", "Rushing Yards", "rushing_yards"),
            ("rushing_touchdowns", "Rushing TDs", "rushing_touchdowns"),
            ("yards_per_carry", "Yards Per Carry", "yards_per_carry"),
            ("receptions", "Receptions", "receptions"),
            ("receiving_yards", "Receiving Yards", "receiving_yards"),
            ("total_touchdowns", "Total TDs", "total_touchdowns"),
        ]
    elif group in {"WR", "TE"}:
        metric_map = [
            ("receptions", "Receptions", "receptions"),
            ("receiving_yards", "Receiving Yards", "receiving_yards"),
            ("receiving_touchdowns", "Receiving TDs", "receiving_touchdowns"),
            ("yards_per_reception", "Yards Per Reception", "yards_per_reception"),
            ("catch_rate", "Catch Rate", "catch_rate"),
            ("targets", "Targets", "targets"),
        ]
    else:
        metric_map = [("games_played", "Games Played", "games_played")]

    for metric, label, key in metric_map:
        raw = stats.get(key)
        if raw is None:
            continue
        item = _previous_season_metric(metric, label, raw, snapshot=snapshot, source_ref=source_ref)
        if item:
            evidence.append(item)

    gp = _previous_season_metric("games_played", "Games Played", games, snapshot=snapshot, source_ref=source_ref)
    if gp and not any(e.metric == "games_played" for e in evidence):
        evidence.insert(0, gp)

    if snapshot.starts is not None:
        starts = _previous_season_metric("starts", "Starts", snapshot.starts, snapshot=snapshot, source_ref=source_ref)
        if starts:
            evidence.append(starts)

    return evidence


def build_nba_previous_season_evidence(
    snapshot: PreviousSeasonPerformanceSnapshot | None,
) -> list[NormalizedPerformanceEvidence]:
    """Previous-season NBA per-game evidence — clearly labeled totals vs per-game."""
    if not snapshot or snapshot.games_played == 0:
        return []

    stats = snapshot.stats
    source_ref = snapshot.source_reference or f"{snapshot.source_method}:nba:{snapshot.season}"
    evidence: list[NormalizedPerformanceEvidence] = []

    per_game_fields = [
        ("points_per_game", "Points Per Game", "points_per_game"),
        ("rebounds_per_game", "Rebounds Per Game", "rebounds_per_game"),
        ("assists_per_game", "Assists Per Game", "assists_per_game"),
        ("steals_per_game", "Steals Per Game", "steals_per_game"),
        ("blocks_per_game", "Blocks Per Game", "blocks_per_game"),
        ("minutes_per_game", "Minutes Per Game", "minutes_per_game"),
        ("field_goal_percentage", "FG%", "field_goal_percentage"),
        ("three_point_percentage", "3PT%", "three_point_percentage"),
        ("free_throw_percentage", "FT%", "free_throw_percentage"),
        ("turnovers_per_game", "Turnovers Per Game", "turnovers_per_game"),
    ]

    for metric, label, key in per_game_fields:
        raw = stats.get(key)
        if raw is None:
            continue
        item = _previous_season_metric(metric, label, raw, snapshot=snapshot, source_ref=source_ref)
        if item:
            evidence.append(item)

    gp = _previous_season_metric("games_played", "Games Played", snapshot.games_played, snapshot=snapshot, source_ref=source_ref)
    if gp:
        evidence.insert(0, gp)

    if snapshot.starts is not None or stats.get("games_started") is not None:
        starts = snapshot.starts if snapshot.starts is not None else stats.get("games_started")
        item = _previous_season_metric("games_started", "Games Started", starts, snapshot=snapshot, source_ref=source_ref)
        if item:
            evidence.append(item)

    return evidence
