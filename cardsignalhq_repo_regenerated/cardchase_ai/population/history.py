"""Append-only population snapshot local history — Sprint 8.6."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from cardchase_ai.market.movement import parse_captured_at

HISTORY_FILENAME = "card_population_snapshot_history.json"
MATCHES_FILENAME = "psa_card_matches.json"


def snapshot_identity_key(snapshot: dict[str, Any]) -> tuple[str, str, str]:
    captured = snapshot.get("captured_at")
    if isinstance(captured, datetime):
        captured_value = captured.isoformat()
    else:
        captured_value = str(captured or "")
    return (
        str(snapshot.get("cs_card_id") or ""),
        str(snapshot.get("provider") or "PSA"),
        captured_value,
    )


def merge_snapshot_collections(*collections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str, str], dict[str, Any]] = {}
    for collection in collections:
        for snapshot in collection:
            if not isinstance(snapshot, dict):
                continue
            key = snapshot_identity_key(snapshot)
            if not key[0]:
                continue
            merged[key] = snapshot
    rows = list(merged.values())
    rows.sort(key=lambda row: parse_captured_at(row.get("captured_at")) or datetime.min.replace(tzinfo=None))
    return rows


def load_local_population_history(output_dir: Path) -> list[dict[str, Any]]:
    collections: list[list[dict[str, Any]]] = []
    history_path = output_dir / HISTORY_FILENAME
    if history_path.exists():
        collections.append(json.loads(history_path.read_text(encoding="utf-8")))

    latest_path = output_dir / "latest_card_population_snapshots.json"
    if latest_path.exists():
        collections.append(json.loads(latest_path.read_text(encoding="utf-8")))

    for path in sorted(output_dir.glob("card_population_snapshots_*.json")):
        collections.append(json.loads(path.read_text(encoding="utf-8")))

    return merge_snapshot_collections(*collections)


def append_local_population_history(snapshots: list[dict[str, Any]], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    history_path = output_dir / HISTORY_FILENAME
    existing: list[dict[str, Any]] = []
    if history_path.exists():
        existing = json.loads(history_path.read_text(encoding="utf-8"))

    merged = merge_snapshot_collections(existing, snapshots)
    serializable = []
    for row in merged:
        item = dict(row)
        captured = item.get("captured_at")
        if isinstance(captured, datetime):
            item["captured_at"] = captured.isoformat()
        serializable.append(item)

    history_path.write_text(json.dumps(serializable, indent=2), encoding="utf-8")
    return history_path


def filter_card_population_history(all_snapshots: list[dict[str, Any]], cs_card_id: str, *, limit: int = 12) -> list[dict[str, Any]]:
    rows = [row for row in all_snapshots if row.get("cs_card_id") == cs_card_id]
    if limit > 0:
        rows = rows[-limit:]
    return rows


def load_local_psa_matches(output_dir: Path) -> list[dict[str, Any]]:
    path = output_dir / MATCHES_FILENAME
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save_local_psa_matches(matches: list[dict[str, Any]], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / MATCHES_FILENAME
    path.write_text(json.dumps(matches, indent=2), encoding="utf-8")
    return path
