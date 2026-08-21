"""Sprint 11.4 — Restore homepage intelligence layer."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from cardchase_ai.config import Settings
from cardchase_ai.models.market_movement import CardMarketMovement
from cardchase_ai.models.schemas import ListingTagSummary, MarketSnapshot
from cardchase_ai.models.weekly import (
    WEEKLY_INTELLIGENCE_V1,
    CardWeeklyIntelligenceSnapshot,
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
        self.assertEqual(sections["biggest_movers"], [])
        self.assertTrue(sections["buy_low_watch"])
        self.assertTrue(sections["most_chased"])

        trending = sections["trending_cards"][0]
        self.assertEqual(trending["player_name"], "Alpha")
        self.assertEqual(trending["evidence"]["avg_price"], 55)
        self.assertIsNone(trending["movement"])
        self.assertFalse(trending["movement_is_historical"])
        self.assertEqual(trending["movement_status"], "pending")
        self.assertNotEqual(trending["movement"], trending["demand_score"])

        buy_low = sections["buy_low_watch"][0]
        self.assertEqual(buy_low["recommendation"], "BUY")
        self.assertIsNone(buy_low["movement"])

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
        self.assertAlmostEqual(intel["card_signal_score"], (min(20 / 30 * 100, 100) + 12 / 20 * 100) / 2, places=2)
        self.assertNotIn("%", str(intel["card_signal_score"]))
        self.assertNotIn("listings", intel["evidence"])

    def test_homepage_card_row_carries_representative_offer_not_listings(self) -> None:
        from cardchase_ai.models.schemas import ListingSummary

        listings = [
            ListingSummary(
                item_id="first",
                title="Alpha Bowman Chrome",
                price=20.0,
                currency="USD",
                item_web_url="https://www.ebay.com/itm/first",
                image_url="https://i.ebayimg.com/images/g/first/s-l1600.jpg",
            ),
            ListingSummary(
                item_id="pick",
                title="Alpha Bowman Chrome Refractor",
                price=55.0,
                currency="USD",
                item_web_url="https://www.ebay.com/itm/pick",
                image_url="https://i.ebayimg.com/images/g/pick/s-l1600.jpg",
            ),
            ListingSummary(
                item_id="high",
                title="Alpha Bowman Chrome Superfractor",
                price=400.0,
                currency="USD",
                item_web_url="https://www.ebay.com/itm/high",
                image_url="https://i.ebayimg.com/images/g/high/s-l1600.jpg",
            ),
        ]
        snap = MarketSnapshot(
            query_name="bowman_chrome",
            listings_count=3,
            avg_price=158.33,
            tags=ListingTagSummary(premium_count=3, chrome_count=3),
            listings=listings,
        )
        intel = card_intelligence_from_snapshot("bowman_chrome", snap, "Alpha")
        card = _card_snap(
            cs_card_id="c-alpha-bowman",
            player_name="Alpha",
            score=intel["card_signal_score"],
            demand=intel["demand_score"],
            momentum=40,
            recommendation="BUY",
            avg_price=158.33,
        )
        card.evidence = intel["evidence"]
        sections = build_homepage_card_sections([card])
        row = sections["trending_cards"][0]
        offer = row["evidence"]["representative_offer"]
        self.assertEqual(offer["source"], "ebay")
        self.assertEqual(offer["external_id"], "pick")
        self.assertEqual(offer["image_url"], "https://i.ebayimg.com/images/g/pick/s-l1600.jpg")
        self.assertEqual(offer["listing_url"], "https://www.ebay.com/itm/pick")
        self.assertNotIn("listings", row)
        self.assertNotIn("listings", row["evidence"])
        self.assertEqual(len(listings), 3)

    def test_trending_ranks_by_demand_not_score(self) -> None:
        snaps = [
            _card_snap(cs_card_id="c-high-score", player_name="HighScore", score=90, demand=40, momentum=10),
            _card_snap(cs_card_id="c-high-demand", player_name="HighDemand", score=60, demand=88, momentum=10),
        ]
        sections = build_homepage_card_sections(snaps)
        self.assertEqual(sections["trending_cards"][0]["player_name"], "HighDemand")
        self.assertEqual(sections["most_chased"][0]["player_name"], "HighDemand")

    def test_buy_low_keeps_existing_buy_filter(self) -> None:
        snaps = [
            _card_snap(cs_card_id="c-buy", player_name="Buyer", score=72, demand=80, momentum=5, recommendation="BUY"),
            _card_snap(cs_card_id="c-hold", player_name="Holder", score=40, demand=20, momentum=90, recommendation="HOLD"),
        ]
        sections = build_homepage_card_sections(snaps)
        self.assertEqual([row["player_name"] for row in sections["buy_low_watch"]], ["Buyer"])
        self.assertEqual(sections["buy_low_watch"][0]["recommendation"], "BUY")

    def test_biggest_movers_empty_without_historical_baseline(self) -> None:
        snaps = [
            _card_snap(cs_card_id="c1", player_name="Alpha", score=82, demand=88, momentum=40, recommendation="BUY", avg_price=55),
            _card_snap(cs_card_id="c2", player_name="Beta", score=70, demand=60, momentum=95, recommendation="HOLD", avg_price=5114.40),
        ]
        sections = build_homepage_card_sections(snaps)
        self.assertEqual(sections["biggest_movers"], [])
        for row in sections["trending_cards"] + sections["buy_low_watch"] + sections["most_chased"]:
            self.assertIsNone(row["movement"])
            self.assertNotEqual(row["movement"], row["demand_score"])
            self.assertNotEqual(row["movement"], row["momentum_score"])

    def test_biggest_movers_does_not_rank_avg_price_over_100(self) -> None:
        expensive = _card_snap(
            cs_card_id="c-ohtani",
            player_name="Shohei Ohtani",
            score=96,
            demand=92,
            momentum=51.14,
            avg_price=5114.40,
        )
        sections = build_homepage_card_sections([expensive])
        self.assertEqual(sections["biggest_movers"], [])

    def test_biggest_movers_uses_calculated_historical_pct(self) -> None:
        snaps = [
            _card_snap(cs_card_id="c1", player_name="Alpha", score=82, demand=88, momentum=40, recommendation="BUY"),
            _card_snap(cs_card_id="c2", player_name="Beta", score=70, demand=60, momentum=95),
        ]
        pending = CardMarketMovement(
            cs_player_id="mlb:Alpha",
            cs_card_id="c1",
            query_name="broad",
            run_id="run-1",
            league="MLB",
            year=2026,
            week_number=28,
            status="pending",
            price_change_pct=None,
        )
        calculated = CardMarketMovement(
            cs_player_id="mlb:Beta",
            cs_card_id="c2",
            query_name="broad",
            run_id="run-1",
            league="MLB",
            year=2026,
            week_number=28,
            status="calculated",
            price_change_pct=12.34,
        )
        sections = build_homepage_card_sections(snaps, market_movements=[pending, calculated])
        self.assertEqual(len(sections["biggest_movers"]), 1)
        mover = sections["biggest_movers"][0]
        self.assertEqual(mover["player_name"], "Beta")
        self.assertEqual(mover["movement"], 12.34)
        self.assertTrue(mover["movement_is_historical"])
        self.assertEqual(mover["movement_status"], "calculated")
        self.assertEqual(mover["movement_type"], "price_change_pct")
        self.assertNotEqual(mover["movement"], mover["momentum_score"])


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

            run_row = {
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
                "homepage_payload": {
                    **homepage_sections,
                    "todays_leaders": [],
                    "data_quality_summary": {"total_players": 0},
                },
            }
            homepage = run_row["homepage_payload"]
            with patch.object(storage, "fetch_latest_official_run_row", return_value=run_row), \
                 patch.object(storage, "fetch_latest_completed_payload") as mock_fetch:
                mock_fetch.return_value = {
                    "run": run_row,
                    "player_snapshots": [],
                    "card_snapshots": [],
                    "signal_of_the_week": None,
                    "homepage": homepage,
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
    def test_weekly_generates_only_when_due(self) -> None:
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
                homepage=None,
            )
            from cardchase_ai.pipeline import _ensure_weekly_intelligence

            with patch("cardchase_ai.sports.registry.is_league_available", return_value=False), \
                 patch("cardchase_ai.weekly_intelligence.build_weekly_storage") as mock_storage_factory, \
                 patch("cardchase_ai.weekly_intelligence.run_weekly_intelligence", return_value=fake_summary) as mock_weekly, \
                 patch(
                     "cardchase_ai.utils.reporting_period.is_weekly_refresh_window_open",
                     return_value=(True, datetime(2026, 7, 8, 6, tzinfo=ZoneInfo("America/New_York"))),
                 ):
                mock_storage = mock_storage_factory.return_value
                mock_storage.find_official_completed_run.return_value = None
                results = _ensure_weekly_intelligence(settings)

            mock_weekly.assert_called_once()
            kwargs = mock_weekly.call_args.kwargs
            self.assertEqual(kwargs["league"], "MLB")
            self.assertEqual(kwargs["triggered_by"], "scheduler")
            self.assertFalse(kwargs["force"])
            self.assertEqual(results[0]["status"], "COMPLETED")
            self.assertEqual(results[0]["cards_processed"], 4)

    def test_weekly_skipped_before_refresh_window(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = _settings(tmp)
            from cardchase_ai.pipeline import _ensure_weekly_intelligence

            refresh_at = datetime(2026, 7, 14, 6, tzinfo=ZoneInfo("America/New_York"))
            with patch("cardchase_ai.sports.registry.is_league_available", return_value=False), \
                 patch("cardchase_ai.weekly_intelligence.build_weekly_storage") as mock_storage_factory, \
                 patch("cardchase_ai.weekly_intelligence.run_weekly_intelligence") as mock_weekly, \
                 patch("cardchase_ai.utils.reporting_period.is_weekly_refresh_window_open", return_value=(False, refresh_at)):
                mock_storage = mock_storage_factory.return_value
                mock_storage.find_official_completed_run.return_value = None
                results = _ensure_weekly_intelligence(settings)

            mock_weekly.assert_not_called()
            self.assertEqual(results[0]["status"], "SKIPPED")
            self.assertIn("not yet due", results[0]["skipped_reason"])

    def test_weekly_skipped_when_official_snapshot_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = _settings(tmp)
            from cardchase_ai.pipeline import _ensure_weekly_intelligence

            existing = WeeklyIntelligenceRun(
                run_id="existing-run",
                league="MLB",
                sport="MLB",
                season=2026,
                year=2026,
                week_number=28,
                period_start=datetime(2026, 7, 7, tzinfo=ZoneInfo("UTC")),
                period_end=datetime(2026, 7, 13, tzinfo=ZoneInfo("UTC")),
                status="COMPLETED",
                algorithm_version=WEEKLY_INTELLIGENCE_V1,
            )
            with patch("cardchase_ai.sports.registry.is_league_available", return_value=False), \
                 patch("cardchase_ai.weekly_intelligence.build_weekly_storage") as mock_storage_factory, \
                 patch("cardchase_ai.weekly_intelligence.run_weekly_intelligence") as mock_weekly:
                mock_storage = mock_storage_factory.return_value
                mock_storage.find_official_completed_run.return_value = existing
                results = _ensure_weekly_intelligence(settings)

            mock_weekly.assert_not_called()
            self.assertEqual(results[0]["status"], "SKIPPED")
            self.assertIn("already completed", results[0]["skipped_reason"])


class WeeklyRefreshWindowTests(unittest.TestCase):
    def test_refresh_window_closed_before_tuesday(self) -> None:
        from cardchase_ai.utils.reporting_period import (
            build_reporting_period,
            is_weekly_refresh_window_open,
        )

        period = build_reporting_period(
            league="MLB",
            anchor=datetime(2026, 7, 13, 12, 0, tzinfo=ZoneInfo("America/New_York")),
            timezone_name="America/New_York",
            season=2026,
        )
        monday = datetime(2026, 7, 13, 10, 0, tzinfo=ZoneInfo("America/New_York"))
        open_now, refresh_at = is_weekly_refresh_window_open(
            period,
            now=monday,
            timezone_name="America/New_York",
            refresh_day=1,
            refresh_hour=6,
        )
        self.assertFalse(open_now)
        self.assertEqual(refresh_at.weekday(), 1)

    def test_refresh_window_open_after_tuesday_six(self) -> None:
        from cardchase_ai.utils.reporting_period import (
            build_reporting_period,
            is_weekly_refresh_window_open,
        )

        period = build_reporting_period(
            league="MLB",
            anchor=datetime(2026, 7, 14, 12, 0, tzinfo=ZoneInfo("America/New_York")),
            timezone_name="America/New_York",
            season=2026,
        )
        tuesday = datetime(2026, 7, 14, 6, 0, tzinfo=ZoneInfo("America/New_York"))
        open_now, _ = is_weekly_refresh_window_open(
            period,
            now=tuesday,
            timezone_name="America/New_York",
            refresh_day=1,
            refresh_hour=6,
        )
        self.assertTrue(open_now)


if __name__ == "__main__":
    unittest.main()
