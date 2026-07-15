#!/usr/bin/env python3
"""Build a verified NFL previous-season seed from nflverse regular-season stats.

Downloads nflverse stats_player_reg_{season}.csv (CC BY 4.0), applies deterministic
skill-position population rules, maps into CardSignal previous-season import rows,
validates each row, and writes:

  output/nfl/import/verified_nfl_previous_season_{season}.json
  output/nfl/import/verified_nfl_previous_season_{season}.manifest.json

Does not fabricate statistics. Derived rate metrics are computed only from source
counting stats. Incomplete rows are rejected.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cardchase_ai.models.nfl import map_nfl_position
from cardchase_ai.nfl_seed_rules import (
    INCLUDED_RAW_POSITIONS,
    NFLVERSE_ATTRIBUTION,
    NFLVERSE_DOWNLOAD_URL,
    NFLVERSE_LICENSE,
    NFLVERSE_LICENSE_URL,
    NFLVERSE_STATS_ASSET,
    NFLVERSE_STATS_RELEASE,
    SEED_SCRIPT_VERSION,
    TARGET_POPULATION_SIZE,
    activity_rank_key,
    meets_activity_threshold,
    num,
    selection_rules_dict,
)
from cardchase_ai.performance_import import validate_import_row
from cardchase_ai.previous_season_validation import validate_previous_season_records

SCRIPT_VERSION = SEED_SCRIPT_VERSION


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_stats_csv(season: int, cache_path: Path, *, force: bool = False) -> tuple[Path, str]:
    url = NFLVERSE_DOWNLOAD_URL.format(season=season)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if cache_path.exists() and not force:
        return cache_path, url
    request = urllib.request.Request(url, headers={"User-Agent": "CardSignalSeedBuilder/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response:
        data = response.read()
    cache_path.write_bytes(data)
    return cache_path, url


def nfl_passer_rating(completions: float, attempts: float, yards: float, tds: float, ints: float) -> float | None:
    """Official NFL passer rating from counting stats (not invented yardage)."""
    if attempts <= 0:
        return None

    def clamp(value: float) -> float:
        return max(0.0, min(2.375, value))

    a = clamp(((completions / attempts) - 0.3) * 5)
    b = clamp(((yards / attempts) - 3) * 0.25)
    c = clamp((tds / attempts) * 20)
    d = clamp(2.375 - ((ints / attempts) * 25))
    return round(((a + b + c + d) / 6.0) * 100.0, 1)


def map_row(raw: dict[str, Any], *, season: int, retrieved_at: str) -> tuple[dict[str, Any] | None, str | None]:
    player_id = str(raw.get("player_id") or "").strip()
    if not player_id:
        return None, "missing player_id"
    name = str(raw.get("player_display_name") or raw.get("player_name") or "").strip()
    if not name:
        return None, "missing player_name"
    position = str(raw.get("position") or "").strip().upper()
    if position not in INCLUDED_RAW_POSITIONS:
        return None, f"unsupported position {position}"
    team = str(raw.get("recent_team") or "").strip().upper()
    if not team:
        return None, "missing recent_team"

    try:
        row_season = int(float(raw.get("season")))
    except (TypeError, ValueError):
        return None, "invalid season"
    if row_season != season:
        return None, f"season mismatch {row_season}"

    games = int(num(raw.get("games")))
    if games <= 0:
        return None, "games_played <= 0"

    group = map_nfl_position(position)
    stats: dict[str, Any] = {"games_played": games}
    fumbles = num(raw.get("fumbles_total"))
    if fumbles < 0:
        return None, "negative fumbles_total"

    if group == "QB":
        attempts = num(raw.get("attempts"))
        completions = num(raw.get("completions"))
        passing_yards = num(raw.get("passing_yards"))
        passing_tds = num(raw.get("passing_tds"))
        interceptions = num(raw.get("passing_interceptions"))
        if attempts <= 0 and passing_yards <= 0:
            return None, "QB missing passing volume"
        stats.update({
            "passing_yards": passing_yards,
            "passing_touchdowns": passing_tds,
            "interceptions": interceptions,
            "rushing_yards": max(0.0, num(raw.get("rushing_yards"))),
            "rushing_touchdowns": num(raw.get("rushing_tds")),
            "fumbles": fumbles,
        })
        if attempts > 0:
            stats["completion_percentage"] = round(completions / attempts, 4)
            stats["yards_per_attempt"] = round(passing_yards / attempts, 3)
            rating = nfl_passer_rating(completions, attempts, passing_yards, passing_tds, interceptions)
            if rating is not None:
                stats["passer_rating"] = rating
    elif group == "RB":
        carries = num(raw.get("carries"))
        rushing_yards = num(raw.get("rushing_yards"))
        if rushing_yards < 0:
            return None, "negative rushing_yards"
        receiving_yards = num(raw.get("receiving_yards"))
        if receiving_yards < 0:
            return None, "negative receiving_yards"
        receptions = num(raw.get("receptions"))
        targets = num(raw.get("targets"))
        rush_tds = num(raw.get("rushing_tds"))
        rec_tds = num(raw.get("receiving_tds"))
        stats.update({
            "rushing_attempts": carries,
            "rushing_yards": rushing_yards,
            "rushing_touchdowns": rush_tds,
            "targets": targets,
            "receptions": receptions,
            "receiving_yards": receiving_yards,
            "receiving_touchdowns": rec_tds,
            "total_yards": rushing_yards + receiving_yards,
            "total_touchdowns": rush_tds + rec_tds,
            "fumbles": fumbles,
        })
        if carries > 0:
            stats["yards_per_carry"] = round(rushing_yards / carries, 3)
    elif group in {"WR", "TE"}:
        targets = num(raw.get("targets"))
        receptions = num(raw.get("receptions"))
        receiving_yards = num(raw.get("receiving_yards"))
        if receiving_yards < 0:
            return None, "negative receiving_yards"
        rush_yards = max(0.0, num(raw.get("rushing_yards")))
        rec_tds = num(raw.get("receiving_tds"))
        stats.update({
            "targets": targets,
            "receptions": receptions,
            "receiving_yards": receiving_yards,
            "receiving_touchdowns": rec_tds,
            "rushing_yards": rush_yards,
            "total_touchdowns": rec_tds + num(raw.get("rushing_tds")),
            "fumbles": fumbles,
        })
        if receptions > 0:
            stats["yards_per_reception"] = round(receiving_yards / receptions, 3)
        if targets > 0:
            stats["catch_rate"] = round(receptions / targets, 4)
    else:
        return None, f"unsupported mapped group {group}"

    # Omit unsupported/unavailable starts rather than inventing equals(games).
    record = {
        "source_player_id": player_id,
        "player_name": name,
        "position": position,
        "team": team,
        "season": season,
        "season_label": str(season),
        "games_played": games,
        "stats": stats,
        "source_method": "APPROVED_IMPORT",
        "source_reference": f"nflverse/{NFLVERSE_STATS_RELEASE}/{NFLVERSE_STATS_ASSET.format(season=season)}",
        "data_quality": "HIGH",
        "headshot_url": str(raw.get("headshot_url") or "") or None,
        "last_updated": retrieved_at,
        "provider_updated_at": retrieved_at,
    }
    # Drop null optionals for cleaner JSON
    if not record["headshot_url"]:
        record.pop("headshot_url")
    return record, None


def select_source_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rejections: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        position = str(row.get("position") or "").upper()
        if position not in INCLUDED_RAW_POSITIONS:
            continue
        player_id = str(row.get("player_id") or "").strip()
        if not player_id:
            rejections.append({"player_id": None, "reason": "missing player_id"})
            continue
        if not meets_activity_threshold(row):
            rejections.append({
                "player_id": player_id,
                "player_name": row.get("player_display_name"),
                "reason": "below activity or games threshold",
            })
            continue
        prior = by_id.get(player_id)
        if prior is None or activity_rank_key(row) < activity_rank_key(prior):
            if prior is not None:
                rejections.append({
                    "player_id": player_id,
                    "reason": "duplicate player_id replaced by higher-activity row",
                })
            by_id[player_id] = row

    ranked = sorted(by_id.values(), key=activity_rank_key)
    selected = ranked[:TARGET_POPULATION_SIZE]
    for row in ranked[TARGET_POPULATION_SIZE:]:
        rejections.append({
            "player_id": row.get("player_id"),
            "player_name": row.get("player_display_name"),
            "reason": f"outside top {TARGET_POPULATION_SIZE} activity ranking",
        })
    return selected, rejections


def build_seed(season: int, stats_csv: Path, *, retrieved_at: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    with stats_csv.open(newline="", encoding="utf-8") as handle:
        source_rows = list(csv.DictReader(handle))

    selected, selection_rejections = select_source_rows(source_rows)
    records: list[dict[str, Any]] = []
    map_rejections: list[dict[str, Any]] = []
    validation_rejections: list[dict[str, Any]] = []

    for raw in selected:
        mapped, reason = map_row(raw, season=season, retrieved_at=retrieved_at)
        if mapped is None:
            map_rejections.append({
                "player_id": raw.get("player_id"),
                "player_name": raw.get("player_display_name"),
                "reason": reason,
            })
            continue
        snap, err = validate_import_row(mapped, league="NFL", season=season, row_index=len(records))
        if err:
            validation_rejections.append(err.model_dump())
            continue
        assert snap is not None
        records.append(mapped)

    # Stable output order: activity ranking already applied; re-sort by player_id for idempotent JSON? 
    # Keep activity order for reviewability of leaderboard candidates.
    diagnostics = {
        "source_row_count": len(source_rows),
        "selected_before_map": len(selected),
        "mapped_valid": len(records),
        "selection_rejections": len(selection_rejections),
        "map_rejections": map_rejections,
        "validation_rejections": validation_rejections,
        "selection_rejection_sample": selection_rejections[:25],
    }
    return records, diagnostics


def score_preview(records: list[dict[str, Any]], limit: int = 20) -> list[dict[str, Any]]:
    from cardchase_ai.nfl_score import score_nfl_performance

    scored: list[dict[str, Any]] = []
    for row in records:
        group = map_nfl_position(row.get("position"))
        stats = dict(row.get("stats") or {})
        games = int(row.get("games_played") or stats.get("games_played") or 0)
        score, normalized, reasons, quality, missing = score_nfl_performance(
            group,
            stats,
            stats,
            games_in_window=games,
        )
        scored.append({
            "source_player_id": row["source_player_id"],
            "player_name": row["player_name"],
            "position": row["position"],
            "team": row["team"],
            "games_played": games,
            "performance_score": score,
            "data_quality": quality,
            "missing_inputs": missing,
            "normalized_metric_count": len(normalized),
            "reasons": reasons[:5],
            "season_label": f"{row['season']} Season Snapshot",
        })
    scored.sort(
        key=lambda item: (
            -(item["performance_score"] if item["performance_score"] is not None else -1),
            item["source_player_id"],
        )
    )
    return scored[:limit]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build verified NFL previous-season seed from nflverse")
    parser.add_argument("--season", type=int, default=2025)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "output" / "nfl" / "import",
        help="Directory for seed + manifest",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=ROOT / "output" / "nfl" / "cache",
        help="Download cache directory",
    )
    parser.add_argument("--stats-csv", type=Path, default=None, help="Use local CSV instead of downloading")
    parser.add_argument("--force-download", action="store_true")
    parser.add_argument("--score-preview", type=int, default=20, help="Print local top-N scoring preview")
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args()

    retrieved_at = _utcnow().isoformat()
    if args.stats_csv:
        stats_csv = args.stats_csv
        source_url = f"local:{stats_csv}"
    else:
        cache_path = args.cache_dir / NFLVERSE_STATS_ASSET.format(season=args.season)
        stats_csv, source_url = download_stats_csv(args.season, cache_path, force=args.force_download)

    records, diagnostics = build_seed(args.season, stats_csv, retrieved_at=retrieved_at)
    report = validate_previous_season_records(records, league="NFL", season=args.season, allow_synthetic=False)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    seed_path = args.output_dir / f"verified_nfl_previous_season_{args.season}.json"
    manifest_path = args.output_dir / f"verified_nfl_previous_season_{args.season}.manifest.json"

    seed_path.write_text(json.dumps(records, indent=2), encoding="utf-8")
    preview = score_preview(records, limit=args.score_preview)

    scores = [p["performance_score"] for p in preview if p["performance_score"] is not None]
    unique_scores = len(set(scores))

    manifest = {
        "provider": "nflverse",
        "license": NFLVERSE_LICENSE,
        "license_url": NFLVERSE_LICENSE_URL,
        "attribution": NFLVERSE_ATTRIBUTION,
        "dataset_names": [NFLVERSE_STATS_ASSET.format(season=args.season)],
        "source_release_identifiers": {
            "github_repo": "nflverse/nflverse-data",
            "release_tag": NFLVERSE_STATS_RELEASE,
            "asset": NFLVERSE_STATS_ASSET.format(season=args.season),
            "download_url": source_url,
            "source_file_sha256": _file_sha256(stats_csv),
        },
        "retrieval_timestamp": retrieved_at,
        "season": args.season,
        "season_type": "REG",
        "transformation_script": "scripts/build_nfl_previous_season_seed.py",
        "transformation_script_version": SCRIPT_VERSION,
        "source_method": "APPROVED_IMPORT",
        "selection_rules": selection_rules_dict(),
        "row_count": len(records),
        "rejected_row_count": (
            diagnostics["selection_rejections"]
            + len(diagnostics["map_rejections"])
            + len(diagnostics["validation_rejections"])
        ),
        "diagnostics": {
            "source_row_count": diagnostics["source_row_count"],
            "selected_before_map": diagnostics["selected_before_map"],
            "mapped_valid": diagnostics["mapped_valid"],
            "map_rejections": diagnostics["map_rejections"],
            "validation_rejections": diagnostics["validation_rejections"],
            "selection_rejection_sample": diagnostics["selection_rejection_sample"],
        },
        "validation_result": report.to_dict(),
        "output_seed_path": str(seed_path.relative_to(ROOT)) if seed_path.is_relative_to(ROOT) else str(seed_path),
        "score_preview_top": preview,
        "score_preview_unique_scores": unique_scores,
        "commercial_use_notes": (
            "CC BY 4.0 permits commercial use with attribution. CardSignal beta may use "
            "this adapted dataset when attribution is retained in the manifest and product docs."
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    summary = {
        "seed_path": str(seed_path),
        "manifest_path": str(manifest_path),
        "valid_players": len(records),
        "safe_to_import": report.safe_to_import,
        "unique_preview_scores": unique_scores,
        "top_preview": preview,
    }
    if args.json_summary:
        print(json.dumps(summary, indent=2))
    else:
        print(f"Wrote {seed_path} ({len(records)} players)")
        print(f"Wrote {manifest_path}")
        print(f"safe_to_import={report.safe_to_import} rejected_validation={report.rejected_rows}")
        print(f"Local score preview unique scores among top {args.score_preview}: {unique_scores}")
        for index, row in enumerate(preview, start=1):
            print(
                f"{index:2d}. {row['player_name']} ({row['position']}/{row['team']}) "
                f"score={row['performance_score']} quality={row['data_quality']}"
            )

    return 0 if report.safe_to_import and len(records) > 0 and unique_scores > 1 else 2


if __name__ == "__main__":
    raise SystemExit(main())
