"""Normalized performance evidence builders for MLB and NFL."""

from __future__ import annotations

from typing import Any

from cardchase_ai.models.intelligence import EvidenceImpact, EvidenceQuality, NormalizedPerformanceEvidence
from cardchase_ai.models.nfl import NFLPerformanceSnapshot
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
    stats_30d: RollingHitterStats,
    *,
    period_start: str | None = None,
    period_end: str | None = None,
) -> list[NormalizedPerformanceEvidence]:
    """Structured season-window evidence for MLB (30-day rolling window)."""
    if stats_30d.games == 0:
        return []

    quality = _quality_from_games(stats_30d.games)
    return [
        NormalizedPerformanceEvidence(
            metric="ops",
            label="OPS (30-Day Window)",
            value=round(stats_30d.ops, 3),
            period_type="LAST_30_DAYS",
            period_start=period_start,
            period_end=period_end,
            impact="neutral",
            quality=quality,
            source_reference="mlb_stats_api:rolling_30d",
        ),
        NormalizedPerformanceEvidence(
            metric="home_runs",
            label="Home Runs (30-Day Window)",
            value=stats_30d.home_runs,
            period_type="LAST_30_DAYS",
            period_start=period_start,
            period_end=period_end,
            impact="positive" if stats_30d.home_runs >= 4 else "neutral",
            quality=quality,
            source_reference="mlb_stats_api:rolling_30d",
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
