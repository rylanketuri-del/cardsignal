"""Formal signal driver adapters — shared orchestration, league-specific generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from cardchase_ai.models.schemas import HitterHotnessBreakdown, MarketSnapshot, RollingHitterStats
from cardchase_ai.score import build_hotness_breakdown, score_hitter_performance, score_market
from cardchase_ai.weekly_scoring import (
    derive_collector_score,
    derive_momentum_score,
    derive_scarcity_score,
)


@dataclass
class SignalDriverResult:
    """Output from a single signal driver computation."""

    driver_id: str
    score: float | None
    evidence: list[str] = field(default_factory=list)
    missing_inputs: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


@runtime_checkable
class SignalDriver(Protocol):
    """Shared signal driver contract."""

    @property
    def driver_id(self) -> str: ...

    def compute(self, context: dict[str, Any]) -> SignalDriverResult: ...


class PerformanceDriver:
    driver_id = "performance"

    def compute(self, context: dict[str, Any]) -> SignalDriverResult:
        stats_7d: RollingHitterStats = context["stats_7d"]
        stats_30d: RollingHitterStats = context["stats_30d"]
        score, reasons = score_hitter_performance(stats_7d, stats_30d)
        missing = ["stats_7d"] if stats_7d.games == 0 else []
        return SignalDriverResult(
            driver_id=self.driver_id,
            score=score,
            reasons=reasons,
            missing_inputs=missing,
            evidence=[f"performance_score={score}"],
        )


class MarketDriver:
    driver_id = "market"

    def compute(self, context: dict[str, Any]) -> SignalDriverResult:
        snapshots: dict[str, MarketSnapshot] = context.get("market_snapshots") or {}
        if not snapshots:
            return SignalDriverResult(
                driver_id=self.driver_id,
                score=None,
                missing_inputs=["market_snapshots"],
            )
        score, reasons = score_market(snapshots)
        return SignalDriverResult(
            driver_id=self.driver_id,
            score=score,
            reasons=reasons,
            evidence=[f"market_score={score}"],
        )


class CollectorDriver:
    driver_id = "collector"

    def compute(self, context: dict[str, Any]) -> SignalDriverResult:
        snapshots: dict[str, MarketSnapshot] = context.get("market_snapshots") or {}
        score, evidence, missing = derive_collector_score(snapshots)
        return SignalDriverResult(
            driver_id=self.driver_id,
            score=score,
            evidence=evidence,
            missing_inputs=missing,
        )


class MomentumDriver:
    driver_id = "momentum"

    def compute(self, context: dict[str, Any]) -> SignalDriverResult:
        stats_7d: RollingHitterStats = context["stats_7d"]
        stats_30d: RollingHitterStats = context["stats_30d"]
        score, evidence, missing = derive_momentum_score(stats_7d, stats_30d)
        return SignalDriverResult(
            driver_id=self.driver_id,
            score=score,
            evidence=evidence,
            missing_inputs=missing,
        )


class ScarcityDriver:
    driver_id = "scarcity"

    def compute(self, context: dict[str, Any]) -> SignalDriverResult:
        snapshots: dict[str, MarketSnapshot] = context.get("market_snapshots") or {}
        score, evidence, missing = derive_scarcity_score(snapshots)
        return SignalDriverResult(
            driver_id=self.driver_id,
            score=score,
            evidence=evidence,
            missing_inputs=missing,
        )


class NarrativeSignalDriver:
    """League-specific narrative signal contributors (evidence only, no score impact)."""

    def __init__(self, driver_id: str, generator) -> None:
        self._driver_id = driver_id
        self._generator = generator

    @property
    def driver_id(self) -> str:
        return self._driver_id

    def compute(self, context: dict[str, Any]) -> SignalDriverResult:
        narratives = self._generator(context)
        return SignalDriverResult(
            driver_id=self._driver_id,
            score=None,
            reasons=narratives,
            evidence=narratives,
        )


def run_signal_drivers(
    drivers: tuple[SignalDriver, ...],
    context: dict[str, Any],
) -> dict[str, SignalDriverResult]:
    """Execute all drivers and return results keyed by driver_id."""
    return {driver.driver_id: driver.compute(context) for driver in drivers}


def build_hotness_from_drivers(
    player_name: str,
    stats_7d: RollingHitterStats,
    stats_30d: RollingHitterStats,
    market_snapshots: dict[str, MarketSnapshot],
) -> HitterHotnessBreakdown:
    """Preserve existing hotness composition — delegates to score module."""
    return build_hotness_breakdown(
        player_name=player_name,
        stats_7d=stats_7d,
        stats_30d=stats_30d,
        market_snapshots=market_snapshots,
    )


MLB_CORE_DRIVERS: tuple[SignalDriver, ...] = (
    PerformanceDriver(),
    MarketDriver(),
    CollectorDriver(),
    MomentumDriver(),
    ScarcityDriver(),
)


def _mlb_batting_surge(context: dict[str, Any]) -> list[str]:
    stats: RollingHitterStats = context["stats_7d"]
    narratives: list[str] = []
    if stats.ops >= 1.000:
        narratives.append("Recent batting surge")
    if stats.home_runs >= 3:
        narratives.append("Home run surge")
    return narratives


def _mlb_call_up(context: dict[str, Any]) -> list[str]:
    candidate = context.get("candidate") or {}
    if candidate.get("candidate_source") == "dynamic" and context["stats_7d"].games <= 3:
        return ["Call-up watch"]
    return []


def _mlb_trade(context: dict[str, Any]) -> list[str]:
    return []


MLB_NARRATIVE_DRIVERS: tuple[SignalDriver, ...] = (
    NarrativeSignalDriver("recent_batting_surge", _mlb_batting_surge),
    NarrativeSignalDriver("call_up", _mlb_call_up),
    NarrativeSignalDriver("trade", _mlb_trade),
)


def _nfl_passing_surge(context: dict[str, Any]) -> list[str]:
    return []


def _nfl_depth_chart(context: dict[str, Any]) -> list[str]:
    return []


def _nfl_injury_return(context: dict[str, Any]) -> list[str]:
    return []


NFL_NARRATIVE_DRIVERS: tuple[SignalDriver, ...] = (
    NarrativeSignalDriver("passing_surge", _nfl_passing_surge),
    NarrativeSignalDriver("depth_chart_change", _nfl_depth_chart),
    NarrativeSignalDriver("injury_return", _nfl_injury_return),
)
