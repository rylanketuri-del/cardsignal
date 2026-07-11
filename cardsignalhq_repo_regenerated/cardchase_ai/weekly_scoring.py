"""Derive CardSignal weekly score components from pipeline output."""

from __future__ import annotations

from typing import Any

from cardchase_ai.card_intelligence import card_intelligence_from_snapshot
from cardchase_ai.models.schemas import HitterHotnessBreakdown, MarketSnapshot, RollingHitterStats
from cardchase_ai.score import clamp_score


def cs_player_id(source_player_id: str | int, league: str = "MLB") -> str:
    return f"{league.lower()}:{source_player_id}"


def cs_card_id(source_player_id: str | int, query_name: str, league: str = "MLB") -> str:
    return f"{league.lower()}:{source_player_id}:card:{query_name}"


def derive_collector_score(market_snapshots: dict[str, MarketSnapshot]) -> tuple[float | None, list[str], list[str]]:
    missing: list[str] = []
    if not market_snapshots:
        missing.append("market_snapshots")
        return None, [], missing

    premium = sum(s.tags.premium_count for s in market_snapshots.values())
    auto = sum(s.tags.auto_count for s in market_snapshots.values())
    volume = sum(s.listings_count for s in market_snapshots.values())

    if volume == 0:
        missing.append("listing_volume")
        return None, [], missing

    premium_ratio = premium / max(volume, 1)
    auto_ratio = auto / max(volume, 1)
    score = clamp_score((premium_ratio * 60) + (auto_ratio * 40) + min(volume / 120, 1) * 20)
    evidence = [f"premium_listings={premium}", f"auto_listings={auto}", f"total_listings={volume}"]
    return round(score, 2), evidence, missing


def derive_momentum_score(stats_7d: RollingHitterStats, stats_30d: RollingHitterStats) -> tuple[float | None, list[str], list[str]]:
    missing: list[str] = []
    if stats_7d.games == 0:
        missing.append("stats_7d")
        return None, [], missing
    if stats_30d.games == 0:
        missing.append("stats_30d")
        return None, [], missing

    ops_delta = stats_7d.ops - stats_30d.ops
    hr_pace = stats_7d.home_runs - (stats_30d.home_runs / max(stats_30d.games, 1)) * stats_7d.games
    score = clamp_score(50 + (ops_delta * 40) + (hr_pace * 5))
    evidence = [f"ops_7d={stats_7d.ops:.3f}", f"ops_30d={stats_30d.ops:.3f}", f"ops_delta={ops_delta:.3f}"]
    return round(score, 2), evidence, missing


def derive_scarcity_score(market_snapshots: dict[str, MarketSnapshot]) -> tuple[float | None, list[str], list[str]]:
    missing: list[str] = []
    if not market_snapshots:
        missing.append("market_snapshots")
        return None, [], missing

    psa10 = sum(s.tags.psa10_count for s in market_snapshots.values())
    numbered = sum(s.tags.numbered_count for s in market_snapshots.values())
    volume = sum(s.listings_count for s in market_snapshots.values())

    if volume == 0:
        missing.append("listing_volume")
        return None, [], missing

    scarcity_signal = (psa10 * 2) + numbered
    score = clamp_score((scarcity_signal / max(volume, 1)) * 100)
    evidence = [f"psa10_listings={psa10}", f"numbered_listings={numbered}"]
    return round(score, 2), evidence, missing


def derive_recommendation(hotness: HitterHotnessBreakdown, collector: float | None) -> str:
    tag = hotness.tag.upper()
    if tag == "BUY LOW":
        return "BUY"
    if tag in {"HOT", "RISING"} and hotness.total_score >= 65:
        return "BUY" if hotness.performance_score >= 60 else "HOLD"
    if tag == "CHASED" and (collector or 0) >= 70:
        return "HOLD"
    if hotness.total_score < 45:
        return "SELL"
    return "HOLD"


def derive_conviction(confidence_multiplier: float, missing_count: int) -> str:
    if missing_count >= 2:
        return "Low"
    if confidence_multiplier >= 0.95 and missing_count == 0:
        return "High"
    if confidence_multiplier >= 0.85:
        return "Medium"
    return "Low"


def derive_status(hotness: HitterHotnessBreakdown, momentum: float | None) -> str:
    tag = hotness.tag.upper()
    if tag == "HOT":
        return "HOT"
    if tag == "BUY LOW":
        return "RISING"
    if tag == "CHASED":
        return "HOT"
    if momentum is not None and momentum < 45:
        return "COOLING"
    if hotness.total_score >= 65:
        return "RISING"
    return "COOLING" if hotness.total_score < 40 else "RISING"


def has_sufficient_evidence(
    performance: float | None,
    market: float | None,
    missing_inputs: list[str],
) -> bool:
    if performance is None or market is None:
        return False
    critical = {"stats_7d", "market_snapshots", "listing_volume"}
    if critical.intersection(set(missing_inputs)):
        return False
    return True


def compute_weekly_change(current: float | None, prior: float | None) -> float | None:
    if current is None or prior is None:
        return None
    return round(current - prior, 2)


CARD_QUERY_LABELS = {
    "broad": "Base Cards",
    "bowman_chrome": "Bowman Chrome",
    "auto": "Autographs",
    "psa10": "PSA 10",
}


__all__ = [
    "CARD_QUERY_LABELS",
    "card_intelligence_from_snapshot",
    "compute_weekly_change",
    "cs_card_id",
    "cs_player_id",
    "derive_collector_score",
    "derive_conviction",
    "derive_momentum_score",
    "derive_recommendation",
    "derive_scarcity_score",
    "derive_status",
    "has_sufficient_evidence",
]
