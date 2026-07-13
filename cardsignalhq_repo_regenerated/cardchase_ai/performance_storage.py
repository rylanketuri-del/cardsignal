"""Durable previous-season performance storage (Supabase primary, JSON fallback)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cardchase_ai.config import Settings, get_settings
from cardchase_ai.models.performance import PreviousSeasonPerformanceSnapshot
from cardchase_ai.storage import SupabaseError, SupabaseStorage


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PerformanceJsonStorage:
    """Append-only / versioned JSON storage for performance snapshots."""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir / "performance"
        self.snapshots_dir = self.base_dir / "snapshots"
        self.index_path = self.base_dir / "index.json"
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        if not self.index_path.exists():
            self._save_index({})

    def _load_index(self) -> dict[str, str]:
        if not self.index_path.exists():
            return {}
        return json.loads(self.index_path.read_text(encoding="utf-8"))

    def _save_index(self, index: dict[str, str]) -> None:
        self.index_path.write_text(json.dumps(index, indent=2, sort_keys=True), encoding="utf-8")

    def _snapshot_path(self, key: str) -> Path:
        safe = key.replace("/", "_").replace(":", "__")
        return self.snapshots_dir / f"{safe}.json"

    def upsert_snapshot(self, snapshot: PreviousSeasonPerformanceSnapshot) -> str:
        key = snapshot.snapshot_key()
        path = self._snapshot_path(key)
        payload = snapshot.model_dump(mode="json")
        if not payload.get("captured_at"):
            payload["captured_at"] = _utcnow().isoformat()
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        index = self._load_index()
        index[key] = path.name
        self._save_index(index)
        return key

    def get_snapshot(self, league: str, cs_player_id: str, season: int) -> PreviousSeasonPerformanceSnapshot | None:
        key = f"{league.upper()}:{cs_player_id}:{season}:PREVIOUS_SEASON"
        index = self._load_index()
        filename = index.get(key)
        if not filename:
            return None
        path = self.snapshots_dir / filename
        if not path.exists():
            return None
        return PreviousSeasonPerformanceSnapshot.model_validate(json.loads(path.read_text(encoding="utf-8")))

    def list_league_snapshots(self, league: str) -> list[PreviousSeasonPerformanceSnapshot]:
        league_upper = league.upper()
        prefix = f"{league_upper}:"
        results: list[PreviousSeasonPerformanceSnapshot] = []
        index = self._load_index()
        for key, filename in index.items():
            if not key.startswith(prefix):
                continue
            path = self.snapshots_dir / filename
            if not path.exists():
                continue
            results.append(PreviousSeasonPerformanceSnapshot.model_validate(json.loads(path.read_text(encoding="utf-8"))))
        return results

    def latest_captured_at(self, league: str) -> str | None:
        snaps = self.list_league_snapshots(league)
        if not snaps:
            return None
        timestamps = [s.captured_at.isoformat() if s.captured_at else "" for s in snaps]
        return max(timestamps) if timestamps else None


class PerformanceStorage:
    """Unified performance storage with Supabase primary and JSON fallback."""

    TABLE = "performance_snapshots"

    def __init__(self, supabase: SupabaseStorage | None, json_storage: PerformanceJsonStorage) -> None:
        self.supabase = supabase
        self.json = json_storage

    @property
    def uses_supabase(self) -> bool:
        return self.supabase is not None

    @property
    def is_durable(self) -> bool:
        return self.uses_supabase

    def upsert_snapshot(self, snapshot: PreviousSeasonPerformanceSnapshot) -> str:
        if self.supabase:
            try:
                row = self._snapshot_to_row(snapshot)
                existing = self.supabase._get(
                    self.TABLE,
                    {
                        "select": "id",
                        "cs_player_id": f"eq.{snapshot.cs_player_id}",
                        "league": f"eq.{snapshot.league.upper()}",
                        "season": f"eq.{snapshot.season}",
                        "period_type": "eq.PREVIOUS_SEASON",
                        "limit": "1",
                    },
                )
                if existing:
                    self.supabase._patch(
                        self.TABLE,
                        {"id": f"eq.{existing[0]['id']}"},
                        row,
                    )
                else:
                    self.supabase._post(self.TABLE, row)
                return snapshot.snapshot_key()
            except SupabaseError:
                pass
        return self.json.upsert_snapshot(snapshot)

    def get_previous_season(
        self,
        league: str,
        cs_player_id: str,
        season: int | None = None,
    ) -> PreviousSeasonPerformanceSnapshot | None:
        league_upper = league.upper()
        if self.supabase:
            try:
                params: dict[str, str] = {
                    "select": "*",
                    "cs_player_id": f"eq.{cs_player_id}",
                    "league": f"eq.{league_upper}",
                    "period_type": "eq.PREVIOUS_SEASON",
                    "order": "season.desc",
                    "limit": "1",
                }
                if season is not None:
                    params["season"] = f"eq.{season}"
                rows = self.supabase._get(self.TABLE, params)
                if rows:
                    return self._row_to_snapshot(rows[0])
            except SupabaseError:
                pass
        if season is not None:
            return self.json.get_snapshot(league_upper, cs_player_id, season)
        snaps = [
            s for s in self.json.list_league_snapshots(league_upper)
            if s.cs_player_id == cs_player_id
        ]
        if not snaps:
            return None
        return sorted(snaps, key=lambda s: s.season, reverse=True)[0]

    def list_league_snapshots(self, league: str) -> list[PreviousSeasonPerformanceSnapshot]:
        league_upper = league.upper()
        if self.supabase:
            try:
                rows = self.supabase._get(
                    self.TABLE,
                    {
                        "select": "*",
                        "league": f"eq.{league_upper}",
                        "period_type": "eq.PREVIOUS_SEASON",
                        "order": "captured_at.desc",
                    },
                )
                return [self._row_to_snapshot(row) for row in rows]
            except SupabaseError:
                pass
        return self.json.list_league_snapshots(league_upper)

    def league_summary(self, league: str) -> dict[str, Any]:
        snaps = self.list_league_snapshots(league)
        latest = None
        if snaps:
            captured = [s.captured_at for s in snaps if s.captured_at]
            if captured:
                latest = max(captured).isoformat()
        return {
            "league": league.upper(),
            "snapshot_count": len(snaps),
            "latest_captured_at": latest,
            "has_data": len(snaps) > 0,
        }

    @staticmethod
    def _snapshot_to_row(snapshot: PreviousSeasonPerformanceSnapshot) -> dict[str, Any]:
        captured = snapshot.captured_at or _utcnow()
        return {
            "cs_player_id": snapshot.cs_player_id,
            "source_player_id": snapshot.source_player_id,
            "league": snapshot.league.upper(),
            "sport": snapshot.sport,
            "season": snapshot.season,
            "season_label": snapshot.season_label,
            "position": snapshot.position,
            "team": snapshot.team,
            "games_played": snapshot.games_played,
            "starts": snapshot.starts,
            "stats": snapshot.stats,
            "data_quality": snapshot.data_quality,
            "source_method": snapshot.source_method,
            "source_reference": snapshot.source_reference,
            "provider_updated_at": snapshot.provider_updated_at,
            "captured_at": captured.isoformat() if isinstance(captured, datetime) else captured,
            "algorithm_version": snapshot.algorithm_version,
            "period_type": snapshot.period_type,
            "player_name": snapshot.player_name,
            "headshot_url": snapshot.headshot_url,
            "team_logo_url": snapshot.team_logo_url,
        }

    @staticmethod
    def _row_to_snapshot(row: dict[str, Any]) -> PreviousSeasonPerformanceSnapshot:
        return PreviousSeasonPerformanceSnapshot(
            cs_player_id=row["cs_player_id"],
            source_player_id=row["source_player_id"],
            league=row["league"],
            sport=row["sport"],
            season=int(row["season"]),
            season_label=row.get("season_label"),
            position=row.get("position"),
            team=row.get("team"),
            games_played=int(row.get("games_played") or 0),
            starts=row.get("starts"),
            stats=row.get("stats") or {},
            data_quality=row.get("data_quality") or "INSUFFICIENT",
            source_method=row.get("source_method") or "APPROVED_IMPORT",
            source_reference=row.get("source_reference") or "",
            provider_updated_at=row.get("provider_updated_at"),
            captured_at=row.get("captured_at"),
            algorithm_version=row.get("algorithm_version") or "PREVIOUS_SEASON_V1",
            period_type="PREVIOUS_SEASON",
            player_name=row.get("player_name"),
            headshot_url=row.get("headshot_url"),
            team_logo_url=row.get("team_logo_url"),
        )


def build_performance_storage(settings: Settings | None = None) -> PerformanceStorage:
    settings = settings or get_settings()
    supabase = None
    if settings.supabase_url and settings.supabase_service_role_key:
        supabase = SupabaseStorage(settings.supabase_url, settings.supabase_service_role_key)
    json_store = PerformanceJsonStorage(settings.output_dir)
    return PerformanceStorage(supabase, json_store)
