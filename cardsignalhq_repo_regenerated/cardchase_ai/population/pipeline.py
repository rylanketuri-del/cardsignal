"""Isolated PSA population snapshot pipeline step — Sprint 8.6."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from cardchase_ai.card_registry import get_enriched_player_cards
from cardchase_ai.clients.mlb import MLBClient
from cardchase_ai.clients.psa import PSAClient
from cardchase_ai.config import Settings, get_settings
from cardchase_ai.identity import enrich_player_entry
from cardchase_ai.population.history import append_local_population_history, save_local_psa_matches
from cardchase_ai.population.import_loader import load_import_file
from cardchase_ai.population.import_provider import ImportPopulationProvider
from cardchase_ai.population.psa_provider import PSAPopulationProvider
from cardchase_ai.population.provider import PopulationProvider
from cardchase_ai.population.scarcity import calculate_card_scarcity_metrics
from cardchase_ai.storage import SupabaseStorage


class PopulationSnapshotResult(BaseModel):
    snapshot_count: int = 0
    match_count: int = 0
    player_count: int = 0
    card_count: int = 0
    error_count: int = 0
    output_path: str | None = None
    snapshots: list[dict[str, Any]] = Field(default_factory=list)


def build_population_provider(settings: Settings) -> PopulationProvider | None:
    if not settings.psa_population_enabled:
        return None

    catalog_rows: list[dict[str, Any]] = []
    if settings.psa_population_import_path:
        try:
            catalog_rows.extend(load_import_file(settings.psa_population_import_path))
        except Exception as error:
            print(f"PSA population import load failed: {error}")

    beta_seed_path = settings.psa_population_beta_seed_path
    if beta_seed_path and beta_seed_path.exists():
        try:
            catalog_rows.extend(load_import_file(beta_seed_path))
        except Exception as error:
            print(f"PSA beta seed load failed: {error}")

    catalog_provider = ImportPopulationProvider(catalog_rows)

    if settings.psa_population_provider == "import":
        return catalog_provider

    psa_client = PSAClient(
        access_token=settings.psa_access_token,
        base_url=settings.psa_api_base_url,
    )
    return PSAPopulationProvider(psa_client=psa_client, catalog_provider=catalog_provider)


def _write_local_snapshots(snapshots: list[dict[str, Any]], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    file_path = output_dir / f"card_population_snapshots_{stamp}.json"
    file_path.write_text(json.dumps(snapshots, indent=2), encoding="utf-8")

    latest_path = output_dir / "latest_card_population_snapshots.json"
    latest_path.write_text(json.dumps(snapshots, indent=2), encoding="utf-8")
    append_local_population_history(snapshots, output_dir)
    return file_path


def run_population_snapshots(
    *,
    settings: Settings | None = None,
    storage: SupabaseStorage | None = None,
    provider: PopulationProvider | None = None,
    persist: bool = True,
) -> PopulationSnapshotResult:
    settings = settings or get_settings()
    if provider is None:
        provider = build_population_provider(settings)

    if provider is None or not provider.is_available():
        return PopulationSnapshotResult()

    mlb_client = MLBClient()
    from cardchase_ai.pipeline import _build_market_universe

    candidates = _build_market_universe(mlb_client, settings)
    players = [enrich_player_entry(candidate) for candidate in candidates[: settings.psa_population_card_limit]]

    snapshots: list[dict[str, Any]] = []
    matches: list[dict[str, Any]] = []
    error_count = 0
    card_count = 0

    for player in players:
        try:
            cards = get_enriched_player_cards(player, limit=settings.card_market_cards_per_player_limit)
        except Exception as error:
            error_count += 1
            print(f"Population registry lookup failed for {player.get('player_name')}: {error}")
            continue

        for card in cards:
            card_count += 1
            try:
                match_candidates = provider.search_card_matches(card)
                if not match_candidates:
                    continue

                primary = next((item for item in match_candidates if item.match_status == "MATCHED"), match_candidates[0])
                if primary.match_status in {"UNMATCHED", "AMBIGUOUS"}:
                    matches.append(primary.model_dump(mode="json"))
                    continue

                raw = provider.fetch_population(primary)
                if raw is None:
                    matches.append(primary.model_dump(mode="json"))
                    continue

                from cardchase_ai.models.population import CardPopulationSnapshot

                snapshot_payload = provider.normalize_population(raw, card_match=primary, card_identity=card)
                snapshot_model = CardPopulationSnapshot.model_validate(snapshot_payload)
                scarcity_model = calculate_card_scarcity_metrics(snapshot_model)
                snapshot_payload = snapshot_model.model_dump(mode="json")
                snapshot_payload["scarcity"] = scarcity_model.model_dump(mode="json")

                snapshots.append(snapshot_payload)
                matches.append(primary.model_dump(mode="json"))
            except Exception as error:
                error_count += 1
                print(f"Population snapshot failed for {card.get('cs_card_id')}: {error}")

    output_path: str | None = None
    if persist and snapshots:
        try:
            file_path = _write_local_snapshots(snapshots, settings.output_dir)
            output_path = str(file_path)
        except Exception as error:
            error_count += 1
            print(f"Local population snapshot write failed: {error}")

        if matches:
            try:
                save_local_psa_matches(matches, settings.output_dir)
            except Exception as error:
                error_count += 1
                print(f"Local PSA match write failed: {error}")

        if storage is None and settings.supabase_url and settings.supabase_service_role_key:
            storage = SupabaseStorage(settings.supabase_url, settings.supabase_service_role_key)

        if storage is not None:
            try:
                if matches:
                    storage.upsert_psa_card_matches(matches)
                if snapshots:
                    storage.insert_card_population_snapshots(snapshots)
            except Exception as error:
                error_count += 1
                print(f"Supabase population persistence failed: {error}")

    return PopulationSnapshotResult(
        snapshot_count=len(snapshots),
        match_count=len(matches),
        player_count=len(players),
        card_count=card_count,
        error_count=error_count,
        output_path=output_path,
        snapshots=snapshots,
    )
