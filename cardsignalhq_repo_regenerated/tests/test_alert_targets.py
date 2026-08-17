"""Focused tests for flat alert-target queries and alert-failure hardening."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from cardchase_ai.pipeline import PipelineResult, run_pipeline
from cardchase_ai.storage import SupabaseStorage


class FetchAlertTargetsFlatJoinTests(unittest.TestCase):
    def setUp(self) -> None:
        self.storage = SupabaseStorage("https://example.supabase.co", "service-role-key")

    def test_fetch_alert_targets_queries_tables_separately_and_joins_by_user_id(self) -> None:
        subscriptions = [
            {
                "user_id": "user-1",
                "email": "one@example.com",
                "hotness_jump_enabled": True,
                "buy_low_enabled": True,
                "most_chased_enabled": False,
                "daily_digest_enabled": True,
            },
            {
                "user_id": "user-2",
                "email": "two@example.com",
                "hotness_jump_enabled": False,
                "buy_low_enabled": True,
                "most_chased_enabled": True,
                "daily_digest_enabled": False,
            },
        ]
        watchlists = [
            {"user_id": "user-1", "player_id": "p1", "player_name": "Elly De La Cruz"},
            {"user_id": "user-1", "player_id": None, "player_name": "Bobby Witt Jr."},
            {"user_id": "user-2", "player_id": "p2", "player_name": "Gunnar Henderson"},
        ]
        rules = [
            {
                "user_id": "user-1",
                "player_name": "Elly De La Cruz",
                "min_hotness_delta": 10,
                "alert_on_hotness_jump": True,
                "alert_on_buy_low": True,
                "alert_on_most_chased": False,
                "muted_until": None,
            },
            {
                "user_id": "user-2",
                "player_name": "Gunnar Henderson",
                "min_hotness_delta": 8,
                "alert_on_hotness_jump": False,
                "alert_on_buy_low": True,
                "alert_on_most_chased": True,
                "muted_until": "2026-09-01T00:00:00+00:00",
            },
        ]

        with patch.object(self.storage, "_get", side_effect=[subscriptions, watchlists, rules]) as mock_get:
            targets = self.storage.fetch_alert_targets()

        self.assertEqual(mock_get.call_count, 3)
        self.assertEqual(mock_get.call_args_list[0].args[0], "alert_subscriptions")
        self.assertEqual(mock_get.call_args_list[1].args[0], "watchlists")
        self.assertEqual(mock_get.call_args_list[2].args[0], "player_alert_rules")

        sub_select = mock_get.call_args_list[0].args[1]["select"]
        self.assertNotIn("profiles(", sub_select)
        self.assertNotIn("watchlists(", sub_select)
        self.assertNotIn("player_alert_rules(", sub_select)

        self.assertEqual(
            mock_get.call_args_list[1].args[1]["user_id"],
            "in.(user-1,user-2)",
        )
        self.assertEqual(
            mock_get.call_args_list[2].args[1]["user_id"],
            "in.(user-1,user-2)",
        )

        self.assertEqual(len(targets), 2)
        self.assertEqual(targets[0]["user_id"], "user-1")
        self.assertEqual(targets[0]["email"], "one@example.com")
        self.assertIsNone(targets[0]["profiles"])
        self.assertEqual(
            targets[0]["watchlists"],
            [
                {"player_id": "p1", "player_name": "Elly De La Cruz"},
                {"player_id": None, "player_name": "Bobby Witt Jr."},
            ],
        )
        self.assertEqual(len(targets[0]["player_alert_rules"]), 1)
        self.assertEqual(targets[0]["player_alert_rules"][0]["player_name"], "Elly De La Cruz")
        self.assertEqual(targets[0]["player_alert_rules"][0]["min_hotness_delta"], 10)

        self.assertEqual(targets[1]["user_id"], "user-2")
        self.assertEqual(
            targets[1]["watchlists"],
            [{"player_id": "p2", "player_name": "Gunnar Henderson"}],
        )
        self.assertEqual(targets[1]["player_alert_rules"][0]["alert_on_most_chased"], True)

    def test_fetch_alert_targets_returns_empty_when_no_subscriptions(self) -> None:
        with patch.object(self.storage, "_get", return_value=[]) as mock_get:
            targets = self.storage.fetch_alert_targets()

        self.assertEqual(targets, [])
        mock_get.assert_called_once_with(
            "alert_subscriptions",
            {
                "select": "user_id,email,hotness_jump_enabled,buy_low_enabled,most_chased_enabled,daily_digest_enabled",
                "order": "updated_at.desc",
            },
        )


class AlertFailureHardeningTests(unittest.TestCase):
    def test_run_pipeline_survives_alert_processing_failure(self) -> None:
        settings = MagicMock()
        settings.output_dir = Path("/tmp/cardsignal-test-output")
        settings.supabase_url = "https://example.supabase.co"
        settings.supabase_service_role_key = "service-role-key"

        fake_storage = MagicMock()
        fake_storage.persist_leaderboard.return_value = 42

        with (
            patch("cardchase_ai.pipeline.get_settings", return_value=settings),
            patch("cardchase_ai.pipeline._build_outputs", return_value=[]),
            patch("cardchase_ai.pipeline._write_outputs", return_value=Path("/tmp/leaderboard.json")),
            patch("cardchase_ai.pipeline.SupabaseStorage", return_value=fake_storage),
            patch(
                "cardchase_ai.pipeline._process_alerts",
                side_effect=RuntimeError("PGRST200: could not find relationship"),
            ),
            patch("cardchase_ai.pipeline._ensure_weekly_intelligence", return_value=[]),
        ):
            result = run_pipeline()

        self.assertIsInstance(result, PipelineResult)
        self.assertEqual(result.run_id, 42)
        self.assertEqual(result.leaderboard_path, "/tmp/leaderboard.json")
        self.assertEqual(result.alerts_created, 0)
        self.assertEqual(result.deliveries_attempted, 0)
        fake_storage.persist_leaderboard.assert_called_once()


if __name__ == "__main__":
    unittest.main()
