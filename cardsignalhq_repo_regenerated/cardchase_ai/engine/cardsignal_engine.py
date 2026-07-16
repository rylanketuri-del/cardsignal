"""Sport-agnostic CardSignal scoring engine.

The engine does not know which sport it is processing. Providers supply
normalized performance and market inputs; pipelines supply configuration
(including engine season phase). Sport-specific stat→performance conversion
stays outside this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from cardchase_ai.models.schemas import HitterHotnessBreakdown, MarketSnapshot
from cardchase_ai.score import assign_tag, clamp_score, score_market
from cardchase_ai.weekly_scoring import (
    compute_weekly_change,
    derive_collector_score,
    derive_conviction,
    derive_momentum_from_prior_snapshots,
    derive_recommendation,
    derive_scarcity_score,
    derive_status,
    has_sufficient_evidence,
)
from cardchase_ai.engine.season_phase import EngineSeasonPhase, uses_previous_season_baseline
from cardchase_ai.offseason_scoring import (
    derive_offseason_recommendation,
    has_offseason_sufficient_evidence,
)


@dataclass(frozen=True)
class CardSignalConfig:
    """Blend weights and evidence settings — sport-agnostic."""

    performance_weight: float = 0.55
    market_weight: float = 0.45
    # MLB daily hotness uses a different blend; weekly leagues use 55/45.
    mlb_performance_weight: float = 0.60
    mlb_market_weight: float = 0.40
    league: str = "MLB"
    season_phase: EngineSeasonPhase = "IN_SEASON"
    algorithm_version: str = "CARDSIGNAL_ENGINE_V1"


@dataclass
class CardSignalEngineInput:
    """Normalized inputs for one player. No sport-specific fields required."""

    player_name: str
    performance_score: float | None
    market_snapshots: dict[str, MarketSnapshot] = field(default_factory=dict)
    confidence_multiplier: float = 1.0
    performance_reasons: list[str] = field(default_factory=list)
    missing_inputs: list[str] = field(default_factory=list)
    prior_card_signal_score: float | None = None
    prior_performance_score: float | None = None
    has_previous_season: bool = False
    has_recent_form: bool = False
    has_signal_drivers: bool = False
    # Optional precomputed market score (when caller already scored market).
    market_score: float | None = None
    market_reasons: list[str] = field(default_factory=list)


@dataclass
class CardSignalEngineResult:
    """Engine outputs used by pipelines for leaderboards and snapshots."""

    card_signal_score: float | None
    performance_score: float | None
    market_score: float | None
    collector_score: float | None
    scarcity_score: float | None
    momentum_score: float | None
    weekly_change: float | None
    recommendation: str | None
    conviction: str
    status: str
    hotness: HitterHotnessBreakdown
    missing_inputs: list[str]
    collector_evidence: list[str]
    scarcity_evidence: list[str]
    market_reasons: list[str]
    evidence_sufficient: bool
    season_phase: EngineSeasonPhase
    algorithm_version: str
    extras: dict[str, Any] = field(default_factory=dict)


def compute_cardsignal(
    data: CardSignalEngineInput,
    config: CardSignalConfig | None = None,
) -> CardSignalEngineResult:
    """Compute CardSignal scores from normalized performance + market inputs."""
    config = config or CardSignalConfig()
    missing = list(data.missing_inputs)

    collector, collector_evidence, collector_missing = derive_collector_score(data.market_snapshots)
    scarcity, scarcity_evidence, scarcity_missing = derive_scarcity_score(data.market_snapshots)
    missing.extend(collector_missing)
    missing.extend(scarcity_missing)
    missing = list(dict.fromkeys(missing))

    if data.market_score is not None:
        market_score = data.market_score
        market_reasons = list(data.market_reasons)
    elif data.market_snapshots:
        market_score, market_reasons = score_market(data.market_snapshots)
    else:
        market_score = None
        market_reasons = []
        if "market_snapshots" not in missing:
            missing.append("market_snapshots")

    performance = data.performance_score
    offseason_like = uses_previous_season_baseline(config.season_phase)

    if performance is None and "stats_recent" not in missing and not offseason_like:
        missing.append("stats_recent")

    if offseason_like and data.has_previous_season and "stats_recent" in missing:
        missing = [m for m in missing if m != "stats_recent"]

    evidence_ok = False
    card_signal: float | None = None

    if offseason_like:
        evidence_ok = has_offseason_sufficient_evidence(
            config.league,
            performance,
            market_score,
            missing,
            has_previous_season=data.has_previous_season,
            season_phase="OFFSEASON",
        )
    else:
        evidence_ok = has_sufficient_evidence(
            performance,
            market_score,
            missing,
            league=config.league,
        )

    # Build a hotness breakdown for compatibility with existing snapshot builders.
    hotness_perf = performance if performance is not None else 0.0
    hotness_mkt = market_score if market_score is not None else 0.0
    if config.league.upper() == "MLB" and not offseason_like:
        raw_total = (
            config.mlb_performance_weight * hotness_perf
            + config.mlb_market_weight * hotness_mkt
        )
    else:
        raw_total = (
            config.performance_weight * hotness_perf
            + config.market_weight * hotness_mkt
        )
    total = round(raw_total * data.confidence_multiplier, 2)
    tag = assign_tag(total, hotness_perf, hotness_mkt)
    hotness = HitterHotnessBreakdown(
        player_name=data.player_name,
        performance_score=round(hotness_perf, 2),
        market_score=round(hotness_mkt, 2),
        total_score=total,
        confidence_multiplier=data.confidence_multiplier,
        tag=tag,
        reasons=list(data.performance_reasons) + list(market_reasons),
    )

    # MLB weekly/daily CardSignal uses confidence-adjusted hotness total.
    # NFL/NBA weekly CardSignal uses the 55/45 blend when evidence passes.
    if evidence_ok and performance is not None:
        if config.league.upper() == "MLB":
            card_signal = total
        else:
            card_signal = round(
                config.performance_weight * performance
                + config.market_weight * (market_score or 0.0),
                2,
            )
    else:
        card_signal = None

    weekly_change = compute_weekly_change(card_signal, data.prior_card_signal_score)
    momentum = None
    if data.prior_performance_score is not None and not offseason_like:
        momentum = derive_momentum_from_prior_snapshots(performance, data.prior_performance_score)

    conviction = derive_conviction(data.confidence_multiplier, len(missing))

    if offseason_like:
        recommendation = derive_offseason_recommendation(
            card_signal_score=card_signal,
            has_recent_form=data.has_recent_form,
            has_market=bool(data.market_snapshots) or market_score is not None,
            has_drivers=data.has_signal_drivers,
        )
    else:
        recommendation = derive_recommendation(hotness, collector) if card_signal is not None else None

    if config.league.upper() == "NFL":
        from cardchase_ai.weekly_scoring import derive_nfl_status

        status = derive_nfl_status(
            performance_score=performance,
            weekly_change=weekly_change,
            card_signal_score=card_signal,
            recommendation=recommendation,
        )
    else:
        status = derive_status(hotness, momentum)

    return CardSignalEngineResult(
        card_signal_score=card_signal,
        performance_score=performance,
        market_score=market_score,
        collector_score=collector,
        scarcity_score=scarcity,
        momentum_score=momentum,
        weekly_change=weekly_change,
        recommendation=recommendation,
        conviction=conviction,
        status=status,
        hotness=hotness,
        missing_inputs=missing,
        collector_evidence=collector_evidence,
        scarcity_evidence=scarcity_evidence,
        market_reasons=market_reasons,
        evidence_sufficient=evidence_ok,
        season_phase=config.season_phase,
        algorithm_version=config.algorithm_version,
        extras={"tag": tag, "clamp": clamp_score},
    )
