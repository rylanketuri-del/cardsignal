"""Isolated card-level active listing snapshot pipeline step."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from cardchase_ai.card_registry import get_enriched_player_cards
from cardchase_ai.clients.ebay import EbayClient
from cardchase_ai.clients.mlb import MLBClient
from cardchase_ai.config import Settings, get_settings
from cardchase_ai.identity import enrich_player_entry
from cardchase_ai.market.queries import build_card_search_query
from cardchase_ai.market.snapshot import build_card_market_snapshot
from cardchase_ai.models.schemas import CardMarketSnapshot
from cardchase_ai.storage import SupabaseStorage


class CardMarketSnapshotResult(BaseModel):
    snapshot_count: int = 0
    player_count: int = 0
    card_count: int = 0
    error_count: int = 0
    output_path: str | None = None
    snapshots: list[CardMarketSnapshot] = Field(default_factory=list)


def _write_local_snapshots(snapshots: list[dict[str, Any]], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    file_path = output_dir / f"card_market_snapshots_{stamp}.json"
    file_path.write_text(json.dumps(snapshots, indent=2), encoding="utf-8")

    latest_path = output_dir / "latest_card_market_snapshots.json"
    latest_path.write_text(json.dumps(snapshots, indent=2), encoding="utf-8")
    return file_path


def _build_player_pool(settings: Settings, mlb_client: MLBClient) -> list[dict[str, Any]]:
    from cardchase_ai.pipeline import _build_market_universe

    candidates = _build_market_universe(mlb_client, settings)
    limit = max(1, settings.card_market_player_limit)
    return [enrich_player_entry(candidate) for candidate in candidates[:limit]]


def run_card_market_snapshots(
    *,
    settings: Settings | None = None,
    storage: SupabaseStorage | None = None,
    ebay_client: EbayClient | None = None,
    persist: bool = True,
) -> CardMarketSnapshotResult:
    settings = settings or get_settings()
    mlb_client = MLBClient()

    if ebay_client is None:
        ebay_client = EbayClient(
            token=settings.ebay_token,
            marketplace_id=settings.ebay_marketplace_id,
            client_id=settings.ebay_client_id,
            client_secret=settings.ebay_client_secret,
        )

    players = _build_player_pool(settings, mlb_client)
    snapshots: list[CardMarketSnapshot] = []
    seen_queries: set[str] = set()
    error_count = 0
    card_count = 0
    scan_limit = max(1, settings.card_market_scan_limit)

    for player in players:
        if len(snapshots) >= scan_limit:
            break

        try:
            cards = get_enriched_player_cards(
                player,
                limit=settings.card_market_cards_per_player_limit,
            )
        except Exception as error:
            error_count += 1
            print(f"Card registry lookup failed for {player.get('player_name')}: {error}")
            continue

        for card in cards:
            if len(snapshots) >= scan_limit:
                break

            card_count += 1
            query = build_card_search_query(card)

            if not query:
                error_count += 1
                print(f"Skipped card without query: {card.get('cs_card_id')}")
                continue

            if query in seen_queries:
                continue
            seen_queries.add(query)

            try:
                payload = ebay_client.search_items(
                    query,
                    limit=settings.ebay_results_per_query_limit,
                    include_auctions=True,
                )
                listings = ebay_client.parse_active_listings(payload)
                snapshot = build_card_market_snapshot(card, listings, query=query)
                snapshots.append(snapshot)
            except Exception as error:
                error_count += 1
                print(f"Card market snapshot failed for {card.get('cs_card_id')}: {error}")

    serialized = [json.loads(snapshot.model_dump_json()) for snapshot in snapshots]
    output_path: str | None = None

    if persist:
        try:
            file_path = _write_local_snapshots(serialized, settings.output_dir)
            output_path = str(file_path)
        except Exception as error:
            error_count += 1
            print(f"Local card snapshot write failed: {error}")

        if storage is None and settings.supabase_url and settings.supabase_service_role_key:
            storage = SupabaseStorage(settings.supabase_url, settings.supabase_service_role_key)

        if storage is not None and serialized:
            try:
                storage.insert_card_market_snapshots(serialized)
            except Exception as error:
                error_count += 1
                print(f"Supabase card snapshot insert failed: {error}")

    return CardMarketSnapshotResult(
        snapshot_count=len(snapshots),
        player_count=len(players),
        card_count=card_count,
        error_count=error_count,
        output_path=output_path,
        snapshots=snapshots,
    )
