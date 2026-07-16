#!/usr/bin/env python3
"""Validate NFL import payloads without modifying data.

Supports:
  1) Provider file objects (output/nfl/import/nfl_data.json)
  2) Previous-season record arrays (verified_nfl_previous_season_YYYY.json)

Usage:
  python3 scripts/validate_nfl_import.py output/nfl/import/nfl_data.json
  python3 scripts/validate_nfl_import.py output/nfl/import/verified_nfl_previous_season_2025.json --expected-season 2025
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cardchase_ai.nfl_data_validation import (
    looks_like_previous_season_records,
    looks_like_provider_file,
    validate_nfl_data_file,
    validate_nfl_data_payload,
)
from cardchase_ai.previous_season_validation import validate_previous_season_records


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate NFL import JSON (provider file or previous-season array).")
    parser.add_argument("path", help="Path to import JSON")
    parser.add_argument(
        "--mode",
        choices=["auto", "provider-file", "previous-season"],
        default="auto",
    )
    parser.add_argument("--allow-synthetic", action="store_true")
    parser.add_argument("--require-games", action="store_true")
    parser.add_argument("--require-season-stats", action="store_true")
    parser.add_argument("--expected-season", type=int, default=None)
    parser.add_argument("--league", default="NFL")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    path = Path(args.path)
    if not path.exists():
        print(json.dumps({"valid": False, "safe_to_import": False, "errors": [f"File not found: {path}"]}))
        return 2

    raw = json.loads(path.read_text(encoding="utf-8"))
    mode = args.mode
    if mode == "auto":
        if looks_like_provider_file(raw):
            mode = "provider-file"
        elif looks_like_previous_season_records(raw):
            mode = "previous-season"
        else:
            print("Unable to detect import mode", file=sys.stderr)
            return 2

    if mode == "provider-file":
        if path.suffix:
            report = validate_nfl_data_file(
                path,
                allow_synthetic=args.allow_synthetic,
                require_games=args.require_games,
                require_season_stats=args.require_season_stats,
                expected_season=args.expected_season,
            )
            payload = report.to_dict()
        else:
            payload = validate_nfl_data_payload(
                raw,
                allow_synthetic=args.allow_synthetic,
                require_games=args.require_games,
                require_season_stats=args.require_season_stats,
                expected_season=args.expected_season,
            ).to_dict()
        safe = payload["safe_to_import"]
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(("VALID" if payload["valid"] else "INVALID") + " / " + ("SAFE_TO_IMPORT" if safe else "NOT_SAFE_TO_IMPORT"))
            print(f"mode=provider-file players={payload.get('player_count')}")
            for err in payload.get("errors") or []:
                print(f"ERROR: {err}")
        return 0 if safe else 2

    season = args.expected_season
    if season is None:
        print("--expected-season is required for previous-season validation", file=sys.stderr)
        return 2
    report = validate_previous_season_records(
        raw,
        league=args.league,
        season=season,
        allow_synthetic=args.allow_synthetic,
    )
    payload = report.to_dict()
    payload["mode"] = "previous-season"
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(("VALID" if report.valid else "INVALID") + " / " + ("SAFE_TO_IMPORT" if report.safe_to_import else "NOT_SAFE_TO_IMPORT"))
        print(f"mode=previous-season total={report.total_rows} valid={report.valid_rows} rejected={report.rejected_rows}")
        print(f"duplicate_ids={report.duplicate_ids}")
        print(f"missing_teams={report.missing_teams} missing_positions={report.missing_positions}")
        print(f"invalid_percentages={report.invalid_percentages}")
        for err in report.errors[:20]:
            print(f"ERROR: {err}")
        for warn in report.warnings:
            print(f"WARN: {warn}")
    return 0 if report.safe_to_import else 2


if __name__ == "__main__":
    raise SystemExit(main())
