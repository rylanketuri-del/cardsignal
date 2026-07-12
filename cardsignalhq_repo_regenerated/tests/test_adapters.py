"""Tests for the sport adapter framework (Sprint 11.0)."""

from __future__ import annotations

import unittest

from cardchase_ai.adapters import (
    get_league_adapter,
    get_sport_adapter,
    list_registered_leagues,
    list_searchable_leagues,
)
from cardchase_ai.models.weekly import (
    MLB_PLAYER_SIGNAL_V1,
    NFL_PLAYER_SIGNAL_V1,
    player_signal_algorithm_version,
)
from cardchase_ai.signals.drivers import MLB_CORE_DRIVERS, run_signal_drivers
from cardchase_ai.models.schemas import RollingHitterStats, MarketSnapshot


class LeagueRegistryTests(unittest.TestCase):
    def test_mlb_and_nfl_registered(self):
        leagues = list_registered_leagues()
        self.assertIn("MLB", leagues)
        self.assertIn("NFL", leagues)

    def test_get_mlb_adapter(self):
        adapter = get_league_adapter("mlb")
        self.assertEqual(adapter.league_code, "MLB")
        self.assertTrue(adapter.pipeline_enabled)

    def test_get_nfl_adapter_stub(self):
        adapter = get_league_adapter("NFL")
        self.assertEqual(adapter.league_code, "NFL")
        self.assertFalse(adapter.pipeline_enabled)

    def test_unknown_league_raises(self):
        with self.assertRaises(KeyError):
            get_league_adapter("SOCCER")

    def test_searchable_leagues_includes_mlb_only(self):
        searchable = list_searchable_leagues()
        self.assertIn("MLB", searchable)
        self.assertNotIn("NFL", searchable)


class SportAdapterTests(unittest.TestCase):
    def test_baseball_sport_adapter(self):
        sport = get_sport_adapter("BASEBALL")
        self.assertEqual(sport.sport_code, "BASEBALL")
        self.assertIn("MLB", sport.leagues())

    def test_football_sport_adapter(self):
        sport = get_sport_adapter("FOOTBALL")
        self.assertIn("NFL", sport.leagues())


class LeagueMetadataTests(unittest.TestCase):
    def test_mlb_recent_window_is_7_days(self):
        meta = get_league_adapter("MLB").metadata
        self.assertEqual(meta.recent_window.kind, "days")
        self.assertEqual(meta.recent_window.value, 7)

    def test_nfl_recent_window_is_3_games(self):
        meta = get_league_adapter("NFL").metadata
        self.assertEqual(meta.recent_window.kind, "games")
        self.assertEqual(meta.recent_window.value, 3)

    def test_mlb_positions(self):
        positions = get_league_adapter("MLB").metadata.supported_positions
        self.assertIn("Pitcher", positions)
        self.assertIn("Outfield", positions)

    def test_nfl_positions(self):
        positions = get_league_adapter("NFL").metadata.supported_positions
        self.assertIn("QB", positions)
        self.assertIn("WR", positions)

    def test_mlb_search_templates(self):
        templates = get_league_adapter("MLB").card_signal.search_templates()
        self.assertIn("broad", templates)
        self.assertIn("baseball", templates["broad"])

    def test_nfl_search_templates(self):
        templates = get_league_adapter("NFL").card_signal.search_templates()
        self.assertIn("football", templates["broad"])


class AlgorithmVersionTests(unittest.TestCase):
    def test_league_player_signal_versions(self):
        self.assertEqual(player_signal_algorithm_version("MLB"), MLB_PLAYER_SIGNAL_V1)
        self.assertEqual(player_signal_algorithm_version("NFL"), NFL_PLAYER_SIGNAL_V1)
        self.assertEqual(MLB_PLAYER_SIGNAL_V1, "MLB_PLAYER_SIGNAL_V1")
        self.assertEqual(NFL_PLAYER_SIGNAL_V1, "NFL_PLAYER_SIGNAL_V1")

    def test_adapter_exposes_algorithm_version(self):
        mlb = get_league_adapter("MLB")
        self.assertEqual(mlb.metadata.player_signal_algorithm_version, MLB_PLAYER_SIGNAL_V1)


class SignalDriverTests(unittest.TestCase):
    def test_core_drivers_preserve_mlb_scoring(self):
        stats_7d = RollingHitterStats(games=7, at_bats=20, ops=0.950, home_runs=3, stolen_bases=2, rbi=8, avg=0.310)
        stats_30d = RollingHitterStats(games=25, at_bats=80, ops=0.820, home_runs=6, stolen_bases=4, rbi=20, avg=0.270)
        market = {
            "broad": MarketSnapshot(query_name="broad", listings_count=50, avg_price=30.0),
        }
        results = run_signal_drivers(
            MLB_CORE_DRIVERS,
            {"stats_7d": stats_7d, "stats_30d": stats_30d, "market_snapshots": market},
        )
        self.assertIsNotNone(results["performance"].score)
        self.assertIsNotNone(results["market"].score)
        self.assertGreater(results["performance"].score, 0)


class SeasonAdapterTests(unittest.TestCase):
    def test_nfl_period_is_thursday_to_monday(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo

        adapter = get_league_adapter("NFL")
        anchor = datetime(2026, 9, 20, 12, 0, tzinfo=ZoneInfo("America/New_York"))  # Sunday
        period = adapter.season.build_reporting_period(
            anchor=anchor,
            timezone_name="America/New_York",
        )
        self.assertEqual(period.period_start.weekday(), 3)
        self.assertEqual(period.period_end.weekday(), 0)


if __name__ == "__main__":
    unittest.main()
