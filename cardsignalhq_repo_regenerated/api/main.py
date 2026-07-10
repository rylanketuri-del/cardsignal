from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from cardchase_ai.intelligence.public import build_player_card_intelligence_response
from cardchase_ai.identity import enrich_player_entry
from cardchase_ai.card_registry import get_enriched_player_cards
from cardchase_ai.clients.mlb import MLBClient
from cardchase_ai.config import get_settings
from cardchase_ai.market.history import (
    build_player_market_activity_points,
    filter_card_history,
    filter_player_history,
    history_to_public_snapshots,
    load_local_card_market_history,
)
from cardchase_ai.market.movement import (
    MovementToleranceConfig,
    SUPPORTED_WINDOWS,
    calculate_card_market_movement,
    movement_to_public_dict,
    normalize_snapshot_row,
    sort_snapshots_asc,
)
from cardchase_ai.market.player_market import aggregate_player_market, build_player_card_market_item
from cardchase_ai.pipeline import run_pipeline
from cardchase_ai.population.history import filter_card_population_history, load_local_population_history, load_local_psa_matches
from cardchase_ai.population.import_loader import validate_import_rows
from cardchase_ai.population.public import (
    build_card_population_latest_response,
    normalize_population_snapshot_row,
    normalize_psa_match_row,
)
from cardchase_ai.storage import SupabaseError, SupabaseStorage


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


class PopulationImportRequest(BaseModel):
    rows: list[dict[str, Any]]

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
    enriched = [enrich_player_entry(entry) for entry in payload]
    return JSONResponse({"data_source": source, "items": enriched})


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
def search_players(q: str = "") -> JSONResponse:
    query = (q or "").strip()
    if len(query) < 2:
        return JSONResponse([])

    try:
        results = MLBClient().search_players(query, limit=10)
        enriched = [enrich_player_entry(result.model_dump()) for result in results]
        return JSONResponse(enriched)
    except Exception:
        return JSONResponse([])


@app.get("/api/players/{player_id}")
def get_player(player_id: str) -> JSONResponse:
    payload, source = _load_player(player_id)
    if isinstance(payload, dict):
        payload = enrich_player_entry(payload)
        payload["data_source"] = source
    return JSONResponse(payload)


def _normalize_card_market_snapshot_row(row: dict[str, Any]) -> dict[str, Any]:
    metrics = row.get("metrics") or {}
    return {
        "cs_card_id": row["cs_card_id"],
        "cs_player_id": row["cs_player_id"],
        "league": metrics.get("league", "MLB"),
        "source": row.get("source", "ebay"),
        "query": row.get("query", ""),
        "captured_at": row.get("captured_at") or row.get("created_at"),
        "algorithm_version": row.get("algorithm_version", ""),
        **metrics,
    }


def _load_latest_card_market_snapshots_from_file() -> list[dict[str, Any]]:
    latest_path = _settings().output_dir / "latest_card_market_snapshots.json"
    if not latest_path.exists():
        return []
    return json.loads(latest_path.read_text(encoding="utf-8"))


def _try_load_latest_card_market_snapshot(cs_card_id: str) -> tuple[dict[str, Any] | None, str | None]:
    storage = _storage()
    if storage:
        try:
            row = storage.fetch_latest_card_market_snapshot(cs_card_id)
            if row:
                return _normalize_card_market_snapshot_row(row), "supabase"
        except SupabaseError:
            pass

    for item in _load_latest_card_market_snapshots_from_file():
        if str(item.get("cs_card_id")) == cs_card_id:
            return item, "file"

    return None, None


def _load_player_card_market_snapshots(cs_player_id: str) -> tuple[dict[str, dict[str, Any]], str | None]:
    snapshots_by_card: dict[str, dict[str, Any]] = {}
    data_source: str | None = None

    storage = _storage()
    if storage:
        try:
            rows = storage.fetch_card_market_snapshots_for_player(cs_player_id)
            for row in rows:
                card_id = str(row.get("cs_card_id") or "")
                if card_id:
                    snapshots_by_card[card_id] = _normalize_card_market_snapshot_row(row)
            if snapshots_by_card:
                return snapshots_by_card, "supabase"
        except SupabaseError:
            pass

    for item in _load_latest_card_market_snapshots_from_file():
        if str(item.get("cs_player_id")) != cs_player_id:
            continue
        card_id = str(item.get("cs_card_id") or "")
        if card_id and card_id not in snapshots_by_card:
            snapshots_by_card[card_id] = item
            data_source = "file"

    return snapshots_by_card, data_source


def _load_latest_card_market_snapshot(cs_card_id: str) -> tuple[dict[str, Any], str]:
    payload, source = _try_load_latest_card_market_snapshot(cs_card_id)
    if not payload or not source:
        raise HTTPException(status_code=404, detail=f"No market snapshot found for card {cs_card_id}.")
    return payload, source


def _movement_tolerance_config() -> MovementToleranceConfig:
    settings = _settings()
    return MovementToleranceConfig(
        tolerance_7d_days=settings.card_market_movement_7d_tolerance_days,
        tolerance_30d_days=settings.card_market_movement_30d_tolerance_days,
        max_gap_7d_days=settings.card_market_movement_max_gap_7d_days,
        max_gap_30d_days=settings.card_market_movement_max_gap_30d_days,
    )


def _normalize_comparison_window(window: str = "7d") -> str:
    normalized = str(window or "7d").strip().lower()
    if normalized not in SUPPORTED_WINDOWS:
        raise HTTPException(status_code=400, detail=f"Unsupported comparison window: {window}")
    return normalized


def _load_card_market_snapshot_history(cs_card_id: str, *, limit: int = 12) -> tuple[list[dict[str, Any]], str | None]:
    storage = _storage()
    if storage:
        try:
            rows = storage.fetch_card_market_snapshot_history(cs_card_id, limit=limit)
            if rows:
                normalized = [_normalize_card_market_snapshot_row(row) for row in rows]
                return normalized, "supabase"
        except SupabaseError:
            pass

    local_rows = filter_card_history(load_local_card_market_history(_settings().output_dir), cs_card_id, limit=limit)
    if local_rows:
        return local_rows, "file"
    return [], None


def _load_card_market_snapshots_for_movement(cs_card_id: str) -> tuple[list[dict[str, Any]], str | None]:
    storage = _storage()
    if storage:
        try:
            rows = storage.fetch_card_market_snapshot_history(cs_card_id, limit=120)
            if rows:
                return [_normalize_card_market_snapshot_row(row) for row in rows], "supabase"
        except SupabaseError:
            pass

    local_rows = filter_card_history(load_local_card_market_history(_settings().output_dir), cs_card_id, limit=0)
    if local_rows:
        return local_rows, "file"
    return [], None


def _load_player_card_market_history(cs_player_id: str) -> tuple[list[dict[str, Any]], str | None]:
    storage = _storage()
    if storage:
        try:
            rows = storage.fetch_card_market_snapshots_for_player_history(cs_player_id)
            if rows:
                return [_normalize_card_market_snapshot_row(row) for row in rows], "supabase"
        except SupabaseError:
            pass

    local_rows = filter_player_history(load_local_card_market_history(_settings().output_dir), cs_player_id)
    if local_rows:
        return local_rows, "file"
    return [], None


def _load_latest_card_population_snapshots_from_file() -> list[dict[str, Any]]:
    latest_path = _settings().output_dir / "latest_card_population_snapshots.json"
    if not latest_path.exists():
        return []
    return json.loads(latest_path.read_text(encoding="utf-8"))


def _try_load_latest_card_population_snapshot(cs_card_id: str) -> tuple[dict[str, Any] | None, str | None]:
    storage = _storage()
    if storage:
        try:
            row = storage.fetch_latest_card_population_snapshot(cs_card_id)
            if row:
                return normalize_population_snapshot_row(row), "supabase"
        except SupabaseError:
            pass

    for item in _load_latest_card_population_snapshots_from_file():
        if str(item.get("cs_card_id")) == cs_card_id:
            return normalize_population_snapshot_row(item), "file"

    return None, None


def _try_load_psa_card_match(cs_card_id: str) -> dict[str, Any] | None:
    storage = _storage()
    if storage:
        try:
            row = storage.fetch_psa_card_match(cs_card_id)
            if row:
                return normalize_psa_match_row(row)
        except SupabaseError:
            pass

    for item in load_local_psa_matches(_settings().output_dir):
        if str(item.get("cs_card_id")) == cs_card_id:
            return normalize_psa_match_row(item)
    return None


def _load_card_population_snapshot_history(cs_card_id: str, *, limit: int = 12) -> tuple[list[dict[str, Any]], str | None]:
    storage = _storage()
    if storage:
        try:
            rows = storage.fetch_card_population_snapshot_history(cs_card_id, limit=limit)
            if rows:
                return [normalize_population_snapshot_row(row) for row in rows], "supabase"
        except SupabaseError:
            pass

    local_rows = filter_card_population_history(load_local_population_history(_settings().output_dir), cs_card_id, limit=limit)
    if local_rows:
        return [normalize_population_snapshot_row(row) for row in local_rows], "file"
    return [], None


def _load_player_card_population_snapshots(cs_player_id: str) -> tuple[dict[str, dict[str, Any]], str | None]:
    snapshots_by_card: dict[str, dict[str, Any]] = {}
    data_source: str | None = None

    storage = _storage()
    if storage:
        try:
            rows = storage.fetch_card_population_snapshots_for_player(cs_player_id)
            for row in rows:
                card_id = str(row.get("cs_card_id") or "")
                if card_id:
                    snapshots_by_card[card_id] = normalize_population_snapshot_row(row)
            if snapshots_by_card:
                return snapshots_by_card, "supabase"
        except SupabaseError:
            pass

    for item in _load_latest_card_population_snapshots_from_file():
        if str(item.get("cs_player_id")) != cs_player_id:
            continue
        card_id = str(item.get("cs_card_id") or "")
        if card_id and card_id not in snapshots_by_card:
            snapshots_by_card[card_id] = normalize_population_snapshot_row(item)
            data_source = "file"

    return snapshots_by_card, data_source


def _card_identity_payload(card: dict[str, Any]) -> dict[str, Any]:
    return {
        "cs_card_id": card.get("cs_card_id"),
        "year": card.get("year"),
        "manufacturer": card.get("manufacturer"),
        "set_name": card.get("set_name"),
        "card_name": card.get("card_name") or card.get("card"),
        "parallel": card.get("parallel"),
        "grade": card.get("grade"),
        "grading_company": card.get("grading_company"),
    }


@app.get("/api/cards/{cs_card_id}/market/latest")
def get_card_market_latest(cs_card_id: str) -> JSONResponse:
    payload, source = _load_latest_card_market_snapshot(cs_card_id)
    payload["data_source"] = source
    return JSONResponse(payload)


@app.get("/api/players/{player_id}/cards/market/latest")
def get_player_card_market_latest(player_id: str) -> JSONResponse:
    payload, source = _load_player(player_id)
    player = enrich_player_entry(payload)
    cs_player_id = player.get("cs_player_id")
    if not cs_player_id:
        raise HTTPException(status_code=404, detail=f"Player identity not found for {player_id}.")

    registry_cards = get_enriched_player_cards(player)
    snapshots_by_card, snapshot_source = _load_player_card_market_snapshots(cs_player_id)

    cards = [
        build_player_card_market_item(card, snapshots_by_card.get(str(card.get("cs_card_id") or "")))
        for card in registry_cards
    ]
    response = {
        "player_id": player.get("player_id") or player_id,
        "cs_player_id": cs_player_id,
        "cards": cards,
        "aggregate": aggregate_player_market(cards),
        "data_source": snapshot_source or source,
    }
    return JSONResponse(response)


@app.get("/api/cards/{cs_card_id}/market/history")
def get_card_market_history(cs_card_id: str, limit: int = 12) -> JSONResponse:
    bounded_limit = max(1, min(limit, 60))
    rows, source = _load_card_market_snapshot_history(cs_card_id, limit=bounded_limit)
    return JSONResponse(
        {
            "cs_card_id": cs_card_id,
            "limit": bounded_limit,
            "order": "oldest_to_newest",
            "items": history_to_public_snapshots(rows),
            "data_source": source,
        }
    )


@app.get("/api/cards/{cs_card_id}/market/movement")
def get_card_market_movement(cs_card_id: str, window: str = "7d") -> JSONResponse:
    comparison_window = _normalize_comparison_window(window)
    rows, source = _load_card_market_snapshots_for_movement(cs_card_id)
    if not rows:
        raise HTTPException(status_code=404, detail=f"No market history found for card {cs_card_id}.")

    movement = calculate_card_market_movement(rows, window=comparison_window, config=_movement_tolerance_config())
    if movement is None:
        raise HTTPException(status_code=404, detail=f"No movement could be calculated for card {cs_card_id}.")

    return JSONResponse(
        {
            "cs_card_id": cs_card_id,
            "window": comparison_window,
            "movement": movement_to_public_dict(movement),
            "data_source": source,
        }
    )


@app.get("/api/players/{player_id}/cards/market/movement")
def get_player_card_market_movement(player_id: str, window: str = "7d") -> JSONResponse:
    comparison_window = _normalize_comparison_window(window)
    payload, source = _load_player(player_id)
    player = enrich_player_entry(payload)
    cs_player_id = player.get("cs_player_id")
    if not cs_player_id:
        raise HTTPException(status_code=404, detail=f"Player identity not found for {player_id}.")

    registry_cards = get_enriched_player_cards(player)
    history_rows, history_source = _load_player_card_market_history(cs_player_id)
    history_by_card: dict[str, list[dict[str, Any]]] = {}
    for row in history_rows:
        card_id = str(row.get("cs_card_id") or "")
        history_by_card.setdefault(card_id, []).append(row)

    tolerance = _movement_tolerance_config()
    cards_payload: list[dict[str, Any]] = []
    for card in registry_cards:
        card_id = str(card.get("cs_card_id") or "")
        card_history = sort_snapshots_asc(history_by_card.get(card_id, []))
        movement = calculate_card_market_movement(card_history, window=comparison_window, config=tolerance)
        cards_payload.append(
            {
                "cs_card_id": card_id,
                "card_identity": _card_identity_payload(card),
                "movement": movement_to_public_dict(movement) if movement else None,
            }
        )

    return JSONResponse(
        {
            "player_id": player.get("player_id") or player_id,
            "cs_player_id": cs_player_id,
            "window": comparison_window,
            "cards": cards_payload,
            "data_source": history_source or source,
        }
    )


@app.get("/api/players/{player_id}/cards/market/activity")
def get_player_card_market_activity(player_id: str, limit: int = 12) -> JSONResponse:
    bounded_limit = max(2, min(limit, 30))
    payload, source = _load_player(player_id)
    player = enrich_player_entry(payload)
    cs_player_id = player.get("cs_player_id")
    if not cs_player_id:
        raise HTTPException(status_code=404, detail=f"Player identity not found for {player_id}.")

    history_rows, history_source = _load_player_card_market_history(cs_player_id)
    normalized = []
    for row in history_rows:
        try:
            normalized.append(normalize_snapshot_row(row))
        except ValueError:
            continue

    points = build_player_market_activity_points(normalized, limit=bounded_limit)
    return JSONResponse(
        {
            "player_id": player.get("player_id") or player_id,
            "cs_player_id": cs_player_id,
            "limit": bounded_limit,
            "points": points,
            "data_source": history_source or source,
        }
    )


@app.get("/api/cards/{cs_card_id}/population/latest")
def get_card_population_latest(cs_card_id: str) -> JSONResponse:
    snapshot, source = _try_load_latest_card_population_snapshot(cs_card_id)
    match = _try_load_psa_card_match(cs_card_id)
    history, _ = _load_card_population_snapshot_history(cs_card_id, limit=12)

    card_identity = {
        "cs_card_id": cs_card_id,
        "cs_player_id": snapshot.get("cs_player_id") if snapshot else (match or {}).get("cs_player_id"),
    }
    if snapshot:
        card_identity.update(
            {
                "year": snapshot.get("year"),
                "manufacturer": snapshot.get("manufacturer"),
                "set_name": snapshot.get("set_name"),
                "card_name": snapshot.get("card_name"),
                "parallel": snapshot.get("parallel"),
                "player_name": snapshot.get("player_name"),
            }
        )

    if not snapshot and not match:
        raise HTTPException(status_code=404, detail=f"No PSA population data found for card {cs_card_id}.")

    response = build_card_population_latest_response(
        card_identity=card_identity,
        snapshot=snapshot,
        match=match,
        history=history,
    )
    response["data_source"] = source
    response["disclaimer"] = "PSA population reflects graded examples, not total card supply."
    return JSONResponse(response)


@app.get("/api/cards/{cs_card_id}/population/history")
def get_card_population_history(cs_card_id: str, limit: int = 12) -> JSONResponse:
    bounded_limit = max(1, min(limit, 60))
    rows, source = _load_card_population_snapshot_history(cs_card_id, limit=bounded_limit)
    if not rows:
        raise HTTPException(status_code=404, detail=f"No population history found for card {cs_card_id}.")
    return JSONResponse(
        {
            "cs_card_id": cs_card_id,
            "limit": bounded_limit,
            "order": "oldest_to_newest",
            "items": rows,
            "data_source": source,
            "disclaimer": "PSA population reflects graded examples, not total card supply.",
        }
    )


@app.get("/api/players/{player_id}/cards/population/latest")
def get_player_card_population_latest(player_id: str) -> JSONResponse:
    payload, source = _load_player(player_id)
    player = enrich_player_entry(payload)
    cs_player_id = player.get("cs_player_id")
    if not cs_player_id:
        raise HTTPException(status_code=404, detail=f"Player identity not found for {player_id}.")

    registry_cards = get_enriched_player_cards(player)
    snapshots_by_card, snapshot_source = _load_player_card_population_snapshots(cs_player_id)

    cards = []
    for card in registry_cards:
        card_id = str(card.get("cs_card_id") or "")
        snapshot = snapshots_by_card.get(card_id)
        match = _try_load_psa_card_match(card_id)
        history, _ = _load_card_population_snapshot_history(card_id, limit=12)
        cards.append(
            build_card_population_latest_response(
                card_identity=card,
                snapshot=snapshot,
                match=match,
                history=history,
            )
        )

    return JSONResponse(
        {
            "player_id": player.get("player_id") or player_id,
            "cs_player_id": cs_player_id,
            "cards": cards,
            "data_source": snapshot_source or source,
            "disclaimer": "PSA population reflects graded examples, not total card supply.",
        }
    )


@app.get("/api/players/{player_id}/card-intelligence")
def get_player_card_intelligence(player_id: str) -> JSONResponse:
    payload, source = _load_player(player_id)
    player = enrich_player_entry(payload)
    cs_player_id = player.get("cs_player_id")
    if not cs_player_id:
        raise HTTPException(status_code=404, detail=f"Player identity not found for {player_id}.")

    registry_cards = get_enriched_player_cards(player)
    market_snapshots_by_card, market_source = _load_player_card_market_snapshots(cs_player_id)
    population_snapshots_by_card, population_source = _load_player_card_population_snapshots(cs_player_id)

    history_rows, history_source = _load_player_card_market_history(cs_player_id)
    market_history_by_card: dict[str, list[dict[str, Any]]] = {}
    for row in history_rows:
        card_id = str(row.get("cs_card_id") or "")
        market_history_by_card.setdefault(card_id, []).append(row)

    population_history_by_card: dict[str, list[dict[str, Any]]] = {}
    psa_matches_by_card: dict[str, dict[str, Any]] = {}
    for card in registry_cards:
        card_id = str(card.get("cs_card_id") or "")
        pop_history, _ = _load_card_population_snapshot_history(card_id, limit=12)
        if pop_history:
            population_history_by_card[card_id] = pop_history
        match = _try_load_psa_card_match(card_id)
        if match:
            psa_matches_by_card[card_id] = match

    response = build_player_card_intelligence_response(
        player=player,
        registry_cards=registry_cards,
        market_snapshots_by_card=market_snapshots_by_card,
        market_history_by_card=market_history_by_card,
        population_snapshots_by_card=population_snapshots_by_card,
        population_history_by_card=population_history_by_card,
        psa_matches_by_card=psa_matches_by_card,
        movement_config=_movement_tolerance_config(),
        data_source=market_source or population_source or history_source or source,
    )
    return JSONResponse(response)


@app.post("/api/admin/population/import")
def post_admin_population_import(payload: PopulationImportRequest, admin=Depends(_require_admin)) -> JSONResponse:
    accepted, errors = validate_import_rows(payload.rows)
    if not accepted and errors:
        return JSONResponse({"status": "error", "accepted": 0, "errors": errors})

    settings = _settings()
    from cardchase_ai.population.import_provider import ImportPopulationProvider

    provider = ImportPopulationProvider(accepted)
    snapshots: list[dict[str, Any]] = []
    matches: list[dict[str, Any]] = []

    for row in accepted:
        card_identity = {"cs_card_id": row["cs_card_id"], "cs_player_id": row.get("cs_player_id", ""), "league": "MLB"}
        match_candidates = provider.search_card_matches({**row, **card_identity})
        if not match_candidates:
            errors.append({"row": row.get("cs_card_id"), "error": "Could not resolve PSA match"})
            continue
        match = match_candidates[0]
        raw = provider.fetch_population(match)
        if raw is None:
            errors.append({"row": row.get("cs_card_id"), "error": "Population payload missing"})
            continue
        snapshot_payload = provider.normalize_population(raw, card_match=match, card_identity={**row, **card_identity})
        snapshots.append(snapshot_payload)
        matches.append(match.model_dump(mode="json"))

    storage = _storage()
    if storage and snapshots:
        try:
            if matches:
                storage.upsert_psa_card_matches(matches)
            storage.insert_card_population_snapshots(snapshots)
        except SupabaseError as exc:
            errors.append({"row": None, "error": str(exc)})

    if snapshots:
        from cardchase_ai.population.history import append_local_population_history, save_local_psa_matches

        append_local_population_history(snapshots, settings.output_dir)
        if matches:
            save_local_psa_matches(matches, settings.output_dir)

    return JSONResponse({"status": "ok", "accepted": len(snapshots), "errors": errors})


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
    return {
        "status": "ok",
        "output_path": result.leaderboard_path,
        "run_id": result.run_id or 0,
        "alerts_created": result.alerts_created,
        "deliveries_attempted": result.deliveries_attempted,
        "card_market_snapshot_count": result.card_market_snapshot_count,
        "card_market_snapshot_path": result.card_market_snapshot_path or "",
    }


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
