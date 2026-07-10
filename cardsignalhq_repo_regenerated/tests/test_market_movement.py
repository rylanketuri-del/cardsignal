"""Tests for historical market movement calculation."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from cardchase_ai.market_movement import (
    MOVEMENT_PENDING_LABEL,
    MarketSnapshotHistory,
    calculate_movement,
    calculate_price_change_pct,
)
from cardchase_ai.models.schemas import MarketSnapshot


class PriceChangeTests(unittest.TestCase):
    def test_valid_movement(self):
        self.assertEqual(calculate_price_change_pct(110.0, 100.0), 10.0)

    def test_zero_denominator(self):
        self.assertIsNone(calculate_price_change_pct(110.0, 0.0))

    def test_missing_history(self):
        current = MarketSnapshot(query_name="broad", listings_count=10, avg_price=50.0)
        movement = calculate_movement(
            source_player_id="1",
            query_name="broad",
            league="MLB",
            run_id="run-1",
            year=2026,
            week_number=28,
            current=current,
            prior=None,
        )
        self.assertIsNone(movement.price_change_pct)
        self.assertEqual(movement.status, "pending")
        self.assertEqual(movement.label, MOVEMENT_PENDING_LABEL)

    def test_currency_mismatch(self):
        current = MarketSnapshot(query_name="broad", listings_count=10, avg_price=50.0)
        prior = {"avg_price": 40.0, "listings_count": 8, "currency": "EUR"}
        movement = calculate_movement(
            source_player_id="1",
            query_name="broad",
            league="MLB",
            run_id="run-1",
            year=2026,
            week_number=28,
            current=current,
            prior=prior,
            currency="USD",
        )
        self.assertEqual(movement.status, "unavailable")
        self.assertEqual(movement.label, MOVEMENT_PENDING_LABEL)


class MarketSnapshotHistoryTests(unittest.TestCase):
    def test_prior_snapshot_enables_calculated_movement(self):
        with tempfile.TemporaryDirectory() as tmp:
            history = MarketSnapshotHistory(Path(tmp))
            captured = datetime(2026, 7, 1, tzinfo=timezone.utc)
            history.append(
                run_id="run-old",
                cs_player_id="mlb:1",
                query_name="broad",
                snapshot=MarketSnapshot(query_name="broad", listings_count=8, avg_price=40.0),
                captured_at=captured,
                currency="USD",
            )
            current = MarketSnapshot(query_name="broad", listings_count=10, avg_price=50.0)
            movement = calculate_movement(
                source_player_id="1",
                query_name="broad",
                league="MLB",
                run_id="run-new",
                year=2026,
                week_number=28,
                current=current,
                prior=history.fetch_prior("mlb:1", "broad", before_iso="2026-07-02T00:00:00+00:00"),
            )
            self.assertEqual(movement.status, "calculated")
            self.assertEqual(movement.price_change_pct, 25.0)
            self.assertEqual(movement.listings_change, 2)


if __name__ == "__main__":
    unittest.main()
