"""Verification checks for card market snapshot foundation."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cardchase_ai.identity import enrich_card_registry_entry, enrich_player_entry  # noqa: E402
from cardchase_ai.market.queries import build_card_search_query  # noqa: E402
from cardchase_ai.market.snapshot import build_card_market_snapshot  # noqa: E402
from cardchase_ai.models.schemas import NormalizedActiveListing  # noqa: E402


def main() -> int:
    errors: list[str] = []

    player = enrich_player_entry({"player_id": 691406, "player_name": "James Wood", "sport": "MLB"})
    card = enrich_card_registry_entry(
        {
            "set": "2025 Topps Chrome",
            "card": "Refractor",
            "parallel": "Refractor",
            "grade": "Raw",
        },
        league="MLB",
        source_player_id=691406,
        cs_player_id=player["cs_player_id"],
        player_name="James Wood",
    )

    query = build_card_search_query(card)
    if query != "James Wood 2025 Topps Chrome Refractor":
        errors.append(f"unexpected raw query: {query}")

    graded = enrich_card_registry_entry(
        {
            "set": "2025 Topps Chrome",
            "card": "Refractor",
            "parallel": "Refractor",
            "grade": "PSA 10",
        },
        league="MLB",
        source_player_id=691406,
        cs_player_id=player["cs_player_id"],
        player_name="James Wood",
    )
    graded_query = build_card_search_query(graded)
    if graded_query != "James Wood 2025 Topps Chrome Refractor PSA 10":
        errors.append(f"unexpected graded query: {graded_query}")

    listings = [
        NormalizedActiveListing(
            source_listing_id="1",
            title="Sample",
            price=100.0,
            shipping=5.0,
            total_price=105.0,
            listing_type="buy_it_now",
            bid_count=0,
            captured_at=datetime.now(timezone.utc).isoformat(),
        ),
        NormalizedActiveListing(
            source_listing_id="2",
            title="Auction",
            price=50.0,
            shipping=0.0,
            total_price=50.0,
            listing_type="auction",
            bid_count=3,
            captured_at=datetime.now(timezone.utc).isoformat(),
        ),
    ]

    snapshot = build_card_market_snapshot(card, listings, query=query)
    if snapshot.sample_size != 2:
        errors.append("expected sample_size=2")
    if snapshot.average_price != 75.0:
        errors.append(f"unexpected average_price: {snapshot.average_price}")
    if snapshot.data_quality != "LOW":
        errors.append(f"unexpected data_quality: {snapshot.data_quality}")
    if snapshot.active_listing_count != 2:
        errors.append("expected active_listing_count=2")

    empty_snapshot = build_card_market_snapshot(card, [], query=query)
    if empty_snapshot.data_quality != "INSUFFICIENT":
        errors.append("empty snapshot should be INSUFFICIENT")

    if errors:
        print("Card market snapshot verification failed:")
        for error in errors:
            print(f" - {error}")
        return 1

    print("Card market snapshot verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
