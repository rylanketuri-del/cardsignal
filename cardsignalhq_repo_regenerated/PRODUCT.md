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
