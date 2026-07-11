# CardSignal — Roadmap

## Shipped

### Foundation (Sprints 1–3)

- MLB pipeline, hotness scoring, FastAPI layer, Supabase persistence
- Static frontend dashboard with leaderboard and player detail
- Chart.js score history and market activity charts
- Auth, watchlists, alerts, notifications, admin tools

### Visual & Search (Sprints 4.x)

- Player headshots and team logos from backend fields
- Universal Player Search (leaderboard + backend MLB pool)
- Backend `GET /api/players/search`
- Search polish: keyboard navigation, Top 20 badges, debounced backend lookup

### Signal Center (Sprints 5–6)

- **Sprint 5** — CardSignal Intelligence: score breakdown, recommendation, conviction, premium card sections
- **Sprint 6.1** — Signal of the Week hero banner
- **Sprint 6.2** — Signal Center dashboard polish (Market Pulse, featured signals, unified intel rows)
- **Sprint 6.3** — Landing page cleanup (compact banner, card intelligence grid)
- **Sprint 6.4** — Homepage redesign (Featured Signal, Quick Intelligence, Today's Leaders centerpiece)
- **Sprint 6.5** — Signal Center polish pass (BETA badge, section descriptions, recommendation/conviction badges)

### Player Intelligence Modal (Sprint 7.x)

- **Sprint 7.1** — Player Intelligence modal complete (backdrop, header, tab shell, open/close UX, mobile drawer)
- **Release v0.8.0** — Player Intelligence Report complete (placeholder beta):
  - [x] **Overview** — score, recommendation, conviction, movement, status, breakdown, why-it-matters
  - [x] **Cards** — player-specific trending, movers, buy-low, most-chased sections
  - [x] **Market** — placeholder sale volume, listings, liquidity, summary
  - [x] **Signals** — performance, market, collector demand, momentum explanations
  - [x] **Forecast** — recommendation, conviction, horizon, risk, summary, bullet reasons

### Scouting Report 2.0 (Sprint 9.x)

- **Release v0.10.2 — Scouting Report 2.0**
  - [x] Single-page editorial report replacing tabbed modal
  - [x] Player Snapshot (Last 7 Days + Season Snapshot from stored stats)
  - [x] Why This Signal contributors from real evidence
  - [x] Cards section with stored card intelligence or pending states
  - [x] Market research panel from stored snapshots
  - [x] Signal Analysis (Performance, Market, Momentum, Scarcity, Collector Demand)
  - [x] CardSignal Outlook with Evidence (replaces Conviction/Confidence)
  - [x] No fabricated report data — pending states when intelligence unavailable

### Real Card Intelligence (Sprint 8.x)

- **Sprint 8.7 — partial in this branch**
  - [x] eBay market snapshots in manual pipeline
  - [x] Card intelligence synthesis from stored eBay query templates
  - [ ] Card registry (not present in this branch)
  - [ ] PSA population provider/integration (not present; optional stage interface only)
  - [x] Historical market movement foundation (stored snapshot comparison; no live provider reads on GET)

- **Sprint 8.8 — Weekly Intelligence Pipeline**
  - [x] Weekly orchestration layer for Tuesday refresh
  - [x] Top 100 MLB beta universe
  - [x] Append-only player/card weekly snapshots
  - [x] Signal of the Week selection with evidence requirements
  - [x] Today's Leaders from latest completed official run
  - [x] Explicit stage outcomes with FAILED / PARTIAL / SKIPPED / UNAVAILABLE handling
  - [x] `GET /api/weekly/latest`, weekly history endpoints
  - [x] Admin `POST /api/weekly/run` with duplicate guard and force option
  - [x] Local JSON fallback when Supabase is unavailable

### Beta Readiness (Sprint 10.x)

- **Sprint 10.0 — Signal Center Integration** *(complete)*
  - [x] Homepage Signal Center redesign integrated with Scouting Report 2.0
  - [x] Weekly intelligence wired into Featured Signal and Today's Leaders

- **Release v0.14.1 — Sprint 10.1 Beta Readiness Audit** *(complete — verification pass pending)*
  - [x] Internal beta-readiness audit (`scripts/run_beta_readiness_audit.py`, `GET /api/admin/beta-readiness`)
  - [x] Beta Feedback button, modal, and `POST /api/beta-feedback`
  - [x] `beta_feedback` Supabase table with private RLS
  - [x] Version/build footer and beta changelog
  - [x] Hash routing for Scouting Report and Card Report deep links
  - [x] Browser back/forward modal state restoration
  - [x] Safe error rendering and dead placeholder code removal
  - [x] `BETA_CHECKLIST.md` closed-beta quality gates

## Current Milestone

### Release v0.14.1 — Closed Beta Readiness

Verification pass pending. Do not merge or deploy until checklist is green.

## Up Next

### Sprint 10.2 — NBA Performance Adapter

- NBA performance data adapter foundation
- League-specific reporting period rules
- No collector invites for NBA until real data is verified

### Closed Beta Launch Checklist

- Apply `BETA_CHECKLIST.md` gates in staging
- Privacy / Terms pages
- Closed-beta invite workflow
- Onboarding guide for first-time collectors

### Beta Feedback Review

- Admin triage workflow for `beta_feedback` submissions
- Status transitions: NEW → REVIEWED → PLANNED → CLOSED

### Product Analytics

- Instrument key collector flows (search, report views, feedback)

### Privacy / Terms

- Collector-facing privacy policy and terms of use

### Support Workflow

- Documented path from feedback → engineering → release notes

### v0.9.1 — Production QA and Data Seeding

- End-to-end weekly run verification in staging
- Seed historical weekly snapshots for chart coverage
- Supabase migration apply + rollback test
- PSA population provider implementation (when credentials/source available)

### v1.0.0 — Multi-Sport Expansion

- Enable NBA, NFL, NHL sport tabs with real data
- Sport-specific leaderboards and scoring adjustments
- Cross-sport Signal Center filters

### v1.1.0 — Collection & Alerts UX

- Activate product nav items: My Collection, Alerts, Settings
- Push notification delivery improvements
- Email template polish and digest scheduling

## Future

- **Card registry** — canonical card identity layer for player-linked intelligence
- **PSA population integration** — wired through `PopulationProvider` when available
- **Tuesday email report** — weekly digest from stored homepage intelligence
- **Signal Vault** — searchable archive of weekly signals and card intelligence
- **Weekly push notifications** — Signal of the Week and mover alerts
- **NFL weekly period support** — Thursday–Monday reporting windows
- **NBA weekly period support** — league-specific period rules
- **Signal Accuracy tracking** — compare weekly forecasts to outcomes
- Sold-comps integration beyond active eBay listings
- Portfolio tracking and cost-basis views
- Mobile-native app or PWA
- Premium subscription tier for advanced forecasts

## Release Rules

1. Read `PRODUCT.md`, `DESIGN_SYSTEM.md`, and this roadmap before each release
2. Scope frontend-only work to allowed files unless backend changes are explicitly approved
3. Do not merge or deploy without verification pass
4. Homepage sections must remain intact during modal and report releases
5. Use feature branches with PR review; no direct pushes to main for release work
