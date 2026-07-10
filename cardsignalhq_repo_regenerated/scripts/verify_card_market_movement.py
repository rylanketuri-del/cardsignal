"""Verification checks for card market historical movement."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cardchase_ai.market.history import build_player_market_activity_points, merge_snapshot_collections  # noqa: E402
from cardchase_ai.market.movement import (  # noqa: E402
    MovementToleranceConfig,
    calculate_card_market_movement,
    find_comparison_snapshot,
    movement_to_public_dict,
)


def _snapshot(
    *,
    card_id: str = "CS-MLB-C-test",
    player_id: str = "CS-MLB-P-1",
    captured_at: datetime,
    median: float,
    listings: int = 10,
    bids: int = 2,
    sample: int = 10,
    quality: str = "HIGH",
) -> dict:
    return {
        "cs_card_id": card_id,
        "cs_player_id": player_id,
        "source": "ebay",
        "captured_at": captured_at,
        "median_price": median,
        "average_price": median,
        "active_listing_count": listings,
        "total_bid_count": bids,
        "auction_count": 2,
        "sample_size": sample,
        "data_quality": quality,
        "currency": "USD",
        "algorithm_version": "card-active-listing-snapshot-v1",
    }


def main() -> int:
    errors: list[str] = []
    now = datetime(2026, 7, 10, 18, 0, tzinfo=timezone.utc)
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)

    history = [
        _snapshot(captured_at=two_weeks_ago, median=30.0, listings=8, bids=1, sample=8, quality="MEDIUM"),
        _snapshot(captured_at=week_ago, median=35.0, listings=10, bids=2, sample=10, quality="HIGH"),
        _snapshot(captured_at=now, median=42.0, listings=12, bids=4, sample=12, quality="HIGH"),
    ]

    comparison, gap = find_comparison_snapshot(history, history[-1], "7d", config=MovementToleranceConfig())
    if comparison is None:
        errors.append("expected 7d comparison snapshot")
    elif gap is None:
        errors.append("expected target gap for 7d window")

    movement = calculate_card_market_movement(history, window="7d")
    if movement is None:
        errors.append("expected movement result")
    else:
        if movement.median_price_change_pct is None:
            errors.append("expected median pct change")
        elif abs(movement.median_price_change_pct - 20.0) > 0.1:
            errors.append(f"unexpected median pct change: {movement.median_price_change_pct}")
        if movement.movement_quality == "INSUFFICIENT":
            errors.append("expected usable movement quality")

    public = movement_to_public_dict(movement)
    if public.get("has_movement") is not True:
        errors.append("public movement should report has_movement=true")

    zero_history = calculate_card_market_movement(
        [_snapshot(captured_at=now, median=40.0)],
        window="7d",
    )
    if zero_history is None or zero_history.median_price_change_pct is not None:
        errors.append("single snapshot should not produce pct movement")

    merged = merge_snapshot_collections(history, history[:1])
    if len(merged) != 3:
        errors.append("merge_snapshot_collections should dedupe without losing rows")

    activity = build_player_market_activity_points(history, limit=12)
    if len(activity) < 2:
        errors.append("expected activity points from multi-day history")

    if errors:
        print("Card market movement verification failed:")
        for error in errors:
            print(f" - {error}")
        return 1

    print("Card market movement verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
