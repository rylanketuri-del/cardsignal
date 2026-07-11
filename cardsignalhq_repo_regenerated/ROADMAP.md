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
- **Release v0.8.0** — Player Intelligence Report complete (placeholder beta)

### Scouting Report 2.0 (Sprint 9.x)

- **Release v0.10.2 — Scouting Report 2.0**
  - [x] Single-page editorial report replacing tabbed modal
  - [x] Player Snapshot (Last 7 Days + Season Snapshot from stored stats)
  - [x] Signal Drivers from real evidence
  - [x] Cards section with stored card intelligence or pending states
  - [x] Market research panel from stored snapshots
  - [x] Signal Analysis (Performance, Market, Momentum, Scarcity, Collector Demand)
  - [x] Outlook with Evidence (replaces Conviction/Confidence)
  - [x] No fabricated report data — pending states when intelligence unavailable

- **Sprint 9.3 — Scouting Report data integrity** *(complete)*
  - [x] Centralized metric mapping with pending states
  - [x] No proxy fallbacks in Scouting Report metrics
  - [x] Evidence tier replaces conviction in report UX

- **Release v0.12.0 — Sprint 9.4 NFL Performance Adapter** *(complete)*
  - [x] Provider-neutral `NFLPerformanceProvider` interface
  - [x] Position-aware scoring (QB, RB, WR, TE) with `NFL_PERFORMANCE_V1`
  - [x] Recent 3-game window with bye-week and inactive-game handling
  - [x] NFL Signal Drivers from stored evidence only
  - [x] NFL API routes and Universal Search integration when registry exists
  - [x] NFL Scouting Report position-aware stat specs

- **Release v0.13.0 — Card Report Foundation (Sprint 9.5)** *(complete)*
  - [x] `CardReport` model with card identity, score, market, population, price history, drivers
  - [x] Read-only API: `GET /api/cards/{cs_card_id}`, `/history`, `/market`, `/drivers`
  - [x] CardReportRouter with deep linking at `/cards/{cs_card_id}`
  - [x] Premium Card Report UI reusing design system and Card Registry formatting

- **Release v0.13.1 — Card Intelligence Ranking (Sprint 9.6)** *(complete)*
  - [x] Cards ranked by stored CardSignal Card Score within player Scouting Reports
  - [x] Top Pick badge and comparison row (CardSignal Card Score, Recommendation, Evidence)
  - [x] View Card Report action on every ranked card

- **Release v0.13.2 — Collector Experience Polish (Sprint 9.7)** *(complete in this branch)*
  - [x] Consistent Scouting Report section order across MLB and NFL
  - [x] Signal Drivers terminology and collector-friendly pending states
  - [x] Card row consistency: Card Identity, CardSignal Card Score, Recommendation, Evidence, View Card Report
  - [x] Card Report identity, Market Snapshot, and Evidence polish
  - [x] Informative error states — no stack traces or raw JSON
  - [x] Typography hierarchy, spacing, responsive, and accessibility improvements

### Real Card Intelligence (Sprint 8.x)

- **Sprint 8.7 — partial**
  - [x] eBay market snapshots in manual pipeline
  - [x] Card intelligence synthesis from stored eBay query templates
  - [x] Historical market movement foundation

- **Sprint 8.8 — Weekly Intelligence Pipeline** *(complete)*
  - [x] Weekly orchestration layer for Tuesday refresh
  - [x] Top 100 MLB beta universe
  - [x] Append-only player/card weekly snapshots
  - [x] Signal of the Week selection with evidence requirements
  - [x] Today's Leaders from latest completed official run

## Current Milestone

### Release v0.13.2 — Collector Experience Polish (Sprint 9.7)

Complete in this branch. Do not merge or deploy until verification pass.

Polish pass for MLB and NFL collector experience — clarity, consistency, and trust:

- Scouting Report section order: Header → Player Snapshot → Signal Drivers → Cards → Market → Signal Analysis → Outlook
- Card rows show Card Identity, CardSignal Card Score, Recommendation, Evidence, View Card Report
- Card Report pending states explain why data is unavailable
- Standardized copy: CardSignal Score, CardSignal Card Score, Evidence, Signal Drivers, Scouting Report, Card Report, Market Snapshot, Recommendation
- No scoring changes, no fabricated data, homepage unchanged

## Up Next

### Sprint 10.0 — NBA Performance Adapter

- Provider-neutral NBA performance interface
- NBA season phases and position-aware scoring
- NBA weekly period rules
- NBA Universal Search and Scouting Report integration

### v0.9.1 — Production QA and Data Seeding

- End-to-end weekly run verification in staging
- Seed historical weekly snapshots for chart coverage
- Supabase migration apply + rollback test
- PSA population provider implementation (when credentials/source available)
- Seed verified NFL import data for beta universe activation

### v1.0.0 — Multi-Sport Expansion

- Enable NBA, NFL, NHL sport tabs with live data
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
- **NFL defensive-player intelligence** — separate scoring model for defensive players
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
