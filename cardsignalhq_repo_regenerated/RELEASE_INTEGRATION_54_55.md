# Combined Backend Release — PR #54 + PR #55 Integration

**Branch:** `cursor/backend-release-integration-5a71`  
**Date:** 2026-07-16  
**Do not deploy until this branch passes review and the post-deploy smoke checklist below.**

---

## 1. Dependency audit

### Does PR #55 depend on PR #54?

**Hard import/runtime dependency: NO for most of #55.**  
PR #55’s unique fixes (`api/main.py` fail-closed reads, storage-contract tests, validation report) work against `main` without #54’s new packages.

**Operational / product dependency: YES — do not ship #55 alone.**

| #55 artifact | Depends on #54? | Notes |
|---|---|---|
| `render.yaml` schedules | **Conflicts / duplicates intent** | Same cron intent as #54; #55’s runner implementation differed |
| `scripts/run_weekly_pipelines.py` (on #55) | **Incompatible with #54** | #55 called `weekly_intelligence.run_weekly_intelligence` directly; #54’s canonical runner calls `pipelines.weekly_pipeline.run_weekly_pipeline` |
| `api/main.py` fail-closed | No | Independent; layered onto #54 cleanly |
| `tests/test_api_storage_contract.py` | No | Independent |
| `VALIDATION_REPORT_SPRINT1.md` | No | Documents pre-#54 production |

### Explicit dependencies introduced by combining (final branch uses #54 paths)

| Consumer | Depends on (#54) |
|---|---|
| `scripts/run_weekly_pipelines.py` | `cardchase_ai.pipelines.schedule.is_weekly_pipeline_due` |
| `scripts/run_weekly_pipelines.py` | `cardchase_ai.pipelines.weekly_pipeline.run_weekly_pipeline` |
| `scripts/run_weekly_pipelines.py` | `cardchase_ai.storage.supabase.build_weekly_storage` |
| `scripts/run_weekly_pipelines.py` | `cardchase_ai.storage.supabase.production_storage_configured` |
| `cardchase_ai.pipelines.weekly_pipeline` | `cardchase_ai.engine.season_phase` (Tue→Tue / offseason baseline) |
| `cardchase_ai.pipelines.weekly_pipeline` | `cardchase_ai.providers` / league hooks |
| `cardchase_ai.weekly_intelligence` | delegates NFL/NBA to `execute_weekly_league_pipeline` |
| `cardchase_ai.storage` package | `storage/client.py`, `storage/supabase.py` |
| MLB cron `scripts/run_pipeline.py` | existing `pipeline.run_pipeline` (+ #54 schedule helpers available) |

**Conclusion:** Stacking #55 onto production independently would recreate a second weekly runner shape and miss the shared engine. Correct order is **#54 base → layer #55 unique fixes → keep #54 entry points**.

---

## 2. Conflict resolution (no duplicates)

| Area | Kept canonical source |
|---|---|
| Providers | `#54` `cardchase_ai/providers/*` |
| Engine | `#54` `cardchase_ai/engine/*` |
| Pipelines | `#54` `cardchase_ai/pipelines/*` |
| Season helpers | `#54` `engine/season_phase.py` + league calendars |
| Storage façade | `#54` `cardchase_ai/storage/*` |
| Cron services | Single `render.yaml` (schedules from #54/#55 agreement) |
| Weekly runner | **`scripts/run_weekly_pipelines.py` from #54** (not #55’s parallel implementation) |

### One obvious production entry point each

| Job | Entry point | Render service |
|---|---|---|
| MLB refresh | `python scripts/run_pipeline.py` | `cardchase-ai-mlb-pipeline-cron` |
| NFL weekly | `python scripts/run_weekly_pipelines.py` → `run_weekly_pipeline("NFL")` | `cardchase-ai-weekly-pipeline-cron` |
| NBA weekly | same script → `run_weekly_pipeline("NBA")` | same Tuesday cron |

No GitHub Actions scheduler in-repo.

---

## 3. Render schedules (UTC + Eastern DST)

| Service | Cron (UTC) | Intent |
|---|---|---|
| MLB | `0 10 */3 * *` | Every 3 days at 10:00 UTC |
| NFL+NBA weekly | `0 10 * * 2` | Tuesdays at 10:00 UTC |

Eastern mapping (Render cannot express TZ-aware cron):

| Season | Offset | `10:00 UTC` local |
|---|---|---|
| EDT (~Mar–Nov) | UTC−4 | **06:00** America/New_York |
| EST (~Nov–Mar) | UTC−5 | **05:00** America/New_York |

Beta anchors to **06:00 Eastern Daylight**. During EST the weekly job is 05:00 local by design of a fixed UTC cron.

---

## 4. Weekly homepage empty diagnosis (production)

**Symptom:** NFL player weekly history exists for run_ids, but `GET /api/weekly/latest?league=NFL` returns empty.

**Root cause (code):** `WeeklyStorage` silently fell back to JSON and accepted **0-row Supabase PATCHes**. That allowed player snapshots to be inserted while the weekly run row never became an official `COMPLETED`/`PARTIAL` row with `homepage_payload`. Homepage activation correctly requires an official completed run — history alone must not activate.

**Fix on this branch:**
- Fail-closed Supabase writes when configured (`create_run` / `update_run` / `persist_run_results`)
- Refuse player snapshot inserts unless the run row patch updates ≥1 row
- Read path filters official runs in Python; requires `homepage_payload`
- API payload exposes `available` / `activation` / `data_source`

**Production data note:** Existing orphaned NFL history rows will still not activate homepage until a new official COMPLETED weekly run is generated after deploy (do not fabricate).

---

## 5. NBA readiness

Keep **NBA Coming Soon** in production until:
1. Verified previous-season data is seeded in Supabase  
2. An official COMPLETED weekly snapshot is persisted with homepage payload  
3. `/api/weekly/latest?league=NBA` returns `activation=ACTIVE`

Fixture contract tests cover the NBA path without inserting placeholder production intelligence.

---

## 6. Recommended merge strategy

1. **Open this combined PR** (superseding release PR).  
2. **Close / supersede PR #54 and PR #55** as superseded by the combined PR (do not merge them independently).  
3. Review + green tests on the combined PR.  
4. **Do not deploy** until reviewers accept the weekly homepage fix and smoke checklist is ready.  
5. After merge to `main`, deploy web + both crons together; run smoke checklist; only then mark NFL homepage active if `/api/weekly/latest?league=NFL` is ACTIVE.

---

## 7. PASS / FAIL (combined branch readiness vs production)

| Area | Combined branch code | Live production (pre-deploy) |
|---|---|---|
| MLB | **PASS** (entry point + schedule) | **PARTIAL PASS** (leaderboard OK; weekly homepage empty) |
| NFL | **PASS** (contract tests); activation needs post-deploy official run | **FAIL** (homepage inactive; orphan history) |
| NBA | **PASS** (fixture contract); keep Coming Soon in prod | **FAIL / Coming Soon** (correctly inactive) |
| Storage contract | **PASS** (fail-closed when Supabase configured) | **FAIL** until deploy |
| API fail-closed | **PASS** | **FAIL** until deploy |
| Homepage weekly activation | **PASS** (tests); prod needs new COMPLETED run | **FAIL** |

---

## 8. Production smoke-test checklist (post-deploy — do not run as deploy gate yet)

- [ ] `GET /health` → `data_source=supabase` (not `file`)
- [ ] `GET /api/leaderboard/latest` → `data_source=supabase`, non-empty MLB items
- [ ] Trigger or wait for Tuesday weekly cron (or admin weekly run for NFL only)
- [ ] Confirm NFL weekly run row `status=COMPLETED` and `homepage_payload` present
- [ ] `GET /api/weekly/latest?league=NFL` → `available=true`, `activation=ACTIVE`, non-empty `todays_leaders` / homepage
- [ ] `GET /api/players/CS-NFL-P-…/signals/weekly` → history for that same `run_id`
- [ ] `GET /api/weekly/latest?league=NBA` → `activation=INACTIVE` until seeded (Coming Soon)
- [ ] Confirm Render services: only `cardchase-ai-mlb-pipeline-cron` + `cardchase-ai-weekly-pipeline-cron` (+ web); no Actions cron
- [ ] Confirm no API response serves `data_source=file` while Supabase env vars are set

---

## 9. Test results (this branch)

| Suite | Result |
|---|---|
| All Python `tests/test_*.py` | **185 passed** |
| All JS `tests/test_*.js` | **capability + homepage + scouting + movement — all passed** (6+13+12+13+10) |
| `tests.test_weekly_homepage_contract` | **5 passed** (NFL + NBA fixtures + orphan refusal) |
| `tests.test_api_storage_contract` | **3 passed** |
| `tests.test_backend_architecture` | **24 passed** |
