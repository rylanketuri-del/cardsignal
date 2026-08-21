"""Sprint 11.5 — Admin pipeline health endpoint tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from cardchase_ai.config import Settings
from cardchase_ai.models.weekly import WEEKLY_INTELLIGENCE_V1
from cardchase_ai.pipeline_status import (
    _card_sections_ready,
    _derive_status,
    build_pipeline_status,
)
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
        admin_api_token="test-admin",
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


class HelperTests(unittest.TestCase):
    def test_card_sections_ready_requires_non_empty_list(self) -> None:
        self.assertFalse(_card_sections_ready(None))
        self.assertFalse(
            _card_sections_ready(
                {
                    "trending_cards": [],
                    "biggest_movers": [],
                    "buy_low_watch": [],
                    "most_chased": [],
                }
            )
        )
        self.assertTrue(
            _card_sections_ready(
                {
                    "trending_cards": [{"cs_card_id": "c1"}],
                    "biggest_movers": [],
                    "buy_low_watch": [],
                    "most_chased": [],
                }
            )
        )

    def test_status_unhealthy_without_leaderboard(self) -> None:
        self.assertEqual(
            _derive_status(
                leaderboard_players=0,
                homepage_intelligence_ready=False,
                weekly_snapshot_exists=False,
                weekly_due=False,
            ),
            "unhealthy",
        )

    def test_status_degraded_when_weekly_due_but_missing(self) -> None:
        self.assertEqual(
            _derive_status(
                leaderboard_players=20,
                homepage_intelligence_ready=False,
                weekly_snapshot_exists=False,
                weekly_due=True,
            ),
            "degraded",
        )

    def test_status_healthy_when_leaderboard_and_intel_ready(self) -> None:
        self.assertEqual(
            _derive_status(
                leaderboard_players=20,
                homepage_intelligence_ready=True,
                weekly_snapshot_exists=True,
                weekly_due=False,
            ),
            "healthy",
        )


class BuildPipelineStatusTests(unittest.TestCase):
    def test_payload_shape_from_leaderboard_and_weekly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = _settings(tmp)
            latest = Path(tmp) / "latest_leaderboard.json"
            latest.write_text(
                json.dumps([{"player_name": f"P{i}", "player_id": i} for i in range(20)]),
                encoding="utf-8",
            )

            weekly_dir = Path(tmp) / "weekly" / "runs"
            weekly_dir.mkdir(parents=True)
            run_id = "run-health-1"
            run_payload = {
                "run": {
                    "run_id": run_id,
                    "league": "MLB",
                    "sport": "MLB",
                    "season": 2026,
                    "year": 2026,
                    "week_number": 28,
                    "period_start": "2026-07-06T00:00:00-04:00",
                    "period_end": "2026-07-12T23:59:59-04:00",
                    "status": "COMPLETED",
                    "completed_at": "2026-07-14T10:00:00-04:00",
                    "triggered_by": "scheduler",
                    "force": False,
                    "algorithm_version": WEEKLY_INTELLIGENCE_V1,
                },
                "player_snapshots": [],
                "card_snapshots": [],
                "signal_of_the_week": None,
                "homepage": {
                    "todays_leaders": [
                        {"player_name": "Alpha", "weekly_change": 2.5, "score": 80}
                    ],
                    "trending_cards": [{"cs_card_id": "mlb:1:broad", "score": 75, "demand_score": 80}],
                    "biggest_movers": [{"cs_card_id": "mlb:1:broad", "score": 75, "momentum_score": 60}],
                    "buy_low_watch": [{"cs_card_id": "mlb:1:broad", "score": 75, "recommendation": "BUY"}],
                    "most_chased": [{"cs_card_id": "mlb:1:broad", "score": 75, "demand_score": 80}],
                    "data_quality_summary": {"total_players": 1},
                },
            }
            (weekly_dir / f"{run_id}.json").write_text(json.dumps(run_payload), encoding="utf-8")
            index = [
                {
                    "run_id": run_id,
                    "league": "MLB",
                    "year": 2026,
                    "week_number": 28,
                    "status": "COMPLETED",
                    "force": False,
                    "triggered_by": "scheduler",
                }
            ]
            (Path(tmp) / "weekly" / "index.json").write_text(json.dumps(index), encoding="utf-8")
            (Path(tmp) / "weekly" / "latest_completed.json").write_text(
                json.dumps({"run_id": run_id, "league": "MLB"}), encoding="utf-8"
            )

            # Second completed run so trend-depth check can pass without weekly_change on snaps.
            run_id_2 = "run-health-0"
            prior = {
                "run": {
                    "run_id": run_id_2,
                    "league": "MLB",
                    "sport": "MLB",
                    "season": 2026,
                    "year": 2026,
                    "week_number": 27,
                    "period_start": "2026-06-29T00:00:00-04:00",
                    "period_end": "2026-07-05T23:59:59-04:00",
                    "status": "COMPLETED",
                    "completed_at": "2026-07-07T10:00:00-04:00",
                    "triggered_by": "scheduler",
                    "force": False,
                    "algorithm_version": WEEKLY_INTELLIGENCE_V1,
                },
                "player_snapshots": [],
                "card_snapshots": [],
                "signal_of_the_week": None,
                "homepage": {},
            }
            (weekly_dir / f"{run_id_2}.json").write_text(json.dumps(prior), encoding="utf-8")
            index.insert(
                0,
                {
                    "run_id": run_id_2,
                    "league": "MLB",
                    "year": 2026,
                    "week_number": 27,
                    "status": "COMPLETED",
                    "force": False,
                    "triggered_by": "scheduler",
                },
            )
            (Path(tmp) / "weekly" / "index.json").write_text(json.dumps(index), encoding="utf-8")

            status = build_pipeline_status(
                settings,
                league="MLB",
                leaderboard_items=[{"player_name": f"P{i}"} for i in range(20)],
                supabase=None,
            )

            self.assertEqual(status["leaderboard_players"], 20)
            self.assertTrue(status["homepage_intelligence_ready"])
            self.assertTrue(status["trend_history_available"])
            self.assertEqual(status["latest_snapshot_week"], 28)
            self.assertEqual(status["latest_snapshot_year"], 2026)
            self.assertEqual(status["last_weekly_snapshot"], "2026-07-14T10:00:00-04:00")
            self.assertIsNotNone(status["next_weekly_snapshot_due"])
            self.assertIn(status["status"], {"healthy", "degraded"})
            self.assertEqual(status["league"], "MLB")

    def test_unhealthy_without_leaderboard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = _settings(tmp)
            status = build_pipeline_status(settings, leaderboard_items=[], supabase=None)
            self.assertEqual(status["leaderboard_players"], 0)
            self.assertFalse(status["homepage_intelligence_ready"])
            self.assertEqual(status["status"], "unhealthy")

    def test_trend_false_on_first_week_without_weekly_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = _settings(tmp)
            weekly_storage = WeeklyStorage(None, WeeklyJsonStorage(Path(tmp)))
            with patch("cardchase_ai.pipeline_status.build_weekly_storage", return_value=weekly_storage), \
                 patch("cardchase_ai.pipeline_status.build_latest_weekly_api_payload") as mock_api, \
                 patch.object(weekly_storage, "fetch_latest_completed_payload") as mock_fetch, \
                 patch.object(weekly_storage, "find_official_completed_run", return_value=MagicMock()):
                mock_fetch.return_value = {
                    "run": {
                        "run_id": "r1",
                        "league": "MLB",
                        "year": 2026,
                        "week_number": 28,
                        "completed_at": "2026-07-14T10:00:00+00:00",
                        "status": "COMPLETED",
                    },
                    "player_snapshots": [
                        {"cs_player_id": "mlb:1", "weekly_change": None, "player_name": "A"}
                    ],
                    "card_snapshots": [],
                    "homepage": {
                        "trending_cards": [{"cs_card_id": "c1"}],
                        "biggest_movers": [],
                        "buy_low_watch": [],
                        "most_chased": [],
                    },
                }
                mock_api.return_value = {
                    "todays_leaders": [{"weekly_change": None}],
                    "card_intelligence": {
                        "trending_cards": [{"cs_card_id": "c1"}],
                        "biggest_movers": [],
                        "buy_low_watch": [],
                        "most_chased": [],
                    },
                }
                status = build_pipeline_status(
                    settings,
                    leaderboard_items=[{"player_name": "A"}],
                    supabase=None,
                )

            self.assertTrue(status["homepage_intelligence_ready"])
            self.assertFalse(status["trend_history_available"])
            self.assertEqual(status["status"], "healthy")


if __name__ == "__main__":
    unittest.main()
