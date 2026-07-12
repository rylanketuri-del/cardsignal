"""Tests for NBA scouting mapper payloads."""

from __future__ import annotations

import unittest

from cardchase_ai.nba_scouting_mapper import build_nba_performance_payload, build_nba_scouting_evidence
from cardchase_ai.models.nba import NBAPerformanceSnapshot, NBASignalDriver


class NBAScoutingMapperTests(unittest.TestCase):
    def test_pending_payload_when_no_snapshots(self):
        payload = build_nba_performance_payload(
            cs_player_id="CS-NBA-P-TEST",
            nba_season_phase="REGULAR_SEASON",
            recent_snap=None,
            season_snap=None,
        )
        self.assertTrue(payload["pending"])
        self.assertFalse(payload["available"])

    def test_evidence_includes_recent_window_metadata(self):
        recent = NBAPerformanceSnapshot(
            cs_player_id="CS-NBA-P-TEST",
            source_player_id="TEST",
            season=2025,
            position="PG",
            position_group="PG",
            period_type="RECENT_5_GAMES",
            period_start="2026-06-01",
            period_end="2026-06-09",
            games_played=5,
            stats={"points_per_game": 24.6},
            performance_score=72.0,
            data_quality="HIGH",
            source_method="APPROVED_IMPORT",
        )
        evidence = build_nba_scouting_evidence(
            nba_season_phase="REGULAR_SEASON",
            season=2025,
            recent_snap=recent,
            season_snap=None,
            drivers=[],
        )
        self.assertEqual(evidence["nba_recent_window"]["recent_window_value"], 5)
        self.assertEqual(evidence["nba_recent_window"]["recent_window_type"], "COMPLETED_GAMES")
        self.assertEqual(evidence["nba_recent_stats"]["points_per_game"], 24.6)

    def test_signal_drivers_serialized(self):
        driver = NBASignalDriver(
            driver_type="HOT_STREAK",
            label="Hot Streak",
            description="Scoring elevated.",
            source_method="APPROVED_IMPORT",
        )
        evidence = build_nba_scouting_evidence(
            nba_season_phase="REGULAR_SEASON",
            season=2025,
            recent_snap=None,
            season_snap=None,
            drivers=[driver],
        )
        self.assertEqual(len(evidence["nba_signal_drivers"]), 1)
        self.assertEqual(evidence["nba_signal_drivers"][0]["driver_type"], "HOT_STREAK")


if __name__ == "__main__":
    unittest.main()
