"""Focused tests for NBA performance adapter."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from cardchase_ai.clients.nba_import import NBAImportProvider, UnavailableNBAProvider, get_nba_provider
from cardchase_ai.identity import cs_nba_player_id, cs_player_id, normalize_api_player_id, parse_cs_player_id
from cardchase_ai.models.nba import NBAGameLogRow, map_nba_position, recent_window_value
from cardchase_ai.nba_score import score_nba_performance
from cardchase_ai.nba_season import nba_season_phase, should_show_recent_window
from cardchase_ai.nba_signal_drivers import driver_alone_recommendation_allowed, generate_nba_signal_drivers
from cardchase_ai.sports.registry import is_league_available
from cardchase_ai.utils.nba_rolling import aggregate_basketball_stats, filter_completed_games, select_recent_games


def _fixture_data() -> dict:
    return {
        "source_method": "APPROVED_IMPORT",
        "season": 2025,
        "last_updated": "2026-07-01T00:00:00Z",
        "players": [
            {
                "source_player_id": "TEST-PG-01",
                "player_name": "Test Point Guard",
                "team": "TST",
                "team_id": "TST",
                "position": "PG",
                "active_status": "ACTIVE",
            },
            {
                "source_player_id": "TEST-UNK-01",
                "player_name": "Test Unknown",
                "team": "TST",
                "team_id": "TST",
                "position": "G-F",
                "active_status": "ACTIVE",
            },
        ],
        "games": {
            "TEST-PG-01": [
                {"game_id": "g1", "game_date": "2026-06-01", "season": 2025, "participated": True, "stats": {
                    "points": 22, "rebounds": 5, "assists": 9, "steals": 2, "blocks": 0, "turnovers": 3,
                    "field_goals_made": 8, "field_goals_attempted": 16,
                    "three_pointers_made": 2, "three_pointers_attempted": 5,
                    "free_throws_made": 4, "free_throws_attempted": 5, "minutes": 34,
                }},
                {"game_id": "g2", "game_date": "2026-06-03", "season": 2025, "participated": True, "stats": {
                    "points": 28, "rebounds": 4, "assists": 11, "steals": 1, "blocks": 0, "turnovers": 2,
                    "field_goals_made": 10, "field_goals_attempted": 18,
                    "three_pointers_made": 3, "three_pointers_attempted": 7,
                    "free_throws_made": 5, "free_throws_attempted": 6, "minutes": 36,
                }},
                {"game_id": "g3", "game_date": "2026-06-05", "season": 2025, "participated": True, "stats": {
                    "points": 19, "rebounds": 6, "assists": 8, "steals": 2, "blocks": 1, "turnovers": 4,
                    "field_goals_made": 7, "field_goals_attempted": 15,
                    "three_pointers_made": 1, "three_pointers_attempted": 4,
                    "free_throws_made": 4, "free_throws_attempted": 4, "minutes": 33,
                }},
                {"game_id": "g4", "game_date": "2026-06-07", "season": 2025, "participated": True, "stats": {
                    "points": 24, "rebounds": 3, "assists": 10, "steals": 1, "blocks": 0, "turnovers": 1,
                    "field_goals_made": 9, "field_goals_attempted": 17,
                    "three_pointers_made": 2, "three_pointers_attempted": 6,
                    "free_throws_made": 4, "free_throws_attempted": 5, "minutes": 35,
                }},
                {"game_id": "g5", "game_date": "2026-06-09", "season": 2025, "participated": True, "stats": {
                    "points": 30, "rebounds": 5, "assists": 7, "steals": 3, "blocks": 0, "turnovers": 2,
                    "field_goals_made": 11, "field_goals_attempted": 20,
                    "three_pointers_made": 4, "three_pointers_attempted": 8,
                    "free_throws_made": 4, "free_throws_attempted": 4, "minutes": 38,
                }},
                {"game_id": "future", "game_date": "2099-12-31", "season": 2025, "participated": True, "stats": {"points": 50}},
            ],
        },
        "season_stats": {
            "TEST-PG-01": {"season": 2025, "stats": {
                "games_played": 60,
                "points": 1200, "rebounds": 240, "assists": 420,
                "steals": 90, "blocks": 20, "turnovers": 180,
                "field_goals_made": 430, "field_goals_attempted": 900,
                "three_pointers_made": 120, "three_pointers_attempted": 320,
                "free_throws_made": 220, "free_throws_attempted": 260,
                "minutes": 1980,
                "points_per_game": 20.0, "rebounds_per_game": 4.0, "assists_per_game": 7.0,
                "steals_per_game": 1.5, "blocks_per_game": 0.3,
                "field_goal_percentage": 47.8, "three_point_percentage": 37.5, "free_throw_percentage": 84.6,
                "minutes_per_game": 33.0,
            }},
        },
    }


class NBAIdentityTests(unittest.TestCase):
    def test_stable_nba_player_id(self):
        self.assertEqual(cs_nba_player_id("203999"), "CS-NBA-P-203999")
        self.assertEqual(cs_nba_player_id("203999"), cs_nba_player_id("203999"))

    def test_cs_player_id_league_specific(self):
        self.assertEqual(cs_player_id("203999", "NBA"), "CS-NBA-P-203999")

    def test_parse_cs_player_id(self):
        league, source = parse_cs_player_id("CS-NBA-P-TEST-PG-01")
        self.assertEqual(league, "NBA")
        self.assertEqual(source, "TEST-PG-01")

    def test_normalize_api_player_id(self):
        self.assertEqual(normalize_api_player_id("TEST-PG-01", "NBA"), "CS-NBA-P-TEST-PG-01")


class NBAPositionTests(unittest.TestCase):
    def test_supported_positions(self):
        self.assertEqual(map_nba_position("PG"), "PG")
        self.assertEqual(map_nba_position("SG"), "SG")
        self.assertEqual(map_nba_position("SF"), "SF")
        self.assertEqual(map_nba_position("PF"), "PF")
        self.assertEqual(map_nba_position("C"), "C")

    def test_unknown_position(self):
        self.assertEqual(map_nba_position("G-F"), "UNKNOWN")
        self.assertEqual(map_nba_position(None), "UNKNOWN")


class NBARollingTests(unittest.TestCase):
    def _games(self) -> list[NBAGameLogRow]:
        data = _fixture_data()["games"]["TEST-PG-01"]
        return [NBAGameLogRow.model_validate(g) for g in data]

    def test_recent_window_from_metadata(self):
        self.assertEqual(recent_window_value(), 5)

    def test_future_games_excluded(self):
        valid = filter_completed_games(self._games(), as_of=date(2026, 7, 1))
        self.assertTrue(all(g.game_date != "2099-12-31" for g in valid))

    def test_recent_five_games_window(self):
        recent = select_recent_games(self._games())
        self.assertEqual(len(recent), 5)

    def test_aggregate_basketball_stats(self):
        recent = select_recent_games(self._games())
        stats = aggregate_basketball_stats(recent)
        self.assertEqual(stats["games_played"], 5)
        self.assertIsNotNone(stats["points_per_game"])
        self.assertIsNotNone(stats["field_goal_percentage"])


class NBAScoringTests(unittest.TestCase):
    def test_score_bounds(self):
        games = [NBAGameLogRow.model_validate(g) for g in _fixture_data()["games"]["TEST-PG-01"][:5]]
        recent = aggregate_basketball_stats(games)
        season = _fixture_data()["season_stats"]["TEST-PG-01"]["stats"]
        score, _, _, _, _ = score_nba_performance("PG", recent, season, games_in_window=5)
        self.assertIsNotNone(score)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)

    def test_unknown_position_no_score(self):
        score, _, _, quality, missing = score_nba_performance("UNKNOWN", {}, None, games_in_window=1)
        self.assertIsNone(score)
        self.assertEqual(quality, "INSUFFICIENT")
        self.assertIn("unsupported_position", missing)

    def test_missing_data_handling(self):
        score, _, _, quality, _ = score_nba_performance("PG", {}, None, games_in_window=0)
        self.assertIsNone(score)
        self.assertEqual(quality, "INSUFFICIENT")


class NBASignalDriverTests(unittest.TestCase):
    def test_generates_from_stored_evidence(self):
        games = [NBAGameLogRow.model_validate(g) for g in _fixture_data()["games"]["TEST-PG-01"][:5]]
        recent = aggregate_basketball_stats(games)
        drivers = generate_nba_signal_drivers(recent_stats=recent, season_stats=None)
        types = {d.driver_type for d in drivers}
        self.assertIn("HOT_STREAK", types)

    def test_no_recommendation_from_one_driver(self):
        self.assertFalse(driver_alone_recommendation_allowed())


class NBAProviderTests(unittest.TestCase):
    def test_unavailable_without_import(self):
        provider = get_nba_provider()
        self.assertIsInstance(provider, UnavailableNBAProvider)
        self.assertFalse(provider.is_available())

    def test_import_provider_loads(self):
        with tempfile.TemporaryDirectory() as tmp:
            import_dir = Path(tmp) / "nba" / "import"
            import_dir.mkdir(parents=True)
            (import_dir / "nba_data.json").write_text(json.dumps(_fixture_data()), encoding="utf-8")
            provider = NBAImportProvider(import_dir=import_dir, season=2025)
            self.assertTrue(provider.is_available())
            results = provider.search_players("Point", limit=5)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].cs_player_id, "CS-NBA-P-TEST-PG-01")


class NBASeasonTests(unittest.TestCase):
    def test_regular_season_shows_recent(self):
        phase = nba_season_phase(today=date(2026, 1, 15), has_active_season_games=True)
        self.assertEqual(phase, "REGULAR_SEASON")
        self.assertTrue(should_show_recent_window(phase))


if __name__ == "__main__":
    unittest.main()
