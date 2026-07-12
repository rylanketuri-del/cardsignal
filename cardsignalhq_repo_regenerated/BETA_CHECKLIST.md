# CardSignal — Beta Checklist

Closed-beta readiness criteria. Mark items only when verified in staging with real data.

## Data Integrity

- [x] **MLB real data** — production MLB Stats API and eBay snapshots; weekly pipeline live for Top 100 universe
- [ ] **NFL real data** — metadata and period rules registered; performance pipeline not yet live
- [ ] **NBA real data before collector invites** — not implemented; sport tab remains Coming Soon
- [x] **No fabricated intelligence** — null scores stay null; Scouting Report uses stored intelligence or honest pending states

## Reports & Registry

- [x] **Stable Scouting Reports** — single-page report from stored weekly signals and stats
- [x] **Stable Card Reports** — card intelligence from stored eBay snapshots or pending states
- [ ] **Stable Card Registry** — canonical card identity layer not yet shipped

## Signal Quality

- [x] **Evidence and freshness** — evidence tiers, missing-input tracking, weekly refresh schedule documented
- [x] **Algorithm versioning** — `WEEKLY_INTELLIGENCE_V1` orchestration version separate from league scoring-model versions (`MLB_PLAYER_SIGNAL_V1`, etc.)

## Product Surfaces

- [x] **Universal Search** — registered leagues via `GET /api/leagues`; generalized `GET /api/players/search`
- [x] **Mobile support** — responsive Signal Center and full-screen Scouting Report drawer
- [x] **Safe loading/empty/error states** — explicit pending and empty states; no fabricated fallback scores in reports

## Platform

- [ ] **Feedback submission** — not yet implemented
- [x] **Version/build visibility** — algorithm version shown in Scouting Report header
- [x] **Authentication** — Supabase auth for watchlists and alerts
- [x] **Watchlists** — save and manage tracked players
- [x] **Alerts** — in-app notifications and email delivery hooks
- [ ] **Privacy/terms** — legal pages not yet linked in product
- [ ] **Closed-beta invite workflow** — not yet implemented

## Architecture (Sprint 11.0)

- [x] **League adapter registry** — canonical source for season rules, reporting periods, recent windows, and search capability
- [ ] **NBA adapter** — not registered as live; do not invite NBA collectors until real data ships
