"""Scheduler preparation notes for weekly intelligence.

Production path (Sprint 11.4+):
  - `python scripts/run_pipeline.py` (Render cron `cardchase-ai-pipeline-cron`)
    writes the leaderboard, then calls `run_weekly_intelligence` for MLB
    (and NFL/NBA when those leagues are available).
  - Duplicate official runs for the same league/year/week are SKIPPED.
  - Homepage card sections and Trend (`weekly_change`) are produced only by
    this weekly intelligence layer — not by the leaderboard writer alone.

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
