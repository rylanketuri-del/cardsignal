"""Card Intelligence synthesis engine — Sprint 8.7."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from cardchase_ai.intelligence.constants import (
    BUY_MIN_DEMAND_SCORE,
    BUY_MIN_MARKET_ACTIVITY,
    BUY_MIN_MOMENTUM_SCORE,
    BUY_MIN_SIGNAL_SCORE,
    BUY_STRONG_DEMAND_SCORE,
    BUY_STRONG_MOMENTUM_SCORE,
    CARD_INTELLIGENCE_ALGORITHM_VERSION,
    CONVICTION_HIGH_MAX_SCORE,
    CONVICTION_HIGH_MIN_SCORE,
    CONVICTION_MEDIUM_MIN_EVIDENCE,
    HOLD_MAX_SIGNAL_SCORE,
    HOLD_MIN_SIGNAL_SCORE,
    INSUFFICIENT_EVIDENCE_MESSAGE,
    MEANINGFUL_BID_LISTINGS,
    MEANINGFUL_TOTAL_BIDS,
    MIN_MARKET_SAMPLE_SIZE,
    QUALITY_RANK,
    SCARCITY_ALONE_CAP,
    SCARCITY_ALONE_DEMAND_MAX,
    SELL_MAX_SIGNAL_SCORE,
    SIGNAL_WEIGHTS,
)
from cardchase_ai.market.player_market import classify_market_depth
from cardchase_ai.models.intelligence import CardIntelligence, IntelligenceEvidenceItem, PlayerCardIntelligenceSummary
from cardchase_ai.models.population import CardPopulationSnapshot, CardScarcityMetrics
from cardchase_ai.models.schemas import CardMarketMovement
from cardchase_ai.population.scarcity import calculate_card_scarcity_metrics


def _clamp_score(value: float | None) -> float | None:
    if value is None:
        return None
    return round(max(0.0, min(100.0, float(value))), 2)


def _quality_factor(quality: str | None) -> float:
    rank = QUALITY_RANK.get(str(quality or "INSUFFICIENT").upper(), 0)
    if rank >= 3:
        return 1.0
    if rank == 2:
        return 0.85
    if rank == 1:
        return 0.65
    return 0.4


def _normalize_count(value: int | None, *, scale: float) -> float | None:
    if value is None or value < 0:
        return None
    if scale <= 0:
        return None
    return _clamp_score(100.0 * min(value / scale, 1.0))


def _has_valid_identity(card: dict[str, Any]) -> bool:
    return bool(card.get("cs_card_id") and card.get("cs_player_id"))


def _has_usable_market_sample(snapshot: dict[str, Any] | None) -> bool:
    if not snapshot:
        return False
    sample_size = int(snapshot.get("sample_size") or snapshot.get("active_listing_count") or 0)
    quality = str(snapshot.get("data_quality") or "INSUFFICIENT").upper()
    return sample_size >= MIN_MARKET_SAMPLE_SIZE and quality != "INSUFFICIENT"


def _has_meaningful_bid_activity(snapshot: dict[str, Any] | None) -> bool:
    if not snapshot:
        return False
    listings_with_bids = int(snapshot.get("listings_with_bids") or 0)
    total_bids = int(snapshot.get("total_bid_count") or 0)
    return listings_with_bids >= MEANINGFUL_BID_LISTINGS or total_bids >= MEANINGFUL_TOTAL_BIDS


def _movement_has_signal(movement: CardMarketMovement | None) -> bool:
    if movement is None:
        return False
    return movement.movement_quality != "INSUFFICIENT" and movement.comparison_captured_at is not None


def _has_population_data(population_snapshot: dict[str, Any] | None) -> bool:
    if not population_snapshot:
        return False
    return population_snapshot.get("total_population") is not None


def meets_minimum_evidence(
    *,
    card: dict[str, Any],
    market_snapshot: dict[str, Any] | None,
    movement_7d: CardMarketMovement | None,
    movement_30d: CardMarketMovement | None,
    population_snapshot: dict[str, Any] | None,
) -> bool:
    if not _has_valid_identity(card):
        return False
    if not _has_usable_market_sample(market_snapshot):
        return False

    secondary = (
        _movement_has_signal(movement_7d)
        or _movement_has_signal(movement_30d)
        or _has_population_data(population_snapshot)
        or _has_meaningful_bid_activity(market_snapshot)
    )
    return secondary


def _score_market_activity(snapshot: dict[str, Any]) -> tuple[float | None, list[str]]:
    inputs: list[str] = []
    active = int(snapshot.get("active_listing_count") or 0)
    auctions = int(snapshot.get("auction_count") or 0)
    listings_with_bids = int(snapshot.get("listings_with_bids") or 0)
    total_bids = int(snapshot.get("total_bid_count") or 0)
    quality = str(snapshot.get("data_quality") or "INSUFFICIENT").upper()

    listing_score = _normalize_count(active, scale=40)
    if listing_score is not None:
        inputs.append("active_listing_count")

    auction_ratio = (auctions / active) if active > 0 else None
    auction_score = _clamp_score(auction_ratio * 100.0) if auction_ratio is not None else None
    if auction_score is not None:
        inputs.append("auction_ratio")

    bid_listing_score = _normalize_count(listings_with_bids, scale=12)
    if bid_listing_score is not None:
        inputs.append("listings_with_bids")

    bid_count_score = _normalize_count(total_bids, scale=25)
    if bid_count_score is not None:
        inputs.append("total_bid_count")

    depth = classify_market_depth(active, 1)
    depth_score = {"HIGH": 85.0, "MEDIUM": 65.0, "LOW": 45.0}.get(depth)
    if depth_score is not None:
        inputs.append("market_depth")

    weighted: list[tuple[float, float]] = []
    if listing_score is not None:
        weighted.append((listing_score, 0.25))
    if auction_score is not None:
        weighted.append((auction_score, 0.15))
    if bid_listing_score is not None:
        weighted.append((bid_listing_score, 0.20))
    if bid_count_score is not None:
        weighted.append((bid_count_score, 0.20))
    if depth_score is not None:
        weighted.append((depth_score, 0.20))

    if not weighted:
        return None, inputs

    total_weight = sum(weight for _, weight in weighted)
    raw = sum(score * weight for score, weight in weighted) / total_weight
    return _clamp_score(raw * _quality_factor(quality)), inputs


def _score_demand(snapshot: dict[str, Any]) -> tuple[float | None, list[str]]:
    inputs: list[str] = []
    active = int(snapshot.get("active_listing_count") or 0)
    auctions = int(snapshot.get("auction_count") or 0)
    listings_with_bids = int(snapshot.get("listings_with_bids") or 0)
    total_bids = int(snapshot.get("total_bid_count") or 0)

    if active <= 0 and auctions <= 0 and total_bids <= 0:
        return None, inputs

    bid_ratio = (listings_with_bids / active) if active > 0 else None
    bid_ratio_score = _clamp_score(bid_ratio * 100.0) if bid_ratio is not None else None
    if bid_ratio_score is not None:
        inputs.append("bid_activity")

    auction_ratio = (auctions / active) if active > 0 else None
    auction_score = _clamp_score(auction_ratio * 100.0) if auction_ratio is not None else None
    if auction_score is not None:
        inputs.append("auction_activity")

    interaction_score = _normalize_count(listings_with_bids + min(total_bids, 50), scale=20)
    if interaction_score is not None:
        inputs.append("listing_interaction")

    weighted: list[tuple[float, float]] = []
    if bid_ratio_score is not None:
        weighted.append((bid_ratio_score, 0.45))
    if auction_score is not None:
        weighted.append((auction_score, 0.30))
    if interaction_score is not None:
        weighted.append((interaction_score, 0.25))

    if not weighted:
        return None, inputs

    total_weight = sum(weight for _, weight in weighted)
    return _clamp_score(sum(score * weight for score, weight in weighted) / total_weight), inputs


def _movement_direction_score(movement: CardMarketMovement | None) -> float | None:
    if not _movement_has_signal(movement):
        return None
    pct = movement.median_price_change_pct if movement else None
    if pct is None:
        return 50.0

    # Map -20%..+20% to 0..100 centered at 50
    bounded = max(-20.0, min(20.0, float(pct)))
    return _clamp_score(50.0 + (bounded / 20.0) * 50.0)


def _score_momentum(
    movement_7d: CardMarketMovement | None,
    movement_30d: CardMarketMovement | None,
) -> tuple[float | None, list[str]]:
    inputs: list[str] = []
    scores: list[tuple[float, float]] = []

    score_7d = _movement_direction_score(movement_7d)
    if score_7d is not None:
        inputs.append("7d_median_price_movement")
        weight_7d = 0.55 * _quality_factor(movement_7d.movement_quality if movement_7d else None)
        scores.append((score_7d, weight_7d))

    score_30d = _movement_direction_score(movement_30d)
    if score_30d is not None:
        inputs.append("30d_median_price_movement")
        weight_30d = 0.45 * _quality_factor(movement_30d.movement_quality if movement_30d else None)
        scores.append((score_30d, weight_30d))

    if movement_7d and movement_7d.listing_count_change_pct is not None:
        inputs.append("listing_count_movement")
        listing_shift = _clamp_score(50.0 - min(max(movement_7d.listing_count_change_pct, -30.0), 30.0))
        scores.append((listing_shift, 0.15))

    if movement_7d and movement_7d.bid_count_change_pct is not None:
        inputs.append("bid_count_movement")
        bid_shift = _clamp_score(50.0 + min(max(movement_7d.bid_count_change_pct, -30.0), 30.0) * 0.8)
        scores.append((bid_shift, 0.15))

    if not scores:
        return None, inputs

    total_weight = sum(weight for _, weight in scores)
    if total_weight <= 0:
        return None, inputs
    return _clamp_score(sum(score * weight for score, weight in scores) / total_weight), inputs


def _score_scarcity(scarcity: CardScarcityMetrics | None) -> tuple[float | None, list[str]]:
    if scarcity is None or scarcity.overall_scarcity_score is None:
        return None, list(scarcity.inputs_available) if scarcity else []
    confidence_factor = {"HIGH": 1.0, "MEDIUM": 0.9, "LOW": 0.75}.get(scarcity.confidence, 0.75)
    return _clamp_score(scarcity.overall_scarcity_score * confidence_factor), list(scarcity.inputs_available)


def _compose_card_signal_score(
    *,
    market_activity_score: float | None,
    demand_score: float | None,
    momentum_score: float | None,
    scarcity_score: float | None,
) -> float | None:
    components = {
        "market_activity": market_activity_score,
        "demand": demand_score,
        "momentum": momentum_score,
        "scarcity": scarcity_score,
    }
    available = {key: value for key, value in components.items() if value is not None}
    if not available:
        return None

    total_weight = sum(SIGNAL_WEIGHTS[key] for key in available)
    if total_weight <= 0:
        return None

    blended = sum(available[key] * SIGNAL_WEIGHTS[key] for key in available) / total_weight
    return _clamp_score(blended)


def _impact_from_score(score: float | None, *, neutral_band: float = 8.0) -> str:
    if score is None:
        return "UNKNOWN"
    if score >= 55 + neutral_band:
        return "POSITIVE"
    if score <= 45 - neutral_band:
        return "NEGATIVE"
    return "NEUTRAL"


def _impact_from_pct(pct: float | None) -> str:
    if pct is None:
        return "UNKNOWN"
    if pct >= 3.0:
        return "POSITIVE"
    if pct <= -3.0:
        return "NEGATIVE"
    return "NEUTRAL"


def _build_evidence(
    *,
    snapshot: dict[str, Any] | None,
    movement_7d: CardMarketMovement | None,
    movement_30d: CardMarketMovement | None,
    population_snapshot: dict[str, Any] | None,
    scarcity: CardScarcityMetrics | None,
    demand_score: float | None,
    market_activity_score: float | None,
    momentum_score: float | None,
    scarcity_score: float | None,
) -> list[IntelligenceEvidenceItem]:
    evidence: list[IntelligenceEvidenceItem] = []

    if snapshot and _has_meaningful_bid_activity(snapshot):
        listings_with_bids = int(snapshot.get("listings_with_bids") or 0)
        total_bids = int(snapshot.get("total_bid_count") or 0)
        label = "Bid activity"
        if listings_with_bids > 0:
            value = f"{listings_with_bids} listing{'s' if listings_with_bids != 1 else ''} with bids"
        else:
            value = f"{total_bids} total bids"
        evidence.append(
            IntelligenceEvidenceItem(
                type="DEMAND",
                label=label,
                value=value,
                impact=_impact_from_score(demand_score),
                quality=str(snapshot.get("data_quality") or "INSUFFICIENT").upper(),
            )
        )

    if snapshot and int(snapshot.get("auction_count") or 0) > 0:
        auctions = int(snapshot.get("auction_count") or 0)
        evidence.append(
            IntelligenceEvidenceItem(
                type="MARKET",
                label="Auction activity",
                value=f"{auctions} active auction{'s' if auctions != 1 else ''}",
                impact=_impact_from_score(market_activity_score),
                quality=str(snapshot.get("data_quality") or "INSUFFICIENT").upper(),
            )
        )

    if movement_7d and _movement_has_signal(movement_7d) and movement_7d.median_price_change_pct is not None:
        pct = movement_7d.median_price_change_pct
        sign = "+" if pct > 0 else ""
        evidence.append(
            IntelligenceEvidenceItem(
                type="MOMENTUM",
                label="7-day active price movement",
                value=f"{sign}{pct:.1f}%",
                impact=_impact_from_pct(pct),
                quality=movement_7d.movement_quality,
            )
        )

    if movement_30d and _movement_has_signal(movement_30d) and movement_30d.median_price_change_pct is not None:
        pct = movement_30d.median_price_change_pct
        sign = "+" if pct > 0 else ""
        evidence.append(
            IntelligenceEvidenceItem(
                type="MOMENTUM",
                label="30-day active price movement",
                value=f"{sign}{pct:.1f}%",
                impact=_impact_from_pct(pct),
                quality=movement_30d.movement_quality,
            )
        )

    if population_snapshot and population_snapshot.get("psa_10_population") is not None:
        psa_10 = int(population_snapshot["psa_10_population"])
        evidence.append(
            IntelligenceEvidenceItem(
                type="SCARCITY",
                label="PSA 10 population",
                value=str(psa_10),
                impact=_impact_from_score(scarcity_score),
                quality=str(population_snapshot.get("data_quality") or "INSUFFICIENT").upper(),
            )
        )

    if population_snapshot and population_snapshot.get("gem_rate") is not None:
        gem_rate = float(population_snapshot["gem_rate"])
        evidence.append(
            IntelligenceEvidenceItem(
                type="POPULATION",
                label="Gem rate",
                value=f"{gem_rate * 100:.1f}%",
                impact=_impact_from_score(scarcity_score, neutral_band=12.0),
                quality=str(population_snapshot.get("data_quality") or "INSUFFICIENT").upper(),
            )
        )

    return evidence


def _collect_missing_inputs(
    *,
    card: dict[str, Any],
    market_snapshot: dict[str, Any] | None,
    movement_7d: CardMarketMovement | None,
    movement_30d: CardMarketMovement | None,
    population_snapshot: dict[str, Any] | None,
    has_minimum: bool,
) -> list[str]:
    missing: list[str] = []
    if not _has_valid_identity(card):
        missing.append("card_identity")
    if not market_snapshot:
        missing.append("latest_market_snapshot")
    elif not _has_usable_market_sample(market_snapshot):
        missing.append("usable_market_sample")

    if not _movement_has_signal(movement_7d):
        missing.append("7d_market_movement")
    if not _movement_has_signal(movement_30d):
        missing.append("30d_market_movement")
    if not _has_population_data(population_snapshot):
        missing.append("psa_population")
    if market_snapshot and not _has_meaningful_bid_activity(market_snapshot):
        missing.append("bid_activity")

    if not has_minimum:
        missing.append("minimum_evidence_requirement")
    return missing


def _determine_recommendation(
    *,
    has_minimum: bool,
    card_signal_score: float | None,
    demand_score: float | None,
    momentum_score: float | None,
    scarcity_score: float | None,
    market_activity_score: float | None,
    movement_7d: CardMarketMovement | None,
    has_bid_activity: bool,
    has_movement: bool,
    has_population: bool,
) -> str:
    if not has_minimum or card_signal_score is None:
        return "WATCH"

    positive_dimensions = sum(
        1
        for score in (demand_score, momentum_score, market_activity_score)
        if score is not None and score >= 55.0
    )

    scarcity_only_buy = (
        scarcity_score is not None
        and scarcity_score >= SCARCITY_ALONE_CAP
        and (demand_score is None or demand_score < SCARCITY_ALONE_DEMAND_MAX)
        and (momentum_score is None or momentum_score < BUY_MIN_MOMENTUM_SCORE)
    )

    price_only_buy = (
        market_activity_score is not None
        and market_activity_score >= 60.0
        and (demand_score is None or demand_score < BUY_MIN_DEMAND_SCORE)
        and not has_movement
        and not has_bid_activity
    )

    momentum_positive = (
        movement_7d is not None
        and movement_7d.median_price_change_pct is not None
        and movement_7d.median_price_change_pct > 0
        and movement_7d.movement_quality in {"HIGH", "MEDIUM"}
    )

    buy_support = (
        (demand_score is not None and demand_score >= BUY_STRONG_DEMAND_SCORE)
        or (momentum_score is not None and momentum_score >= BUY_STRONG_MOMENTUM_SCORE and momentum_positive)
        or (
            demand_score is not None
            and demand_score >= BUY_MIN_DEMAND_SCORE
            and momentum_score is not None
            and momentum_score >= BUY_MIN_MOMENTUM_SCORE
            and market_activity_score is not None
            and market_activity_score >= BUY_MIN_MARKET_ACTIVITY
        )
    )

    if (
        card_signal_score >= BUY_MIN_SIGNAL_SCORE
        and positive_dimensions >= 2
        and buy_support
        and (has_movement or has_bid_activity or has_population)
        and not scarcity_only_buy
        and not price_only_buy
    ):
        return "BUY"

    negative_momentum = (
        movement_7d is not None
        and movement_7d.median_price_change_pct is not None
        and movement_7d.median_price_change_pct < 0
        and movement_7d.movement_quality in {"HIGH", "MEDIUM"}
    )

    if (
        card_signal_score <= SELL_MAX_SIGNAL_SCORE
        and momentum_score is not None
        and momentum_score <= 40.0
        and negative_momentum
    ):
        return "SELL"

    if HOLD_MIN_SIGNAL_SCORE <= card_signal_score <= HOLD_MAX_SIGNAL_SCORE:
        return "HOLD"

    if card_signal_score > HOLD_MAX_SIGNAL_SCORE and not buy_support:
        return "HOLD"

    return "WATCH"


def _determine_conviction(
    *,
    has_minimum: bool,
    card_signal_score: float | None,
    evidence: list[IntelligenceEvidenceItem],
) -> str:
    if not has_minimum or card_signal_score is None:
        return "INSUFFICIENT"

    strong_evidence = sum(
        1 for item in evidence if QUALITY_RANK.get(item.quality, 0) >= 2
    )

    if card_signal_score >= CONVICTION_HIGH_MIN_SCORE or card_signal_score <= CONVICTION_HIGH_MAX_SCORE:
        if strong_evidence >= 3:
            return "HIGH"
        if strong_evidence >= 2:
            return "MEDIUM"

    if strong_evidence >= CONVICTION_MEDIUM_MIN_EVIDENCE + 1:
        return "MEDIUM"
    if strong_evidence >= CONVICTION_MEDIUM_MIN_EVIDENCE:
        return "LOW"
    return "LOW"


def _determine_risk(
    *,
    has_minimum: bool,
    market_data_quality: str | None,
    movement_7d: CardMarketMovement | None,
    momentum_score: float | None,
) -> str:
    if not has_minimum:
        return "UNKNOWN"

    market_q = QUALITY_RANK.get(str(market_data_quality or "INSUFFICIENT").upper(), 0)
    movement_q = QUALITY_RANK.get(movement_7d.movement_quality if movement_7d else "INSUFFICIENT", 0)

    if market_q <= 1 or movement_q <= 1:
        return "HIGH"

    if (
        momentum_score is not None
        and momentum_score <= 35.0
        and movement_7d
        and movement_7d.median_price_change_pct is not None
        and movement_7d.median_price_change_pct < -5.0
    ):
        return "HIGH"

    if market_q >= 3 and movement_q >= 2:
        return "LOW"

    return "MEDIUM"


def _determine_time_horizon(
    *,
    has_minimum: bool,
    movement_7d: CardMarketMovement | None,
    momentum_score: float | None,
    scarcity_score: float | None,
) -> str:
    if not has_minimum:
        return "Not available"

    if (
        movement_7d
        and movement_7d.movement_quality == "HIGH"
        and momentum_score is not None
        and momentum_score >= 60.0
    ):
        return "1–2 weeks"

    if momentum_score is not None and momentum_score >= 50.0:
        return "2–4 weeks"

    if scarcity_score is not None and scarcity_score >= 65.0:
        return "1–3 months"

    return "2–4 weeks"


def synthesize_card_intelligence(
    *,
    card: dict[str, Any],
    market_snapshot: dict[str, Any] | None = None,
    movement_7d: CardMarketMovement | None = None,
    movement_30d: CardMarketMovement | None = None,
    population_snapshot: dict[str, Any] | None = None,
    population_history: list[dict[str, Any]] | None = None,
    psa_match: dict[str, Any] | None = None,
    scarcity: CardScarcityMetrics | None = None,
    calculated_at: datetime | None = None,
) -> CardIntelligence:
    now = calculated_at or datetime.now(timezone.utc)

    scarcity_metrics = scarcity
    if scarcity_metrics is None and population_snapshot:
        try:
            snapshot_model = CardPopulationSnapshot.model_validate(population_snapshot)
            active_listings = int(market_snapshot.get("active_listing_count") or 0) if market_snapshot else None
            scarcity_metrics = calculate_card_scarcity_metrics(
                snapshot_model,
                prior_snapshots=population_history,
                active_listing_count=active_listings,
            )
        except Exception:
            scarcity_metrics = None

    has_minimum = meets_minimum_evidence(
        card=card,
        market_snapshot=market_snapshot,
        movement_7d=movement_7d,
        movement_30d=movement_30d,
        population_snapshot=population_snapshot,
    )

    market_activity_score = None
    demand_score = None
    momentum_score = None
    scarcity_score = None

    if market_snapshot and _has_usable_market_sample(market_snapshot):
        market_activity_score, _ = _score_market_activity(market_snapshot)
        demand_score, _ = _score_demand(market_snapshot)

    momentum_score, _ = _score_momentum(movement_7d, movement_30d)
    scarcity_score, _ = _score_scarcity(scarcity_metrics)

    card_signal_score = None
    if has_minimum:
        card_signal_score = _compose_card_signal_score(
            market_activity_score=market_activity_score,
            demand_score=demand_score,
            momentum_score=momentum_score,
            scarcity_score=scarcity_score,
        )

    evidence = _build_evidence(
        snapshot=market_snapshot,
        movement_7d=movement_7d,
        movement_30d=movement_30d,
        population_snapshot=population_snapshot,
        scarcity=scarcity_metrics,
        demand_score=demand_score,
        market_activity_score=market_activity_score,
        momentum_score=momentum_score,
        scarcity_score=scarcity_score,
    )

    missing_inputs = _collect_missing_inputs(
        card=card,
        market_snapshot=market_snapshot,
        movement_7d=movement_7d,
        movement_30d=movement_30d,
        population_snapshot=population_snapshot,
        has_minimum=has_minimum,
    )

    has_bid_activity = _has_meaningful_bid_activity(market_snapshot)
    has_movement = _movement_has_signal(movement_7d) or _movement_has_signal(movement_30d)
    has_population = _has_population_data(population_snapshot)

    recommendation = _determine_recommendation(
        has_minimum=has_minimum,
        card_signal_score=card_signal_score,
        demand_score=demand_score,
        momentum_score=momentum_score,
        scarcity_score=scarcity_score,
        market_activity_score=market_activity_score,
        movement_7d=movement_7d,
        has_bid_activity=has_bid_activity,
        has_movement=has_movement,
        has_population=has_population,
    )

    conviction = _determine_conviction(
        has_minimum=has_minimum,
        card_signal_score=card_signal_score,
        evidence=evidence,
    )

    if not has_minimum:
        recommendation = "WATCH"
        conviction = "INSUFFICIENT"
        if INSUFFICIENT_EVIDENCE_MESSAGE not in missing_inputs:
            missing_inputs = [*missing_inputs, INSUFFICIENT_EVIDENCE_MESSAGE]

    risk = _determine_risk(
        has_minimum=has_minimum,
        market_data_quality=market_snapshot.get("data_quality") if market_snapshot else None,
        movement_7d=movement_7d,
        momentum_score=momentum_score,
    )

    time_horizon = _determine_time_horizon(
        has_minimum=has_minimum,
        movement_7d=movement_7d,
        momentum_score=momentum_score,
        scarcity_score=scarcity_score,
    )

    active_count = int(market_snapshot.get("active_listing_count") or 0) if market_snapshot else None
    market_depth = classify_market_depth(active_count or 0, 1) if active_count is not None else None

    population_change = None
    if population_history and population_snapshot:
        try:
            from cardchase_ai.population.movement import calculate_population_movement

            movement = calculate_population_movement([*population_history, population_snapshot])
            if movement:
                population_change = movement.population_change
        except Exception:
            population_change = None

    return CardIntelligence(
        cs_card_id=str(card.get("cs_card_id") or ""),
        cs_player_id=str(card.get("cs_player_id") or ""),
        league=str(card.get("league") or "MLB"),
        player_name=str(card.get("player_name") or ""),
        year=card.get("year"),
        manufacturer=card.get("manufacturer"),
        set_name=card.get("set_name"),
        card_name=card.get("card_name") or card.get("card"),
        card_number=card.get("card_number"),
        parallel=card.get("parallel"),
        variety=card.get("variety"),
        grade=card.get("grade"),
        grading_company=card.get("grading_company"),
        latest_market_snapshot=market_snapshot,
        market_movement_7d=movement_7d.model_dump(mode="json") if movement_7d else None,
        market_movement_30d=movement_30d.model_dump(mode="json") if movement_30d else None,
        active_listing_count=active_count,
        auction_count=int(market_snapshot.get("auction_count") or 0) if market_snapshot else None,
        buy_it_now_count=int(market_snapshot.get("buy_it_now_count") or 0) if market_snapshot else None,
        listings_with_bids=int(market_snapshot.get("listings_with_bids") or 0) if market_snapshot else None,
        total_bid_count=int(market_snapshot.get("total_bid_count") or 0) if market_snapshot else None,
        median_active_price=market_snapshot.get("median_price") if market_snapshot else None,
        average_active_price=market_snapshot.get("average_price") if market_snapshot else None,
        market_depth=market_depth,
        market_data_quality=market_snapshot.get("data_quality") if market_snapshot else None,
        psa_match_status=(psa_match or {}).get("match_status"),
        total_psa_population=population_snapshot.get("total_population") if population_snapshot else None,
        psa_10_population=population_snapshot.get("psa_10_population") if population_snapshot else None,
        psa_9_population=population_snapshot.get("psa_9_population") if population_snapshot else None,
        gem_rate=population_snapshot.get("gem_rate") if population_snapshot else None,
        population_change=population_change,
        population_data_quality=population_snapshot.get("data_quality") if population_snapshot else None,
        population_source_method=population_snapshot.get("source_method") if population_snapshot else None,
        scarcity_metrics=scarcity_metrics.model_dump(mode="json") if scarcity_metrics else None,
        market_activity_score=market_activity_score,
        demand_score=demand_score,
        scarcity_score=scarcity_score,
        momentum_score=momentum_score,
        card_signal_score=card_signal_score,
        recommendation=recommendation,
        conviction=conviction,
        risk=risk,
        time_horizon=time_horizon,
        evidence=evidence,
        missing_inputs=missing_inputs,
        calculated_at=now,
        algorithm_version=CARD_INTELLIGENCE_ALGORITHM_VERSION,
    )


def build_player_intelligence_summary(cards: list[CardIntelligence]) -> PlayerCardIntelligenceSummary:
    def _max_score(items: list[CardIntelligence], attr: str) -> tuple[float | None, str | None]:
        best_score = None
        best_id = None
        for card in items:
            value = getattr(card, attr)
            if value is None:
                continue
            if best_score is None or value > best_score:
                best_score = value
                best_id = card.cs_card_id
        return best_score, best_id

    sufficient = [card for card in cards if card.card_signal_score is not None]
    pending = [card for card in cards if card.card_signal_score is None]

    highest_signal, highest_signal_id = _max_score(cards, "card_signal_score")
    strongest_market, strongest_market_id = _max_score(cards, "market_activity_score")
    strongest_scarcity, strongest_scarcity_id = _max_score(cards, "scarcity_score")

    most_bids = None
    most_bids_id = None
    for card in cards:
        bids = card.total_bid_count
        if bids is None:
            continue
        if most_bids is None or bids > most_bids:
            most_bids = bids
            most_bids_id = card.cs_card_id

    return PlayerCardIntelligenceSummary(
        highest_card_signal=highest_signal,
        highest_card_signal_card_id=highest_signal_id,
        strongest_market_activity=strongest_market,
        strongest_market_activity_card_id=strongest_market_id,
        strongest_scarcity=strongest_scarcity,
        strongest_scarcity_card_id=strongest_scarcity_id,
        most_bid_activity=most_bids,
        most_bid_activity_card_id=most_bids_id,
        cards_with_sufficient_evidence=len(sufficient),
        cards_pending_evidence=len(pending),
        total_cards=len(cards),
    )
