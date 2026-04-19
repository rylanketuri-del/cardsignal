from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict

from pydantic import BaseModel

from cardchase_ai.alerts import AlertEvent, build_daily_digest, detect_player_events, event_passes_player_rule
from cardchase_ai.clients.ebay import EbayClient
from cardchase_ai.clients.mlb import MLBClient
from cardchase_ai.config import get_settings
from cardchase_ai.delivery import AlertDeliveryClient, DeliverySettings, build_notification_email
from cardchase_ai.models.schemas import HitterHotnessBreakdown, MarketSnapshot, RollingHitterStats
from cardchase_ai.score import build_hotness_breakdown
from cardchase_ai.storage import SupabaseStorage
from cardchase_ai.utils.rolling import filter_last_n_days, summarize_hitter_window, summarize_market

SEARCH_TEMPLATES = {
    "broad": "{player} baseball card",
    "bowman_chrome": "{player} Bowman Chrome rookie",
    "auto": "{player} auto baseball card",
    "psa10": "{player} PSA 10 baseball card",
}


class PlayerPipelineOutput(BaseModel):
    player_name: str
    player_id: int
    stats_7d: RollingHitterStats
    stats_30d: RollingHitterStats
    market_snapshots: Dict[str, MarketSnapshot]
    hotness: HitterHotnessBreakdown


class PipelineResult(BaseModel):
    leaderboard_path: str
    run_id: int | None = None
    alerts_created: int = 0
    deliveries_attempted: int = 0


def _build_outputs() -> list[PlayerPipelineOutput]:
    settings = get_settings()
    mlb_client = MLBClient()
    ebay_client = EbayClient(settings.ebay_token, marketplace_id=settings.ebay_marketplace_id)

    outputs = []
    for player_name in settings.tracked_players:
        player = mlb_client.search_player(player_name)
        gamelog = mlb_client.get_hitter_gamelog(player.player_id, settings.mlb_season)
        stats_7d = summarize_hitter_window(filter_last_n_days(gamelog, 7))
        stats_30d = summarize_hitter_window(filter_last_n_days(gamelog, 30))

        market_snapshots: Dict[str, MarketSnapshot] = {}
        for query_name, template in SEARCH_TEMPLATES.items():
            payload = ebay_client.search_items(template.format(player=player_name), include_auctions=True)
            listings = ebay_client.parse_listings(payload)
            market_snapshots[query_name] = summarize_market(query_name, listings)

        hotness = build_hotness_breakdown(
            player_name=player.full_name,
            stats_7d=stats_7d,
            stats_30d=stats_30d,
            market_snapshots=market_snapshots,
        )

        outputs.append(
            PlayerPipelineOutput(
                player_name=player.full_name,
                player_id=player.player_id,
                stats_7d=stats_7d,
                stats_30d=stats_30d,
                market_snapshots=market_snapshots,
                hotness=hotness,
            )
        )

    outputs.sort(key=lambda item: item.hotness.total_score, reverse=True)
    return outputs


def _write_outputs(serialized: list[dict], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    file_path = output_dir / f"leaderboard_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.json"
    file_path.write_text(json.dumps(serialized, indent=2), encoding="utf-8")
    latest_path = output_dir / "latest_leaderboard.json"
    latest_path.write_text(json.dumps(serialized, indent=2), encoding="utf-8")
    return file_path


def _notification_key(user_id: str, event: AlertEvent) -> tuple[str, str, str]:
    return user_id, event.event_type, (event.player_name or "")


def _recent_notification_keys(storage: SupabaseStorage, settings) -> set[tuple[str, str, str]]:
    window_hours = max(settings.alert_cooldown_hours, settings.daily_digest_cooldown_hours, 1)
    since = (datetime.now(timezone.utc) - timedelta(hours=window_hours)).isoformat()
    rows = storage.fetch_recent_notifications(since)
    keys: set[tuple[str, str, str]] = set()
    for row in rows:
        keys.add((str(row.get("user_id")), str(row.get("event_type")), str(row.get("player_name") or "")))
    return keys


def _event_in_cooldown(recent_keys: set[tuple[str, str, str]], user_id: str, event: AlertEvent) -> bool:
    return _notification_key(user_id, event) in recent_keys


def _process_alerts(storage: SupabaseStorage, run_id: int, current_entries: list[dict]) -> tuple[int, int]:
    previous_run = storage.fetch_previous_run(exclude_run_id=run_id)
    previous_entries = storage.fetch_run_leaderboard(int(previous_run["id"])) if previous_run else []
    event_map = detect_player_events(current_entries, previous_entries, hotness_jump_threshold=1.0)
    targets = storage.fetch_alert_targets()
    if not targets:
        return 0, 0

    settings = get_settings()
    recent_keys = _recent_notification_keys(storage, settings)
    delivery_client = AlertDeliveryClient(
        DeliverySettings(
            alert_webhook_url=settings.alert_webhook_url,
            alert_webhook_bearer_token=settings.alert_webhook_bearer_token,
            alert_from_email=settings.alert_from_email,
            alert_sender_name=settings.alert_sender_name,
            app_base_url=settings.app_base_url,
            resend_api_key=settings.resend_api_key,
        )
    )

    notification_rows = []
    sendable_notifications = []

    for target in targets:
        user_id = str(target["user_id"])
        email = target.get("email") or (target.get("profiles") or {}).get("email")
        watchlists = target.get("watchlists") or []
        watch_names = [item["player_name"] for item in watchlists]
        rule_map = {item["player_name"]: item for item in (target.get("player_alert_rules") or [])}
        seen = set()

        for player_name in watch_names:
            player_rule = rule_map.get(player_name)
            for event in event_map.get(player_name, []):
                if event.event_type == "hotness_jump" and not target.get("hotness_jump_enabled"):
                    continue
                if event.event_type == "buy_low" and not target.get("buy_low_enabled"):
                    continue
                if event.event_type == "most_chased" and not target.get("most_chased_enabled"):
                    continue
                if not event_passes_player_rule(event, player_rule, default_hotness_jump_threshold=8.0):
                    continue
                key = (user_id, player_name, event.event_type)
                if key in seen or _event_in_cooldown(recent_keys, user_id, event):
                    continue
                seen.add(key)
                recent_keys.add(_notification_key(user_id, event))
                notification_rows.append(event.to_row(run_id=run_id, user_id=user_id, channel="in_app"))
                sendable_notifications.append({"user_id": user_id, "email": email, "event": event})

        if target.get("daily_digest_enabled"):
            digest = build_daily_digest(current_entries, watch_names)
            if digest and not _event_in_cooldown(recent_keys, user_id, digest):
                recent_keys.add(_notification_key(user_id, digest))
                notification_rows.append(digest.to_row(run_id=run_id, user_id=user_id, channel="in_app"))
                sendable_notifications.append({"user_id": user_id, "email": email, "event": digest})

    inserted = storage.insert_notifications(notification_rows)
    deliveries_attempted = 0
    for row in inserted:
        deliveries_attempted += 1
        storage.mark_notification_delivery(int(row["id"]), channel="in_app", status="stored", destination=row.get("user_id"), provider="supabase")

    for row, plan in zip(inserted, sendable_notifications):
        event = plan["event"]
        email = plan["email"]
        if email:
            html_body, text_body = build_notification_email(
                event.event_type,
                event.title,
                event.message,
                None if event.player_name == "Daily Digest" else event.player_name,
                settings.app_base_url,
            )
            ok, status = delivery_client.send_resend_email(email, event.title, text_body, html_body=html_body)
            storage.mark_notification_delivery(int(row["id"]), channel="email", status="sent" if ok else "failed", destination=email, provider="resend", error=None if ok else status)
            deliveries_attempted += 1
        if settings.alert_webhook_url:
            webhook_payload = {
                "notification_id": row["id"],
                "user_id": row["user_id"],
                "player_name": row.get("player_name"),
                "event_type": row["event_type"],
                "title": row["title"],
                "message": row["message"],
                "metadata": row.get("metadata") or {},
                "app_base_url": settings.app_base_url,
            }
            ok, status = delivery_client.send_webhook(webhook_payload)
            storage.mark_notification_delivery(int(row["id"]), channel="webhook", status="sent" if ok else "failed", destination=settings.alert_webhook_url, provider="webhook", error=None if ok else status)
            deliveries_attempted += 1

    return len(inserted), deliveries_attempted


def run() -> Path:
    result = run_pipeline()
    return Path(result.leaderboard_path)


def run_pipeline() -> PipelineResult:
    settings = get_settings()
    outputs = _build_outputs()
    serialized = [json.loads(output.model_dump_json()) for output in outputs]
    file_path = _write_outputs(serialized, settings.output_dir)

    result = PipelineResult(leaderboard_path=str(file_path))
    if settings.supabase_url and settings.supabase_service_role_key:
        storage = SupabaseStorage(settings.supabase_url, settings.supabase_service_role_key)
        run_id = storage.persist_leaderboard(str(file_path), serialized)
        alerts_created, deliveries_attempted = _process_alerts(storage, run_id, serialized)
        result = PipelineResult(
            leaderboard_path=str(file_path),
            run_id=run_id,
            alerts_created=alerts_created,
            deliveries_attempted=deliveries_attempted,
        )
    return result
