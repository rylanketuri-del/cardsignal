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

- **Sprint 8.8 — Weekly Intelligence Pipeline** *(in progress — verification pass pending)*
  - Weekly orchestration layer for Tuesday refresh
  - Top 100 MLB beta universe
  - Append-only player/card weekly snapshots
  - Signal of the Week selection with evidence requirements
  - Today's Leaders from latest completed official run
  - Explicit stage outcomes with FAILED / PARTIAL / SKIPPED / UNAVAILABLE handling
  - `GET /api/weekly/latest`, weekly history endpoints
  - Admin `POST /api/weekly/run` with duplicate guard and force option
  - Local JSON fallback when Supabase is unavailable

### Data Confidence & Explainability (Sprint 10.0)

- **Release v0.14.0 — Data Confidence Layer**
  - [x] Reusable `DataConfidence` model (`DATA_CONFIDENCE_V1`)
  - [x] Confidence levels: VERY_HIGH, HIGH, MEDIUM, LOW, INSUFFICIENT — independent of recommendations
  - [x] Freshness buckets: LIVE, RECENT, CURRENT, STALE, UNKNOWN
  - [x] Explainability categories with available / missing / pending states
  - [x] Honest missing-input explanations from stored gaps only
  - [x] `GET /api/confidence/player/{id}` and `GET /api/confidence/card/{id}` (read-only)
  - [x] Scouting Report + Card Report headers: Evidence, Freshness, Updated
  - [x] Expandable “Why this report?” trust section
  - [x] No proprietary scoring weights exposed

## Current Milestone

### Release v0.14.0 — Data Confidence & Explainability

Shipped in this branch. Do not merge or deploy until verification pass.

**Data Confidence Layer** introduces transparent evidence quality across player and card reports:

- Evidence and freshness badges in report headers
- Trust section summarizing verified snapshots and honest gaps
- Confidence computed from stored signals only — never from BUY/HOLD/SELL
- API endpoints for programmatic confidence access

## Up Next

### Sprint 10.1 — NBA Performance Adapter

- NBA stats client and performance scoring adapter
- League-specific reporting period rules for NBA beta
- NBA player universe for weekly intelligence

### v0.9.1 — Production QA and Data Seeding

- End-to-end weekly run verification in staging
- Seed historical weekly snapshots for chart coverage
- Supabase migration apply + rollback test
- PSA population provider implementation (when credentials/source available)

### v1.0.0 — Multi-Sport Expansion

- Enable NBA, NFL, NHL sport tabs
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
