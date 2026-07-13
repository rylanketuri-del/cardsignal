from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from cardchase_ai.clients.mlb import MLBClient
from cardchase_ai.config import get_settings
from cardchase_ai.nfl_api import (
    fetch_nfl_leaderboard,
    fetch_nfl_performance,
    fetch_nfl_player,
    fetch_nfl_signal_drivers,
    nfl_availability_payload,
    search_nfl_players,
)
from cardchase_ai.nba_api import (
    fetch_nba_leaderboard,
    fetch_nba_performance,
    fetch_nba_player,
    fetch_nba_signal_drivers,
    nba_availability_payload,
    search_nba_players,
)
from cardchase_ai.pipeline import run_pipeline
from cardchase_ai.storage import SupabaseError, SupabaseStorage
from cardchase_ai.weekly_intelligence import build_latest_weekly_api_payload, build_weekly_storage, run_weekly_intelligence
from cardchase_ai.intelligence_api import fetch_player_intelligence_payload


class ApiStatus(BaseModel):
    status: str
    season: int
    tracked_players: List[str]
    generated_at: str | None = None
    data_source: str | None = None


class WatchlistAddRequest(BaseModel):
    player_id: str | None = None
    player_name: str


class AlertsUpdateRequest(BaseModel):
    hotness_jump_enabled: bool = True
    buy_low_enabled: bool = True
    most_chased_enabled: bool = False
    daily_digest_enabled: bool = True


class NotificationReadRequest(BaseModel):
    notification_id: int


class PlayerAlertRuleUpdateRequest(BaseModel):
    min_hotness_delta: float = 8.0
    alert_on_hotness_jump: bool = True
    alert_on_buy_low: bool = True
    alert_on_most_chased: bool = False
    muted_until: str | None = None




class AdminSettingsUpdateRequest(BaseModel):
    tracked_players_csv: str | None = None
    hotness_jump_threshold: float | None = None
    daily_digest_hour_utc: int | None = None


class AdminTrackedPlayerRequest(BaseModel):
    player_name: str
    notes: str = ""
    active: bool = True


class WeeklyRunRequest(BaseModel):
    league: str = "MLB"
    force: bool = False
    player_limit: int | None = None
    market_enabled: bool | None = None
    population_enabled: bool | None = None

app = FastAPI(title="CardChase AI API", version="0.6.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _settings():
    return get_settings()


def _latest_file() -> Path:
    settings = _settings()
    return settings.output_dir / "latest_leaderboard.json"


def _storage() -> SupabaseStorage | None:
    settings = _settings()
    if settings.supabase_url and settings.supabase_service_role_key:
        return SupabaseStorage(settings.supabase_url, settings.supabase_service_role_key)
    return None


def _load_latest_from_file() -> list[dict[str, Any]]:
    latest = _latest_file()
    if not latest.exists():
        raise HTTPException(status_code=404, detail="No leaderboard found yet. Run the pipeline first.")
    return json.loads(latest.read_text(encoding="utf-8"))


def _load_latest() -> tuple[list[dict[str, Any]], str]:
    storage = _storage()
    if storage:
        try:
            payload = storage.fetch_latest_leaderboard()
            if payload:
                return payload, "supabase"
        except SupabaseError:
            pass
    return _load_latest_from_file(), "file"


def _load_player(player_id: str) -> tuple[dict[str, Any], str]:
    storage = _storage()
    if storage:
        try:
            payload = storage.fetch_player_latest(player_id)
            if payload:
                return payload, "supabase"
        except SupabaseError:
            pass
    payload, _ = _load_latest()
    for entry in payload:
        if str(entry.get("player_id")) == str(player_id):
            return entry, "file"
    raise HTTPException(status_code=404, detail=f"Player {player_id} not found in latest leaderboard.")


def _authorize_pipeline_trigger(authorization: str | None) -> None:
    expected = _settings().pipeline_trigger_token
    if not expected:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token.")
    provided = authorization.replace("Bearer ", "", 1)
    if provided != expected:
        raise HTTPException(status_code=403, detail="Invalid pipeline trigger token.")


def _get_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing user bearer token.")
    return authorization.replace("Bearer ", "", 1)




def _require_admin(authorization: str | None = Header(default=None)) -> bool:
    expected = _settings().admin_api_token
    if not expected:
        raise HTTPException(status_code=503, detail="Admin API token not configured.")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing admin bearer token.")
    provided = authorization.replace("Bearer ", "", 1)
    if provided != expected:
        raise HTTPException(status_code=403, detail="Invalid admin token.")
    return True

def get_current_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    storage = _storage()
    if not storage:
        raise HTTPException(status_code=503, detail="Supabase is not configured.")
    token = _get_bearer_token(authorization)
    try:
        user = storage.fetch_user(token)
    except SupabaseError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    if not user or not user.get("id"):
        raise HTTPException(status_code=401, detail="Invalid user token.")
    return {"user": user, "token": token}


@app.get("/health", response_model=ApiStatus)
def health() -> ApiStatus:
    settings = _settings()
    generated_at = None
    data_source = None
    storage = _storage()
    if storage:
        try:
            latest_run = storage.fetch_latest_run()
            if latest_run:
                generated_at = latest_run["created_at"]
                data_source = "supabase"
        except SupabaseError:
            data_source = "file"
    if generated_at is None:
        latest = _latest_file()
        if latest.exists():
            generated_at = datetime.fromtimestamp(latest.stat().st_mtime, tz=timezone.utc).isoformat()
            data_source = "file"
    return ApiStatus(status="ok", season=settings.mlb_season, tracked_players=settings.tracked_players, generated_at=generated_at, data_source=data_source)

@app.get("/api/ebay/account-deletion")
def verify_ebay_account_deletion_challenge(challenge_code: str):
    import hashlib
    import os

    verification_token = os.getenv("EBAY_MARKETPLACE_DELETION_VERIFICATION_TOKEN", "")
    endpoint = os.getenv(
        "EBAY_MARKETPLACE_DELETION_ENDPOINT",
        "https://cardsignal-api.onrender.com/api/ebay/account-deletion",
    )

    m = hashlib.sha256()
    m.update(challenge_code.encode("utf-8"))
    m.update(verification_token.encode("utf-8"))
    m.update(endpoint.encode("utf-8"))

    return {"challengeResponse": m.hexdigest()}


@app.post("/api/ebay/account-deletion")
async def receive_ebay_account_deletion_notification():
    return {"status": "received"}


@app.post("/api/ebay/account-deletion")
async def receive_ebay_account_deletion_notification():
    return {"status": "received"}

@app.get("/api/config")
def get_public_config() -> JSONResponse:
    settings = _settings()
    return JSONResponse({"supabase_url": settings.supabase_url, "supabase_anon_key": settings.supabase_anon_key})


@app.get("/api/leaderboard/latest")
def get_latest_leaderboard() -> JSONResponse:
    payload, source = _load_latest()
    return JSONResponse({"data_source": source, "items": payload})


@app.get("/api/runs/latest")
def get_latest_run() -> JSONResponse:
    storage = _storage()
    if not storage:
        raise HTTPException(status_code=404, detail="Supabase is not configured.")
    latest_run = storage.fetch_latest_run()
    if not latest_run:
        raise HTTPException(status_code=404, detail="No pipeline runs found.")
    return JSONResponse(latest_run)


@app.get("/api/players/search")
def search_players(q: str = "", sport: str = "MLB") -> JSONResponse:
    query = (q or "").strip()
    if len(query) < 2:
        return JSONResponse([])

    sport_upper = (sport or "MLB").upper()
    if sport_upper == "NFL":
        return JSONResponse(search_nfl_players(query, limit=10))
    if sport_upper == "NBA":
        return JSONResponse(search_nba_players(query, limit=10))

    try:
        results = MLBClient().search_players(query, limit=10)
        return JSONResponse(results)
    except Exception:
        return JSONResponse([])


@app.get("/api/nfl/players/search")
def search_nfl_players_route(q: str = "") -> JSONResponse:
    query = (q or "").strip()
    if len(query) < 2:
        return JSONResponse([])
    return JSONResponse(search_nfl_players(query, limit=10))


@app.get("/api/nfl/leaderboard/latest")
def get_nfl_leaderboard_latest() -> JSONResponse:
    return JSONResponse(fetch_nfl_leaderboard())


@app.get("/api/nfl/players/{player_id}")
def get_nfl_player(player_id: str) -> JSONResponse:
    payload = fetch_nfl_player(player_id)
    if not payload:
        raise HTTPException(status_code=404, detail="NFL player not found or NFL data unavailable.")
    return JSONResponse(payload)


@app.get("/api/nfl/players/{player_id}/performance")
def get_nfl_player_performance(player_id: str) -> JSONResponse:
    return JSONResponse(fetch_nfl_performance(player_id))


@app.get("/api/nfl/players/{player_id}/signal-drivers")
def get_nfl_player_signal_drivers(player_id: str) -> JSONResponse:
    return JSONResponse(fetch_nfl_signal_drivers(player_id))


@app.get("/api/nfl/status")
def get_nfl_status() -> JSONResponse:
    return JSONResponse(nfl_availability_payload())


@app.get("/api/nba/players/search")
def search_nba_players_route(q: str = "") -> JSONResponse:
    query = (q or "").strip()
    if len(query) < 2:
        return JSONResponse([])
    return JSONResponse(search_nba_players(query, limit=10))


@app.get("/api/nba/leaderboard/latest")
def get_nba_leaderboard_latest() -> JSONResponse:
    return JSONResponse(fetch_nba_leaderboard())


@app.get("/api/nba/players/{player_id}")
def get_nba_player(player_id: str) -> JSONResponse:
    payload = fetch_nba_player(player_id)
    if not payload:
        raise HTTPException(status_code=404, detail="NBA player not found or NBA data unavailable.")
    return JSONResponse(payload)


@app.get("/api/nba/players/{player_id}/performance")
def get_nba_player_performance(player_id: str) -> JSONResponse:
    return JSONResponse(fetch_nba_performance(player_id))


@app.get("/api/nba/players/{player_id}/signal-drivers")
def get_nba_player_signal_drivers(player_id: str) -> JSONResponse:
    return JSONResponse(fetch_nba_signal_drivers(player_id))


@app.get("/api/nba/status")
def get_nba_status() -> JSONResponse:
    return JSONResponse(nba_availability_payload())


@app.get("/api/players/{player_id}")
def get_player(player_id: str) -> JSONResponse:
    payload, source = _load_player(player_id)
    if isinstance(payload, dict):
        payload["data_source"] = source
    return JSONResponse(payload)


@app.get("/api/me")
def get_me(auth=Depends(get_current_user)) -> JSONResponse:
    user = auth["user"]
    return JSONResponse({"id": user["id"], "email": user.get("email")})


@app.get("/api/watchlist")
def get_watchlist(auth=Depends(get_current_user)) -> JSONResponse:
    storage = _storage()
    user = auth["user"]
    token = auth["token"]
    items = storage.fetch_user_watchlist(user["id"], token)
    return JSONResponse({"items": items})


@app.post("/api/watchlist")
def add_watchlist_player(payload: WatchlistAddRequest, auth=Depends(get_current_user)) -> JSONResponse:
    storage = _storage()
    user = auth["user"]
    token = auth["token"]
    item = storage.add_user_watchlist_player(user["id"], payload.player_id, payload.player_name, token)
    return JSONResponse(item)


@app.delete("/api/watchlist/{player_name}")
def remove_watchlist_player(player_name: str, auth=Depends(get_current_user)) -> JSONResponse:
    storage = _storage()
    user = auth["user"]
    token = auth["token"]
    storage.remove_user_watchlist_player(user["id"], player_name, token)
    return JSONResponse({"status": "ok"})


@app.get("/api/watchlist/rules")
def get_watchlist_rules(auth=Depends(get_current_user)) -> JSONResponse:
    storage = _storage()
    user = auth["user"]
    token = auth["token"]
    items = storage.fetch_user_player_alert_rules(user["id"], token)
    return JSONResponse({"items": items})


@app.put("/api/watchlist/rules/{player_name}")
def upsert_watchlist_rule(player_name: str, payload: PlayerAlertRuleUpdateRequest, auth=Depends(get_current_user)) -> JSONResponse:
    storage = _storage()
    user = auth["user"]
    token = auth["token"]
    item = storage.upsert_user_player_alert_rule(user["id"], player_name, payload.model_dump(), token)
    return JSONResponse(item)


@app.delete("/api/watchlist/rules/{player_name}")
def delete_watchlist_rule(player_name: str, auth=Depends(get_current_user)) -> JSONResponse:
    storage = _storage()
    user = auth["user"]
    token = auth["token"]
    storage.remove_user_player_alert_rule(user["id"], player_name, token)
    return JSONResponse({"status": "ok"})


@app.get("/api/alerts")
def get_alerts(auth=Depends(get_current_user)) -> JSONResponse:
    storage = _storage()
    user = auth["user"]
    token = auth["token"]
    alert = storage.fetch_user_alert_subscription(user["id"], token)
    return JSONResponse(alert or {})


@app.put("/api/alerts")
def update_alerts(payload: AlertsUpdateRequest, auth=Depends(get_current_user)) -> JSONResponse:
    storage = _storage()
    user = auth["user"]
    token = auth["token"]
    alert = storage.upsert_user_alert_subscription(user["id"], user.get("email"), payload.model_dump(), token)
    return JSONResponse(alert)


@app.post("/api/pipeline/run")
def trigger_pipeline(authorization: str | None = Header(default=None)) -> dict[str, str | int]:
    _authorize_pipeline_trigger(authorization)
    result = run_pipeline()
    return {"status": "ok", "output_path": result.leaderboard_path, "run_id": result.run_id or 0, "alerts_created": result.alerts_created, "deliveries_attempted": result.deliveries_attempted}


@app.get("/api/weekly/latest")
def get_weekly_latest(league: str = "MLB") -> JSONResponse:
    """Return latest completed official weekly run — read-only, no provider calls."""
    settings = _settings()
    storage = build_weekly_storage(settings)
    payload = build_latest_weekly_api_payload(league.upper(), storage, settings)
    return JSONResponse(payload)


@app.get("/api/players/{league}/{player_id}/intelligence")
def get_player_intelligence(league: str, player_id: str) -> JSONResponse:
    """Normalized player intelligence — read-only, stored weekly snapshots only."""
    settings = _settings()
    storage = build_weekly_storage(settings)
    league_upper = league.upper()
    if league_upper not in {"MLB", "NFL"}:
        raise HTTPException(status_code=404, detail=f"League {league} intelligence not available.")
    payload = fetch_player_intelligence_payload(league_upper, player_id, storage)
    if not payload:
        raise HTTPException(
            status_code=404,
            detail=f"No stored intelligence found for {league_upper} player {player_id}.",
        )
    return JSONResponse(payload)


@app.get("/api/players/{player_id}/signals/weekly")
def get_player_weekly_signals(player_id: str, limit: int = 12) -> JSONResponse:
    """Player weekly signal history — read-only."""
    settings = _settings()
    storage = build_weekly_storage(settings)
    cs_id = player_id if ":" in player_id or player_id.startswith("CS-NFL-P-") or player_id.startswith("CS-NBA-P-") else f"mlb:{player_id}"
    items = storage.fetch_player_weekly_history(cs_id, max(2, min(limit, 52)))
    return JSONResponse({"items": items})


@app.get("/api/cards/{cs_card_id}/intelligence/weekly")
def get_card_weekly_intelligence(cs_card_id: str, limit: int = 12) -> JSONResponse:
    """Card weekly intelligence history — read-only."""
    settings = _settings()
    storage = build_weekly_storage(settings)
    items = storage.fetch_card_weekly_history(cs_card_id, max(2, min(limit, 52)))
    return JSONResponse({"items": items})


@app.post("/api/weekly/run")
def trigger_weekly_run(
    payload: WeeklyRunRequest,
    admin=Depends(_require_admin),
) -> JSONResponse:
    """Admin-only manual weekly intelligence run."""
    settings = _settings()
    summary = run_weekly_intelligence(
        league=payload.league.upper(),
        force=payload.force,
        triggered_by="admin",
        player_limit=payload.player_limit,
        market_enabled=payload.market_enabled,
        population_enabled=payload.population_enabled,
        settings=settings,
    )
    return JSONResponse(summary.model_dump(mode="json"))


@app.get("/api/notifications")
def get_notifications(auth=Depends(get_current_user)) -> JSONResponse:
    storage = _storage()
    user = auth["user"]
    token = auth["token"]
    items = storage.fetch_user_notifications(user["id"], token)
    summary = storage.fetch_user_notification_summary(user["id"], token)
    return JSONResponse({"items": items, "summary": summary})


@app.post("/api/notifications/read")
def mark_notification_read(payload: NotificationReadRequest, auth=Depends(get_current_user)) -> JSONResponse:
    storage = _storage()
    user = auth["user"]
    token = auth["token"]
    item = storage.mark_notification_read(user["id"], payload.notification_id, token)
    if not item:
        raise HTTPException(status_code=404, detail="Notification not found.")
    return JSONResponse(item)


@app.post("/api/notifications/read-all")
def mark_all_notifications_read(auth=Depends(get_current_user)) -> JSONResponse:
    storage = _storage()
    user = auth["user"]
    token = auth["token"]
    items = storage.mark_all_notifications_read(user["id"], token)
    return JSONResponse({"status": "ok", "updated": len(items)})


@app.get("/api/players/{player_id}/history")
def get_player_history(player_id: str, limit: int = 14) -> JSONResponse:
    storage = _storage()
    if not storage:
        raise HTTPException(status_code=404, detail="Supabase is not configured.")
    return JSONResponse({"items": storage.fetch_player_history(player_id, max(2, min(limit, 60)))})


@app.get("/api/history/leaderboard")
def get_leaderboard_history(limit: int = 10) -> JSONResponse:
    storage = _storage()
    if not storage:
        raise HTTPException(status_code=404, detail="Supabase is not configured.")
    return JSONResponse({"items": storage.fetch_leaderboard_history(max(2, min(limit, 30)))})


@app.get("/api/admin/settings")
def get_admin_settings(admin=Depends(_require_admin)) -> JSONResponse:
    storage = _storage()
    if not storage:
        raise HTTPException(status_code=404, detail="Supabase is not configured.")
    tracked = storage.fetch_tracked_players()
    settings_map = storage.fetch_admin_settings()
    return JSONResponse({"settings": settings_map, "tracked_players": tracked})


@app.put("/api/admin/settings")
def put_admin_settings(payload: AdminSettingsUpdateRequest, admin=Depends(_require_admin)) -> JSONResponse:
    storage = _storage()
    if not storage:
        raise HTTPException(status_code=404, detail="Supabase is not configured.")
    updates = {}
    if payload.tracked_players_csv is not None:
        updates["tracked_players_csv"] = payload.tracked_players_csv
    if payload.hotness_jump_threshold is not None:
        updates["hotness_jump_threshold"] = payload.hotness_jump_threshold
    if payload.daily_digest_hour_utc is not None:
        updates["daily_digest_hour_utc"] = payload.daily_digest_hour_utc
    storage.upsert_admin_settings(updates)
    return JSONResponse({"status": "ok", "settings": storage.fetch_admin_settings()})


@app.post("/api/admin/tracked-players")
def post_admin_tracked_player(payload: AdminTrackedPlayerRequest, admin=Depends(_require_admin)) -> JSONResponse:
    storage = _storage()
    if not storage:
        raise HTTPException(status_code=404, detail="Supabase is not configured.")
    row = storage.add_tracked_player(payload.player_name, payload.notes)
    if payload.active is not True:
        row = storage.update_tracked_player(payload.player_name, {"active": payload.active}) or row
    return JSONResponse(row)


@app.put("/api/admin/tracked-players/{player_name}")
def put_admin_tracked_player(player_name: str, payload: AdminTrackedPlayerRequest, admin=Depends(_require_admin)) -> JSONResponse:
    storage = _storage()
    if not storage:
        raise HTTPException(status_code=404, detail="Supabase is not configured.")
    row = storage.update_tracked_player(player_name, {"notes": payload.notes, "active": payload.active, "player_name": payload.player_name})
    return JSONResponse(row or {"status": "ok"})


@app.delete("/api/admin/tracked-players/{player_name}")
def delete_admin_tracked_player(player_name: str, admin=Depends(_require_admin)) -> JSONResponse:
    storage = _storage()
    if not storage:
        raise HTTPException(status_code=404, detail="Supabase is not configured.")
    storage.delete_tracked_player(player_name)
    return JSONResponse({"status": "ok"})
