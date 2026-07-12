"""Derive CardSignal weekly score components from pipeline output."""

from __future__ import annotations

from typing import Any

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


def card_intelligence_from_snapshot(
    query_name: str,
    snapshot: MarketSnapshot,
    player_name: str,
) -> dict[str, Any]:
    missing: list[str] = []
    if snapshot.listings_count == 0:
        missing.append("listings")
        return {
            "card_signal_score": None,
            "recommendation": "WATCH",
            "conviction": "Low",
            "risk": "Medium",
            "time_horizon": "2-4 weeks",
            "market_activity_score": None,
            "demand_score": None,
            "momentum_score": None,
            "scarcity_score": None,
            "missing_inputs": missing,
            "evidence": {"query_name": query_name, "listings_count": 0},
        }

    activity = clamp_score((snapshot.listings_count / 30) * 100)
    demand = clamp_score((snapshot.tags.premium_count / max(snapshot.listings_count, 1)) * 100)
    scarcity = clamp_score((snapshot.tags.psa10_count / max(snapshot.listings_count, 1)) * 100)
    momentum = clamp_score((snapshot.avg_price or 0) / 100) if snapshot.avg_price else None

    score_parts = [v for v in [activity, demand] if v is not None]
    card_score = round(sum(score_parts) / len(score_parts), 2) if score_parts else None

    recommendation = "WATCH"
    if card_score is not None:
        if card_score >= 70 and demand >= 60:
            recommendation = "BUY"
        elif card_score < 40:
            recommendation = "SELL"
        else:
            recommendation = "HOLD"

    return {
        "card_signal_score": card_score,
        "recommendation": recommendation,
        "conviction": "Medium" if card_score and card_score >= 60 else "Low",
        "risk": "Low" if demand >= 65 else "Medium",
        "time_horizon": "2-4 weeks",
        "market_activity_score": round(activity, 2),
        "demand_score": round(demand, 2),
        "momentum_score": round(momentum, 2) if momentum is not None else None,
        "scarcity_score": round(scarcity, 2),
        "missing_inputs": missing,
        "evidence": {
            "query_name": query_name,
            "listings_count": snapshot.listings_count,
            "avg_price": snapshot.avg_price,
            "tags": snapshot.tags.model_dump(),
        },
    }


from cardchase_ai.adapters.league_constants import MLB_CARD_QUERY_LABELS

CARD_QUERY_LABELS = MLB_CARD_QUERY_LABELS
