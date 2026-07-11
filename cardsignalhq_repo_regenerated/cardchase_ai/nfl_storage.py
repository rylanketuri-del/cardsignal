"""NFL performance snapshot storage with JSON fallback."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cardchase_ai.config import Settings, get_settings
from cardchase_ai.identity import cs_nfl_player_id, normalize_api_player_id, parse_cs_player_id
from cardchase_ai.models.nfl import (
    NFLPerformanceSnapshot,
    NFLPlayerIdentity,
    NFLSignalDriver,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class NFLStorage:
    """Append-only NFL intelligence storage."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.snapshots_dir = output_dir / "nfl" / "snapshots"
        self.players_file = output_dir / "nfl" / "registry" / "players.json"
        self.leaderboard_file = output_dir / "nfl" / "latest_leaderboard.json"
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self.players_file.parent.mkdir(parents=True, exist_ok=True)

    def is_data_available(self) -> bool:
        from cardchase_ai.clients.nfl_import import get_nfl_provider
        return get_nfl_provider().is_available()

    def append_snapshot(self, snapshot: NFLPerformanceSnapshot) -> None:
        path = self.snapshots_dir / f"{snapshot.cs_player_id.replace('/', '_')}.jsonl"
        line = snapshot.model_dump(mode="json")
        line["captured_at"] = (snapshot.captured_at or _utcnow()).isoformat()
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(line) + "\n")

    def fetch_latest_snapshots(self, cs_player_id: str) -> list[NFLPerformanceSnapshot]:
        path = self.snapshots_dir / f"{cs_player_id.replace('/', '_')}.jsonl"
        if not path.exists():
            return []
        snapshots: list[NFLPerformanceSnapshot] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            snapshots.append(NFLPerformanceSnapshot.model_validate(json.loads(line)))
        return snapshots

    def fetch_latest_snapshot_by_period(
        self,
        cs_player_id: str,
        period_type: str,
    ) -> NFLPerformanceSnapshot | None:
        matches = [s for s in self.fetch_latest_snapshots(cs_player_id) if s.period_type == period_type]
        if not matches:
            return None
        return matches[-1]

    def save_player_registry(self, players: list[NFLPlayerIdentity]) -> None:
        payload = [p.model_dump(mode="json") for p in players]
        self.players_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def load_player_registry(self) -> list[NFLPlayerIdentity]:
        if not self.players_file.exists():
            return []
        data = json.loads(self.players_file.read_text(encoding="utf-8"))
        return [NFLPlayerIdentity.model_validate(p) for p in data]

    def find_player(self, player_id: str) -> NFLPlayerIdentity | None:
        cs_id = normalize_api_player_id(player_id, "NFL")
        for player in self.load_player_registry():
            if player.cs_player_id == cs_id:
                return player
        league, source_id = parse_cs_player_id(cs_id)
        if league == "NFL":
            from cardchase_ai.clients.nfl_import import get_nfl_provider
            profile = get_nfl_provider().fetch_player_profile(source_id)
            return profile
        return None

    def save_leaderboard(self, entries: list[dict[str, Any]]) -> None:
        payload = {
            "generated_at": _utcnow().isoformat(),
            "league": "NFL",
            "sport": "FOOTBALL",
            "items": entries,
        }
        self.leaderboard_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def fetch_leaderboard(self) -> list[dict[str, Any]]:
        if not self.leaderboard_file.exists():
            return []
        data = json.loads(self.leaderboard_file.read_text(encoding="utf-8"))
        return data.get("items") or []

    def save_signal_drivers(self, cs_player_id: str, drivers: list[NFLSignalDriver]) -> None:
        path = self.output_dir / "nfl" / "signal_drivers" / f"{cs_player_id.replace('/', '_')}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "cs_player_id": cs_player_id,
            "captured_at": _utcnow().isoformat(),
            "drivers": [d.model_dump(mode="json") for d in drivers],
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def fetch_signal_drivers(self, cs_player_id: str) -> list[NFLSignalDriver]:
        path = self.output_dir / "nfl" / "signal_drivers" / f"{cs_player_id.replace('/', '_')}.json"
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        return [NFLSignalDriver.model_validate(d) for d in data.get("drivers") or []]


def build_nfl_storage(settings: Settings | None = None) -> NFLStorage:
    settings = settings or get_settings()
    return NFLStorage(settings.output_dir)
