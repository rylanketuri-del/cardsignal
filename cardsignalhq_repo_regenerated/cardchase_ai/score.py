from __future__ import annotations

from typing import Dict, List

from cardchase_ai.models.schemas import HitterHotnessBreakdown, MarketSnapshot, RollingHitterStats



def clamp_score(value: float, floor: float = 0.0, ceiling: float = 100.0) -> float:
    return max(floor, min(ceiling, value))



def score_hitter_performance(stats_7d: RollingHitterStats, stats_30d: RollingHitterStats) -> tuple[float, List[str]]:
    reasons: List[str] = []

    ops_score = clamp_score((stats_7d.ops / 1.200) * 100)
    hr_score = clamp_score((stats_7d.home_runs / 5) * 100)
    sb_score = clamp_score((stats_7d.stolen_bases / 5) * 100)
    rbi_runs_proxy_score = clamp_score((stats_7d.rbi / 10) * 100)
    avg_score = clamp_score((stats_7d.avg / 0.400) * 100)
    playing_time_score = clamp_score((stats_7d.at_bats / 25) * 100)
    baseline_score = clamp_score((stats_30d.ops / 1.050) * 100)

    score = (
        0.25 * ops_score
        + 0.15 * hr_score
        + 0.10 * sb_score
        + 0.10 * rbi_runs_proxy_score
        + 0.10 * avg_score
        + 0.10 * playing_time_score
        + 0.20 * baseline_score
    )

    if stats_7d.ops >= 1.000:
        reasons.append("elite 7-day OPS")
    if stats_7d.home_runs >= 3:
        reasons.append("home run surge")
    if stats_7d.stolen_bases >= 2:
        reasons.append("speed contribution")
    if stats_7d.at_bats >= 18:
        reasons.append("full playing time")

    return round(clamp_score(score), 2), reasons



def score_market(market_snapshots: Dict[str, MarketSnapshot]) -> tuple[float, List[str]]:
    reasons: List[str] = []
    if not market_snapshots:
        return 0.0, reasons

    listing_volume = sum(snapshot.listings_count for snapshot in market_snapshots.values())
    premium_count = sum(snapshot.tags.premium_count for snapshot in market_snapshots.values())
    psa10_count = sum(snapshot.tags.psa10_count for snapshot in market_snapshots.values())
    auto_count = sum(snapshot.tags.auto_count for snapshot in market_snapshots.values())

    broad_avg = market_snapshots.get("broad").avg_price if market_snapshots.get("broad") else None
    premium_avgs = [
        snapshot.avg_price
        for name, snapshot in market_snapshots.items()
        if name != "broad" and snapshot.avg_price is not None
    ]
    premium_avg = sum(premium_avgs) / len(premium_avgs) if premium_avgs else None

    listing_volume_score = clamp_score((listing_volume / 120) * 100)
    premium_presence_score = clamp_score((premium_count / max(listing_volume, 1)) * 100)
    psa10_score = clamp_score((psa10_count / 20) * 100)
    auto_score = clamp_score((auto_count / 20) * 100)

    price_strength_score = 0.0
    if broad_avg and premium_avg:
        price_strength_score = clamp_score((premium_avg / max(broad_avg, 1)) * 20)

    score = (
        0.35 * listing_volume_score
        + 0.25 * premium_presence_score
        + 0.15 * psa10_score
        + 0.15 * auto_score
        + 0.10 * price_strength_score
    )

    if listing_volume >= 40:
        reasons.append("high listing volume")
    if premium_count >= 15:
        reasons.append("strong premium-card presence")
    if psa10_count >= 5:
        reasons.append("PSA 10 activity")
    if auto_count >= 5:
        reasons.append("auto demand")

    return round(clamp_score(score), 2), reasons



def confidence_multiplier(stats_7d: RollingHitterStats, market_snapshots: Dict[str, MarketSnapshot]) -> float:
    listing_volume = sum(snapshot.listings_count for snapshot in market_snapshots.values())
    ab_factor = 1.0 if stats_7d.at_bats >= 15 else 0.85 if stats_7d.at_bats >= 8 else 0.7
    listing_factor = 1.0 if listing_volume >= 20 else 0.9 if listing_volume >= 8 else 0.8
    return round(min(ab_factor, listing_factor), 2)



def assign_tag(total_score: float, performance_score: float, market_score: float) -> str:
    if total_score >= 80 and performance_score >= 75 and market_score >= 65:
        return "HOT"
    if performance_score >= 75 and market_score <= 55:
        return "BUY LOW"
    if market_score >= 75 and performance_score < 65:
        return "CHASED"
    if total_score >= 65:
        return "RISING"
    return "WATCH"



def build_hotness_breakdown(
    player_name: str,
    stats_7d: RollingHitterStats,
    stats_30d: RollingHitterStats,
    market_snapshots: Dict[str, MarketSnapshot],
) -> HitterHotnessBreakdown:
    performance_score, performance_reasons = score_hitter_performance(stats_7d, stats_30d)
    market_score, market_reasons = score_market(market_snapshots)
    confidence = confidence_multiplier(stats_7d, market_snapshots)
    raw_total = (0.60 * performance_score) + (0.40 * market_score)
    total_score = round(raw_total * confidence, 2)
    tag = assign_tag(total_score, performance_score, market_score)
    reasons = performance_reasons + market_reasons

    return HitterHotnessBreakdown(
        player_name=player_name,
        performance_score=performance_score,
        market_score=market_score,
        total_score=total_score,
        confidence_multiplier=confidence,
        tag=tag,
        reasons=reasons,
    )
