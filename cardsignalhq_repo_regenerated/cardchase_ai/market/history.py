"""Historical card-market snapshot loading from Supabase and local fallback files."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any

from cardchase_ai.market.movement import normalize_snapshot_row, parse_captured_at, sort_snapshots_asc
from cardchase_ai.market.player_market import format_public_market_snapshot


HISTORY_FILENAME = "card_market_snapshot_history.json"


def snapshot_identity_key(snapshot: dict[str, Any]) -> tuple[str, str]:
    captured = snapshot.get("captured_at")
    if isinstance(captured, datetime):
        captured_value = captured.isoformat()
    else:
        captured_value = str(captured or "")
    return (str(snapshot.get("cs_card_id") or ""), captured_value)


def merge_snapshot_collections(*collections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for collection in collections:
        for snapshot in collection:
            if not isinstance(snapshot, dict):
                continue
            key = snapshot_identity_key(snapshot)
            if not key[0]:
                continue
            merged[key] = snapshot
    rows: list[dict[str, Any]] = []
    for snapshot in merged.values():
        try:
            rows.append(normalize_snapshot_row(snapshot))
        except ValueError:
            continue
    return sorted(rows, key=lambda row: row["captured_at"])


def load_local_card_market_history(output_dir: Path) -> list[dict[str, Any]]:
    collections: list[list[dict[str, Any]]] = []

    history_path = output_dir / HISTORY_FILENAME
    if history_path.exists():
        collections.append(json.loads(history_path.read_text(encoding="utf-8")))

    latest_path = output_dir / "latest_card_market_snapshots.json"
    if latest_path.exists():
        collections.append(json.loads(latest_path.read_text(encoding="utf-8")))

    for path in sorted(output_dir.glob("card_market_snapshots_*.json")):
        collections.append(json.loads(path.read_text(encoding="utf-8")))

    return merge_snapshot_collections(*collections)


def append_local_card_market_history(snapshots: list[dict[str, Any]], output_dir: Path) -> Path:
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


def filter_card_history(all_snapshots: list[dict[str, Any]], cs_card_id: str, *, limit: int = 12) -> list[dict[str, Any]]:
    rows = [row for row in all_snapshots if row.get("cs_card_id") == cs_card_id]
    rows = sort_snapshots_asc(rows)
    if limit > 0:
        rows = rows[-limit:]
    return rows


def filter_player_history(all_snapshots: list[dict[str, Any]], cs_player_id: str) -> list[dict[str, Any]]:
    return sort_snapshots_asc([row for row in all_snapshots if row.get("cs_player_id") == cs_player_id])


def history_to_public_snapshots(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    public_rows: list[dict[str, Any]] = []
    for row in rows:
        captured = row["captured_at"]
        payload = {
            "cs_card_id": row["cs_card_id"],
            "cs_player_id": row["cs_player_id"],
            "league": row.get("league", "MLB"),
            "source": row.get("source", "ebay"),
            "captured_at": captured.isoformat() if isinstance(captured, datetime) else captured,
            "algorithm_version": row.get("algorithm_version", ""),
        }
        public = format_public_market_snapshot({**payload, **row})
        if public:
            public_rows.append({**payload, **public})
    return public_rows


def build_player_market_activity_points(
    player_snapshots: list[dict[str, Any]],
    *,
    limit: int = 12,
) -> list[dict[str, Any]]:
    """Aggregate snapshot history across a player's tracked cards by capture day."""
    if not player_snapshots:
        return []

    by_day: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in player_snapshots:
        captured = row.get("captured_at")
        moment = captured if isinstance(captured, datetime) else parse_captured_at(captured)
        if moment is None:
            continue
        day_key = moment.date().isoformat()
        by_day[day_key][row["cs_card_id"]].append(row)

    points: list[dict[str, Any]] = []
    for day_key in sorted(by_day.keys()):
        card_groups = by_day[day_key]
        day_rows: list[dict[str, Any]] = []
        for card_rows in card_groups.values():
            day_rows.append(max(card_rows, key=lambda row: row["captured_at"]))

        medians = [float(row["median_price"]) for row in day_rows if row.get("median_price") is not None]
        if not medians:
            continue

        points.append(
            {
                "captured_at": f"{day_key}T12:00:00+00:00",
                "median_active_price": round(float(median(medians)), 2),
                "active_listing_count": sum(int(row.get("active_listing_count") or 0) for row in day_rows),
                "total_bid_count": sum(int(row.get("total_bid_count") or 0) for row in day_rows),
                "cards_observed": len(day_rows),
            }
        )

    if limit > 0:
        points = points[-limit:]
    return points
