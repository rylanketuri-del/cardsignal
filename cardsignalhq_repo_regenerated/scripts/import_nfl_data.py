#!/usr/bin/env python3
"""Repeatable NFL production import helper.

Two durable-aware modes:

1) provider-file
   Validates nfl_data.json and installs it under OUTPUT_DIR/nfl/import/nfl_data.json.
   WARNING: Render free web/cron filesystems are ephemeral and not shared unless a
   persistent disk is attached. Prefer previous-season + Supabase for production.

2) previous-season
   Validates previous-season records using cardchase_ai.performance_import, then either:
     - writes locally via PerformanceStorage (JSON / Supabase per env), or
     - POSTs to /api/admin/performance/import when --api-base is set.

Does not fabricate players. Does not modify MLB data.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cardchase_ai.config import get_settings
from cardchase_ai.nfl_data_validation import (
    looks_like_previous_season_records,
    looks_like_provider_file,
    suggest_import_path,
    validate_nfl_data_file,
    validate_nfl_data_payload,
)
from cardchase_ai.performance_import import import_performance_records, validate_import_row
from cardchase_ai.performance_storage import build_performance_storage


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _install_provider_file(source: Path, destination: Path, *, dry_run: bool) -> dict:
    report = validate_nfl_data_file(source, allow_synthetic=False)
    result = {
        "mode": "provider-file",
        "validation": report.to_dict(),
        "destination": str(destination),
        "written": False,
        "rejected_rows": 0,
        "imported_players": report.active_player_count if report.safe_to_import else 0,
        "persistence": "filesystem OUTPUT_DIR (ephemeral on Render unless a disk is mounted)",
    }
    if not report.safe_to_import:
        result["status"] = "failed_validation"
        return result
    if dry_run:
        result["status"] = "validated_dry_run"
        return result
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    result["written"] = True
    result["status"] = "installed"
    return result


def _validate_previous_season_records(records: list, *, league: str, season: int) -> dict:
    errors: list[dict] = []
    accepted = 0
    for index, row in enumerate(records):
        if not isinstance(row, dict):
            errors.append({"row_index": index, "error": "row must be an object"})
            continue
        # Reject obvious synthetic fixtures unless source ids are clearly non-test.
        sid = str(row.get("source_player_id") or "")
        name = str(row.get("player_name") or "").lower()
        if sid.upper().startswith(("TEST-", "DEMO-", "MOCK-", "FAKE-")) or "test qb" in name or "demo player" in name:
            errors.append({
                "row_index": index,
                "source_player_id": sid or None,
                "error": "Synthetic/test record refused for production import",
            })
            continue
        _, err = validate_import_row(row, league=league, season=season, row_index=index)
        if err:
            errors.append(err.model_dump())
        else:
            accepted += 1
    return {
        "valid": len(errors) == 0 and accepted > 0,
        "accepted": accepted,
        "failed": len(errors),
        "errors": errors,
        "rows_received": len(records),
    }


def _import_previous_season_local(records: list, *, season: int, dry_run: bool) -> dict:
    validation = _validate_previous_season_records(records, league="NFL", season=season)
    result = {
        "mode": "previous-season-local",
        "validation": validation,
        "written": False,
        "imported_players": 0,
        "rejected_rows": validation["failed"],
        "persistence": "PerformanceStorage (Supabase when configured, else OUTPUT_DIR/performance JSON)",
    }
    if not validation["valid"]:
        result["status"] = "failed_validation"
        return result
    if dry_run:
        result["status"] = "validated_dry_run"
        result["imported_players"] = validation["accepted"]
        return result
    settings = get_settings()
    storage = build_performance_storage(settings)
    summary = import_performance_records(
        storage,
        league="NFL",
        season=season,
        records=records,
        source_method="APPROVED_IMPORT",
    )
    result["written"] = True
    result["status"] = "imported"
    result["imported_players"] = summary.rows_imported + summary.rows_updated
    result["summary"] = summary.model_dump(mode="json")
    result["uses_supabase"] = storage.uses_supabase
    result["persistence_destination"] = (
        "supabase.performance_snapshots" if storage.uses_supabase else str(settings.output_dir / "performance")
    )
    return result


def _import_previous_season_api(
    records: list,
    *,
    season: int,
    api_base: str,
    admin_token: str,
    dry_run: bool,
) -> dict:
    validation = _validate_previous_season_records(records, league="NFL", season=season)
    result = {
        "mode": "previous-season-api",
        "validation": validation,
        "api_base": api_base.rstrip("/"),
        "written": False,
        "imported_players": 0,
        "rejected_rows": validation["failed"],
        "persistence": "POST /api/admin/performance/import → PerformanceStorage on API host",
    }
    if not validation["valid"]:
        result["status"] = "failed_validation"
        return result
    if dry_run:
        result["status"] = "validated_dry_run"
        result["imported_players"] = validation["accepted"]
        return result
    if not admin_token:
        result["status"] = "missing_admin_token"
        result["errors"] = ["ADMIN_API_TOKEN / --admin-token is required for API import"]
        return result

    body = json.dumps({
        "league": "NFL",
        "season": season,
        "period_type": "PREVIOUS_SEASON",
        "source_method": "APPROVED_IMPORT",
        "records": records,
    }).encode("utf-8")
    request = urllib.request.Request(
        f"{api_base.rstrip('/')}/api/admin/performance/import",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {admin_token}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        result["status"] = "api_error"
        result["http_status"] = exc.code
        result["errors"] = [detail]
        return result
    except urllib.error.URLError as exc:
        result["status"] = "api_error"
        result["errors"] = [str(exc)]
        return result

    result["written"] = True
    result["status"] = "imported"
    result["summary"] = payload
    result["imported_players"] = int(payload.get("rows_imported", 0)) + int(payload.get("rows_updated", 0))
    result["rejected_rows"] = int(payload.get("rows_failed", 0))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and import verified NFL production data")
    parser.add_argument("--input", required=True, help="Path to nfl_data.json OR previous-season records JSON array")
    parser.add_argument(
        "--mode",
        choices=["auto", "provider-file", "previous-season"],
        default="auto",
        help="Import mode (auto detects provider-file object vs previous-season array)",
    )
    parser.add_argument(
        "--environment",
        choices=["local", "production"],
        default="local",
        help="Label only; production refuses synthetic markers",
    )
    parser.add_argument("--season", type=int, default=None, help="Required for previous-season mode")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Override OUTPUT_DIR for provider-file install (default: settings.output_dir)",
    )
    parser.add_argument(
        "--api-base",
        default=None,
        help="When set with previous-season mode, POST to remote admin import endpoint",
    )
    parser.add_argument(
        "--admin-token",
        default=os.getenv("ADMIN_API_TOKEN", ""),
        help="Bearer token for admin API (or set ADMIN_API_TOKEN)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate only; do not write")
    parser.add_argument("--json", action="store_true", help="Print JSON result")
    args = parser.parse_args()

    source = Path(args.input)
    if not source.exists():
        print(json.dumps({"status": "missing_input", "path": str(source)}), file=sys.stderr)
        return 1

    payload = _load_json(source)
    mode = args.mode
    if mode == "auto":
        if looks_like_provider_file(payload):
            mode = "provider-file"
        elif looks_like_previous_season_records(payload):
            mode = "previous-season"
        else:
            print("Unable to detect mode: expected provider object or previous-season array", file=sys.stderr)
            return 1

    if args.environment == "production" and mode == "provider-file":
        # still enforced inside validator; keep explicit
        pass

    if mode == "provider-file":
        if not looks_like_provider_file(payload):
            print("provider-file mode requires top-level object with players[]", file=sys.stderr)
            return 1
        # Pre-validate in-memory for clearer auto errors
        inline = validate_nfl_data_payload(payload, allow_synthetic=False)
        if not inline.safe_to_import and not args.dry_run:
            # allow dry-run still produce report via install helper
            pass
        settings = get_settings()
        output_dir = Path(args.output_dir) if args.output_dir else settings.output_dir
        destination = suggest_import_path(output_dir)
        result = _install_provider_file(source, destination, dry_run=args.dry_run)
        if args.environment == "production":
            result["production_warning"] = (
                "Render web/cron do not declare a persistent disk in render.yaml. "
                "provider-file installs are lost on redeploy unless a disk is attached and "
                "OUTPUT_DIR points at the mount. Prefer --mode previous-season with Supabase."
            )
    else:
        if args.season is None:
            print("--season is required for previous-season mode", file=sys.stderr)
            return 1
        if not looks_like_previous_season_records(payload):
            print("previous-season mode requires a JSON array of player records", file=sys.stderr)
            return 1
        if args.api_base:
            result = _import_previous_season_api(
                payload,
                season=args.season,
                api_base=args.api_base,
                admin_token=args.admin_token,
                dry_run=args.dry_run,
            )
        else:
            result = _import_previous_season_local(payload, season=args.season, dry_run=args.dry_run)

    text = json.dumps(result, indent=2)
    print(text)
    status = result.get("status", "")
    if status in {"installed", "imported", "validated_dry_run"}:
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
