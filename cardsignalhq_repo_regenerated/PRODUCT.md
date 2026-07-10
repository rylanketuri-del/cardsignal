# CardSignal — Product Overview

CardSignal is market intelligence for modern sports-card collectors. The product combines player performance signals, collector demand indicators, and card-market activity into a single **CardSignal Score** that helps collectors decide what to watch, buy, hold, or sell.

## Product Architecture

### Signal Center (Homepage)

The homepage is the **Signal Center** — a market-wide overview dashboard.

Primary sections:

- **Universal Search** — find any MLB player; leaderboard players show scores, others show search results from the backend player pool
- **Featured Signal (Signal of the Week)** — editorial hero highlighting the top signal with score, weekly movement, recommendation pill, and View Report CTA
- **Card Intelligence** — market-wide card sections: Trending Cards, Biggest Movers, Buy Low Watch, Most Chased
- **Today's Leaders** — ranked table of tracked players with signal, performance, market, trend, and View Report action
- **Signal Timeline** — selected player score history chart
- **Market Activity** — leaderboard trend chart
- **Account / Collection / Alerts / Notifications** — authenticated user layer

Global **BETA Early Access** badge is visible in the header.

### Scouting Report (Player Modal)

The player modal is a **premium Scouting Report** — where collectors understand why CardSignal made its recommendation. It opens from:

- Today's Leaders row click
- Signal of the Week View Report CTA
- Universal Search result selection

Report sections (scrollable, editorial layout):

| Section | Purpose |
|---------|---------|
| **Header** | Player, team, position, CardSignal Score, recommendation, status, updated timestamp, algorithm version |
| **Player Snapshot** | Last 7 Days and Season Snapshot from stored MLB stats |
| **Why This Signal** | Signal contributors explaining score changes from real evidence |
| **Cards** | Player-linked card intelligence with pricing, movement, listings, PSA population when available |
| **Market** | Research-style market summary from stored eBay snapshots |
| **Signal Analysis** | Performance, Market, Momentum, Scarcity, Collector Demand with scores and evidence quality |
| **Outlook** | Recommendation, Evidence, Risk, Time Horizon, and analyst summary |

Report UX:

- Dark backdrop; homepage (Signal Center) remains visible behind
- Close via X, Escape, or backdrop click
- Centered panel on desktop; full-screen drawer on mobile
- Body scroll locked while open
- Uses only real stored intelligence or honest pending states — no fabricated report data

## CardSignal Score

The CardSignal Score (0–100) blends:

- **Performance** — recent on-field production
- **Market** — card-market pricing and listing activity
- **Collector Demand** — chase pressure and buyer interest
- **Momentum** — directional trend across inputs

Each player also receives:

- **Recommendation** — BUY / HOLD / SELL / WATCH (derived from evidence tier and score)
- **Evidence** — HIGH / MEDIUM / LOW / INSUFFICIENT (replaces legacy Conviction/Confidence in the Scouting Report)
- **Status** — HOT / RISING / COOLING

Forecast language uses tentative phrasing (“suggests,” “may,” “could”) and never implies guaranteed returns.

## Data Sources

Current production scope:

- **MLB hitters only** (NBA, NFL, NHL tabs shown as coming soon)
- MLB Stats API for performance
- eBay Browse API for active listings
- Supabase for leaderboard persistence, auth, watchlists, alerts, and notifications

Placeholder intelligence (card rows, market metrics, forecast reasons) uses stable seeded values when backend fields are missing. Live card-market snapshots will replace placeholders in a future release.

## Weekly Intelligence Principles

CardSignal refreshes market-wide intelligence **weekly on Tuesdays at 6:00 AM America/New_York** (beta schedule).

- **Reporting period (MLB/NBA beta):** Monday 12:00 AM through Sunday 11:59 PM in the league timezone
- **NFL (future):** Thursday through Monday — period rules are configurable per league
- **Append-only snapshots:** player weekly signals and card weekly intelligence are never overwritten
- **Latest completed run:** remains available if a new run fails or is skipped
- **Signal of the Week:** selected only from players with sufficient real evidence — no random recommendations
- **No fabricated weekly data:** null scores stay null; WATCH fallback is valid when evidence is insufficient
- **Algorithm versioning:** `WEEKLY_INTELLIGENCE_V1` is stored on every run, snapshot, and Signal of the Week record
- **Beta scope:** Top 100 MLB players from dynamic candidate logic; universal search remains available for players outside the universe

GET routes serve stored weekly intelligence only — they never trigger provider work.

## User Layers

- **Anonymous** — browse Signal Center, search players, open Intelligence Reports
- **Authenticated** — save watchlist players, configure alert preferences, per-player alert rules, notification center
- **Admin** — hidden from public UI; protected by admin token for settings and tracked-player management

## Release Principles

- Homepage = Signal Center / market-wide overview
- Player modal = Intelligence Report / one-player deep dive
- Frontend-only releases must not modify backend files unless explicitly scoped
- No new dependencies without approval
- Preserve existing homepage sections during modal and report releases
