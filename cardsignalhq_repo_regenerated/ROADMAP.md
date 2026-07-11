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

- **Release v0.10.3 — Sprint 9.1A Data Integrity**
  - [x] Centralized player stat field mapping (display label, source field, formatter, pending label)
  - [x] Last 7 Days populated only from stored `stats_7d` — no derived strikeout rate
  - [x] Season Snapshot populated only from stored `stats_30d` — no cross-fallback
  - [x] Missing metrics display `Pending` with optional tooltip
  - [x] Validation guards: AVG≠OPS, Runs≠Hits, WAR never synthesized
  - [ ] Verification pass pending — do not merge or deploy

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

## Current Milestone

### Release v0.10.3 — Sprint 9.1A Data Integrity

In progress. Do not merge or deploy until verification pass.

**Scouting Report** player statistics must come only from trusted stored sources:

- Centralized field mapping for every displayed stat (label, source, formatter, pending copy)
- Last 7 Days from `stats_7d`; Season Snapshot from `stats_30d` — no cross-fallback
- Missing values display `Pending` — never `—`, `0`, season proxies, or derived substitutes
- Validation guards prevent AVG←OPS, Runs←Hits, and synthesized WAR

### Release v0.10.2 — Scouting Report 2.0

Shipped. Scouting Report editorial layout and pending-state foundation.

### Release v0.9.0 — Weekly Intelligence Pipeline

Shipped in prior release. Verification pass complete for weekly pipeline foundation.

**Beta schedule (documented, idempotent guard):** Tuesday 6:00 AM America/New_York via external scheduler calling `POST /api/weekly/run` with admin token.

## Up Next

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
