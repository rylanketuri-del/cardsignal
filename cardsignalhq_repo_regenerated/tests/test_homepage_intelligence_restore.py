"""Sprint 11.4 — Restore homepage intelligence layer."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from cardchase_ai.config import Settings
from cardchase_ai.models.schemas import ListingTagSummary, MarketSnapshot
from cardchase_ai.models.weekly import (
    WEEKLY_INTELLIGENCE_V1,
    CardWeeklyIntelligenceSnapshot,
    WeeklyHomepageIntelligence,
    WeeklyIntelligenceRun,
    WeeklyRunSummary,
)
from cardchase_ai.weekly_intelligence import (
    build_homepage_card_sections,
    build_latest_weekly_api_payload,
    card_intelligence_from_homepage,
    empty_card_intelligence,
)
from cardchase_ai.weekly_scoring import card_intelligence_from_snapshot, compute_weekly_change
from cardchase_ai.weekly_storage import WeeklyJsonStorage, WeeklyStorage


def _settings(tmp: str) -> Settings:
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
        weekly_player_limit=20,
        weekly_card_limit_per_player=4,
        weekly_market_enabled=True,
        weekly_population_enabled=False,
        weekly_timezone="America/New_York",
        weekly_refresh_day=1,
        weekly_refresh_hour=6,
        nfl_season=2025,
        nfl_player_limit=20,
        nfl_enabled=False,
        nba_season=2025,
        nba_player_limit=20,
        nba_enabled=False,
    )


def _card_snap(
    *,
    cs_card_id: str,
    player_name: str,
    score: float,
    demand: float,
    momentum: float,
    recommendation: str = "HOLD",
    avg_price: float = 42.5,
) -> CardWeeklyIntelligenceSnapshot:
    period = datetime(2026, 7, 7, tzinfo=ZoneInfo("UTC"))
    return CardWeeklyIntelligenceSnapshot(
        snapshot_id=f"snap-{cs_card_id}",
        run_id="run-1",
        cs_card_id=cs_card_id,
        cs_player_id=f"mlb:{player_name}",
        league="MLB",
        year=2026,
        week_number=28,
        period_start=period,
        period_end=period,
        card_signal_score=score,
        recommendation=recommendation,
        conviction="Medium",
        demand_score=demand,
        momentum_score=momentum,
        market_activity_score=55.0,
        evidence={"query_name": "broad", "listings_count": 12, "avg_price": avg_price},
        card_label="Broad Market",
        player_name=player_name,
        algorithm_version=WEEKLY_INTELLIGENCE_V1,
    )


class HomepageCardSectionsTests(unittest.TestCase):
    def test_sections_populated_from_genuine_card_snapshots(self) -> None:
        snaps = [
            _card_snap(cs_card_id="c1", player_name="Alpha", score=82, demand=88, momentum=40, recommendation="BUY", avg_price=55),
            _card_snap(cs_card_id="c2", player_name="Beta", score=70, demand=60, momentum=95, recommendation="HOLD", avg_price=33),
            _card_snap(cs_card_id="c3", player_name="Gamma", score=45, demand=70, momentum=20, recommendation="HOLD", avg_price=18),
        ]
        sections = build_homepage_card_sections(snaps)

        self.assertTrue(sections["trending_cards"])
        self.assertTrue(sections["biggest_movers"])
        self.assertTrue(sections["buy_low_watch"])
        self.assertTrue(sections["most_chased"])

        trending = sections["trending_cards"][0]
        self.assertEqual(trending["player_name"], "Alpha")
        self.assertEqual(trending["evidence"]["avg_price"], 55)
        self.assertIn("movement", trending)

        movers = sections["biggest_movers"][0]
        self.assertEqual(movers["player_name"], "Beta")
        self.assertEqual(movers["movement"], 95)

        buy_low = sections["buy_low_watch"][0]
        self.assertEqual(buy_low["recommendation"], "BUY")

    def test_card_intelligence_from_snapshot_scores_listings(self) -> None:
        snap = MarketSnapshot(
            query_name="broad",
            listings_count=20,
            avg_price=40.0,
            tags=ListingTagSummary(premium_count=12, psa10_count=4),
        )
        intel = card_intelligence_from_snapshot("broad", snap, "Test Player")
        self.assertIsNotNone(intel["card_signal_score"])
        self.assertIsNotNone(intel["demand_score"])
        self.assertEqual(intel["evidence"]["avg_price"], 40.0)


class ApiPayloadFallbackTests(unittest.TestCase):
    def test_falls_back_to_homepage_when_card_snapshots_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = _settings(tmp)
            storage = WeeklyStorage(None, WeeklyJsonStorage(Path(tmp)))
            homepage_sections = {
                "trending_cards": [{"cs_card_id": "c1", "player_name": "Alpha", "score": 80, "demand_score": 70}],
                "biggest_movers": [{"cs_card_id": "c2", "player_name": "Beta", "score": 75, "momentum_score": 90}],
                "buy_low_watch": [{"cs_card_id": "c3", "player_name": "Gamma", "score": 55, "recommendation": "BUY"}],
                "most_chased": [{"cs_card_id": "c1", "player_name": "Alpha", "score": 80, "demand_score": 70}],
            }

            with patch.object(storage, "fetch_latest_completed_payload") as mock_fetch:
                mock_fetch.return_value = {
                    "run": {
                        "run_id": "r1",
                        "league": "MLB",
                        "sport": "MLB",
                        "season": 2026,
                        "year": 2026,
                        "week_number": 28,
                        "period_start": "2026-07-07T00:00:00+00:00",
                        "period_end": "2026-07-13T23:59:59+00:00",
                        "status": "COMPLETED",
                        "completed_at": "2026-07-14T10:00:00+00:00",
                        "algorithm_version": WEEKLY_INTELLIGENCE_V1,
                    },
                    "player_snapshots": [],
                    "card_snapshots": [],
                    "signal_of_the_week": None,
                    "homepage": {
                        **homepage_sections,
                        "todays_leaders": [],
                        "data_quality_summary": {"total_players": 0},
                    },
                }
                payload = build_latest_weekly_api_payload("MLB", storage, settings)

            self.assertEqual(payload["card_intelligence"]["trending_cards"][0]["player_name"], "Alpha")
            self.assertEqual(payload["card_intelligence"]["biggest_movers"][0]["player_name"], "Beta")
            self.assertEqual(payload["card_intelligence"]["buy_low_watch"][0]["recommendation"], "BUY")
            self.assertEqual(payload["card_intelligence"]["most_chased"][0]["player_name"], "Alpha")

    def test_empty_card_intelligence_helper(self) -> None:
        empty = empty_card_intelligence()
        self.assertEqual(empty["trending_cards"], [])
        self.assertEqual(card_intelligence_from_homepage(None), empty)


class TrendCalculationTests(unittest.TestCase):
    def test_weekly_change_pending_without_prior(self) -> None:
        self.assertIsNone(compute_weekly_change(80.0, None))

    def test_weekly_change_populates_with_prior_snapshot(self) -> None:
        self.assertEqual(compute_weekly_change(85.5, 80.0), 5.5)


class PipelineIntegrationTests(unittest.TestCase):
    def test_run_pipeline_invokes_weekly_intelligence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = _settings(tmp)
            fake_summary = WeeklyRunSummary(
                run=WeeklyIntelligenceRun(
                    run_id="weekly-1",
                    league="MLB",
                    sport="MLB",
                    season=2026,
                    year=2026,
                    week_number=28,
                    period_start=datetime(2026, 7, 7, tzinfo=ZoneInfo("UTC")),
                    period_end=datetime(2026, 7, 13, tzinfo=ZoneInfo("UTC")),
                    status="COMPLETED",
                    triggered_by="scheduler",
                    algorithm_version=WEEKLY_INTELLIGENCE_V1,
                    players_processed=2,
                    cards_processed=4,
                ),
                stages=[],
                homepage=WeeklyHomepageIntelligence(
                    run=WeeklyIntelligenceRun(
                        run_id="weekly-1",
                        league="MLB",
                        sport="MLB",
                        season=2026,
                        year=2026,
                        week_number=28,
                        period_start=datetime(2026, 7, 7, tzinfo=ZoneInfo("UTC")),
                        period_end=datetime(2026, 7, 13, tzinfo=ZoneInfo("UTC")),
                        status="COMPLETED",
                        algorithm_version=WEEKLY_INTELLIGENCE_V1,
                    ),
                    trending_cards=[{"cs_card_id": "c1", "score": 80}],
                    biggest_movers=[{"cs_card_id": "c2", "score": 70}],
                    buy_low_watch=[{"cs_card_id": "c3", "score": 55}],
                    most_chased=[{"cs_card_id": "c1", "score": 80}],
                ),
            )

            with patch("cardchase_ai.pipeline.get_settings", return_value=settings), \
                 patch("cardchase_ai.pipeline._build_outputs", return_value=[]), \
                 patch("cardchase_ai.pipeline._write_outputs", return_value=Path(tmp) / "latest_leaderboard.json"), \
                 patch("cardchase_ai.weekly_intelligence.run_weekly_intelligence", return_value=fake_summary) as mock_weekly, \
                 patch("cardchase_ai.sports.registry.is_league_available", return_value=False):
                from cardchase_ai.pipeline import run_pipeline

                (Path(tmp) / "latest_leaderboard.json").write_text("[]", encoding="utf-8")
                result = run_pipeline()

            mock_weekly.assert_called_once()
            kwargs = mock_weekly.call_args.kwargs
            self.assertEqual(kwargs["league"], "MLB")
            self.assertEqual(kwargs["triggered_by"], "scheduler")
            self.assertFalse(kwargs["force"])
            self.assertEqual(result.weekly_intelligence[0]["status"], "COMPLETED")
            self.assertEqual(result.weekly_intelligence[0]["cards_processed"], 4)


if __name__ == "__main__":
    unittest.main()
