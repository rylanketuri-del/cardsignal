"""Centralized CardSignal card intelligence synthesis from stored data only."""

from __future__ import annotations

from typing import Any

from cardchase_ai.card_registry import get_card_identity
from cardchase_ai.models.schemas import MarketSnapshot
from cardchase_ai.score import clamp_score

CARD_INTELLIGENCE_V1 = "CARD_INTELLIGENCE_V1"

_COMPONENT_KEYS = (
    "player_performance",
    "market_momentum",
    "price_movement",
    "collector_demand",
    "scarcity",
    "population",
    "listing_supply",
    "auction_activity",
    "card_liquidity",
)


def _median_price(snapshot: MarketSnapshot) -> float | None:
    prices = sorted(
        listing.price
        for listing in snapshot.listings
        if listing.price is not None
    )
    if not prices:
        return None
    mid = len(prices) // 2
    if len(prices) % 2:
        return round(prices[mid], 2)
    return round((prices[mid - 1] + prices[mid]) / 2, 2)


def _score_listing_supply(listings_count: int) -> float:
    """Lower active supply supports tighter market conditions."""
    if listings_count <= 0:
        return 0.0
    if listings_count <= 5:
        return clamp_score(90 - listings_count)
    if listings_count <= 15:
        return clamp_score(75 - (listings_count - 5))
    if listings_count <= 30:
        return clamp_score(55 - (listings_count - 15))
    return clamp_score(max(20, 45 - (listings_count - 30) * 0.5))


def _score_card_liquidity(listings_count: int) -> float | None:
    if listings_count <= 0:
        return None
    return clamp_score(min(listings_count / 40, 1) * 100)


def _score_price_movement(price_change_pct: float | None) -> float | None:
    if price_change_pct is None:
        return None
    return clamp_score(50 + (price_change_pct * 2.5))


def _score_collector_demand(snapshot: MarketSnapshot) -> float | None:
    if snapshot.listings_count <= 0:
        return None
    premium = snapshot.tags.premium_count
    auto = snapshot.tags.auto_count
    ratio = (premium + auto * 0.5) / max(snapshot.listings_count, 1)
    return round(clamp_score(ratio * 120), 2)


def _score_scarcity(snapshot: MarketSnapshot) -> float | None:
    if snapshot.listings_count <= 0:
        return None
    scarcity_signal = (snapshot.tags.psa10_count * 2) + snapshot.tags.numbered_count
    return round(clamp_score((scarcity_signal / max(snapshot.listings_count, 1)) * 100), 2)


def _score_market_momentum(
    momentum_score: float | None,
    price_change_pct: float | None,
) -> float | None:
    if momentum_score is not None:
        return round(clamp_score(momentum_score), 2)
    return _score_price_movement(price_change_pct)


def _derive_evidence_tier(components: dict[str, float | None], missing_inputs: list[str]) -> str:
    available = [key for key in _COMPONENT_KEYS if components.get(key) is not None]
    if "listings" in missing_inputs or len(available) == 0:
        return "INSUFFICIENT"
    if len(available) >= 5:
        return "HIGH"
    if len(available) >= 3:
        return "MEDIUM"
    return "LOW"


def _derive_card_recommendation(
    *,
    evidence_tier: str,
    components: dict[str, float | None],
    price_change_pct: float | None,
    listings_change: int | None,
    query_signals: dict[str, bool],
) -> str:
    if evidence_tier == "INSUFFICIENT":
        return "WATCH"

    bullish = 0
    bearish = 0

    performance = components.get("player_performance")
    demand = components.get("collector_demand")
    scarcity = components.get("scarcity")
    supply = components.get("listing_supply")
    movement = components.get("price_movement")
    liquidity = components.get("card_liquidity")
    auction = components.get("auction_activity")

    if performance is not None and performance >= 70:
        bullish += 1
    elif performance is not None and performance < 45:
        bearish += 1

    if demand is not None and demand >= 65:
        bullish += 1
    elif demand is not None and demand < 40:
        bearish += 1

    if movement is not None and movement >= 60:
        bullish += 1
    elif movement is not None and movement < 40:
        bearish += 1

    if scarcity is not None and scarcity >= 65:
        bullish += 1

    if supply is not None and supply >= 70:
        bullish += 1
    elif supply is not None and supply < 35:
        bearish += 1

    if price_change_pct is not None:
        if price_change_pct >= 5:
            bullish += 1
        elif price_change_pct <= -5:
            bearish += 1

    if listings_change is not None:
        if listings_change <= -3:
            bullish += 1
        elif listings_change >= 5:
            bearish += 1

    if auction is not None and auction >= 60:
        bullish += 1

    if liquidity is not None and liquidity >= 70 and demand is not None and demand >= 60:
        bullish += 1

    if query_signals.get("rookie") and performance is not None and performance >= 65:
        bullish += 1
    if query_signals.get("autograph") and demand is not None and demand >= 60:
        bullish += 1

    if bullish >= 3 and bearish == 0:
        return "BUY"
    if bearish >= 2 and bullish <= 1:
        return "SELL"
    if bullish >= 2 or bearish >= 2:
        return "HOLD"
    return "WATCH"


def _build_factor_chips(
    *,
    components: dict[str, float | None],
    snapshot: MarketSnapshot,
    price_change_pct: float | None,
    listings_change: int | None,
    population_count: int | None,
) -> list[dict[str, str]]:
    chips: list[dict[str, str]] = []
    tags = snapshot.tags

    if components.get("player_performance") is not None and components["player_performance"] >= 75:
        chips.append({"emoji": "🔥", "label": "Strong Performance", "key": "strong_performance"})
    if components.get("collector_demand") is not None and components["collector_demand"] >= 65:
        if price_change_pct is not None and price_change_pct > 0:
            chips.append({"emoji": "📈", "label": "Rising Demand", "key": "rising_demand"})
        else:
            chips.append({"emoji": "📈", "label": "Strong Demand", "key": "strong_demand"})
    if components.get("listing_supply") is not None and components["listing_supply"] >= 70:
        chips.append({"emoji": "🏷", "label": "Low Supply", "key": "low_supply"})
    if tags.rookie_count > 0:
        chips.append({"emoji": "⭐", "label": "Rookie", "key": "rookie"})
    if tags.auto_count > 0:
        chips.append({"emoji": "✍", "label": "Autograph", "key": "autograph"})
    if population_count is not None and population_count <= 250:
        chips.append({"emoji": "💎", "label": "Low Population", "key": "low_population"})
    elif components.get("scarcity") is not None and components["scarcity"] >= 70:
        chips.append({"emoji": "💎", "label": "Scarce Listings", "key": "scarcity"})
    if price_change_pct is not None and price_change_pct >= 3:
        chips.append({"emoji": "📈", "label": "Price Rising", "key": "price_rising"})
    if listings_change is not None and listings_change <= -3:
        chips.append({"emoji": "🏷", "label": "Supply Tightening", "key": "supply_tightening"})
    if components.get("auction_activity") is not None and components["auction_activity"] >= 60:
        chips.append({"emoji": "🔨", "label": "Auction Activity", "key": "auction_activity"})
    if components.get("card_liquidity") is not None and components["card_liquidity"] >= 75:
        chips.append({"emoji": "💧", "label": "High Liquidity", "key": "high_liquidity"})

    return chips


def _phrase_from_chips(chips: list[dict[str, str]], limit: int = 3) -> str:
    labels = [chip["label"].lower() for chip in chips[:limit]]
    if not labels:
        return ""
    if len(labels) == 1:
        return labels[0]
    if len(labels) == 2:
        return f"{labels[0]} and {labels[1]}"
    return ", ".join(labels[:-1]) + f", and {labels[-1]}"


def _build_explanation(
    *,
    components: dict[str, float | None],
    chips: list[dict[str, str]],
    price_change_pct: float | None,
    listings_change: int | None,
) -> str:
    supportive: list[str] = []
    limiting: list[str] = []

    performance = components.get("player_performance")
    demand = components.get("collector_demand")
    supply = components.get("listing_supply")
    movement = components.get("price_movement")

    if performance is not None and performance >= 70:
        supportive.append("strong recent offensive production")
    elif performance is not None and performance < 45:
        limiting.append("weaker recent offensive production")

    if demand is not None and demand >= 65:
        supportive.append("increasing collector demand")
    elif demand is not None and demand < 40:
        limiting.append("soft collector demand")

    if movement is not None and movement >= 60:
        supportive.append("positive market momentum")
    elif movement is not None and movement < 40:
        limiting.append("weakening market momentum")

    if price_change_pct is not None and price_change_pct >= 3:
        supportive.append("rising auction and listing prices")
    elif price_change_pct is not None and price_change_pct <= -3:
        limiting.append("recent price softness")

    if supply is not None and supply >= 70:
        supportive.append("tightening listing supply")
    elif supply is not None and supply < 35:
        limiting.append("increasing supply")

    if listings_change is not None and listings_change >= 5:
        limiting.append("expanding active listings")

    chip_phrase = _phrase_from_chips(chips)
    if chip_phrase and not supportive:
        supportive.append(chip_phrase)

    if len(supportive) >= len(limiting) and supportive:
        return f"Supported by {', '.join(supportive[:3])}."
    if limiting:
        return f"Limited by {', '.join(limiting[:3])}."
    if supportive:
        return f"Supported by {', '.join(supportive[:3])}."
    return "Stored card intelligence is still building for this card."


def build_card_intelligence(
    *,
    query_name: str,
    snapshot: MarketSnapshot,
    card_label: str | None = None,
    player_name: str | None = None,
    player_performance_score: float | None = None,
    player_momentum_score: float | None = None,
    price_change_pct: float | None = None,
    listings_change: int | None = None,
    population_count: int | None = None,
    auction_count: int | None = None,
    listings_with_bids: int | None = None,
) -> dict[str, Any]:
    """Synthesize card intelligence from stored inputs only."""
    missing: list[str] = []
    if snapshot.listings_count == 0:
        missing.append("listings")
        identity = get_card_identity(card_label=card_label, evidence={"query_name": query_name})
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
            "evidence": {
                "query_name": query_name,
                "listings_count": 0,
                "card_label": card_label,
                "player_name": player_name,
                "evidence_tier": "INSUFFICIENT",
                "explanation": "Stored card intelligence is still building for this card.",
                "factors": [],
                "identity": identity,
                "card_intelligence_version": CARD_INTELLIGENCE_V1,
            },
        }

    median_price = _median_price(snapshot)
    demand = _score_collector_demand(snapshot)
    scarcity = _score_scarcity(snapshot)
    listing_supply = _score_listing_supply(snapshot.listings_count)
    card_liquidity = _score_card_liquidity(snapshot.listings_count)
    price_movement = _score_price_movement(price_change_pct)
    market_momentum = _score_market_momentum(player_momentum_score, price_change_pct)
    activity = clamp_score((snapshot.listings_count / 30) * 100)

    population_score = None
    if population_count is not None:
        population_score = clamp_score(max(20, 100 - (population_count / 50)))

    auction_score = None
    if auction_count is not None and snapshot.listings_count > 0:
        auction_score = clamp_score((auction_count / max(snapshot.listings_count, 1)) * 100)

    components: dict[str, float | None] = {
        "player_performance": round(player_performance_score, 2) if player_performance_score is not None else None,
        "market_momentum": market_momentum,
        "price_movement": price_movement,
        "collector_demand": demand,
        "scarcity": scarcity,
        "population": round(population_score, 2) if population_score is not None else None,
        "listing_supply": round(listing_supply, 2),
        "auction_activity": round(auction_score, 2) if auction_score is not None else None,
        "card_liquidity": round(card_liquidity, 2) if card_liquidity is not None else None,
    }

    score_parts = [v for v in components.values() if v is not None]
    card_score = round(sum(score_parts) / len(score_parts), 2) if score_parts else None

    evidence_tier = _derive_evidence_tier(components, missing)
    query_signals = {
        "rookie": snapshot.tags.rookie_count > 0 or query_name == "bowman_chrome",
        "autograph": snapshot.tags.auto_count > 0 or query_name == "auto",
        "psa10": snapshot.tags.psa10_count > 0 or query_name == "psa10",
    }
    recommendation = _derive_card_recommendation(
        evidence_tier=evidence_tier,
        components=components,
        price_change_pct=price_change_pct,
        listings_change=listings_change,
        query_signals=query_signals,
    )

    chips = _build_factor_chips(
        components=components,
        snapshot=snapshot,
        price_change_pct=price_change_pct,
        listings_change=listings_change,
        population_count=population_count,
    )
    explanation = _build_explanation(
        components=components,
        chips=chips,
        price_change_pct=price_change_pct,
        listings_change=listings_change,
    )

    identity = get_card_identity(
        card_label=card_label,
        evidence={
            "query_name": query_name,
            "tags": snapshot.tags.model_dump(),
            "card_label": card_label,
        },
    )

    return {
        "card_signal_score": card_score,
        "recommendation": recommendation,
        "conviction": "High" if evidence_tier == "HIGH" else ("Medium" if evidence_tier == "MEDIUM" else "Low"),
        "risk": "Low" if demand is not None and demand >= 65 else "Medium",
        "time_horizon": "2-4 weeks",
        "market_activity_score": round(activity, 2),
        "demand_score": demand,
        "momentum_score": market_momentum,
        "scarcity_score": scarcity,
        "missing_inputs": missing,
        "evidence": {
            "query_name": query_name,
            "listings_count": snapshot.listings_count,
            "avg_price": snapshot.avg_price,
            "median_price": median_price,
            "price_change_pct": price_change_pct,
            "listings_change": listings_change,
            "auction_count": auction_count,
            "listings_with_bids": listings_with_bids,
            "population_count": population_count,
            "tags": snapshot.tags.model_dump(),
            "components": components,
            "evidence_tier": evidence_tier,
            "explanation": explanation,
            "factors": chips,
            "identity": identity,
            "card_label": card_label,
            "player_name": player_name,
            "card_intelligence_version": CARD_INTELLIGENCE_V1,
        },
    }


def card_intelligence_from_snapshot(
    query_name: str,
    snapshot: MarketSnapshot,
    player_name: str,
    *,
    card_label: str | None = None,
    player_performance_score: float | None = None,
    player_momentum_score: float | None = None,
    price_change_pct: float | None = None,
    listings_change: int | None = None,
    population_count: int | None = None,
) -> dict[str, Any]:
    """Backward-compatible entry point used by weekly scoring."""
    return build_card_intelligence(
        query_name=query_name,
        snapshot=snapshot,
        card_label=card_label,
        player_name=player_name,
        player_performance_score=player_performance_score,
        player_momentum_score=player_momentum_score,
        price_change_pct=price_change_pct,
        listings_change=listings_change,
        population_count=population_count,
    )
