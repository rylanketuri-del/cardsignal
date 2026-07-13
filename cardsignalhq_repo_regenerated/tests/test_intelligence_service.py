"""Tests for normalized intelligence read service and repositories."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

from cardchase_ai.intelligence_service import (
    build_normalized_leader_rows,
    get_player_intelligence,
    intelligence_to_leader_entry,
)
from cardchase_ai.league_evidence import has_sufficient_evidence
from cardchase_ai.models.weekly import WEEKLY_INTELLIGENCE_V1, PlayerWeeklySignalSnapshot
from cardchase_ai.repositories.adapters import (
    MarketSnapshotRepositoryAdapter,
    PerformanceSnapshotRepositoryAdapter,
    PlayerRegistryRepositoryAdapter,
    RepositoryBundle,
    SignalDriverRepositoryAdapter,
    WeeklySnapshotRepositoryAdapter,
)
from cardchase_ai.weekly_storage import WeeklyJsonStorage, WeeklyStorage


def _snap(**overrides) -> PlayerWeeklySignalSnapshot:
    now = datetime(2026, 7, 8, 12, 0, tzinfo=ZoneInfo("UTC"))
    base = dict(
        snapshot_id="snap-1",
        run_id="run-1",
        cs_player_id="mlb:1",
        source_player_id="1",
        league="MLB",
        sport="MLB",
        season=2026,
        year=2026,
        week_number=28,
        period_start=now,
        period_end=now,
        card_signal_score=75.0,
        performance_score=70.0,
        market_score=65.0,
        recommendation="HOLD",
        conviction="High",
        status="RISING",
        missing_inputs=[],
        algorithm_version=WEEKLY_INTELLIGENCE_V1,
        captured_at=now,
        player_name="Test Player",
        signal_drivers=[{
            "driver_type": "POWER_PRODUCTION",
            "label": "Power Production",
            "description": "3 HR in 7 days",
            "evidence": {},
            "source_method": "mlb_stats_api",
        }],
        capabilities={"recent_form": "SUPPORTED", "signal_drivers": "SUPPORTED"},
    )
    base.update(overrides)
    return PlayerWeeklySignalSnapshot(**base)


class FakeWeeklyRepo:
    def __init__(self, snapshot: PlayerWeeklySignalSnapshot | None, history: list[dict] | None = None):
        self.snapshot = snapshot
        self.history = history or []

    def get_latest_official_run(self, league: str):
        return {"player_snapshots": [self.snapshot.model_dump(mode="json")] if self.snapshot else []}

    def get_player_weekly_history(self, league: str, player_id: str, limit: int = 12):
        return self.history

    def get_latest_player_snapshot(self, league: str, player_id: str):
        return self.snapshot

    def get_card_snapshots_for_player(self, league: str, player_id: str):
        return []


class EvidenceGateTests(unittest.TestCase):
    def test_mlb_stats_7d_missing_fails(self):
        self.assertFalse(has_sufficient_evidence("MLB", 70.0, 60.0, ["stats_7d"]))

    def test_mlb_valid_stats_7d_passes(self):
        self.assertTrue(has_sufficient_evidence("MLB", 70.0, 60.0, []))

    def test_nfl_uses_stats_recent(self):
        self.assertFalse(has_sufficient_evidence("NFL", 70.0, 60.0, ["stats_recent"]))
        self.assertTrue(has_sufficient_evidence("NFL", 70.0, 60.0, []))

    def test_nfl_keys_do_not_alter_mlb(self):
        self.assertFalse(has_sufficient_evidence("MLB", 70.0, 60.0, ["stats_7d"]))
        self.assertTrue(has_sufficient_evidence("MLB", 70.0, 60.0, ["stats_recent"]))


class NormalizedReadServiceTests(unittest.TestCase):
    def _bundle(self, snapshot: PlayerWeeklySignalSnapshot | None) -> RepositoryBundle:
        weekly = FakeWeeklyRepo(snapshot, history=[snapshot.model_dump(mode="json")] if snapshot else [])
        return RepositoryBundle(
            weekly=weekly,
            performance=MagicMock(),
            drivers=MagicMock(),
            market=MagicMock(get_latest_player_market=MagicMock(return_value=None), get_player_market_history=MagicMock(return_value=[])),
            registry=MagicMock(),
        )

    def test_get_player_intelligence_mlb(self):
        snap = _snap()
        repos = self._bundle(snap)
        payload = get_player_intelligence("MLB", "1", repos)
        self.assertIsNotNone(payload)
        self.assertEqual(payload.league, "MLB")
        self.assertGreater(payload.driver_count, 0)

    def test_get_player_intelligence_nfl(self):
        snap = _snap(
            cs_player_id="CS-NFL-P-TEST",
            source_player_id="TEST",
            league="NFL",
            sport="FOOTBALL",
            algorithm_version="NFL_PLAYER_SIGNAL_V1",
            missing_inputs=["stats_recent"],
            recommendation=None,
        )
        repos = self._bundle(snap)
        payload = get_player_intelligence("NFL", "TEST", repos)
        self.assertIsNotNone(payload)
        self.assertEqual(payload.recommendation, "WATCH")
        self.assertEqual(payload.evidence, "INSUFFICIENT")

    def test_homepage_leader_rows_from_normalized_payload(self):
        snaps = [_snap(), _snap(cs_player_id="mlb:2", source_player_id="2", player_name="Player Two", card_signal_score=80.0)]
        repos = RepositoryBundle(
            weekly=FakeWeeklyRepo(snaps[0], history=[s.model_dump(mode="json") for s in snaps]),
            performance=MagicMock(),
            drivers=MagicMock(),
            market=MagicMock(get_latest_player_market=MagicMock(return_value=None), get_player_market_history=MagicMock(return_value=[])),
            registry=MagicMock(),
        )
        rows = build_normalized_leader_rows("MLB", snaps, repos)
        self.assertEqual(len(rows), 2)
        self.assertIn("intelligence", rows[0])
        self.assertEqual(rows[0]["intelligence"]["league"], "MLB")

    def test_leader_entry_preserves_nulls(self):
        snap = _snap(card_signal_score=None, momentum_score=None)
        repos = self._bundle(snap)
        payload = get_player_intelligence("MLB", "1", repos)
        row = intelligence_to_leader_entry(payload, 1)
        self.assertIsNone(row["score"])
        self.assertIsNone(row["momentum"])


class RepositoryAdapterTests(unittest.TestCase):
    def test_weekly_adapter_reads_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = WeeklyStorage(None, WeeklyJsonStorage(Path(tmp)))
            adapter = WeeklySnapshotRepositoryAdapter(store)
            self.assertIsNone(adapter.get_latest_player_snapshot("MLB", "999"))


if __name__ == "__main__":
    unittest.main()
