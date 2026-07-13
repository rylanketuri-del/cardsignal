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
from cardchase_ai.intelligence_service import build_normalized_leader_rows, get_player_intelligence
from cardchase_ai.league_evidence import critical_evidence_requirements, has_sufficient_evidence
from cardchase_ai.models.nfl import NFLSignalDriver
from cardchase_ai.models.performance import PreviousSeasonPerformanceSnapshot
from cardchase_ai.models.schemas import HitterHotnessBreakdown, MarketSnapshot, RollingHitterStats
from cardchase_ai.models.weekly import PlayerWeeklySignalSnapshot, WeeklyIntelligenceRun
from cardchase_ai.nfl_api import fetch_nfl_leaderboard
from cardchase_ai.nba_api import fetch_nba_leaderboard
from cardchase_ai.nfl_storage import build_nfl_storage
from cardchase_ai.nba_storage import build_nba_storage
from cardchase_ai.offseason_scoring import (
    derive_offseason_recommendation,
    has_offseason_sufficient_evidence,
    is_offseason_phase,
    previous_season_label,
)
from cardchase_ai.performance_evidence import (
    build_mlb_recent_evidence,
    build_nba_previous_season_evidence,
    build_nfl_previous_season_evidence,
)
from cardchase_ai.performance_import import (
    import_performance_records,
    parse_csv_records,
    validate_import_row,
)
from cardchase_ai.performance_storage import build_performance_storage
from cardchase_ai.repositories.factory import build_repository_bundle
from cardchase_ai.storage_diagnostics import build_storage_diagnostics
from cardchase_ai.weekly_intelligence import (
    build_latest_weekly_api_payload,
    build_player_snapshot,
    run_weekly_intelligence,
)
from cardchase_ai.weekly_storage import WeeklyJsonStorage, WeeklyStorage
from cardchase_ai.pipeline import PlayerPipelineOutput
from cardchase_ai.utils.reporting_period import build_reporting_period
from zoneinfo import ZoneInfo


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


def _test_settings(tmp: str, *, nfl_season: int = 2026, nba_season: int = 2026) -> object:
    from cardchase_ai.config import Settings

    return Settings(
        ebay_token="",
        ebay_client_id="",
        ebay_client_secret="",
        ebay_marketplace_id="EBAY_US",
        tracked_players=[],
        output_dir=Path(tmp),
        mlb_season=2026,
        supabase_url="",
        supabase_service_role_key="",
        supabase_anon_key="",
        pipeline_trigger_token="",
        alert_webhook_url="",
        alert_webhook_bearer_token="",
        alert_from_email="",
        alert_sender_name="",
        app_base_url="",
        resend_api_key="",
        alert_cooldown_hours=12,
        daily_digest_cooldown_hours=20,
        notification_limit=50,
        admin_api_token="test-admin-token",
        weekly_player_limit=100,
        weekly_card_limit_per_player=4,
        weekly_market_enabled=False,
        weekly_population_enabled=False,
        weekly_timezone="America/New_York",
        weekly_refresh_day=1,
        weekly_refresh_hour=6,
        nfl_season=nfl_season,
        nfl_player_limit=100,
        nfl_enabled=False,
        nba_season=nba_season,
        nba_player_limit=100,
        nba_enabled=False,
    )


def _patch_settings(settings: object):
    return (
        patch("cardchase_ai.performance_storage.get_settings", return_value=settings),
        patch("cardchase_ai.nfl_storage.get_settings", return_value=settings),
        patch("cardchase_ai.nba_storage.get_settings", return_value=settings),
        patch("cardchase_ai.repositories.factory.get_settings", return_value=settings),
        patch("cardchase_ai.storage_diagnostics.get_settings", return_value=settings),
        patch("cardchase_ai.nfl_api.get_settings", return_value=settings),
        patch("cardchase_ai.nba_api.get_settings", return_value=settings),
        patch("cardchase_ai.sports.registry.get_settings", return_value=settings),
        patch("cardchase_ai.weekly_intelligence.get_settings", return_value=settings),
    )


def _run_official_weekly(
    *,
    league: str,
    settings: object,
    storage: WeeklyStorage,
    player_limit: int = 1,
    market_enabled: bool = False,
) -> object:
    """Run a weekly pipeline that persists latest_completed for homepage reads."""
    return run_weekly_intelligence(
        league=league,
        force=False,
        triggered_by="admin",
        player_limit=player_limit,
        market_enabled=market_enabled,
        settings=settings,
        storage=storage,
    )


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


class TestOffseasonNflWeeklyRun(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = _test_settings(self.tmp.name, nfl_season=2026)
        self.storage = WeeklyStorage(None, WeeklyJsonStorage(Path(self.tmp.name)))
        self.patches = _patch_settings(self.settings)
        for p in self.patches:
            p.start()

    def tearDown(self) -> None:
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def test_complete_nfl_offseason_weekly_run(self) -> None:
        perf = build_performance_storage(self.settings)
        import_performance_records(perf, league="NFL", season=2025, records=[_nfl_qb_row("12345", 2025)])

        nfl_storage = build_nfl_storage(self.settings)
        cs_id = cs_nfl_player_id("12345")
        nfl_storage.save_signal_drivers(
            cs_id,
            [
                NFLSignalDriver(
                    driver_type="TRADE",
                    label="Verified Trade",
                    description="Approved offseason roster move.",
                    source_method="APPROVED_IMPORT",
                    season_phase="OFFSEASON",
                )
            ],
        )

        summary = _run_official_weekly(
            league="NFL",
            settings=self.settings,
            storage=self.storage,
        )

        self.assertEqual(summary.run.status, "COMPLETED")
        self.assertEqual(summary.run.players_processed, 1)

        run_path = Path(self.tmp.name) / "weekly" / "runs" / f"{summary.run.run_id}.json"
        persisted = json.loads(run_path.read_text(encoding="utf-8"))
        self.assertEqual(len(persisted["player_snapshots"]), 1)

        snap = PlayerWeeklySignalSnapshot.model_validate(persisted["player_snapshots"][0])
        self.assertEqual(snap.season_phase, "OFFSEASON")
        self.assertEqual(len(snap.recent_performance), 0)
        self.assertGreater(len(snap.previous_season_performance), 0)
        self.assertEqual(snap.evidence.get("previous_season_label"), "2025 Season Snapshot")
        self.assertNotEqual(snap.recent_window_label, "Recent 3 Games")
        self.assertIsNone(snap.momentum_score)
        self.assertNotEqual(snap.recommendation, "BUY")
        self.assertIsNone(snap.card_signal_score)

        payload = build_latest_weekly_api_payload("NFL", self.storage, self.settings)
        self.assertIsNotNone(payload["run"])
        self.assertEqual(payload["run"]["status"], "COMPLETED")
        self.assertEqual(len(payload["todays_leaders"]), 1)
        intel = payload["todays_leaders"][0]["intelligence"]
        self.assertEqual(intel["season_phase"], "OFFSEASON")
        self.assertEqual(intel["previous_season_label"], "2025 Season Snapshot")
        self.assertEqual(len(intel["recent_performance"]), 0)
        self.assertGreater(len(intel["previous_season_performance"]), 0)
        self.assertNotEqual(intel.get("recommendation"), "BUY")
        self.assertIsNone(intel.get("card_signal_score"))

        repos = build_repository_bundle(self.settings)
        normalized = get_player_intelligence("NFL", "12345", repos)
        assert normalized is not None
        self.assertEqual(normalized.season_phase, "OFFSEASON")
        self.assertEqual(normalized.previous_season_label, "2025 Season Snapshot")


class TestOffseasonNbaWeeklyRun(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = _test_settings(self.tmp.name, nba_season=2026)
        self.storage = WeeklyStorage(None, WeeklyJsonStorage(Path(self.tmp.name)))
        self.patches = _patch_settings(self.settings)
        for p in self.patches:
            p.start()

    def tearDown(self) -> None:
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def test_complete_nba_offseason_weekly_run(self) -> None:
        perf = build_performance_storage(self.settings)
        import_performance_records(perf, league="NBA", season=2025, records=[_nba_row("2544", 2025)])

        summary = _run_official_weekly(
            league="NBA",
            settings=self.settings,
            storage=self.storage,
        )

        self.assertEqual(summary.run.status, "COMPLETED")
        self.assertEqual(summary.run.players_processed, 1)

        from cardchase_ai.nba_weekly import build_nba_market_universe
        from cardchase_ai.clients.nba_import import get_nba_provider
        from cardchase_ai.sports.registry import SUPPORTED_LEAGUES

        self.assertIn("NBA", SUPPORTED_LEAGUES)
        provider = get_nba_provider(self.settings)
        candidates = build_nba_market_universe(provider, 1, performance_storage=perf)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["candidate_source"], "previous_season_import")
        self.assertEqual(candidates[0]["player_id"], "2544")

        run_path = Path(self.tmp.name) / "weekly" / "runs" / f"{summary.run.run_id}.json"
        persisted = json.loads(run_path.read_text(encoding="utf-8"))
        snap = PlayerWeeklySignalSnapshot.model_validate(persisted["player_snapshots"][0])

        self.assertEqual(snap.league, "NBA")
        self.assertEqual(snap.season_phase, "OFFSEASON")
        self.assertEqual(len(snap.recent_performance), 0)
        self.assertGreater(len(snap.previous_season_performance), 0)
        self.assertEqual(snap.evidence.get("previous_season_label"), "2025–26 Season Snapshot")
        self.assertNotEqual(snap.recent_window_label, "Recent 5 Games")
        self.assertIsNone(snap.momentum_score)
        self.assertNotEqual(snap.recommendation, "BUY")
        self.assertIsNone(snap.card_signal_score)

        payload = build_latest_weekly_api_payload("NBA", self.storage, self.settings)
        self.assertIsNotNone(payload["run"])
        self.assertEqual(payload["run"]["status"], "COMPLETED")
        self.assertEqual(len(payload["todays_leaders"]), 1)
        intel = payload["todays_leaders"][0]["intelligence"]
        self.assertEqual(intel["previous_season_label"], "2025–26 Season Snapshot")
        self.assertEqual(len(intel["recent_performance"]), 0)
        self.assertNotEqual(intel.get("recommendation"), "BUY")
        self.assertIsNone(intel.get("card_signal_score"))


class TestHomepageActivation(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = _test_settings(self.tmp.name)
        self.storage = WeeklyStorage(None, WeeklyJsonStorage(Path(self.tmp.name)))
        self.patches = _patch_settings(self.settings)
        for p in self.patches:
            p.start()

    def tearDown(self) -> None:
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def test_nfl_without_weekly_intelligence_has_empty_homepage_payload(self) -> None:
        perf = build_performance_storage(self.settings)
        import_performance_records(perf, league="NFL", season=2025, records=[_nfl_qb_row("12345", 2025)])

        payload = build_latest_weekly_api_payload("NFL", self.storage, self.settings)
        self.assertIsNone(payload["run"])
        self.assertEqual(payload["todays_leaders"], [])

        board = fetch_nfl_leaderboard(self.settings)
        self.assertEqual(board["items"], [])

    def test_nfl_with_genuine_weekly_intelligence_activates_homepage(self) -> None:
        perf = build_performance_storage(self.settings)
        import_performance_records(perf, league="NFL", season=2025, records=[_nfl_qb_row("12345", 2025)])
        _run_official_weekly(
            league="NFL",
            settings=self.settings,
            storage=self.storage,
        )

        payload = build_latest_weekly_api_payload("NFL", self.storage, self.settings)
        self.assertIsNotNone(payload["run"])
        self.assertEqual(payload["run"]["status"], "COMPLETED")
        self.assertEqual(len(payload["todays_leaders"]), 1)
        leader = payload["todays_leaders"][0]
        self.assertEqual(leader["player_name"], "Test QB")
        self.assertEqual(leader["source_player_id"], "12345")
        self.assertIn("intelligence", leader)
        self.assertIsNone(leader["score"])
        self.assertIsNone(leader["intelligence"]["card_signal_score"])

        board = fetch_nfl_leaderboard(self.settings)
        self.assertEqual(len(board["items"]), 1)
        self.assertEqual(board["items"][0]["player_name"], "Test QB")

    def test_nba_without_weekly_intelligence_has_empty_homepage_payload(self) -> None:
        perf = build_performance_storage(self.settings)
        import_performance_records(perf, league="NBA", season=2025, records=[_nba_row()])

        payload = build_latest_weekly_api_payload("NBA", self.storage, self.settings)
        self.assertIsNone(payload["run"])
        self.assertEqual(payload["todays_leaders"], [])

        board = fetch_nba_leaderboard(self.settings)
        self.assertEqual(board["items"], [])

    def test_nba_with_genuine_weekly_intelligence_activates_homepage(self) -> None:
        perf = build_performance_storage(self.settings)
        import_performance_records(perf, league="NBA", season=2025, records=[_nba_row()])
        _run_official_weekly(
            league="NBA",
            settings=self.settings,
            storage=self.storage,
        )

        payload = build_latest_weekly_api_payload("NBA", self.storage, self.settings)
        self.assertIsNotNone(payload["run"])
        self.assertEqual(payload["run"]["status"], "COMPLETED")
        self.assertEqual(len(payload["todays_leaders"]), 1)
        self.assertEqual(payload["todays_leaders"][0]["league"], "NBA")

        board = fetch_nba_leaderboard(self.settings)
        self.assertEqual(len(board["items"]), 1)

    def test_incomplete_leader_row_preserves_null_score(self) -> None:
        period = build_reporting_period("NFL", timezone_name="America/New_York", season=2026)
        run = WeeklyIntelligenceRun(
            run_id="run-incomplete",
            league="NFL",
            sport="FOOTBALL",
            season=2026,
            year=2026,
            week_number=period.week_number,
            period_start=period.period_start,
            period_end=period.period_end,
            status="COMPLETED",
            triggered_by="test",
        )
        snap = PlayerWeeklySignalSnapshot(
            snapshot_id="snap-incomplete",
            run_id=run.run_id,
            cs_player_id=cs_nfl_player_id("00001"),
            source_player_id="00001",
            league="NFL",
            sport="FOOTBALL",
            season=2026,
            year=2026,
            week_number=period.week_number,
            period_start=period.period_start,
            period_end=period.period_end,
            card_signal_score=None,
            performance_score=None,
            market_score=None,
            season_phase="OFFSEASON",
            rank=1,
            player_name="Incomplete Player",
            missing_inputs=["stats_recent", "market_snapshots"],
        )
        repos = build_repository_bundle(self.settings)
        rows = build_normalized_leader_rows("NFL", [snap], repos)
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["score"])


class TestMlbRegression(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = _test_settings(self.tmp.name)
        self.storage = WeeklyStorage(None, WeeklyJsonStorage(Path(self.tmp.name)))
        self.patches = _patch_settings(self.settings)
        for p in self.patches:
            p.start()

    def tearDown(self) -> None:
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def test_mlb_regular_season_behavior_unchanged(self) -> None:
        period = build_reporting_period("MLB", timezone_name="America/New_York", season=2026)
        run = WeeklyIntelligenceRun(
            run_id="mlb-run",
            league="MLB",
            sport="MLB",
            season=2026,
            year=2026,
            week_number=period.week_number,
            period_start=period.period_start,
            period_end=period.period_end,
            status="RUNNING",
            triggered_by="test",
            market_snapshots_created=1,
        )
        stats_7d = RollingHitterStats(games=7, at_bats=28, home_runs=3, ops=0.95, avg=0.310)
        stats_30d = RollingHitterStats(games=25, at_bats=95, home_runs=8, ops=0.880, avg=0.285)
        output = PlayerPipelineOutput(
            player_name="MLB Star",
            player_id=101,
            stats_7d=stats_7d,
            stats_30d=stats_30d,
            market_snapshots={"broad": MarketSnapshot(query_name="broad", listings_count=12, avg_price=30.0)},
            hotness=HitterHotnessBreakdown(
                player_name="MLB Star",
                performance_score=78.0,
                market_score=65.0,
                total_score=74.0,
                confidence_multiplier=0.95,
                tag="RISING",
                reasons=["ops_7d=0.950"],
            ),
            team="NYY",
            position="OF",
        )

        snap = build_player_snapshot(output, run, period, 1, self.storage)

        self.assertEqual(snap.season_phase, "REGULAR_SEASON")
        self.assertEqual(snap.recent_window_label, "Last 7 Days")
        self.assertGreater(len(snap.recent_performance), 0)
        self.assertEqual(len(snap.previous_season_performance), 0)
        self.assertIn("stats_7d", critical_evidence_requirements("MLB"))
        self.assertTrue(
            has_sufficient_evidence(
                "MLB",
                snap.performance_score,
                snap.market_score,
                snap.missing_inputs,
                season_phase="REGULAR_SEASON",
            )
        )
        self.assertGreater(len(snap.signal_drivers), 0)
        self.assertIsNotNone(snap.card_signal_score)

        payload = serialize_player_intelligence(snap)
        self.assertGreater(len(payload.recent_performance), 0)
        self.assertEqual(len(payload.previous_season_performance), 0)
        self.assertEqual(payload.recent_window_label, "Last 7 Days")

        recent_labels = [e.label for e in build_mlb_recent_evidence(stats_7d, stats_30d)]
        self.assertTrue(any("Last 7 Days" in label for label in recent_labels))


if __name__ == "__main__":
    unittest.main()
