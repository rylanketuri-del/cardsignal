#!/usr/bin/env python3
"""CLI for admin-verified previous-season performance imports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from cardchase_ai.config import get_settings
from cardchase_ai.performance_import import import_performance_records, parse_csv_records
from cardchase_ai.performance_storage import build_performance_storage


def main() -> int:
    parser = argparse.ArgumentParser(description="Import verified previous-season performance data")
    parser.add_argument("--league", required=True, choices=["NFL", "NBA"])
    parser.add_argument("--season", required=True, type=int)
    parser.add_argument("--source-method", default="APPROVED_IMPORT")
    parser.add_argument("--file", required=True, help="JSON array or CSV file path")
    parser.add_argument("--format", choices=["json", "csv"], default="json")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"File not found: {path}", file=sys.stderr)
        return 1

    content = path.read_text(encoding="utf-8")
    if args.format == "csv":
        records = parse_csv_records(content)
    else:
        records = json.loads(content)
        if not isinstance(records, list):
            print("JSON file must contain an array of player records", file=sys.stderr)
            return 1

    settings = get_settings()
    storage = build_performance_storage(settings)
    summary = import_performance_records(
        storage,
        league=args.league,
        season=args.season,
        records=records,
        source_method=args.source_method,
    )
    print(json.dumps(summary.model_dump(mode="json"), indent=2))
    return 0 if summary.rows_failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
