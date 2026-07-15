"""Scheduler preparation notes for weekly intelligence.

Architecture (Sprint 11.4+):
  Daily / frequent pipeline (`python scripts/run_pipeline.py`):
    - Refresh leaderboard + market data
    - Check whether a weekly intelligence snapshot is due
    - Do NOT regenerate weekly intelligence on every run

  Weekly intelligence generation runs only when both are true:
    1) No completed official weekly run exists for the current league/year/week
    2) The configured weekly refresh window has opened (default: Tuesday 06:00 America/New_York)

  This keeps daily and weekly semantics intact while hosting the weekly due-check
  inside the existing cron (no second Render service required). Failed Tuesday
  generations are retried by later pipeline runs until one completes.

Optional admin / Tuesday endpoint:
  - Day: Tuesday (weekday=1)
  - Time: 06:00 America/New_York
  - Endpoint: POST /api/weekly/run (admin bearer token required)
  - Idempotent: duplicate official runs for the same league/year/week are SKIPPED

Example cron (external scheduler, not embedded in app):

  0 6 * * 2 curl -sS -X POST "$API_BASE/api/weekly/run" \\
    -H "Authorization: Bearer $ADMIN_API_TOKEN" \\
    -H "Content-Type: application/json" \\
    -d '{"league":"MLB","force":false}'

Manual force replacement run:

  curl -sS -X POST "$API_BASE/api/weekly/run" \\
    -H "Authorization: Bearer $ADMIN_API_TOKEN" \\
    -H "Content-Type: application/json" \\
    -d '{"league":"MLB","force":true,"triggered_by":"admin"}'
"""
