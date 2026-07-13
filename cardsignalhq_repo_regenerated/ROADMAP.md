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

- **Release v0.10.2 — Scouting Report 2.0** — single-page editorial report, evidence tier, real stored intelligence only

### Real Card Intelligence (Sprint 8.x)

- **Sprint 8.8 — Weekly Intelligence Pipeline** — Tuesday refresh, append-only snapshots, Signal of the Week, Today's Leaders

### Multi-Sport Adapters (Sprint 9.x–11.x)

- **Sprint 9.4 — NFL Performance Adapter** *(complete)*
  - [x] Provider-neutral `NFLPerformanceProvider` interface
  - [x] Approved import path (`output/nfl/import/nfl_data.json`)
  - [x] Deterministic NFL identity (`CS-NFL-P-{SOURCE_PLAYER_ID}`)
  - [x] Position-aware scoring with `NFL_PERFORMANCE_V1`
  - [x] NFL Signal Drivers, weekly pipeline, API routes, Scouting Report integration

- **Release v0.16.0 — Sprint 11.1 NBA Performance Adapter** *(complete)*
  - [x] Sport Adapter Framework contracts (`SportAdapter`, `LeagueAdapter`, `PerformanceAdapter`, `SeasonAdapter`, `SignalDriverAdapter`)
  - [x] Provider-neutral `NBAPerformanceProvider` interface
  - [x] Approved import path (`output/nba/import/nba_data.json`)
  - [x] Deterministic NBA identity (`CS-NBA-P-{STABLE_SOURCE_PLAYER_ID}`)
  - [x] Supported positions PG/SG/SF/PF/C; unknown → `INSUFFICIENT`
  - [x] Recent window metadata (`COMPLETED_GAMES`, value 5)
  - [x] `NBA_PERFORMANCE_V1` scoring from stored basketball stats only
  - [x] `NBA_PLAYER_SIGNAL_V1` CardSignal player signal (market + collector + scarcity + drivers)
  - [x] NBA Signal Drivers from stored evidence only
  - [x] NBA weekly pipeline stage (Mon–Sun period)
  - [x] NBA API routes (`/api/nba/players/search`, leaderboard, player, performance, signal-drivers, status)
  - [x] Universal Search NBA registration when data exists
  - [x] NBA Scouting Report (Recent 5 Games: PPG, RPG, APG, SPG, BPG, FG%, 3PT%, FT%, MPG)
  - [x] Homepage NBA activation only when genuine weekly data exists

- **Release v0.16.1 — Sprint 11.2 League Intelligence Convergence** *(verification pass pending)*
  - [x] Normalized `PlayerIntelligencePayload` contract
  - [x] Explicit capability declarations per league
  - [x] Structured performance evidence in weekly snapshots
  - [x] MLB Signal Drivers from stored evidence
  - [x] NFL momentum/status/market convergence without baseball assumptions
  - [x] Shared intelligence serializer + `GET /api/players/{league}/{player_id}/intelligence`

NBA remains **Coming Soon** in the UI until verified import data is seeded.

## Current Milestone

### Release v0.16.1 — Sprint 11.2 League Intelligence Convergence

- [x] Normalized `PlayerIntelligencePayload` contract for MLB and NFL
- [x] Explicit league capability declarations (`SUPPORTED` / `UNAVAILABLE` / `PENDING` / `DISABLED`)
- [x] Structured performance evidence persisted in weekly snapshots
- [x] MLB Signal Drivers from stored performance evidence
- [x] NFL momentum from prior official snapshots only; league-neutral status labels
- [x] Shared intelligence serializer for homepage, Scouting Report, and API
- [x] `GET /api/players/{league}/{player_id}/intelligence` read-only endpoint
- [ ] Verification pass pending — do not merge or deploy until tests pass

## Up Next

### Sprint 11.3 — Cross-Sport Signal Center

- Unified cross-sport leaderboards and filters in Signal Center
- Cross-sport Signal of the Week selection rules
- Sport-aware homepage sections when multiple leagues are active
- Cross-sport universal search ranking polish
- Builds on normalized league intelligence from Sprint 11.2

### v0.9.1 — Production QA and Data Seeding

- End-to-end weekly run verification in staging
- Seed historical weekly snapshots for chart coverage
- Seed verified NFL and NBA import data for beta universe activation

### v1.0.0 — Multi-Sport Expansion

- Enable NHL sport tab with live data
- Sport-specific leaderboards and scoring adjustments
- Cross-sport Signal Center filters (builds on Sprint 11.2)

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
