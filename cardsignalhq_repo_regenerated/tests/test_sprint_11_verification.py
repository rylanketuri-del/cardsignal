"""Sprint 11.0 verification tests — blocker remediation."""

from __future__ import annotations

import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from cardchase_ai.adapters import get_league_adapter, list_searchable_leagues, search_players
from cardchase_ai.adapters.metadata import RecentWindow
from cardchase_ai.adapters.period_rules import build_reporting_period_from_metadata
from cardchase_ai.adapters.registry import league_api_payload
from cardchase_ai.models.schemas import HitterHotnessBreakdown, MarketSnapshot, RollingHitterStats
from cardchase_ai.models.weekly import (
    MLB_PLAYER_SIGNAL_V1,
    NFL_PLAYER_SIGNAL_V1,
    WEEKLY_INTELLIGENCE_V1,
    PlayerWeeklySignalSnapshot,
)
from cardchase_ai.utils.reporting_period import build_reporting_period
from cardchase_ai.weekly_intelligence import build_player_snapshot, run_weekly_intelligence
from cardchase_ai.weekly_storage import WeeklyJsonStorage, WeeklyStorage


REPO_ROOT = Path(__file__).resolve().parents[1]


class BetaChecklistTests(unittest.TestCase):
    def test_beta_checklist_exists_at_repo_root(self):
        path = REPO_ROOT / "BETA_CHECKLIST.md"
        self.assertTrue(path.exists(), "BETA_CHECKLIST.md must exist at repository root")
        content = path.read_text(encoding="utf-8")
        self.assertIn("NBA real data", content)
        self.assertNotIn("[x] **NBA real data", content)


class AlgorithmVersionSeparationTests(unittest.TestCase):
    def test_player_snapshot_stores_both_versions(self):
        from cardchase_ai.config import Settings
        from cardchase_ai.models.weekly import WeeklyIntelligenceRun
        from cardchase_ai.pipeline import PlayerPipelineOutput
        from cardchase_ai.utils.reporting_period import ReportingPeriod

        now = datetime(2026, 7, 8, 12, 0, tzinfo=ZoneInfo("UTC"))
        run = WeeklyIntelligenceRun(
            run_id="run-1",
            league="MLB",
            sport="BASEBALL",
            season=2026,
            year=2026,
            week_number=28,
            period_start=now,
            period_end=now,
            market_snapshots_created=1,
        )
        period = ReportingPeriod(
            league="MLB",
            sport="BASEBALL",
            season=2026,
            year=2026,
            week_number=28,
            period_start=now,
            period_end=now,
        )
        stats = RollingHitterStats(games=7, at_bats=20, ops=0.9)
        output = PlayerPipelineOutput(
            player_name="Test Player",
            player_id=1,
            stats_7d=stats,
            stats_30d=stats,
            market_snapshots={"broad": MarketSnapshot(query_name="broad", listings_count=5, avg_price=10.0)},
            hotness=HitterHotnessBreakdown(
                player_name="Test Player",
                performance_score=70.0,
                market_score=60.0,
                total_score=66.0,
                confidence_multiplier=0.9,
                tag="RISING",
                reasons=["test"],
            ),
        )
        storage = WeeklyStorage(None, WeeklyJsonStorage(REPO_ROOT / "output"))
        snap = build_player_snapshot(output, run, period, 1, storage)
        self.assertEqual(snap.algorithm_version, WEEKLY_INTELLIGENCE_V1)
        self.assertEqual(snap.weekly_algorithm_version, WEEKLY_INTELLIGENCE_V1)
        self.assertEqual(snap.scoring_algorithm_version, MLB_PLAYER_SIGNAL_V1)


class ReportingPeriodAdapterTests(unittest.TestCase):
    def test_mlb_period_unchanged(self):
        tz = ZoneInfo("America/New_York")
        anchor = datetime(2026, 7, 8, 12, 0, tzinfo=tz)
        period = build_reporting_period("MLB", anchor=anchor)
        self.assertEqual(period.period_start.weekday(), 0)
        self.assertEqual(period.period_end.weekday(), 6)

    def test_nfl_thursday_monday_unchanged(self):
        tz = ZoneInfo("America/New_York")
        anchor = datetime(2026, 9, 20, 12, 0, tzinfo=tz)
        period = build_reporting_period("NFL", anchor=anchor)
        self.assertEqual(period.period_start.weekday(), 3)
        self.assertEqual(period.period_end.weekday(), 0)

    def test_metadata_change_alters_period_without_reporting_period_edit(self):
        from dataclasses import replace

        meta = get_league_adapter("MLB").metadata
        modified = replace(meta, period_start_weekday=1, period_end_weekday=0)
        tz = ZoneInfo("America/New_York")
        anchor = datetime(2026, 7, 8, 12, 0, tzinfo=tz)
        period = build_reporting_period_from_metadata(modified, anchor=anchor)
        self.assertEqual(period.period_start.weekday(), 1)

    def test_unknown_league_raises(self):
        with self.assertRaises(KeyError):
            build_reporting_period("SOCCER")


class RecentWindowAdapterTests(unittest.TestCase):
    def test_mlb_uses_metadata_days(self):
        adapter = get_league_adapter("MLB")
        self.assertEqual(adapter.metadata.recent_window.kind, "days")
        self.assertEqual(adapter.metadata.recent_window.value, 7)

    def test_performance_adapter_reads_recent_window_from_metadata(self):
        adapter = get_league_adapter("MLB")
        perf = adapter.performance
        with patch("cardchase_ai.adapters.mlb.MLBClient") as mock_client:
            mock_client.return_value.get_hitter_gamelog.return_value = []
            with patch("cardchase_ai.adapters.mlb.filter_last_n_days") as mock_days:
                mock_days.return_value = []
                with patch("cardchase_ai.adapters.mlb.summarize_hitter_window", return_value=RollingHitterStats()):
                    from cardchase_ai.config import get_settings

                    perf.fetch_performance_windows(1, 2026, get_settings())
                    self.assertEqual(mock_days.call_args_list[0][0][1], adapter.metadata.recent_window.value)

    def test_nfl_uses_games_metadata(self):
        meta = get_league_adapter("NFL").metadata
        self.assertEqual(meta.recent_window.kind, "games")
        self.assertEqual(meta.recent_window.value, 3)


class PeriodConfigSingleSourceTests(unittest.TestCase):
    def test_no_league_period_rules_dict(self):
        source = (REPO_ROOT / "cardchase_ai" / "utils" / "reporting_period.py").read_text(encoding="utf-8")
        self.assertNotIn("LEAGUE_PERIOD_RULES", source)

    def test_adapter_metadata_matches_period_output(self):
        adapter = get_league_adapter("MLB")
        meta = adapter.metadata
        tz = ZoneInfo("America/New_York")
        anchor = datetime(2026, 7, 8, 12, 0, tzinfo=tz)
        period = build_reporting_period_from_metadata(meta, anchor=anchor)
        self.assertEqual(period.period_start.weekday(), meta.period_start_weekday)
        self.assertEqual(period.period_end.weekday(), meta.period_end_weekday)


class RuntimeBranchAuditTests(unittest.TestCase):
    def test_weekly_intelligence_has_no_runtime_league_branches(self):
        source = (REPO_ROOT / "cardchase_ai" / "weekly_intelligence.py").read_text(encoding="utf-8")
        self.assertNotIn('league.upper() == "MLB"', source)
        self.assertNotIn("== \"NFL\"", source)

    def test_reporting_period_has_no_runtime_league_branches(self):
        source = (REPO_ROOT / "cardchase_ai" / "utils" / "reporting_period.py").read_text(encoding="utf-8")
        self.assertNotIn("== \"MLB\"", source)
        self.assertNotIn("LEAGUE_PERIOD_RULES", source)


class UniversalSearchTests(unittest.TestCase):
    def test_leagues_api_payload_shape(self):
        payload = league_api_payload(get_league_adapter("MLB"))
        for key in ("league", "sport", "display_name", "search_enabled", "live_status"):
            self.assertIn(key, payload)

    def test_searchable_leagues_live_only(self):
        searchable = list_searchable_leagues()
        self.assertIn("MLB", searchable)
        self.assertNotIn("NFL", searchable)

    def test_nfl_search_returns_empty_not_fabricated(self):
        results = search_players("mahomes", league="NFL", limit=5)
        self.assertEqual(results, [])

    def test_frontend_uses_league_registry(self):
        app_js = (REPO_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
        self.assertIn("/api/leagues", app_js)
        self.assertIn("fetchRegisteredLeagues", app_js)
        self.assertIn("/api/players/search", app_js)


class MlbOutputCompatibilityTests(unittest.TestCase):
    def test_weekly_run_still_completes_with_adapter_dispatch(self):
        import tempfile

        from cardchase_ai.config import Settings

        with tempfile.TemporaryDirectory() as tmp:
            settings = Settings(
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
                admin_api_token="",
                weekly_player_limit=100,
                weekly_card_limit_per_player=4,
                weekly_market_enabled=False,
                weekly_population_enabled=False,
                weekly_timezone="America/New_York",
                weekly_refresh_day=1,
                weekly_refresh_hour=6,
            )
            storage = WeeklyStorage(None, WeeklyJsonStorage(Path(tmp)))

            def fake_processor(candidate, _mlb, ebay, settings, *, market_enabled):
                from cardchase_ai.pipeline import PlayerPipelineOutput

                stats = RollingHitterStats(games=7, at_bats=20, ops=0.9)
                hotness = HitterHotnessBreakdown(
                    player_name=candidate["player_name"],
                    performance_score=75.0,
                    market_score=60.0,
                    total_score=70.0,
                    confidence_multiplier=0.95,
                    tag="RISING",
                    reasons=["test"],
                )
                return PlayerPipelineOutput(
                    player_name=candidate["player_name"],
                    player_id=candidate["player_id"],
                    stats_7d=stats,
                    stats_30d=stats,
                    market_snapshots={"broad": MarketSnapshot(query_name="broad", listings_count=10, avg_price=25.0)},
                    hotness=hotness,
                ), [], None

            with patch("cardchase_ai.weekly_intelligence._build_market_universe") as mock_universe:
                mock_universe.return_value = [
                    {"player_id": 1, "player_name": "Player One", "team": "CIN", "candidate_source": "dynamic"},
                ]
                summary = run_weekly_intelligence(
                    league="MLB",
                    force=True,
                    player_limit=1,
                    market_enabled=False,
                    settings=settings,
                    storage=storage,
                    player_processor=fake_processor,
                )
            self.assertIn(summary.run.status, {"COMPLETED", "PARTIAL"})
            import json

            run_file = Path(tmp) / "weekly" / "runs" / f"{summary.run.run_id}.json"
            data = json.loads(run_file.read_text(encoding="utf-8"))
            snap = PlayerWeeklySignalSnapshot.model_validate(data["player_snapshots"][0])
            self.assertEqual(snap.algorithm_version, WEEKLY_INTELLIGENCE_V1)
            self.assertEqual(snap.scoring_algorithm_version, MLB_PLAYER_SIGNAL_V1)


if __name__ == "__main__":
    unittest.main()
