# CardSignal — Product Overview

CardSignal is market intelligence for modern sports-card collectors. The product combines player performance signals, collector demand indicators, and card-market activity into a single **CardSignal Score** that helps collectors decide what to watch, buy, hold, or sell.

## Product Architecture

### Signal Center (Homepage)

The homepage is the **Signal Center** — a market-wide overview dashboard.

Primary sections:

- **Universal Search** — find any MLB or NFL player; leaderboard players show scores, others show search results from the backend player pool
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

Scouting Reports explain **"Why is this player moving?"**

Report sections (scrollable, editorial layout — consistent order for MLB and NFL):

| Section | Purpose |
|---------|---------|
| **Header** | Player, team, position, CardSignal Score, Recommendation, status, updated timestamp, algorithm version |
| **Player Snapshot** | Last 7 Days / Recent 3 Games and Season Snapshot from stored stats |
| **Signal Drivers** | Verified performance and market evidence explaining score changes |
| **Cards** | Ranked player-linked cards with CardSignal Card Score, Recommendation, Evidence, View Card Report |
| **Market** | Research-style Market Snapshot from stored eBay snapshots |
| **Signal Analysis** | Performance, Market, Momentum, Scarcity, Collector Demand with scores and Evidence quality |
| **Outlook** | Recommendation, Evidence, Risk, Time Horizon, and analyst summary |

### Card Report (Individual Collectible)

Card Reports are the destination for an individual collectible. They explain **"Why is THIS card moving?"** — never conflated with player-level Scouting Reports.

Card Reports open from:

- Card Intelligence rows on the Signal Center homepage
- Cards section within a Scouting Report
- Deep link: `/cards/{cs_card_id}`

Report sections (scrollable, editorial layout):

| Section | Purpose |
|---------|---------|
| **Header** | Card identity, player link, CardSignal Card Score, Recommendation, Evidence, updated timestamp, algorithm version |
| **Card Identity** | Year, brand, set, parallel, card #, grade, grading company, serial number from Card Registry |
| **Card Snapshot** | Median/average price, active listings, population, sales activity, data quality from stored intelligence |
| **Price History** | Time series foundation (chart adapter pending) |
| **Market Drivers** | Card-level market signals — separate from player Signal Drivers |
| **Scarcity** | Population, serial number, parallel, print run, scarcity score |
| **Card Outlook** | Recommendation, Evidence, summary, and supporting factors |

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

- **Recommendation** — BUY / HOLD / SELL / WATCH (from stored weekly or card intelligence only)
- **Evidence** — HIGH / MEDIUM / LOW / INSUFFICIENT (replaces legacy Conviction/Confidence in the Scouting Report)
- **Status** — HOT / RISING / COOLING

Forecast language uses tentative phrasing (“suggests,” “may,” “could”) and never implies guaranteed returns.

## Data Sources

Current production scope:

- **MLB hitters** — MLB Stats API for performance
- **NFL (beta adapter):** approved import path; unavailable until verified data is seeded — no fabricated intelligence
- **NBA, NHL** — shown as coming soon
- eBay Browse API for active listings
- Supabase for leaderboard persistence, auth, watchlists, alerts, and notifications

Placeholder intelligence (card rows, market metrics, forecast reasons) uses stable seeded values when backend fields are missing. Live card-market snapshots will replace placeholders in a future release.

## Weekly Intelligence Principles

CardSignal refreshes market-wide intelligence **weekly on Tuesdays at 6:00 AM America/New_York** (beta schedule).

- **Reporting period (MLB/NBA beta):** Monday 12:00 AM through Sunday 11:59 PM in the league timezone
- **NFL:** Thursday through Monday — period rules are configurable per league; refresh target remains Tuesday morning
- **Append-only snapshots:** player weekly signals and card weekly intelligence are never overwritten
- **Latest completed run:** remains available if a new run fails or is skipped
- **Signal of the Week:** selected only from players with sufficient real evidence — no random recommendations
- **No fabricated weekly data:** null scores stay null; WATCH fallback is valid when evidence is insufficient
- **Algorithm versioning:** `WEEKLY_INTELLIGENCE_V1` is stored on every run, snapshot, and Signal of the Week record
- **Beta scope:** Top 100 MLB players from dynamic candidate logic; universal search remains available for players outside the universe

GET routes serve stored weekly intelligence only — they never trigger provider work.

## Card Intelligence Ranking Principles

Within a player's Scouting Report, the **Cards** section is an intelligence ranking — not a flat list.

- **Sort key:** CardSignal Card Score (highest first) from stored weekly card intelligence
- **Never sort by:** price, newest, alphabetical order, grade, or listing count unless explicitly selected in a future sprint
- **Top Pick:** the #1 ranked card receives a subtle analyst-style badge
- **Comparison:** every card row surfaces Card Identity, CardSignal Card Score, Recommendation, Evidence, and View Card Report
- **Tie handling:** equal scores break deterministically on stronger stored evidence → card identity → `cs_card_id`
- **Data rules:** ranking explanations, evidence copy, and recommendations come only from stored intelligence — no fabricated ranking logic
- **Card Report entry:** each card exposes a clear **View Card Report** action using existing `/cards/{cs_card_id}` routing

## NFL Intelligence Principles

NFL support follows the same evidence-first architecture as MLB, with football-specific rules:

- **Position-aware performance:** QB, RB, WR, and TE use separate scoring models — defensive players are not forced into offensive formulas
- **Recent 3-game window:** during the active season, recent form uses the last 3 completed games (not calendar days)
- **Bye weeks:** bye weeks are excluded from performance windows and do not count as zero-stat games
- **Season phases:** REGULAR/POSTSEASON show Recent 3 Games + Season Snapshot; PRESEASON shows verified preseason + previous season; OFFSEASON shows previous season only
- **No projections or rumors:** Signal Drivers require stored, verified evidence — fantasy projections and rumors are excluded
- **Data quality:** HIGH / MEDIUM / LOW / INSUFFICIENT based on completed games, metric completeness, and sample size
- **Player score vs card score:** NFL performance (`NFL_PERFORMANCE_V1`) feeds player-level signals; CardSignal Card Score remains a separate market-aware layer
- **Provider policy:** NFL uses a provider-neutral interface; approved imports are labeled `APPROVED_IMPORT`; NFL stays unavailable until real data is loaded
- **Identity:** deterministic IDs use `CS-NFL-P-{SOURCE_PLAYER_ID}` and never change on team trades

## User Layers

- **Anonymous** — browse Signal Center, search players, open Scouting Reports and Card Reports
- **Authenticated** — save watchlist players, configure alert preferences, per-player alert rules, notification center
- **Admin** — hidden from public UI; protected by admin token for settings and tracked-player management

## Release Principles

- Homepage = Signal Center / market-wide overview
- Player modal = Scouting Report / one-player deep dive
- Card Report = individual collectible research destination
- Frontend-only releases must not modify backend files unless explicitly scoped
- No new dependencies without approval
- Preserve existing homepage sections during modal and report releases
