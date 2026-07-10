"""Player-level card market response helpers for API and UI consumption."""

from __future__ import annotations

from statistics import median
from typing import Any


def format_public_market_snapshot(snapshot: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return sanitized snapshot metrics — never raw eBay listing payloads."""
    if not snapshot:
        return None

    metrics = snapshot.get("metrics") or {}
    if metrics.get("active_listing_count") is None and snapshot.get("active_listing_count") is not None:
        metrics = snapshot

    return {
        "source": snapshot.get("source", "ebay"),
        "captured_at": snapshot.get("captured_at") or snapshot.get("created_at"),
        "active_listing_count": int(metrics.get("active_listing_count") or 0),
        "auction_count": int(metrics.get("auction_count") or 0),
        "buy_it_now_count": int(metrics.get("buy_it_now_count") or 0),
        "listings_with_bids": int(metrics.get("listings_with_bids") or 0),
        "total_bid_count": int(metrics.get("total_bid_count") or 0),
        "average_price": metrics.get("average_price"),
        "median_price": metrics.get("median_price"),
        "minimum_price": metrics.get("minimum_price"),
        "maximum_price": metrics.get("maximum_price"),
        "average_shipping": metrics.get("average_shipping"),
        "sample_size": int(metrics.get("sample_size") or 0),
        "data_quality": metrics.get("data_quality") or "INSUFFICIENT",
        "currency": metrics.get("currency") or "USD",
    }


def _parse_year(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def build_player_card_market_item(card: dict[str, Any], snapshot: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "cs_card_id": card.get("cs_card_id"),
        "year": _parse_year(card.get("year")),
        "manufacturer": card.get("manufacturer"),
        "set_name": card.get("set_name"),
        "card_name": card.get("card_name") or card.get("card"),
        "parallel": card.get("parallel"),
        "grade": card.get("grade"),
        "grading_company": card.get("grading_company"),
        "market_snapshot": format_public_market_snapshot(snapshot),
    }


def classify_market_depth(total_listings: int, cards_observed: int) -> str:
    if cards_observed <= 0 or total_listings <= 0:
        return "INSUFFICIENT"
    if total_listings >= 30 and cards_observed >= 3:
        return "HIGH"
    if total_listings >= 10:
        return "MEDIUM"
    if total_listings >= 3:
        return "LOW"
    return "INSUFFICIENT"


def aggregate_player_market(cards: list[dict[str, Any]]) -> dict[str, Any]:
    observed = [card for card in cards if card.get("market_snapshot")]
    snapshots = [card["market_snapshot"] for card in observed]

    total_active = sum(int(s.get("active_listing_count") or 0) for s in snapshots)
    total_auctions = sum(int(s.get("auction_count") or 0) for s in snapshots)
    total_bin = sum(int(s.get("buy_it_now_count") or 0) for s in snapshots)
    listings_with_bids = sum(int(s.get("listings_with_bids") or 0) for s in snapshots)
    total_bids = sum(int(s.get("total_bid_count") or 0) for s in snapshots)

    median_prices = [float(s["median_price"]) for s in snapshots if s.get("median_price") is not None]
    average_prices = [float(s["average_price"]) for s in snapshots if s.get("average_price") is not None]

    captured_times = [s.get("captured_at") for s in snapshots if s.get("captured_at")]
    most_recent = max(captured_times) if captured_times else None

    sample_sizes = [int(s.get("sample_size") or 0) for s in snapshots]
    total_sample = sum(sample_sizes)

    qualities = [str(s.get("data_quality") or "INSUFFICIENT").upper() for s in snapshots]
    if not qualities:
        aggregate_quality = "INSUFFICIENT"
    elif all(q == "HIGH" for q in qualities) and total_sample >= 10:
        aggregate_quality = "HIGH"
    elif any(q == "HIGH" for q in qualities) or (total_sample >= 10 and any(q == "MEDIUM" for q in qualities)):
        aggregate_quality = "MEDIUM"
    elif total_sample >= 2:
        aggregate_quality = "LOW"
    else:
        aggregate_quality = "INSUFFICIENT"

    return {
        "cards_observed": len(observed),
        "total_active_listings": total_active,
        "total_auctions": total_auctions,
        "total_buy_it_now": total_bin,
        "listings_with_bids": listings_with_bids,
        "total_bids": total_bids,
        "median_active_price": round(float(median(median_prices)), 2) if median_prices else None,
        "average_active_price": round(sum(average_prices) / len(average_prices), 2) if average_prices else None,
        "market_depth": classify_market_depth(total_active, len(observed)),
        "data_quality": aggregate_quality,
        "most_recent_captured_at": most_recent,
    }
