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

- **Sprint 9.3 — Scouting Report data integrity** *(complete)*
  - [x] Centralized metric mapping with pending states
  - [x] No proxy fallbacks in Scouting Report metrics
  - [x] Evidence tier replaces conviction in report UX

## Current Milestone

### Release v0.12.0 — Sprint 9.4 NFL Performance Adapter

In progress. Do not merge or deploy until verification pass.

- [x] Provider-neutral `NFLPerformanceProvider` interface
- [x] Approved import path (`output/nfl/import/nfl_data.json`)
- [x] Deterministic NFL identity (`CS-NFL-P-{SOURCE_PLAYER_ID}`)
- [x] Position-aware scoring (QB, RB, WR, TE) with `NFL_PERFORMANCE_V1`
- [x] Recent 3-game window with bye-week and inactive-game handling
- [x] NFL Signal Drivers from stored evidence only
- [x] NFL weekly pipeline stage (independent from MLB; Thu–Mon period)
- [x] NFL API routes (`/api/nfl/players/search`, leaderboard, player, performance, signal-drivers)
- [x] Universal Search NFL integration when registry exists
- [x] NFL homepage activation only when genuine weekly data exists
- [x] NFL Scouting Report position-aware stat specs
- [ ] End-to-end verification with live approved import data

NFL remains **Coming Soon** in the UI until verified import data is seeded.

## Up Next

### Sprint 9.5 — NBA Performance Adapter

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
- **NBA weekly period support** — league-specific period rules
- **NFL defensive-player intelligence** — separate scoring model for defensive players
- **NFL rookie/draft intelligence** — draft class and rookie card relevance
- **NFL training-camp provider** — verified role developments
- **NFL depth-chart provider** — starter/backup role tracking
- **NFL playoff weighting** — postseason performance emphasis
- **NFL legacy intelligence** — retired-player archive (separate from active universe)
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
