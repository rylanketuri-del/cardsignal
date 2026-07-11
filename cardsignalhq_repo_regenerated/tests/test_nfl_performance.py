"""Focused tests for NFL performance adapter."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from cardchase_ai.clients.nfl_import import NFLImportProvider, UnavailableNFLProvider, get_nfl_provider
from cardchase_ai.identity import cs_nfl_player_id, cs_player_id, normalize_api_player_id, parse_cs_player_id
from cardchase_ai.models.nfl import NFLGameLogRow, map_nfl_position
from cardchase_ai.nfl_score import score_nfl_performance
from cardchase_ai.nfl_season import nfl_presentation_mode, nfl_season_phase, should_show_recent_window
from cardchase_ai.nfl_signal_drivers import driver_alone_recommendation_allowed, generate_nfl_signal_drivers
from cardchase_ai.score import clamp_score
from cardchase_ai.utils.nfl_rolling import (
    aggregate_qb_stats,
    aggregate_rb_stats,
    aggregate_receiver_stats,
    filter_completed_games,
    select_recent_games,
)
from cardchase_ai.utils.reporting_period import build_reporting_period
from cardchase_ai.nfl_api import search_nfl_players
from cardchase_ai.sports.registry import is_league_available


def _fixture_data() -> dict:
    return {
        "source_method": "APPROVED_IMPORT",
        "season": 2025,
        "last_updated": "2026-07-01T00:00:00Z",
        "players": [
            {
                "source_player_id": "TEST-QB-01",
                "player_name": "Test Quarterback",
                "team": "TST",
                "team_id": "TST",
                "position": "QB",
                "active_status": "ACTIVE",
            },
            {
                "source_player_id": "TEST-RB-01",
                "player_name": "Test Running Back",
                "team": "TST",
                "team_id": "TST",
                "position": "RB",
                "active_status": "ACTIVE",
            },
            {
                "source_player_id": "TEST-WR-01",
                "player_name": "Test Wide Receiver",
                "team": "TST",
                "team_id": "TST",
                "position": "WR",
                "active_status": "ACTIVE",
            },
            {
                "source_player_id": "TEST-TE-01",
                "player_name": "Test Tight End",
                "team": "TST",
                "team_id": "TST",
                "position": "TE",
                "active_status": "ACTIVE",
            },
        ],
        "games": {
            "TEST-QB-01": [
                {"game_id": "g1", "game_date": "2026-06-01", "season": 2025, "participated": True, "stats": {
                    "passing_yards": 280, "passing_touchdowns": 2, "interceptions": 1,
                    "completions": 22, "attempts": 35, "passer_rating": 95.2,
                    "rushing_yards": 15, "fumbles": 0,
                }},
                {"game_id": "g2", "game_date": "2026-06-08", "season": 2025, "participated": True, "stats": {
                    "passing_yards": 310, "passing_touchdowns": 3, "interceptions": 0,
                    "completions": 25, "attempts": 38, "passer_rating": 110.4,
                    "rushing_yards": 20, "fumbles": 0,
                }},
                {"game_id": "bye", "game_date": "2026-06-15", "season": 2025, "is_bye_week": True, "participated": False, "stats": {}},
                {"game_id": "g3", "game_date": "2026-06-22", "season": 2025, "participated": True, "stats": {
                    "passing_yards": 265, "passing_touchdowns": 1, "interceptions": 1,
                    "completions": 20, "attempts": 33, "passer_rating": 88.0,
                    "rushing_yards": 10, "fumbles": 1,
                }},
                {"game_id": "future", "game_date": "2099-12-31", "season": 2025, "participated": True, "stats": {"passing_yards": 500}},
                {"game_id": "inactive", "game_date": "2026-05-18", "season": 2025, "participated": False, "stats": {}},
            ],
            "TEST-RB-01": [
                {"game_id": "r1", "game_date": "2026-06-01", "season": 2025, "participated": True, "stats": {
                    "rushing_attempts": 18, "rushing_yards": 85, "rushing_touchdowns": 1,
                    "targets": 3, "receptions": 2, "receiving_yards": 15, "receiving_touchdowns": 0, "fumbles": 0,
                }},
            ],
            "TEST-WR-01": [
                {"game_id": "w1", "game_date": "2026-06-01", "season": 2025, "participated": True, "stats": {
                    "targets": 10, "receptions": 7, "receiving_yards": 95, "receiving_touchdowns": 1, "fumbles": 0,
                }},
            ],
            "TEST-TE-01": [
                {"game_id": "t1", "game_date": "2026-06-01", "season": 2025, "participated": True, "stats": {
                    "targets": 8, "receptions": 6, "receiving_yards": 72, "receiving_touchdowns": 1, "fumbles": 0,
                }},
            ],
        },
        "season_stats": {
            "TEST-QB-01": {"season": 2025, "stats": {
                "games_played": 8, "starts": 8, "passing_yards": 2100, "passing_touchdowns": 14,
                "interceptions": 5, "completion_percentage": 64.5, "yards_per_attempt": 7.1,
                "passer_rating": 92.3, "rushing_yards": 85, "rushing_touchdowns": 2, "fumbles": 2,
            }},
            "TEST-RB-01": {"season": 2025, "stats": {
                "games_played": 8, "starts": 6, "rushing_attempts": 120, "rushing_yards": 520,
                "rushing_touchdowns": 4, "yards_per_carry": 4.3, "targets": 20, "receptions": 15,
                "receiving_yards": 110, "receiving_touchdowns": 1, "total_yards": 630, "total_touchdowns": 5, "fumbles": 1,
            }},
            "TEST-WR-01": {"season": 2025, "stats": {
                "games_played": 8, "starts": 8, "targets": 70, "receptions": 48, "receiving_yards": 640,
                "receiving_touchdowns": 5, "yards_per_reception": 13.3, "catch_rate": 68.6, "total_touchdowns": 5, "fumbles": 0,
            }},
            "TEST-TE-01": {"season": 2025, "stats": {
                "games_played": 8, "starts": 7, "targets": 55, "receptions": 40, "receiving_yards": 480,
                "receiving_touchdowns": 4, "yards_per_reception": 12.0, "catch_rate": 72.7, "total_touchdowns": 4, "fumbles": 0,
            }},
        },
    }


class NFLIdentityTests(unittest.TestCase):
    def test_stable_nfl_player_id(self):
        self.assertEqual(cs_nfl_player_id("00-0033873"), "CS-NFL-P-00-0033873")
        self.assertEqual(cs_nfl_player_id("00-0033873"), cs_nfl_player_id("00-0033873"))

    def test_cs_player_id_league_specific(self):
        self.assertEqual(cs_player_id(660271, "MLB"), "mlb:660271")
        self.assertEqual(cs_player_id("00-0033873", "NFL"), "CS-NFL-P-00-0033873")

    def test_parse_cs_player_id(self):
        league, source = parse_cs_player_id("CS-NFL-P-TEST-QB-01")
        self.assertEqual(league, "NFL")
        self.assertEqual(source, "TEST-QB-01")

    def test_normalize_api_player_id(self):
        self.assertEqual(normalize_api_player_id("TEST-QB-01", "NFL"), "CS-NFL-P-TEST-QB-01")


class NFLPositionTests(unittest.TestCase):
    def test_position_mapping(self):
        self.assertEqual(map_nfl_position("QB"), "QB")
        self.assertEqual(map_nfl_position("FB"), "RB")
        self.assertEqual(map_nfl_position("WR"), "WR")
        self.assertEqual(map_nfl_position("TE"), "TE")
        self.assertEqual(map_nfl_position("CB"), "DEFENSIVE_PLAYER")
        self.assertEqual(map_nfl_position(None), "UNKNOWN")


class NFLRollingTests(unittest.TestCase):
    def _qb_games(self) -> list[NFLGameLogRow]:
        data = _fixture_data()["games"]["TEST-QB-01"]
        return [NFLGameLogRow.model_validate(g) for g in data]

    def test_bye_week_excluded(self):
        games = self._qb_games()
        valid = filter_completed_games(games, as_of=date(2026, 7, 1))
        self.assertTrue(all(not g.is_bye_week for g in valid))

    def test_future_games_excluded(self):
        games = self._qb_games()
        valid = filter_completed_games(games, as_of=date(2026, 7, 1))
        self.assertTrue(all(g.game_date != "2099-12-31" for g in valid))

    def test_inactive_games_excluded(self):
        games = self._qb_games()
        valid = filter_completed_games(games, as_of=date(2026, 7, 1))
        self.assertEqual(len(valid), 3)

    def test_recent_three_games_window(self):
        games = self._qb_games()
        recent = select_recent_games(games, limit=3)
        self.assertEqual(len(recent), 3)

    def test_fewer_than_three_games(self):
        games = [NFLGameLogRow.model_validate(_fixture_data()["games"]["TEST-RB-01"][0])]
        recent = select_recent_games(games, limit=3)
        self.assertEqual(len(recent), 1)


class NFLStatMappingTests(unittest.TestCase):
    def test_qb_recent_mapping(self):
        games = [NFLGameLogRow.model_validate(g) for g in _fixture_data()["games"]["TEST-QB-01"][:3]]
        stats = aggregate_qb_stats(games)
        self.assertEqual(stats["games_played"], 3)
        self.assertGreater(stats["passing_yards"], 0)
        self.assertIsNotNone(stats["completion_percentage"])

    def test_rb_recent_mapping(self):
        games = [NFLGameLogRow.model_validate(g) for g in _fixture_data()["games"]["TEST-RB-01"]]
        stats = aggregate_rb_stats(games)
        self.assertEqual(stats["games_played"], 1)
        self.assertIsNotNone(stats["yards_per_carry"])
        self.assertEqual(stats["total_yards"], stats["rushing_yards"] + stats["receiving_yards"])

    def test_wr_recent_mapping(self):
        games = [NFLGameLogRow.model_validate(g) for g in _fixture_data()["games"]["TEST-WR-01"]]
        stats = aggregate_receiver_stats(games)
        self.assertIsNotNone(stats["catch_rate"])
        self.assertIsNotNone(stats["yards_per_reception"])

    def test_te_recent_mapping(self):
        games = [NFLGameLogRow.model_validate(g) for g in _fixture_data()["games"]["TEST-TE-01"]]
        stats = aggregate_receiver_stats(games)
        self.assertEqual(stats["games_played"], 1)


class NFLScoringTests(unittest.TestCase):
    def test_score_bounds(self):
        recent = aggregate_qb_stats([NFLGameLogRow.model_validate(g) for g in _fixture_data()["games"]["TEST-QB-01"][:3]])
        season = _fixture_data()["season_stats"]["TEST-QB-01"]["stats"]
        score, _, _, _, _ = score_nfl_performance("QB", recent, season, games_in_window=3)
        self.assertIsNotNone(score)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)

    def test_deterministic_scoring(self):
        recent = aggregate_rb_stats([NFLGameLogRow.model_validate(g) for g in _fixture_data()["games"]["TEST-RB-01"]])
        season = _fixture_data()["season_stats"]["TEST-RB-01"]["stats"]
        s1, _, _, _, _ = score_nfl_performance("RB", recent, season, games_in_window=1)
        s2, _, _, _, _ = score_nfl_performance("RB", recent, season, games_in_window=1)
        self.assertEqual(s1, s2)

    def test_unsupported_position_no_score(self):
        score, _, _, quality, missing = score_nfl_performance("DEFENSIVE_PLAYER", {}, None, games_in_window=1)
        self.assertIsNone(score)
        self.assertEqual(quality, "INSUFFICIENT")
        self.assertIn("unsupported_position", missing)

    def test_missing_data_handling(self):
        score, _, _, quality, _ = score_nfl_performance("QB", {}, None, games_in_window=0)
        self.assertIsNone(score)
        self.assertEqual(quality, "INSUFFICIENT")

    def test_no_cross_position_comparison_in_weights(self):
        qb_recent = aggregate_qb_stats([NFLGameLogRow.model_validate(g) for g in _fixture_data()["games"]["TEST-QB-01"][:1]])
        wr_recent = aggregate_receiver_stats([NFLGameLogRow.model_validate(g) for g in _fixture_data()["games"]["TEST-WR-01"]])
        qb_score, qb_norm, _, _, _ = score_nfl_performance("QB", qb_recent, None, games_in_window=1)
        wr_score, wr_norm, _, _, _ = score_nfl_performance("WR", wr_recent, None, games_in_window=1)
        self.assertNotEqual(set(qb_norm.keys()), set(wr_norm.keys()))


class NFLSignalDriverTests(unittest.TestCase):
    def test_generates_from_stored_evidence(self):
        recent = aggregate_qb_stats([NFLGameLogRow.model_validate(g) for g in _fixture_data()["games"]["TEST-QB-01"][:3]])
        drivers = generate_nfl_signal_drivers(recent_stats=recent, season_stats=None, position_group="QB")
        types = {d.driver_type for d in drivers}
        self.assertIn("THREE_GAME_FORM", types)

    def test_no_rumor_ingestion(self):
        recent = aggregate_qb_stats([NFLGameLogRow.model_validate(g) for g in _fixture_data()["games"]["TEST-QB-01"][:1]])
        drivers = generate_nfl_signal_drivers(
            recent_stats=recent,
            season_stats=None,
            position_group="QB",
            developments=[{"driver_type": "TRADE", "label": "Rumor Trade", "verified": False}],
        )
        self.assertFalse(any(d.driver_type == "TRADE" for d in drivers))

    def test_no_recommendation_from_one_driver(self):
        self.assertFalse(driver_alone_recommendation_allowed())


class NFLSeasonPresentationTests(unittest.TestCase):
    def test_offseason_hides_recent(self):
        phase = nfl_season_phase(today=date(2026, 3, 15), has_active_season_games=False)
        self.assertEqual(phase, "OFFSEASON")
        self.assertFalse(should_show_recent_window(phase))
        self.assertEqual(nfl_presentation_mode(phase), "OFFSEASON_PREVIOUS")

    def test_preseason_presentation(self):
        phase = nfl_season_phase(today=date(2026, 8, 15), is_preseason=True)
        self.assertEqual(phase, "PRESEASON")
        self.assertEqual(nfl_presentation_mode(phase), "PRESEASON_MIX")


class NFLReportingPeriodTests(unittest.TestCase):
    def test_nfl_thursday_monday_period(self):
        tz = ZoneInfo("America/New_York")
        anchor = datetime(2026, 10, 10, 12, 0, tzinfo=tz)  # Saturday
        period = build_reporting_period("NFL", anchor=anchor)
        self.assertEqual(period.period_start.weekday(), 3)
        self.assertEqual(period.period_end.weekday(), 0)
        self.assertEqual(period.league, "NFL")


class NFLProviderTests(unittest.TestCase):
    def test_unavailable_without_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            provider = NFLImportProvider(Path(tmp) / "nfl" / "import", season=2025)
            self.assertFalse(provider.is_available())
            self.assertEqual(get_nfl_provider().__class__.__name__, "UnavailableNFLProvider")

    def test_import_provider_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            import_dir = Path(tmp) / "nfl" / "import"
            import_dir.mkdir(parents=True)
            (import_dir / "nfl_data.json").write_text(json.dumps(_fixture_data()), encoding="utf-8")
            provider = NFLImportProvider(import_dir, season=2025)
            self.assertTrue(provider.is_available())
            results = provider.search_players("Quarterback", limit=5)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].cs_player_id, "CS-NFL-P-TEST-QB-01")
            self.assertEqual(results[0].player_id, "TEST-QB-01")
            self.assertEqual(results[0].player_id, results[0].source_player_id)

    def test_search_empty_when_unavailable(self):
        with patch("cardchase_ai.nfl_api.is_league_available", return_value=False):
            self.assertEqual(search_nfl_players("test"), [])


class NFLClampTests(unittest.TestCase):
    def test_clamp_score_bounds(self):
        self.assertEqual(clamp_score(150), 100)
        self.assertEqual(clamp_score(-10), 0)


if __name__ == "__main__":
    unittest.main()
