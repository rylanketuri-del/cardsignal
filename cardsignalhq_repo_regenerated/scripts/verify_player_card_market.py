"""Verification for player-level card market API response helpers."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cardchase_ai.market.player_market import (  # noqa: E402
    aggregate_player_market,
    build_player_card_market_item,
    classify_market_depth,
    format_public_market_snapshot,
)


def main() -> int:
    errors: list[str] = []

    snapshot = format_public_market_snapshot(
        {
            "source": "ebay",
            "captured_at": "2026-07-09T18:15:00Z",
            "metrics": {
                "active_listing_count": 24,
                "auction_count": 5,
                "buy_it_now_count": 19,
                "listings_with_bids": 3,
                "total_bid_count": 14,
                "average_price": 42.18,
                "median_price": 38.5,
                "sample_size": 24,
                "data_quality": "HIGH",
                "currency": "USD",
            },
        }
    )
    if snapshot is None or snapshot["data_quality"] != "HIGH":
        errors.append("expected sanitized snapshot with HIGH quality")

    if "query" in (snapshot or {}):
        errors.append("sanitized snapshot must not expose query field")

    card_item = build_player_card_market_item(
        {
            "cs_card_id": "CS-MLB-C-test",
            "year": "2025",
            "manufacturer": "Topps",
            "set_name": "Topps Chrome",
            "card_name": "Base Rookie",
            "parallel": "Base",
            "grade": "Raw",
            "grading_company": None,
        },
        snapshot,
    )
    if card_item["year"] != 2025:
        errors.append("expected numeric year in card item")

    aggregate = aggregate_player_market([card_item])
    if aggregate["cards_observed"] != 1:
        errors.append("expected one observed card")
    if classify_market_depth(30, 3) != "HIGH":
        errors.append("expected HIGH market depth")

    if errors:
        print("Player card market verification failed:")
        for error in errors:
            print(f" - {error}")
        return 1

    print("Player card market verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
