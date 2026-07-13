"""Sprint 11.3 — Offseason Baseline Intelligence tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from cardchase_ai.identity import cs_nfl_player_id, cs_nba_player_id
from cardchase_ai.intelligence_serializer import serialize_player_intelligence
from cardchase_ai.league_evidence import has_sufficient_evidence
from cardchase_ai.models.performance import PreviousSeasonPerformanceSnapshot
from cardchase_ai.models.weekly import PlayerWeeklySignalSnapshot
from cardchase_ai.offseason_scoring import (
    derive_offseason_recommendation,
    has_offseason_sufficient_evidence,
    is_offseason_phase,
    previous_season_label,
)
from cardchase_ai.performance_evidence import (
    build_nba_previous_season_evidence,
    build_nfl_previous_season_evidence,
)
from cardchase_ai.performance_import import (
    PerformanceImportSummary,
    import_performance_records,
    parse_csv_records,
    validate_import_row,
)
from cardchase_ai.performance_storage import build_performance_storage
from cardchase_ai.storage_diagnostics import build_storage_diagnostics


def _nfl_qb_row(source_id: str = "12345", season: int = 2024) -> dict:
    return {
        "source_player_id": source_id,
        "player_name": "Test QB",
        "position": "QB",
        "team": "TEST",
        "season": season,
        "games_played": 17,
        "starts": 17,
        "stats": {
            "passing_yards": 4500,
            "passing_touchdowns": 35,
            "interceptions": 10,
            "completion_percentage": 0.68,
            "passer_rating": 102.5,
            "rushing_yards": 200,
            "rushing_touchdowns": 2,
            "fumbles": 3,
        },
        "source_method": "APPROVED_IMPORT",
        "source_reference": "test_import_v1",
    }


def _nba_row(source_id: str = "2544", season: int = 2025) -> dict:
    return {
        "source_player_id": source_id,
        "player_name": "Test Star",
        "position": "SF",
        "team": "LAL",
        "season": season,
        "games_played": 70,
        "starts": 70,
        "stats": {
            "points_per_game": 25.5,
            "rebounds_per_game": 7.2,
            "assists_per_game": 8.1,
            "steals_per_game": 1.2,
            "blocks_per_game": 0.6,
            "minutes_per_game": 35.2,
            "field_goal_percentage": 0.52,
            "three_point_percentage": 0.38,
            "free_throw_percentage": 0.74,
            "turnovers_per_game": 3.1,
        },
        "source_method": "APPROVED_IMPORT",
    }


class TestPreviousSeasonImport(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.settings_patch = patch(
            "cardchase_ai.performance_storage.get_settings",
            return_value=type("S", (), {"output_dir": Path(self.tmp.name), "supabase_url": None, "supabase_service_role_key": None})(),
        )
        self.settings_patch.start()

    def tearDown(self) -> None:
        self.settings_patch.stop()
        self.tmp.cleanup()

    def test_nfl_import_and_idempotency(self) -> None:
        storage = build_performance_storage()
        summary = import_performance_records(storage, league="NFL", season=2024, records=[_nfl_qb_row()])
        self.assertEqual(summary.rows_imported, 1)
        self.assertEqual(summary.rows_failed, 0)

        snap = storage.get_previous_season("NFL", cs_nfl_player_id("12345"), 2024)
        self.assertIsNotNone(snap)
        assert snap is not None
        self.assertEqual(snap.period_type, "PREVIOUS_SEASON")
        self.assertEqual(snap.stats["passing_yards"], 4500)

        summary2 = import_performance_records(storage, league="NFL", season=2024, records=[_nfl_qb_row()])
        self.assertEqual(summary2.rows_updated, 1)
        self.assertEqual(summary2.rows_imported, 0)

    def test_nba_import(self) -> None:
        storage = build_performance_storage()
        summary = import_performance_records(storage, league="NBA", season=2025, records=[_nba_row()])
        self.assertEqual(summary.rows_imported, 1)
        snap = storage.get_previous_season("NBA", cs_nba_player_id("2544"), 2025)
        self.assertIsNotNone(snap)

    def test_invalid_row_isolated(self) -> None:
        storage = build_performance_storage()
        bad = dict(_nfl_qb_row())
        bad.pop("source_player_id")
        summary = import_performance_records(
            storage,
            league="NFL",
            season=2024,
            records=[bad, _nfl_qb_row("99999")],
        )
        self.assertEqual(summary.rows_failed, 1)
        self.assertEqual(summary.rows_imported, 1)

    def test_percentage_validation(self) -> None:
        row = _nfl_qb_row()
        row["stats"]["completion_percentage"] = 1.5
        _, err = validate_import_row(row, league="NFL", season=2024)
        self.assertIsNotNone(err)

    def test_csv_import(self) -> None:
        csv = "source_player_id,player_name,position,team,season,games_played,stat_passing_yards,stat_passing_touchdowns\n"
        csv += "88888,CSV QB,QB,NYG,2024,16,4000,30\n"
        records = parse_csv_records(csv)
        storage = build_performance_storage()
        summary = import_performance_records(storage, league="NFL", season=2024, records=records)
        self.assertEqual(summary.rows_imported, 1)

    def test_stable_player_id_resolution(self) -> None:
        snap, _ = validate_import_row(_nfl_qb_row("77777"), league="NFL", season=2024)
        assert snap is not None
        self.assertEqual(snap.cs_player_id, cs_nfl_player_id("77777"))


class TestOffseasonScoring(unittest.TestCase):
    def test_previous_season_separate_from_recent(self) -> None:
        snap = PreviousSeasonPerformanceSnapshot(
            cs_player_id=cs_nfl_player_id("1"),
            source_player_id="1",
            league="NFL",
            sport="FOOTBALL",
            season=2024,
            position="QB",
            games_played=17,
            stats={"passing_yards": 4000, "passing_touchdowns": 30},
            data_quality="HIGH",
        )
        evidence = build_nfl_previous_season_evidence(snap)
        self.assertTrue(all(e.period_type == "PREVIOUS_SEASON" for e in evidence))
        self.assertTrue(len(evidence) > 0)

    def test_offseason_evidence_gate(self) -> None:
        self.assertTrue(
            has_offseason_sufficient_evidence(
                "NFL",
                70.0,
                65.0,
                ["stats_recent"],
                has_previous_season=True,
                season_phase="OFFSEASON",
            )
        )
        self.assertFalse(
            has_sufficient_evidence(
                "NFL",
                70.0,
                65.0,
                ["stats_recent", "market_snapshots"],
                season_phase="REGULAR_SEASON",
            )
        )

    def test_previous_season_no_confident_buy(self) -> None:
        rec = derive_offseason_recommendation(
            card_signal_score=85.0,
            has_recent_form=False,
            has_market=True,
            has_drivers=False,
        )
        self.assertEqual(rec, "WATCH")

    def test_offseason_labels(self) -> None:
        self.assertEqual(previous_season_label("NFL", 2025), "2025 Season Snapshot")
        self.assertEqual(previous_season_label("NBA", 2025), "2025–26 Season Snapshot")

    def test_is_offseason_phase(self) -> None:
        self.assertTrue(is_offseason_phase("OFFSEASON"))
        self.assertFalse(is_offseason_phase("REGULAR_SEASON"))


class TestOffseasonSerialization(unittest.TestCase):
    def _snap(self, **kwargs) -> PlayerWeeklySignalSnapshot:
        base = dict(
            snapshot_id="s1",
            run_id="r1",
            cs_player_id=cs_nfl_player_id("1"),
            source_player_id="1",
            league="NFL",
            sport="FOOTBALL",
            season=2026,
            year=2026,
            week_number=28,
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc),
            season_phase="OFFSEASON",
            recent_window_label="2025 Season Snapshot",
            previous_season_performance=[
                {
                    "metric": "passing_yards",
                    "label": "Passing Yards",
                    "value": 4500,
                    "period_type": "PREVIOUS_SEASON",
                    "quality": "HIGH",
                }
            ],
            recent_performance=[],
            evidence={
                "previous_season_label": "2025 Season Snapshot",
                "season_phase": "OFFSEASON",
            },
        )
        base.update(kwargs)
        return PlayerWeeklySignalSnapshot(**base)

    def test_serializer_includes_previous_season_fields(self) -> None:
        payload = serialize_player_intelligence(self._snap())
        self.assertEqual(payload.season_phase, "OFFSEASON")
        self.assertEqual(len(payload.previous_season_performance), 1)
        self.assertEqual(payload.previous_season_label, "2025 Season Snapshot")
        self.assertEqual(len(payload.recent_performance), 0)
        self.assertEqual(payload.capabilities.get("recent_form"), "UNAVAILABLE")

    def test_nba_previous_season_evidence(self) -> None:
        snap = PreviousSeasonPerformanceSnapshot(
            cs_player_id=cs_nba_player_id("1"),
            source_player_id="1",
            league="NBA",
            sport="BASKETBALL",
            season=2025,
            position="SF",
            games_played=70,
            stats={"points_per_game": 25.0, "rebounds_per_game": 7.0},
            data_quality="HIGH",
        )
        evidence = build_nba_previous_season_evidence(snap)
        self.assertTrue(any(e.metric == "points_per_game" for e in evidence))


class TestStorageDiagnostics(unittest.TestCase):
    def test_diagnostics_no_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch("cardchase_ai.storage_diagnostics.get_settings") as mock_settings:
                mock_settings.return_value = type(
                    "S",
                    (),
                    {
                        "output_dir": Path(tmp),
                        "supabase_url": None,
                        "supabase_service_role_key": None,
                        "nfl_season": 2025,
                        "nba_season": 2025,
                        "nfl_player_limit": 100,
                        "nba_player_limit": 100,
                    },
                )()
                diag = build_storage_diagnostics()
        self.assertIn("performance_storage_backend", diag)
        self.assertIn("storage_is_durable", diag)
        self.assertFalse(diag["storage_is_durable"])
        self.assertIn("warnings", diag)
        dumped = json.dumps(diag)
        self.assertNotIn("secret", dumped.lower())
        self.assertNotIn("password", dumped.lower())


class TestOffseasonReportLabels(unittest.TestCase):
    def test_nfl_offseason_no_recent_panel(self) -> None:
        from cardchase_ai.nfl_season import should_show_recent_window

        self.assertFalse(should_show_recent_window("OFFSEASON"))
        self.assertTrue(should_show_recent_window("REGULAR_SEASON"))

    def test_nba_offseason_no_recent_panel(self) -> None:
        from cardchase_ai.nba_season import should_show_recent_window

        self.assertFalse(should_show_recent_window("OFFSEASON"))


if __name__ == "__main__":
    unittest.main()
