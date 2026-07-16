# CardSignal Beta Validation Sprint 1 — Infrastructure Validation Report

**Date:** 2026-07-16  
**Scope:** Production architecture verification only (no feature work, no architecture refactor)  
**Production API:** `https://cardsignal-api.onrender.com`  
**Repo HEAD validated:** `main` @ `93d545e` (live deploy basis)  
**Related completed-but-undeployed work:** draft PR #54 `cursor/backend-simplification-9b65` (provider/engine/pipeline + correct cron schedules)

---

## Summary verdict

| Category | Result |
|---|---|
| Scheduling | **FAIL** |
| Pipeline Flow | **FAIL** |
| Storage | **FAIL** |
| API | **FAIL** |
| Season Logic | **PASS** (with notes) |
| Production Smoke — MLB | **PARTIAL PASS** |
| Production Smoke — NFL | **FAIL** |
| Production Smoke — NBA | **FAIL** |

Overall: **FAIL** — production does not yet satisfy the Sprint 1 infrastructure contract end-to-end for all three sports.

---

## 1. Scheduling — FAIL

### Expected
- MLB every 3 days
- NFL Tuesday 06:00 America/New_York
- NBA Tuesday 06:00 America/New_York
- No duplicate schedulers

### Observed on `main` / current `render.yaml`
- Single cron `cardchase-ai-pipeline-cron` with schedule `0 */3 * * *` (**every 3 hours**, not every 3 days)
- NFL/NBA weekly refresh is only a **due-check gate** inside that same frequent cron (`pipeline._ensure_weekly_intelligence`), not a dedicated Tuesday 06:00 job
- No `.github/workflows` schedule present (README still documents a GitHub Actions every-3-hours option that does not exist in-repo)

### Observed on completed simplification branch (PR #54, not merged/deployed)
- MLB cron: `0 10 */3 * *` (every 3 days ~06:00 Eastern)
- Weekly cron: `0 10 * * 2` → `python scripts/run_weekly_pipelines.py` (Tuesday ~06:00 Eastern)
- Architecture unit tests for these schedules: **24 passed**

### Duplicate schedulers
- **No live duplicate cron + GitHub Actions pair** (Actions workflow file absent)
- README still advertises both Render and GitHub Actions every-3-hours paths → documentation risk of future duplicates

### Root cause
Production/`main` still uses the pre-simplification schedule. Correct schedules exist only on draft PR #54 and were not deployed.

### Minimal fix applied in this PR
- Updated `render.yaml` to MLB every-3-days + Tuesday weekly cron
- Added thin `scripts/run_weekly_pipelines.py` using existing `run_weekly_intelligence` (no architecture refactor)
- Aligned README scheduling docs; removed non-existent Actions schedule as a live option

---

## 2. Pipeline Flow — FAIL

### Expected (every sport)
Provider → CardSignal Engine → Supabase → API → Frontend

### Observed on `main`
| Sport | Provider | Shared Engine | Supabase persist | API read | Frontend |
|---|---|---|---|---|---|
| MLB | MLB Stats API (`clients/mlb.py`) | League-specific scoring in `pipeline.py` / weekly path (not shared CardSignal engine on `main`) | Leaderboard runs/entries yes | Leaderboard/player yes (`data_source=supabase`) | `frontend/` wired to API; public sports UI host not confirmed |
| NFL | Import/provider + previous-season seed | `nfl_weekly.py` path | Player weekly snapshots present; `/api/weekly/latest` empty | Mixed: intelligence/history work; player detail 404; leaderboard from local NFL storage | Same |
| NBA | Import provider (no seed/data) | `nba_weekly.py` path | No completed weekly run | `available=false` | Same |

### Simplification branch (PR #54)
Implements Provider → `CardSignalEngine` → Supabase weekly pipeline for NFL/NBA, plus schedule helpers. **Not merged / not deployed.**

### Root cause
- Intended architecture lives on unmerged PR #54
- Live MLB path works for leaderboard persistence, but weekly homepage payload path is empty for all leagues
- NFL/NBA on `main` still depend on local JSON registries/leaderboards for several reads

---

## 3. Storage — FAIL

### Expected
- Production never depends on local JSON
- JSON may remain as debug artifacts only
- Supabase is production source of truth

### Observed
| Layer | Behavior |
|---|---|
| MLB leaderboard | Supabase primary in production smoke (`data_source=supabase`) |
| Weekly storage | Supabase primary **with silent JSON fallback** (`weekly_storage.py`) |
| Previous-season performance | Supabase primary **with JSON fallback** (`performance_storage.py`) |
| NFL storage | **JSON/files under `output/nfl/`** (`nfl_storage.py`) — not Supabase |
| NBA storage | **JSON/files under `output/nba/`** (`nba_storage.py`) — not Supabase |
| Pipeline writes | Always writes `output/latest_leaderboard.json` even when Supabase succeeds (debug artifact OK; API fallback not OK) |

`storage_diagnostics` explicitly warns that local JSON is ephemeral on Render.

### Root cause
Production still has dual-write / dual-read paths. NFL/NBA league storage modules are filesystem-backed on `main`.

---

## 4. API — FAIL

### Expected
Every production endpoint reads persisted Supabase data. No silent filesystem fallback.

### Observed violations on `main` (`api/main.py`)
- `_load_latest()` / `_load_player()`: on Supabase miss/error → **silent fall back to `latest_leaderboard.json`**
- `/health`: can report `data_source=file`
- NFL/NBA leaderboard/player helpers read `NFLStorage` / `NBAStorage` filesystem registries
- `/api/weekly/latest` for MLB/NFL/NBA: HTTP 200 but **`run: null`, empty leaders** despite NFL player weekly history existing in storage (orphaned snapshots / run row not matching COMPLETED query filters)

### Production probes (2026-07-16)
- `GET /health` → 200, `data_source=supabase`, season 2026
- `GET /api/leaderboard/latest` → 200, `data_source=supabase`, 20 items
- `GET /api/weekly/latest?league=MLB|NFL|NBA` → 200, empty run/leaders
- `GET /api/nfl/leaderboard/latest` → 200, `available=true`, 20 items, scores mostly null/0
- `GET /api/nba/leaderboard/latest` → 200, `available=false`
- `GET /api/players/NFL/{id}/intelligence` → 200 with OFFSEASON / 2025 previous-season evidence
- `GET /api/nfl/players/{id}` → 404 (registry/provider gap)

### Minimal fix applied in this PR
When Supabase credentials are configured, MLB leaderboard/player endpoints **fail closed** (404/503) instead of silently serving filesystem data. Local JSON remains allowed only when Supabase is not configured (local/dev).

---

## 5. Season Logic — PASS (with notes)

### Expected
- MLB: current season
- NFL offseason: completed 2025
- NBA offseason: completed 2025–26
- When seasons begin: NFL/NBA use previous Tuesday → current Tuesday
- No fabricated recent form

### Observed
| Rule | Status | Evidence |
|---|---|---|
| MLB current season | **PASS** | Config/default `MLB_SEASON=2026`; production health `season=2026`; live 7d stats present |
| NFL offseason → 2025 | **PASS** | Config `NFL_SEASON=2025`; intelligence `season_phase=OFFSEASON`, `previous_season_label=2025 Season Performance`, real nflverse 2025 stats |
| NBA offseason → 2025–26 | **PASS (code)** / **FAIL (data)** | Config `NBA_SEASON=2025`; `format_nba_split_season_label` → `2025–26`; no production NBA seed/data |
| In-season Tue→Tue window | **PASS on PR #54 only** | `engine/season_phase.in_season_tuesday_window` + architecture tests; **not on `main`** (`reporting_period` still Mon–Sun / NFL Thu–Mon) |
| No fabricated recent form | **PASS** | Offseason capabilities set `recent_form=UNAVAILABLE`; `recent_performance=[]`; recommendation WATCH with insufficient confidence rather than invented recent games |

Unit tests on `main` (offseason / weekly / homepage restore / convergence): **73 passed**.

---

## 6. Production Smoke Test

### MLB — PARTIAL PASS
- Pipeline → Supabase → API leaderboard/player: **works**
- Weekly intelligence homepage (`/api/weekly/latest`): **empty**
- Frontend: `frontend/config.js` points at production API; public collector UI deployment URL for this static app was **not confirmed** (known public hosts serve a different CardSignal One Piece product)

### NFL — FAIL
- Previous-season intelligence path partially works (OFFSEASON/2025)
- Leaderboard scores null/0; player detail 404; search empty; provider `source_method=UNAVAILABLE`
- Weekly latest empty while player weekly history has rows → broken homepage contract
- End-to-end Provider→Engine→Supabase→API→Frontend **not healthy**

### NBA — FAIL
- `available=false`, empty leaderboard, no weekly run, no import seed in repo `output/nba/`
- End-to-end path **does not work**

---

## Failures & root causes (consolidated)

1. **Wrong live cron schedule** — `main`/`render.yaml` every 3 hours; expected every 3 days + Tuesday weekly.  
   Root cause: simplification schedule not merged/deployed.

2. **API silent filesystem fallback** — violates production source-of-truth rule.  
   Root cause: `_load_latest` / `_load_player` catch Supabase errors and read JSON.

3. **NFL/NBA storage not Supabase-backed on `main`** — Render ephemeral disk risk.  
   Root cause: `nfl_storage.py` / `nba_storage.py` are file stores; weekly/performance have fallbacks.

4. **Weekly latest API empty for all leagues** despite some NFL snapshot history.  
   Root cause: `fetch_latest_completed_payload` finds no COMPLETED/PARTIAL official run rows matching filters (status/force/triggered_by), or homepage payload never persisted — while player snapshots exist.

5. **NBA not activated in production** — no provider import / previous-season seed deployed.

6. **Shared CardSignal engine path not live** — exists on PR #54 only.

7. **Collector frontend deployment unverified** — static `frontend/` is API-wired in repo, but no confirmed public host serving that app was found during smoke testing.

---

## Files changed (this validation PR)

| File | Change |
|---|---|
| `VALIDATION_REPORT_SPRINT1.md` | This report |
| `render.yaml` | MLB every 3 days + Tuesday weekly cron |
| `scripts/run_weekly_pipelines.py` | Thin Tuesday entrypoint for NFL/NBA weekly intelligence |
| `api/main.py` | Fail closed on Supabase-configured leaderboard/player reads (no silent file fallback) |
| `README.md` | Correct scheduling docs; remove non-existent Actions schedule as a live option |
| `tests/test_api_storage_contract.py` | Regression test for fail-closed API reads |

---

## Test results

| Suite | Result |
|---|---|
| `tests.test_offseason_intelligence` + weekly + homepage restore + convergence (`main`) | **73 passed** |
| `tests.test_backend_architecture` (simplification branch PR #54) | **24 passed** |
| `tests.test_api_storage_contract` (added) | **3 passed** |
| `tests.test_api_storage_contract` + offseason + weekly (combined local run) | **48 passed** |
| Production HTTP smoke (MLB/NFL/NBA) | See section 6 |

### Post-fix status note

Repo fixes in this PR correct **scheduling config** and **MLB API fail-closed reads**. They do **not** by themselves flip overall Sprint 1 to PASS: NFL/NBA filesystem storage, empty `/api/weekly/latest`, NBA activation, undeployed shared engine (PR #54), and unverified collector frontend hosting remain open.

---

## Recommended next actions (outside this validation-only scope)

1. Merge/deploy draft PR #54 (backend simplification) so Provider→Engine→Supabase is live.
2. Repair weekly run rows / re-run official weekly intelligence so `/api/weekly/latest` returns COMPLETED payloads for MLB and NFL.
3. Seed/activate NBA previous-season performance in Supabase (mirror NFL 2025 activation path).
4. Move NFL/NBA registry/leaderboard reads fully onto Supabase (no Render-local JSON dependency).
5. Confirm and document the deployed collector frontend URL that serves `frontend/` against the Render API.
