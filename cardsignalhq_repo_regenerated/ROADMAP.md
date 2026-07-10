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

### Player Card Registry (Sprint 8.x)

- **Release v0.9.0** — Player Card Registry (Sprint 8.1):
  - [x] Per-player card registry with realistic MLB product entries
  - [x] Reusable pricing enrichment helpers for future eBay/PSA integration
  - [x] Cards tab displays year, set, parallel, estimated price, movement, CardSignal mini-score
  - [x] Homepage intelligence rows use real card product names

- **Sprint 8.2** — CardSignal Identity Foundation (Release v0.9.0):
  - [x] Deterministic CardSignal IDs for players, cards, weekly signals, and forecasts
  - [x] Shared identity helpers in backend and frontend
  - [x] Player model fields: `cs_player_id`, `source_player_id`, `league`, `sport`, `player_name`
  - [x] Card registry extended with `cs_card_id` and normalized identity fields
  - [x] Relationship model documented for future market and population snapshots

- **Sprint 8.3** — eBay Market Snapshot Foundation (Release v0.9.0):
  - [x] Reusable `CardMarketSnapshot` model for active listing observations
  - [x] Deterministic registry card search queries and eBay listing normalization
  - [x] Isolated card-market snapshot pipeline step with beta cost controls
  - [x] Append-only Supabase persistence and local JSON fallback
  - [x] `GET /api/cards/{cs_card_id}/market/latest` read endpoint

- **Sprint 8.4** — Real Card Market UI (Release v0.9.0):
  - [x] `GET /api/players/{player_id}/cards/market/latest` player-level snapshot endpoint
  - [x] Cards tab surfaces real active-listing metrics per registry card
  - [x] Market tab aggregates player-level listing depth and bid activity
  - [x] Data-quality badges, active-listing disclaimers, and captured timestamps
  - [x] Session cache for card-market fetches; graceful loading/empty/error states

- **Sprint 8.5** — Historical Price Movement (Release v0.9.0):
  - [x] Reusable `CardMarketMovement` model with comparison windows (`previous`, `7d`, `30d`)
  - [x] Append-only local history file plus Supabase history reads/indexes
  - [x] `GET /api/cards/{cs_card_id}/market/history` and `/market/movement`
  - [x] `GET /api/players/{player_id}/cards/market/movement` and `/market/activity`
  - [x] Cards tab 7-day active listing movement when history exists
  - [x] Biggest Movers ranked by valid median movement quality
  - [x] Market Activity chart wired to stored player snapshot history
  - [x] Signal Timeline uses stored player score history when available

## Current Milestone

### Sprint 8 — Real Card Intelligence

- **Sprint 8.1** — Player Card Registry (Release v0.9.0) — complete
- **Sprint 8.2** — Foundation & Identity (Release v0.9.0) — complete
- **Sprint 8.3** — eBay Market Snapshot Foundation (Release v0.9.0) — complete
- **Sprint 8.4** — Real Card Market UI (Release v0.9.0) — complete
- **Sprint 8.5** — Historical Price Movement (Release v0.9.0) — complete

## Up Next

### Sprint 8.6 — PSA Population Foundation

- PSA population snapshots linked to `cs_card_id`
- Population-aware collector demand inputs

### Future Sprint 8+ Work

- Sold-comps integration
- Buy Low Engine
- Signal Accuracy tracking
- Weekly snapshot scheduler

### v1.0.0 — Multi-Sport Expansion

- Enable NBA, NFL, NHL sport tabs
- Sport-specific leaderboards and scoring adjustments
- Cross-sport Signal Center filters

### v1.1.0 — Collection & Alerts UX

- Activate product nav items: My Collection, Alerts, Settings
- Push notification delivery improvements
- Email template polish and digest scheduling

### Future

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
