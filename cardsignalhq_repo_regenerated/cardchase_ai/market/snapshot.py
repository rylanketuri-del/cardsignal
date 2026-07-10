"""Active listing summary calculations for card market snapshots."""

from __future__ import annotations

from datetime import datetime, timezone
from statistics import median
from typing import Any

from cardchase_ai.models.schemas import CardMarketSnapshot, NormalizedActiveListing

CARD_MARKET_SNAPSHOT_ALGORITHM_VERSION = "card-active-listing-snapshot-v1"


def _round_money(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 2)


def _classify_data_quality(sample_size: int) -> str:
    if sample_size >= 10:
        return "HIGH"
    if sample_size >= 5:
        return "MEDIUM"
    if sample_size >= 2:
        return "LOW"
    return "INSUFFICIENT"


def build_card_market_snapshot(
    card: dict[str, Any],
    listings: list[NormalizedActiveListing | dict[str, Any]],
    *,
    query: str,
    captured_at: datetime | None = None,
    algorithm_version: str = CARD_MARKET_SNAPSHOT_ALGORITHM_VERSION,
) -> CardMarketSnapshot:
    moment = captured_at or datetime.now(timezone.utc)

    normalized: list[NormalizedActiveListing] = []
    for listing in listings:
        try:
            if isinstance(listing, NormalizedActiveListing):
                normalized.append(listing)
            else:
                normalized.append(NormalizedActiveListing.model_validate(listing))
        except Exception:
            continue

    auction_count = sum(1 for row in normalized if row.listing_type == "auction")
    buy_it_now_count = sum(1 for row in normalized if row.listing_type == "buy_it_now")
    listings_with_bids = sum(1 for row in normalized if (row.bid_count or 0) > 0)
    total_bid_count = sum(int(row.bid_count or 0) for row in normalized)

    priced = [row for row in normalized if row.total_price is not None and row.total_price > 0]
    sample_size = len(priced)

    item_prices = [float(row.price) for row in priced if row.price is not None]
    total_prices = [float(row.total_price) for row in priced if row.total_price is not None]
    shipping_values = [float(row.shipping) for row in priced if row.shipping is not None]

    currency = priced[0].currency if priced else "USD"

    average_price = _round_money(sum(item_prices) / len(item_prices)) if item_prices else None
    median_price = _round_money(float(median(item_prices))) if item_prices else None
    minimum_price = _round_money(min(item_prices)) if item_prices else None
    maximum_price = _round_money(max(item_prices)) if item_prices else None
    average_shipping = _round_money(sum(shipping_values) / len(shipping_values)) if shipping_values else None
    total_market_value = _round_money(sum(total_prices)) if total_prices else None

    return CardMarketSnapshot(
        cs_card_id=card["cs_card_id"],
        cs_player_id=card["cs_player_id"],
        league=card.get("league") or "MLB",
        source="ebay",
        query=query,
        captured_at=moment,
        active_listing_count=len(normalized),
        auction_count=auction_count,
        buy_it_now_count=buy_it_now_count,
        listings_with_bids=listings_with_bids,
        total_bid_count=total_bid_count,
        average_price=average_price,
        median_price=median_price,
        minimum_price=minimum_price,
        maximum_price=maximum_price,
        average_shipping=average_shipping,
        total_market_value=total_market_value,
        currency=currency,
        sample_size=sample_size,
        data_quality=_classify_data_quality(sample_size),
        algorithm_version=algorithm_version,
    )
