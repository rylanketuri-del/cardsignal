"""Append-only Signal Driver persistence (Supabase + local JSON fallback)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cardchase_ai.models.signal_driver import LeagueSeasonMetadata, SignalDriver
from cardchase_ai.storage import SupabaseError, SupabaseStorage


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _serialize(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    return obj


class SignalDriverJsonStorage:
    """Local JSON storage for signal drivers and season metadata."""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir / "signal_drivers"
        self.drivers_dir = self.base_dir / "drivers"
        self.drivers_dir.mkdir(parents=True, exist_ok=True)
        self.developments_path = self.base_dir / "developments.json"
        self.metadata_path = self.base_dir / "league_season_metadata.json"

    def _player_path(self, cs_player_id: str) -> Path:
        safe_id = cs_player_id.replace(":", "_")
        return self.drivers_dir / f"{safe_id}.json"

    def _load_player_file(self, cs_player_id: str) -> list[dict[str, Any]]:
        path = self._player_path(cs_player_id)
        if not path.exists():
            return []
        return json.loads(path.read_text(encoding="utf-8"))

    def _save_player_file(self, cs_player_id: str, drivers: list[dict[str, Any]]) -> None:
        path = self._player_path(cs_player_id)
        path.write_text(json.dumps(drivers, indent=2, default=_serialize), encoding="utf-8")

    def fetch_drivers(
        self,
        cs_player_id: str,
        *,
        league: str | None = None,
        driver_type: str | None = None,
        limit: int = 100,
    ) -> list[SignalDriver]:
        rows = self._load_player_file(cs_player_id)
        drivers: list[SignalDriver] = []
        for row in rows:
            if league and row.get("league", "").upper() != league.upper():
                continue
            if driver_type and row.get("driver_type") != driver_type:
                continue
            drivers.append(SignalDriver.model_validate(row))
        drivers.sort(key=lambda d: d.occurred_at, reverse=True)
        return drivers[:limit]

    def append_drivers(self, drivers: list[SignalDriver]) -> list[SignalDriver]:
        if not drivers:
            return []

        by_player: dict[str, list[SignalDriver]] = {}
        for driver in drivers:
            by_player.setdefault(driver.cs_player_id, []).append(driver)

        appended: list[SignalDriver] = []
        for cs_id, new_drivers in by_player.items():
            existing_rows = self._load_player_file(cs_id)
            existing_keys = {row.get("identity_key") or _identity_from_row(row) for row in existing_rows}

            for driver in new_drivers:
                key = driver.identity_key()
                if key in existing_keys:
                    continue
                row = driver.model_dump(mode="json")
                row["identity_key"] = key
                existing_rows.append(row)
                existing_keys.add(key)
                appended.append(driver)

            if appended:
                self._save_player_file(cs_id, existing_rows)

        return appended

    def fetch_league_metadata(self, league: str, season: int) -> LeagueSeasonMetadata | None:
        if not self.metadata_path.exists():
            return None
        data = json.loads(self.metadata_path.read_text(encoding="utf-8"))
        for entry in data.get("leagues", []):
            if entry.get("league", "").upper() == league.upper() and entry.get("season") == season:
                return LeagueSeasonMetadata.model_validate(entry)
        return None

    def upsert_league_metadata(self, metadata: LeagueSeasonMetadata) -> None:
        data: dict[str, Any] = {"leagues": []}
        if self.metadata_path.exists():
            data = json.loads(self.metadata_path.read_text(encoding="utf-8"))

        leagues = data.setdefault("leagues", [])
        replaced = False
        for idx, entry in enumerate(leagues):
            if entry.get("league") == metadata.league and entry.get("season") == metadata.season:
                leagues[idx] = metadata.model_dump(mode="json")
                replaced = True
                break
        if not replaced:
            leagues.append(metadata.model_dump(mode="json"))

        self.metadata_path.write_text(json.dumps(data, indent=2, default=_serialize), encoding="utf-8")

    def fetch_developments(self, cs_player_id: str | None = None) -> list[dict[str, Any]]:
        if not self.developments_path.exists():
            return []
        rows = json.loads(self.developments_path.read_text(encoding="utf-8"))
        if cs_player_id:
            return [r for r in rows if r.get("cs_player_id") == cs_player_id]
        return rows

    def append_development(self, development: dict[str, Any]) -> dict[str, Any]:
        rows = self.fetch_developments()
        key = development.get("development_id") or development.get("source_reference", "")
        if any(r.get("development_id") == key or r.get("source_reference") == key for r in rows):
            return development
        rows.append(development)
        self.developments_path.parent.mkdir(parents=True, exist_ok=True)
        self.developments_path.write_text(json.dumps(rows, indent=2, default=_serialize), encoding="utf-8")
        return development


def _identity_from_row(row: dict[str, Any]) -> str:
    cs_id = row.get("cs_player_id", "")
    driver_type = row.get("driver_type", "")
    metric = row.get("metric_name") or ""
    occurred = str(row.get("occurred_at", ""))[:10]
    source_ref = row.get("source_reference", "")
    return f"{cs_id}:{driver_type}:{metric}:{occurred}:{source_ref}"


class SignalDriverStorage:
    """Supabase-first storage with JSON fallback."""

    TABLE = "signal_drivers"
    METADATA_TABLE = "league_season_metadata"
    DEVELOPMENTS_TABLE = "player_developments"

    def __init__(self, supabase: SupabaseStorage | None, json_storage: SignalDriverJsonStorage):
        self.supabase = supabase
        self.json = json_storage

    def fetch_drivers(
        self,
        cs_player_id: str,
        *,
        league: str | None = None,
        driver_type: str | None = None,
        limit: int = 100,
    ) -> list[SignalDriver]:
        if self.supabase:
            try:
                params: dict[str, str] = {
                    "cs_player_id": f"eq.{cs_player_id}",
                    "order": "occurred_at.desc",
                    "limit": str(limit),
                }
                if league:
                    params["league"] = f"eq.{league.upper()}"
                if driver_type:
                    params["driver_type"] = f"eq.{driver_type}"
                rows = self.supabase._get(self.TABLE, params=params)
                return [SignalDriver.model_validate(r) for r in rows]
            except SupabaseError:
                pass
        return self.json.fetch_drivers(cs_player_id, league=league, driver_type=driver_type, limit=limit)

    def append_drivers(self, drivers: list[SignalDriver]) -> list[SignalDriver]:
        if not drivers:
            return []

        existing_by_player: dict[str, set[str]] = {}
        to_insert: list[SignalDriver] = []

        for driver in drivers:
            if driver.cs_player_id not in existing_by_player:
                current = self.fetch_drivers(driver.cs_player_id, limit=500)
                existing_by_player[driver.cs_player_id] = {d.identity_key() for d in current}
            if driver.identity_key() in existing_by_player[driver.cs_player_id]:
                continue
            existing_by_player[driver.cs_player_id].add(driver.identity_key())
            to_insert.append(driver)

        if not to_insert:
            return []

        if self.supabase:
            try:
                payload = []
                for driver in to_insert:
                    row = driver.model_dump(mode="json")
                    row["identity_key"] = driver.identity_key()
                    payload.append(row)
                self.supabase._post(self.TABLE, payload)
                return to_insert
            except SupabaseError:
                pass

        return self.json.append_drivers(to_insert)

    def fetch_league_metadata(self, league: str, season: int) -> LeagueSeasonMetadata | None:
        if self.supabase:
            try:
                rows = self.supabase._get(
                    self.METADATA_TABLE,
                    params={"league": f"eq.{league.upper()}", "season": f"eq.{season}", "limit": "1"},
                )
                if rows:
                    return LeagueSeasonMetadata.model_validate(rows[0])
            except SupabaseError:
                pass
        return self.json.fetch_league_metadata(league, season)

    def upsert_league_metadata(self, metadata: LeagueSeasonMetadata) -> None:
        if self.supabase:
            try:
                self.supabase._post(
                    self.METADATA_TABLE,
                    [metadata.model_dump(mode="json")],
                    prefer="resolution=merge-duplicates",
                )
                return
            except SupabaseError:
                pass
        self.json.upsert_league_metadata(metadata)

    def fetch_developments(self, cs_player_id: str | None = None) -> list[dict[str, Any]]:
        if self.supabase:
            try:
                params: dict[str, str] = {"order": "occurred_at.desc", "limit": "100"}
                if cs_player_id:
                    params["cs_player_id"] = f"eq.{cs_player_id}"
                return self.supabase._get(self.DEVELOPMENTS_TABLE, params=params)
            except SupabaseError:
                pass
        return self.json.fetch_developments(cs_player_id)

    def append_development(self, development: dict[str, Any]) -> dict[str, Any]:
        if self.supabase:
            try:
                self.supabase._post(self.DEVELOPMENTS_TABLE, [development])
                return development
            except SupabaseError:
                pass
        return self.json.append_development(development)


def build_signal_driver_storage(settings) -> SignalDriverStorage:
    json_storage = SignalDriverJsonStorage(settings.output_dir)
    supabase = None
    if settings.supabase_url and settings.supabase_service_role_key:
        supabase = SupabaseStorage(settings.supabase_url, settings.supabase_service_role_key)
    return SignalDriverStorage(supabase, json_storage)
