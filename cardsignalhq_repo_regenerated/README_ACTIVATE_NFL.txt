CardSignal NFL Production Activation Bundle
===========================================

Unpack this ZIP into your local repo root:

  /Users/rylanketuri/Downloads/cardsignalhq_repo_regenerated

so these paths exist:

  output/nfl/import/verified_nfl_previous_season_2025.json
  output/nfl/import/verified_nfl_previous_season_2025.manifest.json
  scripts/import_nfl_data.py
  scripts/smoke_nfl_activation.py
  scripts/validate_nfl_import.py
  cardchase_ai/nfl_data_validation.py
  cardchase_ai/previous_season_validation.py

Preflight (already verified in this bundle)
-------------------------------------------
- Seed contains 180 genuine players
- Season is 2025
- Manifest provider=nflverse, license=CC-BY-4.0
- Validation reports SAFE_TO_IMPORT
- No synthetic TEST players
- No secrets / ADMIN_API_TOKEN values are included

Exact commands
--------------

1) Open a terminal and enter the repo root:

cd /Users/rylanketuri/Downloads/cardsignalhq_repo_regenerated

2) Validate the seed (expect VALID / SAFE_TO_IMPORT):

python3 scripts/validate_nfl_import.py \
  output/nfl/import/verified_nfl_previous_season_2025.json \
  --expected-season 2025

3) Dry-run import (no writes):

python3 scripts/import_nfl_data.py \
  --mode previous-season \
  --input output/nfl/import/verified_nfl_previous_season_2025.json \
  --season 2025 \
  --dry-run

4) Production import via admin API (set your own token from Render; do not commit it):

export ADMIN_API_TOKEN='YOUR_TOKEN_FROM_RENDER'
python3 scripts/import_nfl_data.py \
  --mode previous-season \
  --input output/nfl/import/verified_nfl_previous_season_2025.json \
  --season 2025 \
  --environment production \
  --api-base https://cardsignal-api.onrender.com

5) Trigger NFL weekly run:

curl -sS -X POST \
  'https://cardsignal-api.onrender.com/api/weekly/run' \
  -H "Authorization: Bearer $ADMIN_API_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"league":"NFL","force":true,"market_enabled":false}'

6) Smoke-test activation:

python3 scripts/smoke_nfl_activation.py \
  --base-url https://cardsignal-api.onrender.com \
  --expect-available

Notes
-----
- Prefer previous-season + Supabase; do not rely on ephemeral provider-file installs on Render.
- Confirm ADMIN_API_TOKEN, SUPABASE_URL, and SUPABASE_SERVICE_ROLE_KEY are set in Render before step 4.
- Run supabase/migrations/20260713_performance_snapshots.sql in Supabase if not already applied.
- Attribution: see verified_nfl_previous_season_2025.manifest.json (nflverse, CC BY 4.0).
