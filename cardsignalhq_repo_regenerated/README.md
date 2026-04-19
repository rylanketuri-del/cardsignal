# CardChase AI Starter Repo

MLB-only starter repository for a live player-performance + card-market tracker.

## What this repo includes

- MLB Stats API client for schedules, player lookup, and hitter game logs
- eBay Browse API client for live card listing searches
- Title normalization utilities for sports card listings
- MLB-only hotness scoring engine for hitters
- A pipeline script that fetches data, computes summaries, writes JSON output, and can persist runs to Supabase
- A FastAPI layer with database-first reads for the latest leaderboard and player detail endpoints
- Hosting scaffolding for Render and a static frontend for Vercel
- Scheduling scaffolding for both Render Cron and GitHub Actions

## Scope

This starter repo is intentionally focused on:

- MLB only
- hitters only
- active listing monitoring via eBay Browse API
- recent performance monitoring via MLB Stats API

## Repo structure

```text
cardchase_ai_starter_repo/
├── README.md
├── requirements.txt
├── .env.example
├── render.yaml
├── .github/workflows/pipeline_schedule.yml
├── api/
│   └── main.py
├── supabase/
│   └── schema.sql
├── frontend/
│   ├── index.html
│   ├── styles.css
│   ├── app.js
│   ├── config.js
│   └── vercel.json
├── cardchase_ai/
│   ├── config.py
│   ├── pipeline.py
│   ├── score.py
│   ├── storage.py
│   ├── models/
│   │   └── schemas.py
│   ├── clients/
│   │   ├── mlb.py
│   │   └── ebay.py
│   └── utils/
│       ├── normalize.py
│       └── rolling.py
└── scripts/
    ├── run_api.py
    └── run_pipeline.py
```

## Environment variables

Copy `.env.example` to `.env` and fill in your values.

- `EBAY_TOKEN`: OAuth bearer token for eBay Buy Browse API
- `EBAY_MARKETPLACE_ID`: defaults to `EBAY_US`
- `TRACKED_PLAYERS`: comma-separated MLB player names
- `OUTPUT_DIR`: local output folder for JSON artifacts
- `MLB_SEASON`: current MLB season for Stats API game logs
- `SUPABASE_URL`: Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY`: server-side key for inserting and reading pipeline data
- `PIPELINE_TRIGGER_TOKEN`: optional bearer token required to call `POST /api/pipeline/run`

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run the pipeline locally

```bash
python scripts/run_pipeline.py
```

The pipeline writes:

- timestamped leaderboard snapshots in `output/`
- `output/latest_leaderboard.json`
- Supabase rows if `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are set

## API server

A real API route layer lives in `api/main.py` using FastAPI.

### Local API run

```bash
python scripts/run_api.py
```

Available endpoints:

- `GET /health`
- `GET /api/leaderboard/latest`
- `GET /api/runs/latest`
- `GET /api/players/{player_id}`
- `POST /api/pipeline/run`

### Read behavior

The API now reads from **Supabase first** when it is configured. If Supabase is unavailable or empty, it falls back to `output/latest_leaderboard.json`.

That means your hosted app can keep using the same routes while you transition from file-backed development to database-backed production.

## Supabase setup

1. Create a new Supabase project.
2. Run `supabase/schema.sql` in the SQL editor.
3. Copy your project URL into `SUPABASE_URL`.
4. Copy your service role key into `SUPABASE_SERVICE_ROLE_KEY`.
5. Run the pipeline. Each run will insert one `pipeline_runs` row and a set of `leaderboard_entries`.

Use the service role key only in server-side environments.

## Frontend dashboard

The lightweight dashboard lives in `frontend/`.

1. Run the pipeline or API first.
2. Start a local web server from the repo root:

```bash
python -m http.server 8080
```

3. Start the API separately:

```bash
python scripts/run_api.py
```

4. Open `http://localhost:8080/frontend/` in your browser.

The frontend reads from `GET /api/leaderboard/latest`.

## Hosted frontend + API

This repo includes deployment scaffolding for a split deploy:

- `render.yaml` for hosting the FastAPI backend on Render
- `frontend/vercel.json` for hosting the static frontend on Vercel
- `frontend/config.js` for pointing the static frontend at your API base URL

### Suggested deploy split

- Host API on Render
- Host frontend on Vercel

### Basic deploy flow

1. Deploy the API with Render using `render.yaml`.
2. Set your environment variables on Render:
   - `EBAY_TOKEN`
   - `TRACKED_PLAYERS`
   - `MLB_SEASON`
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`
   - `PIPELINE_TRIGGER_TOKEN` if you want a protected run endpoint
3. Deploy the `frontend/` folder to Vercel.
4. Edit `frontend/config.js` so `CARDCHASE_API_BASE_URL` points to your hosted API.

## Scheduling options

### Option 1: Render Cron

`render.yaml` now includes a cron service named `cardchase-ai-pipeline-cron` that runs:

```bash
python scripts/run_pipeline.py
```

on this schedule:

```text
0 */3 * * *
```

That refreshes the MLB leaderboard every 3 hours.

### Option 2: GitHub Actions

A scheduled workflow lives at `.github/workflows/pipeline_schedule.yml`.

It calls your hosted API endpoint every 3 hours:

```text
POST /api/pipeline/run
```

Set these GitHub repository secrets:

- `CARDCHASE_API_URL`
- `PIPELINE_TRIGGER_TOKEN` if your API run endpoint is protected

## Notes

- MLB endpoint shapes used here are based on the public Stats API behavior.
- eBay search returns active listings, not a perfect sold-comps feed.
- For production, tighten Supabase read/write policies and consider moving to anon-key reads through a server-side API instead of using the service role key for everything.


## Auth + watchlists + alerts

This repo now includes a first user layer for the hosted app:

- email/password auth through Supabase Auth on the frontend
- `GET /api/me` for the signed-in user
- `GET /api/watchlist`, `POST /api/watchlist`, and `DELETE /api/watchlist/{player_name}`
- `GET /api/alerts` and `PUT /api/alerts`
- Supabase SQL for `profiles`, `watchlists`, and `alert_subscriptions`

### Extra environment variables

- `SUPABASE_ANON_KEY`: safe public key used by the frontend for Supabase Auth

### Auth flow

1. Run the updated `supabase/schema.sql` in Supabase.
2. In Supabase Auth, enable email/password sign-in.
3. Set `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and `SUPABASE_ANON_KEY`.
4. The frontend will call `GET /api/config` to discover the auth keys if they are not hard-coded in `frontend/config.js`.
5. After sign-in, the frontend passes the Supabase access token to the API for watchlist and alert routes.

### Local dev with auth

Start the API:

```bash
python scripts/run_api.py
```

Serve the frontend:

```bash
python -m http.server 8080
```

Open:

```text
http://localhost:8080/frontend/
```

### Notes

- Watchlists and alert preferences are stored per user in Supabase.
- The backend verifies the user token through Supabase Auth before reading or writing personal data.
- This is an MVP auth layer. For production, tighten CORS, confirm email policies, add password reset UX, and consider moving alert delivery to a background worker.


## Actual alert delivery pipeline

The pipeline now creates real notification records after each successful leaderboard run.

### What it does

- compares the latest leaderboard run to the previous run
- detects watchlist events such as:
  - hotness jumps
  - buy-low tags
  - most-chased tags
- creates in-app notifications in Supabase
- optionally sends email notifications when `RESEND_API_KEY` is configured
- optionally posts each notification payload to a webhook when `ALERT_WEBHOOK_URL` is configured

### New tables

- `notifications`
- `notification_deliveries`

### New API routes

- `GET /api/notifications`
- `POST /api/notifications/read`

### New environment variables

- `ALERT_WEBHOOK_URL`
- `ALERT_WEBHOOK_BEARER_TOKEN`
- `ALERT_FROM_EMAIL`
- `ALERT_SENDER_NAME`
- `APP_BASE_URL`
- `RESEND_API_KEY`

### Delivery behavior

- in-app notifications are always stored when Supabase is configured
- email delivery is attempted only when a user has an email and `RESEND_API_KEY` is set
- webhook delivery is attempted only when `ALERT_WEBHOOK_URL` is set

### Current event logic

- `hotness_jump`: player score rises meaningfully versus the previous run
- `buy_low`: player is tagged BUY LOW
- `most_chased`: player is tagged CHASED
- `daily_digest`: one summary notification per subscribed user per pipeline run

### Notes

For an MVP, the notification engine is intentionally simple and tied to pipeline runs. A production version would usually add stronger deduping windows, email templates, and queue-based delivery retries.


## Alert cooldowns

Set `ALERT_COOLDOWN_HOURS` to control repeat watchlist alerts like hotness jumps, buy-low, and most-chased events. Set `DAILY_DIGEST_COOLDOWN_HOURS` to keep daily digests from firing too often when the pipeline runs frequently.

The frontend now includes a notification center with unread counts, mark-read actions, and a mark-all-read control.


## New in v8

- HTML email templates for alert delivery through Resend
- Player-specific alert rules for watchlist names
- Notification center formatting upgrades in the frontend

### Player-specific alert rules

Use the watchlist rules panel to set per-player logic like:
- only alert when hotness jumps by 10+
- buy low only
- mute a player until a future date

API routes:
- `GET /api/watchlist/rules`
- `PUT /api/watchlist/rules/{player_name}`
- `DELETE /api/watchlist/rules/{player_name}`


## Admin tools and charts

- Frontend now includes Chart.js-powered player score history and leaderboard trend charts.
- Admin endpoints are protected with `ADMIN_API_TOKEN`.
- New admin endpoints:
  - `GET /api/admin/settings`
  - `PUT /api/admin/settings`
  - `POST /api/admin/tracked-players`
  - `PUT /api/admin/tracked-players/{player_name}`
  - `DELETE /api/admin/tracked-players/{player_name}`
- New history endpoints:
  - `GET /api/players/{player_id}/history`
  - `GET /api/history/leaderboard`
