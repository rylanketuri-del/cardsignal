"""Tests for NFL scouting mapper and season-phase persistence."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from cardchase_ai.models.nfl import NFLPerformanceSnapshot, NFLSignalDriver
from cardchase_ai.nfl_scouting_mapper import (
    build_nfl_performance_payload,
    build_nfl_scouting_evidence,
    resolve_nfl_season_phase,
)


class NFLSeasonPhasePersistenceTests(unittest.TestCase):
    def test_preseason_phase_persisted(self):
        evidence = build_nfl_scouting_evidence(
            nfl_season_phase="PRESEASON",
            season=2025,
            recent_snap=None,
            season_snap=None,
            drivers=[],
        )
        self.assertEqual(evidence["nfl_season_phase"], "PRESEASON")

    def test_offseason_phase_persisted(self):
        evidence = build_nfl_scouting_evidence(
            nfl_season_phase="OFFSEASON",
            season=2024,
            recent_snap=None,
            season_snap=None,
            drivers=[],
        )
        self.assertEqual(evidence["nfl_season_phase"], "OFFSEASON")
        self.assertEqual(evidence["nfl_season"], 2024)

    def test_unknown_phase_remains_unknown(self):
        phase = resolve_nfl_season_phase(active_status="ACTIVE", computed_phase=None, explicit_phase="UNKNOWN")
        self.assertEqual(phase, "UNKNOWN")

    def test_inactive_phase(self):
        phase = resolve_nfl_season_phase(active_status="INACTIVE", computed_phase="REGULAR_SEASON")
        self.assertEqual(phase, "INACTIVE")


class NFLPeriodPayloadTests(unittest.TestCase):
    def _snap(self, period_type: str, start: str, end: str) -> NFLPerformanceSnapshot:
        return NFLPerformanceSnapshot(
            cs_player_id="CS-NFL-P-TEST-01",
            source_player_id="TEST-01",
            season=2025,
            period_type=period_type,
            period_start=start,
            period_end=end,
            games_played=3,
            captured_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )

    def test_period_start_and_end_in_payload(self):
        recent = self._snap("RECENT_3_GAMES", "2026-06-01", "2026-06-22")
        season = self._snap("REGULAR_SEASON", "2026-01-01", "2026-06-22")
        payload = build_nfl_performance_payload(
            cs_player_id="CS-NFL-P-TEST-01",
            nfl_season_phase="REGULAR_SEASON",
            recent_snap=recent,
            season_snap=season,
        )
        self.assertEqual(payload["nfl_recent_window"]["period_start"], "2026-06-01")
        self.assertEqual(payload["nfl_recent_window"]["period_end"], "2026-06-22")
        self.assertNotEqual(payload["nfl_recent_window"]["captured_at"], payload["nfl_recent_window"]["period_start"])

    def test_missing_ranges_pending(self):
        payload = build_nfl_performance_payload(
            cs_player_id="CS-NFL-P-TEST-01",
            nfl_season_phase="UNKNOWN",
            recent_snap=None,
            season_snap=None,
        )
        self.assertTrue(payload["pending"])
        self.assertIsNone(payload["nfl_recent_window"])

    def test_offseason_label_context_via_phase(self):
        payload = build_nfl_performance_payload(
            cs_player_id="CS-NFL-P-TEST-01",
            nfl_season_phase="OFFSEASON",
            recent_snap=None,
            season_snap=self._snap("REGULAR_SEASON", "2025-09-01", "2026-01-15"),
        )
        self.assertEqual(payload["nfl_season_phase"], "OFFSEASON")
        self.assertEqual(payload["season"]["season"], 2025)


class NFLSearchResultIdTests(unittest.TestCase):
    def test_search_result_requires_player_id(self):
        from cardchase_ai.models.nfl import NFLPlayerSearchResult

        result = NFLPlayerSearchResult(
            player_id="TEST-QB-01",
            cs_player_id="CS-NFL-P-TEST-QB-01",
            source_player_id="TEST-QB-01",
            player_name="Test QB",
        )
        dumped = result.model_dump()
        self.assertEqual(dumped["player_id"], "TEST-QB-01")
        self.assertEqual(dumped["player_id"], dumped["source_player_id"])


class NFLSignalDriverPayloadTests(unittest.TestCase):
    def test_stored_drivers_serialized(self):
        driver = NFLSignalDriver(
            driver_type="PASSING_SURGE",
            label="Passing Surge",
            description="Passing production elevated in recent window.",
            source_method="APPROVED_IMPORT",
            captured_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
            season_phase="REGULAR_SEASON",
        )
        evidence = build_nfl_scouting_evidence(
            nfl_season_phase="REGULAR_SEASON",
            season=2025,
            recent_snap=None,
            season_snap=None,
            drivers=[driver],
        )
        self.assertEqual(len(evidence["nfl_signal_drivers"]), 1)
        self.assertEqual(evidence["nfl_signal_drivers"][0]["driver_type"], "PASSING_SURGE")


if __name__ == "__main__":
    unittest.main()
