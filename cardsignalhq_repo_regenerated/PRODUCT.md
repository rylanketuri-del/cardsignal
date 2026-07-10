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

### Player Intelligence Report (Modal)

The player modal is a **deep-dive Intelligence Report** for one player. It opens from:

- Today's Leaders row click
- Signal of the Week View Report CTA
- Universal Search result selection

Modal tabs:

| Tab | Purpose |
|-----|---------|
| **Overview** | Score, recommendation, conviction, weekly movement, status, signal breakdown, why-it-matters summary |
| **Cards** | Player-specific trending, movers, buy-low, and most-chased card rows |
| **Market** | Placeholder sale volume, listings, liquidity, and market summary (live pricing snapshots pending) |
| **Signals** | Performance, Market, Collector Demand, and Momentum explanations with scores and progress bars |
| **Forecast** | BUY/HOLD/SELL recommendation, conviction, 2–4 week horizon, risk, summary, and bullet reasons |

Modal UX:

- Dark backdrop; homepage remains visible behind
- Close via X, Escape, or backdrop click
- Centered panel on desktop; full-screen drawer on mobile
- Body scroll locked while open

## CardSignal Score

The CardSignal Score (0–100) blends:

- **Performance** — recent on-field production
- **Market** — card-market pricing and listing activity
- **Collector Demand** — chase pressure and buyer interest
- **Momentum** — directional trend across inputs

Each player also receives:

- **Recommendation** — BUY / HOLD / SELL (derived from conviction tier)
- **Conviction** — Low / Medium / High
- **Status** — HOT / RISING / COOLING

Forecast language uses tentative phrasing (“suggests,” “may,” “could”) and never implies guaranteed returns.

## Data Sources

Current production scope:

- **MLB hitters only** (NBA, NFL, NHL tabs shown as coming soon)
- MLB Stats API for performance
- eBay Browse API for active listings
- Supabase for leaderboard persistence, auth, watchlists, alerts, and notifications

Placeholder intelligence (card rows, market metrics, forecast reasons) uses stable seeded values when backend fields are missing. Live card-market snapshots will replace placeholders in a future release.

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

## CardSignal Identity Model

CardSignal uses deterministic, sport/league-aware IDs so players, cards, signals, and forecasts can be linked across pipeline runs, pricing sources, and future assets without relying on leaderboard rank or random page-render values.

### ID Formats

| Entity | Format | Example |
|--------|--------|---------|
| Player | `CS-{LEAGUE}-P-{STABLE_ID}` | `CS-MLB-P-660271` |
| Card | `CS-{LEAGUE}-C-{STABLE_CARD_ID}` | `CS-MLB-C-a1b2c3d4e5f6` |
| Weekly Signal | `CS-{LEAGUE}-S-{YEAR}W{WEEK}-{STABLE_ID}` | `CS-MLB-S-2026W28-660271` |
| Forecast | `CS-{LEAGUE}-F-{YEAR}W{WEEK}-{STABLE_ID}` | `CS-MLB-F-2026W28-660271` |

`STABLE_ID` is the official league/player ID when available (MLB player ID for MLB). Card `STABLE_CARD_ID` is a deterministic hash of normalized card identity fields (year, manufacturer, set, card name, parallel, grade, grading company, and player source ID). Price and movement are never used in ID generation.

### Supported Namespaces

League namespaces are reserved for: **MLB**, **NFL**, **NBA**, **NHL**, **SOCCER**, **F1**, **UFC**, **POKEMON**, **TCG**. Only MLB is active in production; other namespaces are prepared for future expansion.

### Deterministic ID Requirement

The same player or card identity must always resolve to the same CardSignal ID. IDs are computed from stable source identifiers and normalized identity fields — never from list position, leaderboard rank, or random runtime values.

### Relationships

```
Player → many Cards
Player → many Weekly Signals
Player → many Forecasts
Card → many Market Snapshots
Card → many Population Snapshots (future)
```

Sprint 8.2 establishes identity relationships; Sprint 8.3 persists append-only card market snapshots linked by `cs_card_id`.

### Player Fields

Player records expose (in addition to legacy `player_id`):

- `cs_player_id`
- `source_player_id`
- `league`
- `sport`
- `player_name`

Legacy `player_id` remains the primary API lookup key for MLB players.

## Card Market Snapshot Principles

CardSignal card market snapshots capture **active eBay listing observations** for registry cards. They are historical market intelligence inputs — not confirmed sales.

- **Active listings are not sold comps** — asking prices, shipping, bids, and listing counts describe current supply; they must never be presented as completed sale prices.
- **Snapshots are historical observations** — each run appends a new snapshot row with `captured_at`, `query`, and `algorithm_version`; prior observations are preserved.
- **Data quality must be shown** — every snapshot includes `data_quality` (`HIGH`, `MEDIUM`, `LOW`, `INSUFFICIENT`) derived from priced listing sample size.
- **Recommendations must cite supporting inputs** — BUY/HOLD/SELL and forecast language should reference the underlying snapshot quality and metrics, not imply guaranteed returns.

Player-level market scoring from the leaderboard pipeline remains separate from card-level active listing snapshots until future sprints wire UI and recommendation logic to card snapshots.
