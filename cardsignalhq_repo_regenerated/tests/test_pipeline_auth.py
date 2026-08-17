"""HTTP fail-closed auth for pipeline and weekly admin triggers."""

from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from cardchase_ai.config import Settings


PIPELINE_TOKEN = "test-pipeline-token"
ADMIN_TOKEN = "test-admin-token"


def _settings(*, pipeline_token: str = PIPELINE_TOKEN, admin_token: str = ADMIN_TOKEN) -> Settings:
    return Settings(
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
        pipeline_trigger_token=pipeline_token,
        alert_webhook_url="",
        alert_webhook_bearer_token="",
        alert_from_email="",
        alert_sender_name="",
        app_base_url="",
        resend_api_key="",
        alert_cooldown_hours=12,
        daily_digest_cooldown_hours=20,
        notification_limit=50,
        admin_api_token=admin_token,
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


def _pipeline_result() -> SimpleNamespace:
    return SimpleNamespace(
        leaderboard_path="output/latest_leaderboard.json",
        run_id=1,
        alerts_created=0,
        deliveries_attempted=0,
        weekly_intelligence=[],
    )


class PipelineTriggerAuthTests(unittest.TestCase):
    def setUp(self) -> None:
        from api.main import app

        self.app = app
        self.client = TestClient(app)

    def _post(self, headers=None):
        return self.client.post("/api/pipeline/run", headers=headers or {})

    def test_empty_pipeline_token_returns_503(self) -> None:
        with patch("api.main._settings", return_value=_settings(pipeline_token="")), patch(
            "api.main.run_pipeline"
        ) as run_pipeline:
            response = self._post(headers={"Authorization": f"Bearer {PIPELINE_TOKEN}"})
        self.assertEqual(response.status_code, 503)
        run_pipeline.assert_not_called()

    def test_whitespace_pipeline_token_returns_503(self) -> None:
        with patch("api.main._settings", return_value=_settings(pipeline_token="   ")), patch(
            "api.main.run_pipeline"
        ) as run_pipeline:
            response = self._post(headers={"Authorization": f"Bearer {PIPELINE_TOKEN}"})
        self.assertEqual(response.status_code, 503)
        run_pipeline.assert_not_called()

    def test_missing_header_returns_401(self) -> None:
        with patch("api.main._settings", return_value=_settings()), patch("api.main.run_pipeline") as run_pipeline:
            response = self._post()
        self.assertEqual(response.status_code, 401)
        run_pipeline.assert_not_called()

    def test_wrong_token_returns_403(self) -> None:
        with patch("api.main._settings", return_value=_settings()), patch("api.main.run_pipeline") as run_pipeline:
            response = self._post(headers={"Authorization": "Bearer wrong-token"})
        self.assertEqual(response.status_code, 403)
        run_pipeline.assert_not_called()

    def test_matching_token_allows_run(self) -> None:
        with patch("api.main._settings", return_value=_settings()), patch(
            "api.main.run_pipeline", return_value=_pipeline_result()
        ) as run_pipeline:
            response = self._post(headers={"Authorization": f"Bearer {PIPELINE_TOKEN}"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        run_pipeline.assert_called_once()


class WeeklyAdminTriggerAuthTests(unittest.TestCase):
    def setUp(self) -> None:
        from api.main import app

        self.client = TestClient(app)

    def _post(self, headers=None):
        return self.client.post("/api/weekly/run", json={"league": "MLB"}, headers=headers or {})

    def test_empty_admin_token_returns_503(self) -> None:
        with patch("api.main._settings", return_value=_settings(admin_token="")), patch(
            "api.main.run_weekly_intelligence"
        ) as run_weekly:
            response = self._post(headers={"Authorization": f"Bearer {ADMIN_TOKEN}"})
        self.assertEqual(response.status_code, 503)
        run_weekly.assert_not_called()

    def test_whitespace_admin_token_returns_503(self) -> None:
        with patch("api.main._settings", return_value=_settings(admin_token=" \t")), patch(
            "api.main.run_weekly_intelligence"
        ) as run_weekly:
            response = self._post(headers={"Authorization": f"Bearer {ADMIN_TOKEN}"})
        self.assertEqual(response.status_code, 503)
        run_weekly.assert_not_called()

    def test_missing_header_returns_401(self) -> None:
        with patch("api.main._settings", return_value=_settings()), patch(
            "api.main.run_weekly_intelligence"
        ) as run_weekly:
            response = self._post()
        self.assertEqual(response.status_code, 401)
        run_weekly.assert_not_called()

    def test_wrong_token_returns_403(self) -> None:
        with patch("api.main._settings", return_value=_settings()), patch(
            "api.main.run_weekly_intelligence"
        ) as run_weekly:
            response = self._post(headers={"Authorization": "Bearer wrong-admin"})
        self.assertEqual(response.status_code, 403)
        run_weekly.assert_not_called()

    def test_matching_token_allows_run(self) -> None:
        summary = MagicMock()
        summary.model_dump.return_value = {"status": "COMPLETED", "league": "MLB"}
        with patch("api.main._settings", return_value=_settings()), patch(
            "api.main.run_weekly_intelligence", return_value=summary
        ) as run_weekly:
            response = self._post(headers={"Authorization": f"Bearer {ADMIN_TOKEN}"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "COMPLETED")
        run_weekly.assert_called_once()


if __name__ == "__main__":
    unittest.main()
