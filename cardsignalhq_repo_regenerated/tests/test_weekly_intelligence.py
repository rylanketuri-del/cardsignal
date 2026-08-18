"""Focused tests for weekly intelligence pipeline."""

from __future__ import annotations

import inspect
import json
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from cardchase_ai.models.schemas import HitterGameLogRow, HitterHotnessBreakdown, MarketSnapshot, RollingHitterStats
from cardchase_ai.models.weekly import (
    WEEKLY_INTELLIGENCE_V1,
    PlayerWeeklySignalSnapshot,
    WeeklyIntelligenceRun,
)
from cardchase_ai.signal_of_week import select_signal_of_the_week
from cardchase_ai.utils.reporting_period import (
    build_reporting_period,
    current_reporting_period,
    next_scheduled_refresh,
    previous_reporting_period,
)
from cardchase_ai.league_evidence import has_sufficient_evidence
from cardchase_ai.weekly_scoring import compute_weekly_change
from cardchase_ai.weekly_storage import WeeklyJsonStorage, WeeklyStorage
from cardchase_ai.clients.ebay import has_usable_ebay_credentials
from cardchase_ai.weekly_intelligence import _weekly_ebay_client, run_weekly_intelligence


class ReportingPeriodTests(unittest.TestCase):
    def test_mlb_period_is_monday_to_sunday(self):
        tz = ZoneInfo("America/New_York")
        anchor = datetime(2026, 7, 8, 12, 0, tzinfo=tz)  # Wednesday
        period = build_reporting_period("MLB", anchor=anchor)
        self.assertEqual(period.period_start.weekday(), 0)
        self.assertEqual(period.period_end.weekday(), 6)
        self.assertEqual(period.league, "MLB")

    def test_timezone_aware_datetimes(self):
        period = current_reporting_period("MLB", "America/New_York")
        self.assertIsNotNone(period.period_start.tzinfo)
        self.assertIsNotNone(period.period_end.tzinfo)

    def test_previous_period_differs(self):
        current = current_reporting_period("MLB", "America/New_York")
        previous = previous_reporting_period("MLB", "America/New_York")
        self.assertNotEqual(current.week_number, previous.week_number)

    def test_nfl_period_is_thursday_to_monday(self):
        tz = ZoneInfo("America/New_York")
        anchor = datetime(2026, 10, 10, 12, 0, tzinfo=tz)
        period = build_reporting_period("NFL", anchor=anchor)
        self.assertEqual(period.period_start.weekday(), 3)
        self.assertEqual(period.period_end.weekday(), 0)
        self.assertEqual(period.league, "NFL")

    def test_next_refresh_is_tuesday_morning(self):
        refresh = next_scheduled_refresh("MLB", "America/New_York", refresh_day=1, refresh_hour=6)
        self.assertEqual(refresh.weekday(), 1)
        self.assertEqual(refresh.hour, 6)
        self.assertIsNotNone(refresh.tzinfo)


class WeeklyChangeTests(unittest.TestCase):
    def test_null_prior_remains_null(self):
        self.assertIsNone(compute_weekly_change(80.0, None))
        self.assertIsNone(compute_weekly_change(None, 70.0))

    def test_weekly_change_calculation(self):
        self.assertEqual(compute_weekly_change(85.5, 80.0), 5.5)


class SignalOfWeekTests(unittest.TestCase):
    def _snap(
        self,
        cs_id: str,
        score: float,
        perf: float,
        market: float,
        weekly_change: float | None = None,
        missing: list | None = None,
    ) -> PlayerWeeklySignalSnapshot:
        now = datetime(2026, 7, 8, 12, 0, tzinfo=ZoneInfo("UTC"))
        return PlayerWeeklySignalSnapshot(
            snapshot_id=cs_id,
            run_id="run-1",
            cs_player_id=cs_id,
            source_player_id=cs_id.split(":")[-1],
            league="MLB",
            sport="MLB",
            season=2026,
            year=2026,
            week_number=28,
            period_start=now,
            period_end=now,
            card_signal_score=score,
            performance_score=perf,
            market_score=market,
            recommendation="BUY",
            conviction="High",
            status="HOT",
            weekly_change=weekly_change,
            rank=1,
            evidence={"performance_reasons": ["elite 7-day OPS"]},
            missing_inputs=missing or [],
            player_name=f"Player {cs_id}",
        )

    def test_excludes_insufficient_evidence(self):
        low = self._snap("mlb:1", 90.0, 80.0, None, missing=["market_snapshots"])
        good = self._snap("mlb:2", 75.0, 70.0, 65.0)
        result = select_signal_of_the_week([low, good], "run-1")
        self.assertIsNotNone(result)
        self.assertEqual(result.cs_player_id, "mlb:2")

    def test_deterministic_tie_break(self):
        a = self._snap("mlb:aaa", 80.0, 70.0, 65.0, weekly_change=2.0)
        b = self._snap("mlb:bbb", 80.0, 70.0, 65.0, weekly_change=2.0)
        r1 = select_signal_of_the_week([b, a], "run-1")
        r2 = select_signal_of_the_week([a, b], "run-1")
        self.assertEqual(r1.cs_player_id, r2.cs_player_id)

    def test_no_selection_when_none_qualify(self):
        bad = self._snap("mlb:1", None, 80.0, None, missing=["market_snapshots"])
        self.assertIsNone(select_signal_of_the_week([bad], "run-1"))


class DuplicateRunTests(unittest.TestCase):
    def test_duplicate_official_run_prevention(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = WeeklyJsonStorage(Path(tmp))
            ws = WeeklyStorage(None, store)
            period = current_reporting_period("MLB", "America/New_York")
            run = WeeklyIntelligenceRun(
                run_id="existing-run",
                league="MLB",
                sport="MLB",
                season=2026,
                year=period.year,
                week_number=period.week_number,
                period_start=period.period_start,
                period_end=period.period_end,
                status="COMPLETED",
                triggered_by="scheduler",
                force=False,
                algorithm_version=WEEKLY_INTELLIGENCE_V1,
                created_at=datetime.now(ZoneInfo("UTC")),
            )
            store.create_run(run)
            found = ws.find_official_completed_run("MLB", period.year, period.week_number)
            self.assertIsNotNone(found)
            self.assertEqual(found.run_id, "existing-run")


class AppendOnlyTests(unittest.TestCase):
    def test_multiple_runs_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = WeeklyJsonStorage(Path(tmp))
            for i in range(3):
                run = WeeklyIntelligenceRun(
                    run_id=f"run-{i}",
                    league="MLB",
                    sport="MLB",
                    season=2026,
                    year=2026,
                    week_number=20 + i,
                    period_start=datetime(2026, 5, 1, tzinfo=ZoneInfo("UTC")),
                    period_end=datetime(2026, 5, 7, tzinfo=ZoneInfo("UTC")),
                    status="COMPLETED",
                    algorithm_version=WEEKLY_INTELLIGENCE_V1,
                )
                store.create_run(run)
            index = json.loads((Path(tmp) / "weekly" / "index.json").read_text())
            self.assertEqual(len(index), 3)


class AlgorithmVersionTests(unittest.TestCase):
    def test_version_constant(self):
        self.assertEqual(WEEKLY_INTELLIGENCE_V1, "WEEKLY_INTELLIGENCE_V1")


class EvidenceTests(unittest.TestCase):
    def test_has_sufficient_evidence(self):
        self.assertTrue(has_sufficient_evidence("MLB", 70.0, 60.0, []))
        self.assertFalse(has_sufficient_evidence("MLB", 70.0, None, []))
        self.assertFalse(has_sufficient_evidence("MLB", 70.0, 60.0, ["market_snapshots"]))
        self.assertFalse(has_sufficient_evidence("MLB", 70.0, 60.0, ["stats_7d"]))


class WeeklyRunIntegrationTests(unittest.TestCase):
    def test_force_run_allowed_when_official_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            from cardchase_ai.config import Settings

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
                nfl_season=2025,
                nfl_player_limit=100,
                nfl_enabled=False,
                nba_season=2025,
                nba_player_limit=100,
                nba_enabled=False,
            )
            storage = WeeklyStorage(None, WeeklyJsonStorage(Path(tmp)))

            def fake_processor(candidate, mlb, ebay, settings, *, market_enabled):
                from cardchase_ai.pipeline import PlayerPipelineOutput

                stats = RollingHitterStats(games=7, at_bats=20, ops=0.9, home_runs=2)
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
                    {"player_id": 2, "player_name": "Player Two", "team": "KC", "candidate_source": "dynamic"},
                ]
                first = run_weekly_intelligence(
                    league="MLB",
                    force=False,
                    triggered_by="manual",
                    player_limit=2,
                    market_enabled=False,
                    settings=settings,
                    storage=storage,
                    player_processor=fake_processor,
                )
                self.assertIn(first.run.status, {"COMPLETED", "PARTIAL"})

                skipped = run_weekly_intelligence(
                    league="MLB",
                    force=False,
                    triggered_by="manual",
                    player_limit=2,
                    market_enabled=False,
                    settings=settings,
                    storage=storage,
                    player_processor=fake_processor,
                )
                self.assertEqual(skipped.run.status, "SKIPPED")

                forced = run_weekly_intelligence(
                    league="MLB",
                    force=True,
                    triggered_by="admin",
                    player_limit=2,
                    market_enabled=False,
                    settings=settings,
                    storage=storage,
                    player_processor=fake_processor,
                )
                self.assertIn(forced.run.status, {"COMPLETED", "PARTIAL"})


class PlayerLimitTests(unittest.TestCase):
    def test_player_limit_capped_by_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            from cardchase_ai.config import Settings

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
                weekly_player_limit=5,
                weekly_card_limit_per_player=4,
                weekly_market_enabled=False,
                weekly_population_enabled=False,
                weekly_timezone="America/New_York",
                weekly_refresh_day=1,
                weekly_refresh_hour=6,
                nfl_season=2025,
                nfl_player_limit=100,
                nfl_enabled=False,
                nba_season=2025,
                nba_player_limit=100,
                nba_enabled=False,
            )
            storage = WeeklyStorage(None, WeeklyJsonStorage(Path(tmp)))
            processed_ids: list[int] = []

            def fake_processor(candidate, mlb, ebay, settings, *, market_enabled):
                from cardchase_ai.pipeline import PlayerPipelineOutput

                processed_ids.append(candidate["player_id"])
                stats = RollingHitterStats(games=7, at_bats=20, ops=0.9)
                hotness = HitterHotnessBreakdown(
                    player_name=candidate["player_name"],
                    performance_score=70.0,
                    market_score=60.0,
                    total_score=65.0,
                    confidence_multiplier=0.9,
                    tag="RISING",
                    reasons=["test"],
                )
                return PlayerPipelineOutput(
                    player_name=candidate["player_name"],
                    player_id=candidate["player_id"],
                    stats_7d=stats,
                    stats_30d=stats,
                    market_snapshots={"broad": MarketSnapshot(query_name="broad", listings_count=5, avg_price=10.0)},
                    hotness=hotness,
                ), [], None

            candidates = [{"player_id": i, "player_name": f"P{i}", "team": "MLB", "candidate_source": "dynamic"} for i in range(10)]

            with patch("cardchase_ai.weekly_intelligence._build_market_universe") as mock_universe:
                mock_universe.return_value = candidates
                summary = run_weekly_intelligence(
                    league="MLB",
                    force=True,
                    player_limit=100,
                    market_enabled=False,
                    settings=settings,
                    storage=storage,
                    player_processor=fake_processor,
                )
            self.assertLessEqual(summary.run.players_processed, 5)
            self.assertLessEqual(len(processed_ids), 5)


class CatastrophicFailureTests(unittest.TestCase):
    def _settings(self, tmp: str):
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
            admin_api_token="",
            weekly_player_limit=100,
            weekly_card_limit_per_player=4,
            weekly_market_enabled=False,
            weekly_population_enabled=False,
            weekly_timezone="America/New_York",
            weekly_refresh_day=1,
            weekly_refresh_hour=6,
            nfl_season=2025,
            nfl_player_limit=100,
            nfl_enabled=False,
            nba_season=2025,
            nba_player_limit=100,
            nba_enabled=False,
        )

    def test_catastrophic_exception_marks_failed_not_running(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = self._settings(tmp)
            storage = WeeklyStorage(None, WeeklyJsonStorage(Path(tmp)))
            with patch(
                "cardchase_ai.weekly_intelligence._build_market_universe",
                side_effect=RuntimeError("catastrophic failure"),
            ):
                summary = run_weekly_intelligence(
                    league="MLB",
                    force=True,
                    triggered_by="test",
                    settings=settings,
                    storage=storage,
                )
            self.assertEqual(summary.run.status, "FAILED")
            self.assertIsNotNone(summary.run.completed_at)
            self.assertTrue(any("catastrophic failure" in err for err in summary.run.errors))
            stored = json.loads((Path(tmp) / "weekly" / "runs" / f"{summary.run.run_id}.json").read_text())
            self.assertEqual(stored["run"]["status"], "FAILED")


class PartialStatusTests(unittest.TestCase):
    def test_partial_when_one_player_fails_and_one_succeeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            from cardchase_ai.config import Settings

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
                nfl_season=2025,
                nfl_player_limit=100,
                nfl_enabled=False,
                nba_season=2025,
                nba_player_limit=100,
                nba_enabled=False,
            )
            storage = WeeklyStorage(None, WeeklyJsonStorage(Path(tmp)))

            def fake_processor(candidate, mlb, ebay, settings, *, market_enabled):
                from cardchase_ai.pipeline import PlayerPipelineOutput

                if int(candidate["player_id"]) == 2:
                    return None, [], "Player Two: simulated stage failure"
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
                    {"player_id": 2, "player_name": "Player Two", "team": "KC", "candidate_source": "dynamic"},
                ]
                summary = run_weekly_intelligence(
                    league="MLB",
                    force=True,
                    triggered_by="test",
                    player_limit=2,
                    market_enabled=False,
                    settings=settings,
                    storage=storage,
                    player_processor=fake_processor,
                )

            self.assertEqual(summary.run.status, "PARTIAL")
            self.assertEqual(summary.run.players_processed, 1)
            self.assertTrue(any("Player Two" in err for err in summary.run.errors))
            payload = json.loads((Path(tmp) / "weekly" / "runs" / f"{summary.run.run_id}.json").read_text())
            self.assertEqual(len(payload["player_snapshots"]), 1)
            self.assertEqual(payload["player_snapshots"][0]["player_name"], "Player One")


class FailedRunPreservesLatestTests(unittest.TestCase):
    def test_failed_run_does_not_replace_latest_pointer(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = WeeklyJsonStorage(Path(tmp))
            good = WeeklyIntelligenceRun(
                run_id="good-run",
                league="MLB",
                sport="MLB",
                season=2026,
                year=2026,
                week_number=10,
                period_start=datetime(2026, 3, 1, tzinfo=ZoneInfo("UTC")),
                period_end=datetime(2026, 3, 7, tzinfo=ZoneInfo("UTC")),
                status="COMPLETED",
                algorithm_version=WEEKLY_INTELLIGENCE_V1,
            )
            store.create_run(good)
            store.latest_path.write_text(json.dumps({"run_id": "good-run", "league": "MLB"}), encoding="utf-8")

            failed = WeeklyIntelligenceRun(
                run_id="failed-run",
                league="MLB",
                sport="MLB",
                season=2026,
                year=2026,
                week_number=11,
                period_start=datetime(2026, 3, 8, tzinfo=ZoneInfo("UTC")),
                period_end=datetime(2026, 3, 14, tzinfo=ZoneInfo("UTC")),
                status="FAILED",
                algorithm_version=WEEKLY_INTELLIGENCE_V1,
            )
            store.create_run(failed)
            store.update_run(failed)

            latest = json.loads(store.latest_path.read_text(encoding="utf-8"))
            self.assertEqual(latest["run_id"], "good-run")


class GetEndpointReadOnlyTests(unittest.TestCase):
    def test_latest_payload_has_no_provider_side_effects(self):
        with tempfile.TemporaryDirectory() as tmp:
            from cardchase_ai.config import Settings
            from cardchase_ai.weekly_intelligence import build_latest_weekly_api_payload
            from cardchase_ai.repositories.factory import build_repository_bundle

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
                nfl_season=2025,
                nfl_player_limit=100,
                nfl_enabled=False,
                nba_season=2025,
                nba_player_limit=100,
                nba_enabled=False,
            )
            storage = WeeklyStorage(None, WeeklyJsonStorage(Path(tmp)))
            repos = build_repository_bundle(settings)
            with patch("cardchase_ai.clients.mlb.MLBClient") as mock_mlb:
                payload = build_latest_weekly_api_payload("MLB", storage, settings)
                mock_mlb.assert_not_called()
            self.assertIn("next_refresh", payload)


def _weekly_test_settings(tmp: str, **overrides):
    from cardchase_ai.config import Settings

    values = dict(
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
        weekly_market_enabled=True,
        weekly_population_enabled=False,
        weekly_timezone="America/New_York",
        weekly_refresh_day=1,
        weekly_refresh_hour=6,
        nfl_season=2025,
        nfl_player_limit=100,
        nfl_enabled=False,
        nba_season=2025,
        nba_player_limit=100,
        nba_enabled=False,
    )
    values.update(overrides)
    return Settings(**values)


def _weekly_gamelog() -> list[HitterGameLogRow]:
    end = date(2026, 8, 17)
    return [
        HitterGameLogRow(
            date=(end - timedelta(days=offset)).isoformat(),
            at_bats=4,
            hits=2,
            home_runs=1,
            rbi=2,
        )
        for offset in range(10)
    ]


class EbayCredentialDetectionTests(unittest.TestCase):
    def test_token_or_oauth_pair_is_usable(self):
        self.assertTrue(has_usable_ebay_credentials(token="tok"))
        self.assertTrue(has_usable_ebay_credentials(token="", client_id="id", client_secret="secret"))
        self.assertFalse(has_usable_ebay_credentials(token="", client_id="id", client_secret=""))
        self.assertFalse(has_usable_ebay_credentials(token="", client_id="", client_secret="secret"))
        self.assertFalse(has_usable_ebay_credentials(token="", client_id="", client_secret=""))
        self.assertFalse(has_usable_ebay_credentials(token="  ", client_id="  ", client_secret="  "))

    def test_weekly_client_uses_oauth_when_token_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = _weekly_test_settings(tmp, ebay_client_id="client-id", ebay_client_secret="client-secret")
            run = MagicMock()
            run.warnings = []
            client, enabled = _weekly_ebay_client(settings, run, True)
            self.assertTrue(enabled)
            self.assertIsNotNone(client)
            self.assertEqual(client.client_id, "client-id")
            self.assertEqual(client.client_secret, "client-secret")
            self.assertFalse(run.warnings)

    def test_weekly_client_disabled_without_any_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = _weekly_test_settings(tmp)
            run = MagicMock()
            run.warnings = []
            client, enabled = _weekly_ebay_client(settings, run, True)
            self.assertFalse(enabled)
            self.assertIsNone(client)
            self.assertTrue(run.warnings)
            self.assertNotIn("client-secret", " ".join(run.warnings))


class WeeklyMarketCredentialRunTests(unittest.TestCase):
    def _run_mlb(self, tmp: str, settings, *, ebay_client=None):
        storage = WeeklyStorage(None, WeeklyJsonStorage(Path(tmp)))
        mlb = MagicMock()
        mlb.get_hitter_gamelog.return_value = _weekly_gamelog()
        with (
            patch("cardchase_ai.weekly_intelligence._build_market_universe") as mock_universe,
            patch("cardchase_ai.weekly_intelligence.MLBClient", return_value=mlb),
            patch("cardchase_ai.weekly_intelligence.EbayClient") as mock_ebay_cls,
            patch("cardchase_ai.storage.SupabaseStorage.persist_leaderboard") as persist_lb,
        ):
            mock_universe.return_value = [
                {
                    "player_id": 608324,
                    "player_name": "Alex Bregman",
                    "team": "HOU",
                    "position": "3B",
                    "headshot_url": "https://img.mlbstatic.com/mlb-photos/image/upload/w_213,q_100/v1/people/608324/headshot/67/current",
                    "candidate_source": "dynamic",
                }
            ]
            if ebay_client is not None:
                mock_ebay_cls.return_value = ebay_client
            summary = run_weekly_intelligence(
                league="MLB",
                force=True,
                triggered_by="test",
                player_limit=1,
                market_enabled=True,
                settings=settings,
                storage=storage,
            )
        return summary, mock_ebay_cls, persist_lb, storage

    def test_no_ebay_credentials_leaves_market_and_cardsignal_null(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = _weekly_test_settings(tmp)
            summary, mock_ebay_cls, persist_lb, _storage = self._run_mlb(tmp, settings)
            self.assertIn(summary.run.status, {"COMPLETED", "PARTIAL"})
            self.assertEqual(summary.run.players_processed, 1)
            self.assertEqual(summary.run.cards_processed, 0)
            self.assertEqual(summary.run.market_snapshots_created, 0)
            mock_ebay_cls.assert_not_called()
            persist_lb.assert_not_called()
            import cardchase_ai.weekly_intelligence as wi

            self.assertNotIn("persist_leaderboard", inspect.getsource(wi._execute_weekly_pipeline))
            payload = json.loads((Path(tmp) / "weekly" / "runs" / f"{summary.run.run_id}.json").read_text())
            player = payload["player_snapshots"][0]
            self.assertIsNotNone(player["performance_score"])
            self.assertGreater(player["performance_score"], 0)
            self.assertIsNone(player["market_score"])
            self.assertIsNone(player["card_signal_score"])
            self.assertEqual(player["evidence"]["stats_season"]["games"], 10)
            self.assertIn("608324", player["headshot_url"])
            self.assertTrue(any("credentials missing" in w for w in summary.run.warnings))

    def test_oauth_client_id_secret_enables_market_and_cards(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = _weekly_test_settings(
                tmp,
                ebay_token="",
                ebay_client_id="ebay-client-id",
                ebay_client_secret="ebay-client-secret",
            )
            ebay_client = MagicMock()
            ebay_client.search_items.return_value = {"itemSummaries": []}
            ebay_client.parse_listings.return_value = [
                {
                    "item_id": "1",
                    "title": "Alex Bregman Bowman Chrome rookie",
                    "price": 42.0,
                    "currency": "USD",
                    "condition": "New",
                    "created_at": None,
                    "item_web_url": "",
                    "tags": [],
                }
            ]
            summary, mock_ebay_cls, persist_lb, _storage = self._run_mlb(tmp, settings, ebay_client=ebay_client)
            self.assertIn(summary.run.status, {"COMPLETED", "PARTIAL"})
            mock_ebay_cls.assert_called()
            kwargs = mock_ebay_cls.call_args.kwargs
            self.assertEqual(kwargs.get("client_id"), "ebay-client-id")
            self.assertEqual(kwargs.get("client_secret"), "ebay-client-secret")
            self.assertTrue(ebay_client.search_items.called)
            self.assertGreater(summary.run.market_snapshots_created, 0)
            self.assertGreater(summary.run.cards_processed, 0)
            persist_lb.assert_not_called()
            payload = json.loads((Path(tmp) / "weekly" / "runs" / f"{summary.run.run_id}.json").read_text())
            player = payload["player_snapshots"][0]
            self.assertIsNotNone(player["performance_score"])
            self.assertIsNotNone(player["market_score"])
            self.assertIsNotNone(player["card_signal_score"])
            self.assertGreater(len(payload["card_snapshots"]), 0)
            warning_blob = " ".join(summary.run.warnings + summary.run.errors)
            self.assertNotIn("ebay-client-secret", warning_blob)
            self.assertNotIn("ebay-client-id", warning_blob)


if __name__ == "__main__":
    unittest.main()
