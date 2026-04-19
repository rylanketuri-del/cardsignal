from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    ebay_token: str
    ebay_marketplace_id: str
    tracked_players: List[str]
    output_dir: Path
    mlb_season: int
    supabase_url: str
    supabase_service_role_key: str
    supabase_anon_key: str
    pipeline_trigger_token: str
    alert_webhook_url: str
    alert_webhook_bearer_token: str
    alert_from_email: str
    alert_sender_name: str
    app_base_url: str
    resend_api_key: str
    alert_cooldown_hours: int
    daily_digest_cooldown_hours: int
    notification_limit: int
    admin_api_token: str


def get_settings() -> Settings:
    tracked_players = [
        name.strip()
        for name in os.getenv("TRACKED_PLAYERS", "Elly De La Cruz").split(",")
        if name.strip()
    ]
    return Settings(
        ebay_token=os.getenv("EBAY_TOKEN", ""),
        ebay_marketplace_id=os.getenv("EBAY_MARKETPLACE_ID", "EBAY_US"),
        tracked_players=tracked_players,
        output_dir=Path(os.getenv("OUTPUT_DIR", "./output")),
        mlb_season=int(os.getenv("MLB_SEASON", "2026")),
        supabase_url=os.getenv("SUPABASE_URL", ""),
        supabase_service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""),
        supabase_anon_key=os.getenv("SUPABASE_ANON_KEY", ""),
        pipeline_trigger_token=os.getenv("PIPELINE_TRIGGER_TOKEN", ""),
        alert_webhook_url=os.getenv("ALERT_WEBHOOK_URL", ""),
        alert_webhook_bearer_token=os.getenv("ALERT_WEBHOOK_BEARER_TOKEN", ""),
        alert_from_email=os.getenv("ALERT_FROM_EMAIL", "alerts@example.com"),
        alert_sender_name=os.getenv("ALERT_SENDER_NAME", "CardChase AI"),
        app_base_url=os.getenv("APP_BASE_URL", ""),
        resend_api_key=os.getenv("RESEND_API_KEY", ""),
        alert_cooldown_hours=int(os.getenv("ALERT_COOLDOWN_HOURS", "12")),
        daily_digest_cooldown_hours=int(os.getenv("DAILY_DIGEST_COOLDOWN_HOURS", "20")),
        notification_limit=int(os.getenv("NOTIFICATION_LIMIT", "50")),
        admin_api_token=os.getenv("ADMIN_API_TOKEN", ""),
    )
