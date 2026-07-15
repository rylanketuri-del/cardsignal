"""Tests for NFL previous-season seed rules and mapping guards."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

from cardchase_ai.nfl_seed_rules import activity_rank_key, meets_activity_threshold
from cardchase_ai.performance_import import validate_import_row


def _load_build_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "build_nfl_previous_season_seed.py"
    spec = importlib.util.spec_from_file_location("build_nfl_previous_season_seed", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NflSeedRulesTests(unittest.TestCase):
    def test_qb_threshold(self) -> None:
        self.assertTrue(meets_activity_threshold({
            "position": "QB", "games": "10", "attempts": "120", "passing_yards": "900",
        }))
        self.assertFalse(meets_activity_threshold({
            "position": "QB", "games": "10", "attempts": "10", "passing_yards": "100",
        }))

    def test_ranking_is_deterministic(self) -> None:
        a = {
            "fantasy_points_ppr": "100",
            "passing_yards": "1",
            "rushing_yards": "0",
            "receiving_yards": "0",
            "games": "10",
            "player_id": "00-1",
        }
        b = {
            "fantasy_points_ppr": "100",
            "passing_yards": "1",
            "rushing_yards": "0",
            "receiving_yards": "0",
            "games": "10",
            "player_id": "00-2",
        }
        self.assertLess(activity_rank_key(a), activity_rank_key(b))


class NflSeedMappingTests(unittest.TestCase):
    def test_map_qb_row_validates(self) -> None:
        build = _load_build_module()
        raw = {
            "player_id": "00-0033873",
            "player_display_name": "Patrick Mahomes",
            "position": "QB",
            "recent_team": "KC",
            "season": "2025",
            "games": "14",
            "completions": "300",
            "attempts": "450",
            "passing_yards": "3587",
            "passing_tds": "22",
            "passing_interceptions": "11",
            "rushing_yards": "422",
            "rushing_tds": "4",
            "fumbles_total": "3",
            "receiving_yards": "-10",
            "headshot_url": "https://example.invalid/headshot.png",
        }
        mapped, reason = build.map_row(raw, season=2025, retrieved_at="2026-07-15T00:00:00+00:00")
        self.assertIsNone(reason)
        assert mapped is not None
        self.assertEqual(mapped["source_player_id"], "00-0033873")
        self.assertNotIn("receiving_yards", mapped["stats"])
        self.assertGreaterEqual(mapped["stats"]["completion_percentage"], 0)
        self.assertLessEqual(mapped["stats"]["completion_percentage"], 1)
        snap, err = validate_import_row(mapped, league="NFL", season=2025)
        self.assertIsNone(err)
        self.assertIsNotNone(snap)


if __name__ == "__main__":
    unittest.main()
