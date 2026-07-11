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

- **Sprint 9.2 — Real Card Intelligence & Weekly Pipeline** *(complete)*
  - [x] eBay market snapshots in manual pipeline
  - [x] Card intelligence synthesis from stored eBay query templates
  - [x] Historical market movement foundation (stored snapshot comparison; no live provider reads on GET)
  - [x] Weekly intelligence orchestration layer for Tuesday refresh
  - [x] Top 100 MLB beta universe
  - [x] Append-only player/card weekly snapshots
  - [x] Signal of the Week selection with evidence requirements
  - [x] Today's Leaders from latest completed official run
  - [x] `GET /api/weekly/latest`, weekly history endpoints
  - [x] Admin `POST /api/weekly/run` with duplicate guard and force option
  - [x] Local JSON fallback when Supabase is unavailable

### Signal Drivers & Seasonal Intelligence (Sprint 9.3)

- **Release v0.11.1 — Signal Drivers & Seasonal Intelligence** *(complete)*
  - [x] Reusable Signal Driver model with impact, evidence quality, timestamps, and source types
  - [x] Sport-season state model (REGULAR_SEASON, POSTSEASON, PRESEASON, OFFSEASON, INACTIVE, UNKNOWN)
  - [x] MLB performance drivers from stored 7d/30d statistics only
  - [x] Market and scarcity drivers from stored snapshots
  - [x] Provider-neutral `PlayerDevelopmentProvider` interface (manual verified, approved import, official API)
  - [x] Append-only Signal Driver storage with duplicate prevention (Supabase + JSON fallback)
  - [x] `GET /api/players/{player_id}/signal-drivers` read-only endpoint
  - [x] Admin-protected development ingestion endpoint
  - [x] Scouting Report Signal Drivers section replacing Why This Signal
  - [x] Season-aware Player Snapshot (active season vs offseason vs preseason layouts)
  - [x] Multi-sport foundation (NBA/NFL adapters prepared, MLB active)
  - [x] Future-compatible score-to-driver relationship fields on weekly snapshots
  - [x] No fabricated NBA/NFL/legacy intelligence

## Current Milestone

### Release v0.11.1 — Signal Drivers & Seasonal Intelligence

Complete. Do not merge or deploy until verification pass.

**Signal Drivers** explain why a player's CardSignal Score matters right now:

- Stored evidence only — performance, market, career/team developments
- Season-aware Scouting Report layouts for active season, offseason, and preseason
- Evidence quality and source-type labels on every driver card
- Honest empty states when no verified drivers exist

## Up Next

### Sprint 9.4 — NFL Performance Adapter

- NFL season metadata from stored schedule
- Recent 3-game performance window
- Season totals/averages drivers
- Offseason developments, training camp, depth-chart and contract changes
- No fabricated NFL players or statistics until real data is stored

### Sprint 9.5 — NBA Performance Adapter

- NBA season metadata from stored schedule
- Recent 5-game performance window
- Season averages drivers
- Playoffs, offseason developments, trades, contracts, Summer League
- No fabricated NBA players or statistics until real data is stored

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

- **Legacy Intelligence** — retired hobby pillars (Michael Jordan, Ken Griffey Jr., Kobe Bryant, Tom Brady, and others) using card-market activity, auction results, sales history, PSA population, scarcity, set anniversaries, Hall of Fame and milestone events, documentaries, major product releases, and historic performance context — never fake recent performance statistics
- **Development/news provider integration** — wire approved news and official APIs through `PlayerDevelopmentProvider`
- **Signal Driver alerts** — notify collectors when verified developments affect watched players
- **Signal Driver history** — searchable archive of past drivers and seasonal context
- **Offseason market reports** — curated market intelligence during league off-seasons
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
