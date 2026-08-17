"""Sprint 1 — production API must not silently fall back to filesystem data."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from cardchase_ai.config import Settings
from cardchase_ai.storage import SupabaseError


def _settings(tmp: str, *, with_supabase: bool) -> Settings:
    return Settings(
        ebay_token="",
        ebay_client_id="",
        ebay_client_secret="",
        ebay_marketplace_id="EBAY_US",
        tracked_players=["Test Player"],
        output_dir=Path(tmp),
        mlb_season=2026,
        supabase_url="https://example.supabase.co" if with_supabase else "",
        supabase_service_role_key="service-role" if with_supabase else "",
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


class ApiStorageContractTests(unittest.TestCase):
    def test_supabase_configured_does_not_fall_back_to_file_on_error(self) -> None:
        from api import main as api_main

        with tempfile.TemporaryDirectory() as tmp:
            stale = [{"player_id": "stale", "player_name": "Stale From Disk"}]
            (Path(tmp) / "latest_leaderboard.json").write_text(json.dumps(stale), encoding="utf-8")
            settings = _settings(tmp, with_supabase=True)
            broken = MagicMock()
            broken.fetch_latest_leaderboard.side_effect = SupabaseError("boom")

            with patch.object(api_main, "_settings", return_value=settings), patch.object(
                api_main, "_storage", return_value=broken
            ):
                with self.assertRaises(HTTPException) as ctx:
                    api_main._load_latest()
                self.assertEqual(ctx.exception.status_code, 503)

    def test_supabase_configured_empty_payload_is_404_not_file(self) -> None:
        from api import main as api_main

        with tempfile.TemporaryDirectory() as tmp:
            stale = [{"player_id": "stale", "player_name": "Stale From Disk"}]
            (Path(tmp) / "latest_leaderboard.json").write_text(json.dumps(stale), encoding="utf-8")
            settings = _settings(tmp, with_supabase=True)
            empty = MagicMock()
            empty.fetch_latest_leaderboard.return_value = []

            with patch.object(api_main, "_settings", return_value=settings), patch.object(
                api_main, "_storage", return_value=empty
            ):
                with self.assertRaises(HTTPException) as ctx:
                    api_main._load_latest()
                self.assertEqual(ctx.exception.status_code, 404)

    def test_without_supabase_local_file_still_allowed(self) -> None:
        from api import main as api_main

        with tempfile.TemporaryDirectory() as tmp:
            local = [{"player_id": "1", "player_name": "Local Dev"}]
            (Path(tmp) / "latest_leaderboard.json").write_text(json.dumps(local), encoding="utf-8")
            settings = _settings(tmp, with_supabase=False)

            with patch.object(api_main, "_settings", return_value=settings), patch.object(
                api_main, "_storage", return_value=None
            ):
                payload, source = api_main._load_latest()
                self.assertEqual(source, "file")
                self.assertEqual(payload[0]["player_name"], "Local Dev")


if __name__ == "__main__":
    unittest.main()
