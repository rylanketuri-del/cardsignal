#!/usr/bin/env python3
"""Lightweight NFL activation smoke checks against a running API.

Does not hardcode production-only values. Pass --base-url to target any environment.

Examples:
  python scripts/smoke_nfl_activation.py --base-url http://127.0.0.1:8000
  python scripts/smoke_nfl_activation.py --base-url https://cardsignal-api.onrender.com --expect-available
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


def _get(url: str) -> tuple[int, object]:
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(detail)
        except json.JSONDecodeError:
            payload = {"detail": detail}
        return exc.code, payload
    except Exception as exc:  # noqa: BLE001 - smoke helper surfaces transport failures
        return 0, {"detail": str(exc)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test NFL activation endpoints")
    parser.add_argument("--base-url", required=True, help="API base URL")
    parser.add_argument(
        "--expect-available",
        action="store_true",
        help="Fail unless /api/nfl/status.available is true and leaderboard has items",
    )
    parser.add_argument(
        "--expect-unavailable",
        action="store_true",
        help="Fail unless /api/nfl/status.available is false",
    )
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    checks: list[tuple[str, bool, str]] = []

    status_code, nfl_status = _get(f"{base}/api/nfl/status")
    ok = status_code == 200 and isinstance(nfl_status, dict)
    available = bool(nfl_status.get("available")) if ok else False
    checks.append(("GET /api/nfl/status returns 200 object", ok, f"http={status_code} body={nfl_status}"))

    if args.expect_available:
        checks.append(("NFL available is true", available, f"available={available}"))
    if args.expect_unavailable:
        checks.append(("NFL available is false", (ok and not available), f"available={available}"))

    lb_code, leaderboard = _get(f"{base}/api/nfl/leaderboard/latest")
    lb_ok = lb_code == 200 and isinstance(leaderboard, dict)
    items = leaderboard.get("items") if lb_ok else None
    item_count = len(items) if isinstance(items, list) else 0
    checks.append(("GET /api/nfl/leaderboard/latest returns 200 object", lb_ok, f"http={lb_code}"))
    if args.expect_available:
        checks.append(("NFL leaderboard has items", item_count > 0, f"items={item_count}"))

    weekly_code, weekly = _get(f"{base}/api/weekly/latest?league=NFL")
    weekly_ok = weekly_code == 200 and isinstance(weekly, dict)
    checks.append(("GET /api/weekly/latest?league=NFL returns 200", weekly_ok, f"http={weekly_code}"))
    if args.expect_available:
        leaders = weekly.get("todays_leaders") if weekly_ok else None
        checks.append(
            (
                "NFL weekly has leaders or completed run when available",
                bool((isinstance(leaders, list) and leaders) or (weekly or {}).get("run")),
                f"leaders={len(leaders) if isinstance(leaders, list) else None} run={bool((weekly or {}).get('run'))}",
            )
        )

    mlb_code, mlb = _get(f"{base}/api/leaderboard/latest")
    mlb_ok = mlb_code == 200 and isinstance(mlb, dict) and isinstance(mlb.get("items"), list) and len(mlb["items"]) > 0
    checks.append(("MLB leaderboard remains healthy", mlb_ok, f"http={mlb_code}"))

    nba_code, nba_status = _get(f"{base}/api/nba/status")
    nba_ok = nba_code == 200 and isinstance(nba_status, dict)
    checks.append(("NBA status endpoint still responds", nba_ok, f"http={nba_code}"))

    failed = 0
    for name, passed, detail in checks:
        mark = "PASS" if passed else "FAIL"
        if not passed:
            failed += 1
        print(f"{mark}: {name} ({detail})")

    print(json.dumps({
        "nfl_available": available,
        "nfl_leaderboard_items": item_count,
        "failed": failed,
    }, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
