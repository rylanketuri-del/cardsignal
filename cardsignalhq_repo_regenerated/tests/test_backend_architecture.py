"""Architecture tests for the provider / engine / pipeline simplification sprint."""

from __future__ import annotations

import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from cardchase_ai.config import Settings
from cardchase_ai.engine.cardsignal_engine import (
    CardSignalConfig,
    CardSignalEngineInput,
    compute_cardsignal,
)
from cardchase_ai.engine.season_phase import (
    in_season_tuesday_window,
    resolve_engine_season_phase,
    season_phase_for_league,
    uses_previous_season_baseline,
)
from cardchase_ai.models.schemas import ListingTagSummary, MarketSnapshot
from cardchase_ai.pipelines.schedule import (
    MLB_INTERVAL_DAYS,
    is_mlb_pipeline_due,
    is_weekly_pipeline_due,
    record_mlb_pipeline_run,
)
from cardchase_ai.pipelines.weekly_pipeline import (
    _league_hooks,
    determine_weekly_season_context,
)
from cardchase_ai.providers import get_provider
from cardchase_ai.providers.mlb_provider import MLBProvider
from cardchase_ai.providers.nba_provider import NBAProvider
from cardchase_ai.providers.nfl_provider import NFLProvider
from cardchase_ai.storage.supabase import (
    build_production_storage,
    build_weekly_storage,
    production_storage_configured,
)
from cardchase_ai.utils.reporting_period import build_reporting_period


def _settings(**overrides) -> Settings:
    base = dict(
        ebay_token="",
        ebay_client_id="",
        ebay_client_secret="",
        ebay_marketplace_id="EBAY_US",
        tracked_players=[],
        output_dir=Path("./output"),
        mlb_season=2026,
        supabase_url="",
        supabase_service_role_key="",
        supabase_anon_key="",
        pipeline_trigger_token="",
        alert_webhook_url="",
        alert_webhook_bearer_token="",
        alert_from_email="alerts@example.com",
        alert_sender_name="CardChase AI",
        app_base_url="",
        resend_api_key="",
        alert_cooldown_hours=12,
        daily_digest_cooldown_hours=20,
        notification_limit=50,
        admin_api_token="",
        weekly_player_limit=20,
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
    base.update(overrides)
    return Settings(**base)


def _market_snap(listings: int = 10) -> MarketSnapshot:
    return MarketSnapshot(
        query_name="broad",
        listings_count=listings,
        avg_price=25.0,
        min_price=5.0,
        max_price=80.0,
        tags=ListingTagSummary(premium_count=3, psa10_count=1, auto_count=1, numbered_count=0),
    )


class ProviderAbstractionTests(unittest.TestCase):
    def test_get_provider_returns_league_wrappers(self):
        self.assertIsInstance(get_provider("MLB"), MLBProvider)
        self.assertIsInstance(get_provider("NFL"), NFLProvider)
        self.assertIsInstance(get_provider("NBA"), NBAProvider)

    def test_providers_expose_retrieval_api_not_scoring(self):
        for league in ("MLB", "NFL", "NBA"):
            provider = get_provider(league)
            self.assertTrue(hasattr(provider, "is_available"))
            self.assertTrue(hasattr(provider, "fetch_player_universe"))
            self.assertTrue(hasattr(provider, "fetch_recent_games"))
            self.assertTrue(hasattr(provider, "fetch_season_stats"))
            self.assertFalse(hasattr(provider, "compute_cardsignal"))
            self.assertFalse(hasattr(provider, "score_performance"))

    def test_nfl_nba_provider_parity(self):
        nfl = NFLProvider()
        nba = NBAProvider()
        shared = {
            "is_available",
            "search_players",
            "fetch_player_universe",
            "fetch_recent_games",
            "fetch_season_stats",
            "fetch_player_profile",
            "fetch_team_roster",
            "fetch_league_schedule",
            "fetch_player_status",
        }
        for name in shared:
            self.assertTrue(callable(getattr(nfl, name)))
            self.assertTrue(callable(getattr(nba, name)))
        self.assertEqual(nfl.league, "NFL")
        self.assertEqual(nba.league, "NBA")


class SeasonPhaseHelperTests(unittest.TestCase):
    def test_resolve_engine_season_phase_mapping(self):
        self.assertEqual(resolve_engine_season_phase("REGULAR_SEASON"), "IN_SEASON")
        self.assertEqual(resolve_engine_season_phase("POSTSEASON"), "IN_SEASON")
        self.assertEqual(resolve_engine_season_phase("OFFSEASON"), "OFFSEASON")
        self.assertEqual(resolve_engine_season_phase("PRESEASON"), "PRESEASON")
        self.assertEqual(resolve_engine_season_phase(None), "OFFSEASON")

    def test_offseason_selects_previous_season_baseline(self):
        self.assertTrue(uses_previous_season_baseline("OFFSEASON"))
        self.assertTrue(uses_previous_season_baseline("PRESEASON"))
        self.assertFalse(uses_previous_season_baseline("IN_SEASON"))

    def test_nfl_offseason_calendar(self):
        phase = season_phase_for_league("NFL", today=date(2026, 5, 1))
        self.assertEqual(phase, "OFFSEASON")

    def test_nba_offseason_calendar(self):
        phase = season_phase_for_league("NBA", today=date(2026, 8, 1))
        self.assertEqual(phase, "OFFSEASON")

    def test_nfl_in_season_calendar(self):
        phase = season_phase_for_league("NFL", today=date(2025, 10, 15), has_active_season_games=True)
        self.assertEqual(phase, "IN_SEASON")

    def test_weekly_context_offseason_uses_previous_season(self):
        settings = _settings(nfl_season=2025)
        with patch(
            "cardchase_ai.pipelines.weekly_pipeline.season_phase_for_league",
            return_value="OFFSEASON",
        ):
            ctx = determine_weekly_season_context("NFL", settings=settings, today=date(2026, 5, 1))
        self.assertEqual(ctx["engine_season_phase"], "OFFSEASON")
        self.assertEqual(ctx["performance_baseline"], "PREVIOUS_SEASON")
        self.assertEqual(ctx["completed_previous_season"], 2025)
        self.assertIsNone(ctx["performance_window"])

    def test_weekly_context_in_season_uses_tuesday_window(self):
        settings = _settings()
        with patch(
            "cardchase_ai.pipelines.weekly_pipeline.season_phase_for_league",
            return_value="IN_SEASON",
        ):
            ctx = determine_weekly_season_context("NFL", settings=settings, today=date(2025, 10, 15))
        self.assertEqual(ctx["engine_season_phase"], "IN_SEASON")
        self.assertEqual(ctx["performance_baseline"], "IN_SEASON_WINDOW")
        self.assertIsNotNone(ctx["performance_window"])


class TuesdayWindowTests(unittest.TestCase):
    def test_previous_tuesday_to_current_tuesday(self):
        tz = ZoneInfo("America/New_York")
        # Wednesday Oct 15, 2025 → current Tuesday is Oct 14, previous is Oct 7.
        anchor = datetime(2025, 10, 15, 12, 0, tzinfo=tz)
        window = in_season_tuesday_window(anchor=anchor, timezone_name="America/New_York")
        self.assertEqual(window.period_start.weekday(), 1)
        self.assertEqual(window.period_start.day, 7)
        self.assertEqual((window.period_end + timedelta(microseconds=1)).weekday(), 1)
        self.assertEqual((window.period_end + timedelta(microseconds=1)).day, 14)
        delta = (window.period_end + timedelta(microseconds=1)) - window.period_start
        self.assertEqual(delta, timedelta(days=7))

    def test_nfl_nba_reporting_periods_align_tuesday(self):
        tz = ZoneInfo("America/New_York")
        anchor = datetime(2026, 10, 10, 12, 0, tzinfo=tz)
        nfl = build_reporting_period("NFL", anchor=anchor)
        nba = build_reporting_period("NBA", anchor=anchor)
        self.assertEqual(nfl.period_start.weekday(), 1)
        self.assertEqual(nba.period_start.weekday(), 1)
        self.assertEqual(nfl.period_start, nba.period_start)


class CardSignalEngineTests(unittest.TestCase):
    def test_engine_is_sport_agnostic(self):
        snaps = {"broad": _market_snap(40)}
        nfl = compute_cardsignal(
            CardSignalEngineInput(
                player_name="A",
                performance_score=80.0,
                market_snapshots=snaps,
                market_score=70.0,
                has_previous_season=False,
                has_recent_form=True,
            ),
            CardSignalConfig(league="NFL", season_phase="IN_SEASON"),
        )
        nba = compute_cardsignal(
            CardSignalEngineInput(
                player_name="B",
                performance_score=80.0,
                market_snapshots=snaps,
                market_score=70.0,
                has_previous_season=False,
                has_recent_form=True,
            ),
            CardSignalConfig(league="NBA", season_phase="IN_SEASON"),
        )
        self.assertEqual(nfl.card_signal_score, nba.card_signal_score)
        self.assertAlmostEqual(nfl.card_signal_score or 0, 0.55 * 80 + 0.45 * 70, places=2)

    def test_offseason_does_not_require_recent_form(self):
        snaps = {"broad": _market_snap(40)}
        result = compute_cardsignal(
            CardSignalEngineInput(
                player_name="Offseason Star",
                performance_score=75.0,
                market_snapshots=snaps,
                market_score=60.0,
                missing_inputs=["stats_recent"],
                has_previous_season=True,
                has_recent_form=False,
            ),
            CardSignalConfig(league="NFL", season_phase="OFFSEASON"),
        )
        self.assertIsNotNone(result.card_signal_score)
        self.assertNotIn("stats_recent", result.missing_inputs)
        # Offseason recommendations stay conservative.
        self.assertIn(result.recommendation, {"WATCH", "HOLD", None})

    def test_mlb_nfl_nba_all_use_compute_cardsignal(self):
        # Source inspection — shared engine is wired into each league path.
        import cardchase_ai.nfl_weekly as nfl_weekly
        import cardchase_ai.nba_weekly as nba_weekly
        import cardchase_ai.weekly_intelligence as weekly_intelligence

        nfl_src = Path(nfl_weekly.__file__).read_text(encoding="utf-8")
        nba_src = Path(nba_weekly.__file__).read_text(encoding="utf-8")
        mlb_src = Path(weekly_intelligence.__file__).read_text(encoding="utf-8")
        self.assertIn("compute_cardsignal", nfl_src)
        self.assertIn("compute_cardsignal", nba_src)
        self.assertIn("compute_cardsignal", mlb_src)


class WeeklyPipelineParityTests(unittest.TestCase):
    def test_nfl_nba_hooks_share_workflow_shape(self):
        nfl = _league_hooks("NFL")
        nba = _league_hooks("NBA")
        self.assertEqual(set(nfl.keys()), set(nba.keys()))
        for key in ("get_provider", "build_storage", "build_universe", "process_player", "build_snapshot"):
            self.assertTrue(callable(nfl[key]))
            self.assertTrue(callable(nba[key]))


class SupabasePersistenceTests(unittest.TestCase):
    def test_production_storage_not_configured_without_keys(self):
        settings = _settings()
        self.assertFalse(production_storage_configured(settings))
        self.assertIsNone(build_production_storage(settings))

    def test_production_storage_configured_with_keys(self):
        settings = _settings(supabase_url="https://example.supabase.co", supabase_service_role_key="secret")
        self.assertTrue(production_storage_configured(settings))
        client = build_production_storage(settings)
        self.assertIsNotNone(client)
        self.assertEqual(client.url, "https://example.supabase.co")

    def test_weekly_storage_prefers_supabase_when_configured(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = _settings(
                output_dir=Path(tmp),
                supabase_url="https://example.supabase.co",
                supabase_service_role_key="secret",
            )
            storage = build_weekly_storage(settings)
            self.assertTrue(storage.uses_supabase)
            self.assertIsNotNone(storage.supabase)

    def test_weekly_storage_json_fallback_without_supabase(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = _settings(output_dir=Path(tmp))
            storage = build_weekly_storage(settings)
            self.assertFalse(storage.uses_supabase)


class ScheduleHelperTests(unittest.TestCase):
    def test_mlb_interval_is_three_days(self):
        self.assertEqual(MLB_INTERVAL_DAYS, 3)

    def test_mlb_due_without_prior_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = _settings(output_dir=Path(tmp))
            self.assertTrue(is_mlb_pipeline_due(settings))

    def test_mlb_not_due_immediately_after_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = _settings(output_dir=Path(tmp))
            record_mlb_pipeline_run(settings)
            self.assertFalse(is_mlb_pipeline_due(settings))

    def test_weekly_due_check_skips_when_official_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = _settings(output_dir=Path(tmp))
            storage = build_weekly_storage(settings)
            mock_run = MagicMock()
            mock_run.run_id = "run-1"
            with patch.object(storage, "find_official_completed_run", return_value=mock_run):
                due, reason = is_weekly_pipeline_due("NFL", settings, storage=storage)
            self.assertFalse(due)
            self.assertIn("already completed", reason.lower())


if __name__ == "__main__":
    unittest.main()
