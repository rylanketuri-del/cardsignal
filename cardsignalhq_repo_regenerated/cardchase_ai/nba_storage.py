"""NBA performance snapshot storage with JSON fallback."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cardchase_ai.config import Settings, get_settings
from cardchase_ai.identity import cs_nba_player_id, normalize_api_player_id, parse_cs_player_id
from cardchase_ai.models.nba import (
    NBAPerformanceSnapshot,
    NBAPlayerIdentity,
    NBASignalDriver,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class NBAStorage:
    """Append-only NBA intelligence storage."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.snapshots_dir = output_dir / "nba" / "snapshots"
        self.players_file = output_dir / "nba" / "registry" / "players.json"
        self.leaderboard_file = output_dir / "nba" / "latest_leaderboard.json"
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self.players_file.parent.mkdir(parents=True, exist_ok=True)

    def is_data_available(self) -> bool:
        from cardchase_ai.clients.nba_import import get_nba_provider
        return get_nba_provider().is_available()

    def append_snapshot(self, snapshot: NBAPerformanceSnapshot) -> None:
        path = self.snapshots_dir / f"{snapshot.cs_player_id.replace('/', '_')}.jsonl"
        line = snapshot.model_dump(mode="json")
        line["captured_at"] = (snapshot.captured_at or _utcnow()).isoformat()
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(line) + "\n")

    def fetch_latest_snapshots(self, cs_player_id: str) -> list[NBAPerformanceSnapshot]:
        path = self.snapshots_dir / f"{cs_player_id.replace('/', '_')}.jsonl"
        if not path.exists():
            return []
        snapshots: list[NBAPerformanceSnapshot] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            snapshots.append(NBAPerformanceSnapshot.model_validate(json.loads(line)))
        return snapshots

    def fetch_latest_snapshot_by_period(
        self,
        cs_player_id: str,
        period_type: str,
    ) -> NBAPerformanceSnapshot | None:
        matches = [s for s in self.fetch_latest_snapshots(cs_player_id) if s.period_type == period_type]
        if not matches:
            return None
        return matches[-1]

    def save_player_registry(self, players: list[NBAPlayerIdentity]) -> None:
        payload = [p.model_dump(mode="json") for p in players]
        self.players_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def load_player_registry(self) -> list[NBAPlayerIdentity]:
        if not self.players_file.exists():
            return []
        data = json.loads(self.players_file.read_text(encoding="utf-8"))
        return [NBAPlayerIdentity.model_validate(p) for p in data]

    def find_player(self, player_id: str) -> NBAPlayerIdentity | None:
        cs_id = normalize_api_player_id(player_id, "NBA")
        for player in self.load_player_registry():
            if player.cs_player_id == cs_id:
                return player
        league, source_id = parse_cs_player_id(cs_id)
        if league == "NBA":
            from cardchase_ai.clients.nba_import import get_nba_provider
            profile = get_nba_provider().fetch_player_profile(source_id)
            return profile
        return None

    def save_leaderboard(self, entries: list[dict[str, Any]]) -> None:
        payload = {
            "generated_at": _utcnow().isoformat(),
            "league": "NBA",
            "sport": "BASKETBALL",
            "items": entries,
        }
        self.leaderboard_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def fetch_leaderboard(self) -> list[dict[str, Any]]:
        if not self.leaderboard_file.exists():
            return []
        data = json.loads(self.leaderboard_file.read_text(encoding="utf-8"))
        return data.get("items") or []

    def save_signal_drivers(self, cs_player_id: str, drivers: list[NBASignalDriver]) -> None:
        path = self.output_dir / "nba" / "signal_drivers" / f"{cs_player_id.replace('/', '_')}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "cs_player_id": cs_player_id,
            "captured_at": _utcnow().isoformat(),
            "drivers": [d.model_dump(mode="json") for d in drivers],
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def fetch_signal_drivers(self, cs_player_id: str) -> list[NBASignalDriver]:
        path = self.output_dir / "nba" / "signal_drivers" / f"{cs_player_id.replace('/', '_')}.json"
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        return [NBASignalDriver.model_validate(d) for d in data.get("drivers") or []]


def build_nba_storage(settings: Settings | None = None) -> NBAStorage:
    settings = settings or get_settings()
    return NBAStorage(settings.output_dir)
