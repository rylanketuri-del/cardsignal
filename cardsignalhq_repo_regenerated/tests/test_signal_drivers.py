"""Focused tests for Signal Drivers & Seasonal Intelligence (Sprint 9.3)."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from cardchase_ai.development_provider import ManualVerifiedDevelopmentProvider, StoredDevelopmentProvider
from cardchase_ai.models.schemas import MarketSnapshot, RollingHitterStats
from cardchase_ai.models.signal_driver import LeagueSeasonMetadata, SignalDriver
from cardchase_ai.season_state import (
    MLBSeasonStateAdapter,
    NBASeasonStateAdapter,
    NFLSeasonStateAdapter,
    resolve_season_state,
)
from cardchase_ai.signal_driver_storage import SignalDriverJsonStorage, SignalDriverStorage
from cardchase_ai.signal_drivers import (
    build_mlb_recent_form_drivers,
    build_player_signal_drivers,
    filter_current_drivers,
    group_drivers_by_category,
)
from cardchase_ai.signal_driver_service import build_signal_drivers_response


def _stats_7d(**kwargs) -> RollingHitterStats:
    defaults = dict(
        games=5,
        at_bats=20,
        hits=8,
        home_runs=2,
        rbi=6,
        stolen_bases=1,
        walks=3,
        strikeouts=4,
        avg=0.400,
        obp=0.450,
        slg=0.650,
        ops=1.100,
    )
    defaults.update(kwargs)
    return RollingHitterStats(**defaults)


def _stats_30d(**kwargs) -> RollingHitterStats:
    defaults = dict(
        games=20,
        at_bats=75,
        hits=22,
        home_runs=4,
        rbi=14,
        stolen_bases=2,
        walks=8,
        strikeouts=18,
        avg=0.293,
        obp=0.350,
        slg=0.450,
        ops=0.800,
    )
    defaults.update(kwargs)
    return RollingHitterStats(**defaults)


def _metadata_offseason(season: int = 2026) -> LeagueSeasonMetadata:
    tz = timezone.utc
    return LeagueSeasonMetadata(
        league="MLB",
        sport="MLB",
        season=season,
        offseason_start=datetime(2025, 11, 1, tzinfo=tz),
        offseason_end=datetime(2026, 2, 15, tzinfo=tz),
        regular_season_start=datetime(2026, 3, 27, tzinfo=tz),
        regular_season_end=datetime(2026, 9, 28, tzinfo=tz),
        source_type="OFFICIAL_API",
        source_reference="test:mlb",
        captured_at=datetime(2026, 1, 15, tzinfo=tz),
    )


def _metadata_regular(season: int = 2026) -> LeagueSeasonMetadata:
    tz = timezone.utc
    return LeagueSeasonMetadata(
        league="MLB",
        sport="MLB",
        season=season,
        regular_season_start=datetime(2026, 3, 27, tzinfo=tz),
        regular_season_end=datetime(2026, 9, 28, tzinfo=tz),
        source_type="OFFICIAL_API",
        source_reference="test:mlb",
        captured_at=datetime(2026, 7, 1, tzinfo=tz),
    )


class SeasonStateTests(unittest.TestCase):
    def test_unknown_without_metadata(self):
        state = resolve_season_state("MLB", season=2026, metadata=None)
        self.assertEqual(state.state, "UNKNOWN")

    def test_regular_season_from_stored_metadata(self):
        anchor = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
        state = resolve_season_state("MLB", season=2026, anchor=anchor, metadata=_metadata_regular())
        self.assertEqual(state.state, "REGULAR_SEASON")

    def test_offseason_from_stored_metadata(self):
        anchor = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
        state = resolve_season_state("MLB", season=2026, anchor=anchor, metadata=_metadata_offseason())
        self.assertEqual(state.state, "OFFSEASON")

    def test_player_inactive_during_regular_season(self):
        anchor = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
        state = resolve_season_state(
            "MLB",
            season=2026,
            anchor=anchor,
            metadata=_metadata_regular(),
            player_games_recent=0,
        )
        self.assertEqual(state.state, "INACTIVE")

    def test_nba_returns_unknown_without_metadata(self):
        adapter = NBASeasonStateAdapter()
        state = adapter.resolve(
            anchor=datetime(2026, 7, 10, tzinfo=timezone.utc),
            season=2026,
            metadata=None,
        )
        self.assertEqual(state.state, "UNKNOWN")

    def test_nfl_returns_unknown_without_metadata(self):
        adapter = NFLSeasonStateAdapter()
        state = adapter.resolve(
            anchor=datetime(2026, 7, 10, tzinfo=timezone.utc),
            season=2026,
            metadata=None,
        )
        self.assertEqual(state.state, "UNKNOWN")


class SignalDriverCreationTests(unittest.TestCase):
    def test_deterministic_recent_form_driver(self):
        drivers = build_mlb_recent_form_drivers(
            player_name="Juan Soto",
            source_player_id=665742,
            stats_7d=_stats_7d(),
            stats_30d=_stats_30d(),
            season=2026,
            captured_at=datetime(2026, 7, 10, tzinfo=timezone.utc),
        )
        self.assertTrue(drivers)
        ids = [d.driver_id for d in drivers]
        self.assertEqual(len(ids), len(set(ids)))

        ops_driver = next(d for d in drivers if d.metric_name == "ops")
        self.assertEqual(ops_driver.impact, "POSITIVE")
        self.assertEqual(ops_driver.evidence_quality, "HIGH")
        self.assertIn("7-day OPS", ops_driver.summary)

    def test_missing_evidence_is_insufficient(self):
        drivers = build_mlb_recent_form_drivers(
            player_name="Test Player",
            source_player_id=1,
            stats_7d=_stats_7d(),
            stats_30d=_stats_30d(games=0, at_bats=0),
            season=2026,
        )
        for driver in drivers:
            if driver.metric_name in {"avg", "obp", "slg", "ops"}:
                self.assertEqual(driver.evidence_quality, "INSUFFICIENT")

    def test_no_recent_form_when_no_games(self):
        drivers = build_mlb_recent_form_drivers(
            player_name="Test Player",
            source_player_id=1,
            stats_7d=_stats_7d(games=0, at_bats=0),
            stats_30d=_stats_30d(),
            season=2026,
        )
        self.assertEqual(drivers, [])

    def test_offseason_skips_recent_form(self):
        drivers = build_player_signal_drivers(
            player_name="Test Player",
            source_player_id=1,
            stats_7d=_stats_7d(),
            stats_30d=_stats_30d(),
            season_state="OFFSEASON",
            season=2025,
        )
        recent = [d for d in drivers if d.driver_type == "RECENT_FORM"]
        self.assertEqual(recent, [])
        prev = [d for d in drivers if "previous_season" in d.source_reference]
        self.assertTrue(prev)

    def test_nba_returns_no_fabricated_drivers(self):
        drivers = build_player_signal_drivers(
            player_name="Fake NBA",
            source_player_id=99,
            league="NBA",
            season_state="REGULAR_SEASON",
        )
        self.assertEqual(drivers, [])

    def test_driver_does_not_issue_buy_recommendation(self):
        drivers = build_player_signal_drivers(
            player_name="Test Player",
            source_player_id=1,
            stats_7d=_stats_7d(),
            stats_30d=_stats_30d(),
            market_snapshots={"broad": MarketSnapshot(query_name="broad", listings_count=12, avg_price=50)},
            season_state="REGULAR_SEASON",
        )
        for driver in drivers:
            self.assertNotIn(driver.title.upper(), {"BUY", "RECOMMENDATION"})
            self.assertNotIn("recommend buy", driver.summary.lower())


class DevelopmentProviderTests(unittest.TestCase):
    def test_rejects_unsupported_rumor(self):
        provider = ManualVerifiedDevelopmentProvider()
        raw = {
            "driver_type": "TRADE",
            "title": "Trade rumor",
            "summary": "Sources say the player may be traded.",
            "occurred_at": "2026-07-01T12:00:00+00:00",
            "source_type": "MANUAL_VERIFIED",
            "source_reference": "rumor:1",
        }
        valid, reason = provider.validate_development(raw)
        self.assertFalse(valid)
        self.assertIn("rumor", reason)

    def test_accepts_verified_development(self):
        provider = ManualVerifiedDevelopmentProvider()
        raw = {
            "driver_type": "AWARD",
            "title": "Silver Slugger",
            "summary": "Player received Silver Slugger award.",
            "occurred_at": "2026-07-01T12:00:00+00:00",
            "source_type": "MANUAL_VERIFIED",
            "source_reference": "award:2026:1",
            "impact": "POSITIVE",
            "evidence_quality": "HIGH",
        }
        valid, _ = provider.validate_development(raw)
        self.assertTrue(valid)
        driver = provider.normalize_development(
            raw,
            cs_player_id="mlb:1",
            source_player_id="1",
            league="MLB",
        )
        self.assertIsNotNone(driver)
        self.assertEqual(driver.source_type, "MANUAL_VERIFIED")


class SignalDriverStorageTests(unittest.TestCase):
    def test_duplicate_prevention(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = SignalDriverJsonStorage(Path(tmp))
            wrapper = SignalDriverStorage(None, storage)
            now = datetime(2026, 7, 10, tzinfo=timezone.utc)
            driver = SignalDriver(
                driver_id="abc",
                cs_player_id="mlb:1",
                source_player_id="1",
                league="MLB",
                sport="MLB",
                driver_type="RECENT_FORM",
                category="PERFORMANCE",
                title="Recent batting surge",
                summary="Test summary",
                metric_name="ops",
                metric_value=1.1,
                comparison_value=0.8,
                impact="POSITIVE",
                evidence_quality="HIGH",
                source_type="PERFORMANCE_SNAPSHOT",
                source_reference="stats_7d_vs_30d:2026",
                occurred_at=now,
                captured_at=now,
            )
            driver.driver_id = driver.identity_key()[:24]
            first = wrapper.append_drivers([driver])
            second = wrapper.append_drivers([driver])
            self.assertEqual(len(first), 1)
            self.assertEqual(len(second), 0)

    def test_expired_drivers_filtered(self):
        now = datetime(2026, 7, 10, tzinfo=timezone.utc)
        active = SignalDriver(
            driver_id="active",
            cs_player_id="mlb:1",
            source_player_id="1",
            league="MLB",
            sport="MLB",
            driver_type="RECENT_FORM",
            category="PERFORMANCE",
            title="Active",
            summary="Active driver",
            impact="POSITIVE",
            evidence_quality="HIGH",
            source_type="PERFORMANCE_SNAPSHOT",
            source_reference="active",
            occurred_at=now,
            captured_at=now,
            expires_at=now + timedelta(days=1),
        )
        expired = SignalDriver(
            driver_id="expired",
            cs_player_id="mlb:1",
            source_player_id="1",
            league="MLB",
            sport="MLB",
            driver_type="RECENT_FORM",
            category="PERFORMANCE",
            title="Expired",
            summary="Expired driver",
            impact="NEUTRAL",
            evidence_quality="HIGH",
            source_type="PERFORMANCE_SNAPSHOT",
            source_reference="expired",
            occurred_at=now - timedelta(days=10),
            captured_at=now - timedelta(days=10),
            expires_at=now - timedelta(days=1),
        )
        current = filter_current_drivers([active, expired], now=now)
        self.assertEqual(len(current), 1)
        self.assertEqual(current[0].driver_id, "active")


class LayoutBehaviorTests(unittest.TestCase):
    def test_offseason_hides_recent_performance_group(self):
        now = datetime(2026, 7, 10, tzinfo=timezone.utc)
        driver = SignalDriver(
            driver_id="recent",
            cs_player_id="mlb:1",
            source_player_id="1",
            league="MLB",
            sport="MLB",
            driver_type="RECENT_FORM",
            category="PERFORMANCE",
            title="Recent batting surge",
            summary="Test",
            impact="POSITIVE",
            evidence_quality="HIGH",
            source_type="PERFORMANCE_SNAPSHOT",
            source_reference="stats_7d:2026",
            occurred_at=now,
            captured_at=now,
        )
        groups = group_drivers_by_category([driver], "OFFSEASON")
        self.assertEqual(groups["recent_performance"], [])

    def test_previous_season_labeling(self):
        now = datetime(2026, 1, 15, tzinfo=timezone.utc)
        driver = SignalDriver(
            driver_id="prev",
            cs_player_id="mlb:1",
            source_player_id="1",
            league="MLB",
            sport="MLB",
            driver_type="SEASON_PERFORMANCE",
            category="PERFORMANCE",
            title="Previous season snapshot",
            summary="Previous season stored stats.",
            impact="NEUTRAL",
            evidence_quality="HIGH",
            source_type="PERFORMANCE_SNAPSHOT",
            source_reference="previous_season:2025",
            occurred_at=now,
            captured_at=now,
            metadata={"label": "previous_season"},
        )
        groups = group_drivers_by_category([driver], "OFFSEASON")
        self.assertEqual(len(groups["previous_season"]), 1)

    def test_empty_driver_response(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = SignalDriverJsonStorage(Path(tmp))
            wrapper = SignalDriverStorage(None, storage)
            player = {
                "player_id": 1,
                "player_name": "Test Player",
                "sport": "MLB",
                "stats_7d": _stats_7d().model_dump(),
                "stats_30d": _stats_30d().model_dump(),
            }
            response = build_signal_drivers_response(
                player_payload=player,
                storage=wrapper,
                league="MLB",
                season=2026,
            )
            self.assertEqual(response.current_drivers, [])
            self.assertEqual(response.data_quality.current_drivers, 0)


class FrontendGuardTests(unittest.TestCase):
    def test_app_js_uses_signal_drivers_section(self):
        app_js = Path(__file__).resolve().parents[1] / "frontend" / "app.js"
        content = app_js.read_text(encoding="utf-8")
        self.assertIn("renderSignalDrivers", content)
        self.assertIn("Signal Drivers", content)
        self.assertNotIn("Why This Signal", content)
        self.assertIn("fetchPlayerSignalDrivers", content)

    def test_no_stale_recent_stats_in_offseason_snapshot(self):
        app_js = Path(__file__).resolve().parents[1] / "frontend" / "app.js"
        content = app_js.read_text(encoding="utf-8")
        self.assertIn("not current recent form", content)
        self.assertIn("Last 7 Days", content)


if __name__ == "__main__":
    unittest.main()
