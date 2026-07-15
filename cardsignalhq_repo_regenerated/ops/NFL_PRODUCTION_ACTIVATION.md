# NFL Production Activation (ops)

## Blocker summary

Code is already on `main` and deployed. `/api/nfl/status` is `available: false` because production has **no verified NFL dataset**.

`render.yaml` does **not** attach a persistent disk. Web and cron services do **not** share filesystems. Do **not** rely on Render Shell `echo > output/nfl/import/nfl_data.json` unless you add a disk and set `OUTPUT_DIR` to that mount.

Preferred durable path: Supabase-backed previous-season import via the admin API, then an admin NFL weekly run.

## Environment variables to verify in Render (values not shown here)

| Variable | Required? | Used for |
|----------|-----------|----------|
| `ADMIN_API_TOKEN` | **Required** for import + weekly trigger | Bearer auth on `/api/admin/*` and `/api/weekly/run` |
| `SUPABASE_URL` | **Required** for durable previous-season / weekly persistence across services | Storage backends |
| `SUPABASE_SERVICE_ROLE_KEY` | **Required** with URL | Server-side Supabase writes |
| `PIPELINE_TRIGGER_TOKEN` | Optional | `POST /api/pipeline/run` only |
| `OUTPUT_DIR` | Optional (default `./output`) | JSON fallback / provider file path |
| `NFL_SEASON` | Optional (default `2025`) | NFL season context |
| `NFL_PLAYER_LIMIT` | Optional (default `100`) | Universe size cap |
| `NFL_ENABLED` | Optional / currently unused by availability gate | Config placeholder |
| `EBAY_TOKEN` | Optional | Market snapshots (may stay empty) |

Live observation at recovery time: `ADMIN_API_TOKEN` was **not configured** (`Admin API token not configured.`).

Also run the Supabase migration:

`supabase/migrations/20260713_performance_snapshots.sql`

## Exact schema: `output/nfl/import/nfl_data.json` (provider file)

Required top-level:

- `source_method` (string): one of `OFFICIAL_API`, `LICENSED_API`, `APPROVED_IMPORT`, `MANUAL_VERIFIED`
- `players` (array, min 1 non-retired for a useful universe)

Optional top-level:

- `season` (int)
- `last_updated` (ISO timestamp)
- `games` (object keyed by `source_player_id` → game row arrays)
- `season_stats` (object keyed by `source_player_id`)
- `schedule` (array)
- `developments` (object keyed by `source_player_id` → signal-driver evidence lists)

Player object:

- required: `source_player_id`, `player_name`
- optional: `team`, `team_id`, `position`, `jersey_number`, `active_status`, `headshot_url`, `team_logo_url`, `season`, `last_updated`

Game row:

- important: `game_date`, `season`, `participated`, `stats`
- optional: `game_id`, `week`, `team`, `opponent`, `home_away`, `is_bye_week`, `is_preseason`, `is_postseason`, `position` / `position_group`

Season stats entry:

- `{ "season": 2025, "stats": { ... numeric fields ... } }`

Market/scouting/evidence fields are **not** stored inside this file for eBay market rows; weekly pipeline derives market separately. Signal driver evidence can come from `developments` or generated/stored drivers after weekly run.

## Previous-season admin records schema (preferred durable)

JSON **array** of rows validated by `cardchase_ai.performance_import.validate_import_row`:

- required: `source_player_id`, `position`, `season`, `games_played`
- recommended: `player_name`, `team`, `starts`, `stats`, `source_method`, `source_reference`
- percentages in this path are **0–1** (not 0–100)
- endpoint: `POST /api/admin/performance/import`

## Validate locally

```bash
cd cardsignalhq_repo_regenerated
python scripts/validate_nfl_import.py path/to/nfl_data.json --expected-season 2025
```

## Import (preferred: previous-season API)

```bash
export ADMIN_API_TOKEN='…'   # from Render dashboard
python scripts/import_nfl_data.py \
  --mode previous-season \
  --input path/to/verified_nfl_previous_season.json \
  --season 2025 \
  --environment production \
  --api-base https://cardsignal-api.onrender.com
```

Dry-run first:

```bash
python scripts/import_nfl_data.py \
  --mode previous-season \
  --input path/to/verified_nfl_previous_season.json \
  --season 2025 \
  --dry-run
```

## Weekly NFL run

```bash
curl -sS -X POST 'https://cardsignal-api.onrender.com/api/weekly/run' \
  -H "Authorization: Bearer $ADMIN_API_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"league":"NFL","force":true,"market_enabled":false}'
```

## Verify

```bash
python scripts/smoke_nfl_activation.py \
  --base-url https://cardsignal-api.onrender.com \
  --expect-available
```

Manual checks:

1. `GET /api/nfl/status` → `available: true`
2. `GET /api/nfl/leaderboard/latest` → real `items`
3. `GET /api/weekly/latest?league=NFL` → run/leaders when weekly completed
4. `GET /api/leaderboard/latest` → MLB still healthy
5. Frontend NFL tab no longer Coming Soon; All includes NFL

## Missing genuine source data

This repo only contains synthetic unit fixtures (`TEST-*`). Do **not** deploy them.

You must supply a verified NFL dataset from an approved source and place it in the import JSON formats above before production activation can complete.
