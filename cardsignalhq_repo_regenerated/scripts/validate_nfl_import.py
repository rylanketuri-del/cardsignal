#!/usr/bin/env python3
"""Validate an NFL provider import JSON file without modifying data.

Usage:
  python scripts/validate_nfl_import.py output/nfl/import/nfl_data.json
  python scripts/validate_nfl_import.py path/to/file.json --allow-synthetic --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cardchase_ai.nfl_data_validation import validate_nfl_data_file


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate NFL provider import file (nfl_data.json). Read-only."
    )
    parser.add_argument("path", help="Path to nfl_data.json")
    parser.add_argument(
        "--allow-synthetic",
        action="store_true",
        help="Allow TEST-/Demo markers (local unit fixtures only; never for production)",
    )
    parser.add_argument(
        "--require-games",
        action="store_true",
        help="Fail when games map is empty",
    )
    parser.add_argument(
        "--require-season-stats",
        action="store_true",
        help="Fail when season_stats map is empty",
    )
    parser.add_argument(
        "--expected-season",
        type=int,
        default=None,
        help="Optional season that top-level / game rows should match",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON report")
    args = parser.parse_args()

    report = validate_nfl_data_file(
        args.path,
        allow_synthetic=args.allow_synthetic,
        require_games=args.require_games,
        require_season_stats=args.require_season_stats,
        expected_season=args.expected_season,
    )
    payload = report.to_dict()

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        status = "VALID" if report.valid else "INVALID"
        safe = "SAFE_TO_IMPORT" if report.safe_to_import else "NOT_SAFE_TO_IMPORT"
        print(f"{status} / {safe}")
        print(f"players: {report.player_count} (active non-retired: {report.active_player_count})")
        print(f"source_method: {report.source_method}")
        print(f"season: {report.season}")
        print(f"games keys: {report.games_player_keys}")
        print(f"season_stats keys: {report.season_stats_player_keys}")
        if report.duplicate_player_ids:
            print(f"duplicate_player_ids: {sorted(set(report.duplicate_player_ids))}")
        if report.synthetic_markers:
            print(f"synthetic_markers: {sorted(set(report.synthetic_markers))}")
        for err in report.errors:
            print(f"ERROR: {err}")
        for warn in report.warnings:
            print(f"WARN: {warn}")

    return 0 if report.safe_to_import else 2


if __name__ == "__main__":
    raise SystemExit(main())
