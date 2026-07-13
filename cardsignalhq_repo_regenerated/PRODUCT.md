# CardSignal — Product Overview

CardSignal is market intelligence for modern sports-card collectors. The product combines player performance signals, collector demand indicators, and card-market activity into a single **CardSignal Score** that helps collectors decide what to watch, buy, hold, or sell.

## Product Architecture

### Signal Center (Homepage)

The homepage is the **Signal Center** — a market-wide overview dashboard.

Primary sections:

- **Universal Search** — find MLB, NFL, and NBA players when league data is available; leaderboard players show scores, others show search results from the backend player pool
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
| **Player Snapshot** | Recent window and Season Snapshot from stored league stats (MLB: Last 7 Days; NBA: Recent 5 Games; NFL: Recent 3 Games) |
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

- **Recommendation** — BUY / HOLD / SELL / WATCH (from stored weekly or card intelligence only)
- **Evidence** — HIGH / MEDIUM / LOW / INSUFFICIENT (replaces legacy Conviction/Confidence in the Scouting Report)
- **Status** — HOT / RISING / COOLING

Forecast language uses tentative phrasing (“suggests,” “may,” “could”) and never implies guaranteed returns.

## Data Sources

Current production scope:

- **MLB hitters** — MLB Stats API for performance
- **NFL (beta adapter):** approved import path; unavailable until verified data is seeded — no fabricated intelligence
- **NBA (beta adapter):** approved import path; unavailable until verified data is seeded — no fabricated intelligence
- **NHL** — shown as coming soon
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

## NFL Intelligence Principles

NFL support follows the same evidence-first architecture as MLB, with football-specific rules:

- **Position-aware performance:** QB, RB, WR, and TE use separate scoring models — defensive players are not forced into offensive formulas
- **Recent 3-game window:** during the active season, recent form uses the last 3 completed games (not calendar days)
- **Bye weeks:** bye weeks are excluded from performance windows and do not count as zero-stat games
- **Season phases:** REGULAR/POSTSEASON show Recent 3 Games + Season Snapshot; PRESEASON shows verified preseason + previous season; OFFSEASON shows previous season only
- **No projections or rumors:** Signal Drivers require stored, verified evidence — fantasy projections and rumors are excluded
- **Data quality:** HIGH / MEDIUM / LOW / INSUFFICIENT based on completed games, metric completeness, and sample size
- **Player score vs card score:** NFL performance (`NFL_PERFORMANCE_V1`) feeds player-level signals; CardSignal Card Score remains a separate market-aware layer (`NFL_PLAYER_SIGNAL_V1`)
- **Provider policy:** NFL uses a provider-neutral interface; approved imports are labeled `APPROVED_IMPORT`; NFL stays unavailable until real data is loaded
- **Identity:** deterministic IDs use `CS-NFL-P-{SOURCE_PLAYER_ID}` and never change on team trades

## NBA Intelligence Principles

NBA support follows the same evidence-first Sport Adapter architecture as MLB and NFL, with basketball-specific rules:

- **Supported positions:** PG, SG, SF, PF, C — unknown positions receive `performance_score = null` and `data_quality = INSUFFICIENT`
- **Recent window:** `recent_window_type = COMPLETED_GAMES`, `recent_window_value = 5` (from league metadata, not hardcoded in UI)
- **Recent performance fields:** points, rebounds, assists, steals, blocks, turnovers, FG%, 3PT%, FT%, minutes, games played
- **Season snapshot:** season totals where available — no fabricated advanced analytics
- **Performance scoring:** `NBA_PERFORMANCE_V1` from stored basketball stats only (no market or fantasy inputs)
- **CardSignal player signal:** `NBA_PLAYER_SIGNAL_V1` integrates market, collector demand, scarcity, and Signal Drivers without altering MLB/NFL algorithms
- **Signal Drivers:** verified basketball drivers only (HOT_STREAK, ROLE_EXPANSION, STARTER_CHANGE, MINUTES_SURGE, TRADE, CONTRACT, INJURY, INJURY_RETURN, ALL_STAR_SELECTION, PLAYOFF_PERFORMANCE)
- **Scouting Report:** Recent 5 Games shows PPG, RPG, APG, SPG, BPG, FG%, 3PT%, FT%, MPG — never MLB/NFL labels
- **Provider policy:** provider-neutral `NBAPerformanceProvider`; approved imports labeled `APPROVED_IMPORT`; NBA stays unavailable until real data is loaded
- **Identity:** deterministic IDs use `CS-NBA-P-{STABLE_SOURCE_PLAYER_ID}` — never derived from rankings or array order
- **Homepage:** NBA tab activates only when genuine weekly intelligence exists; otherwise Coming Soon

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

## League Intelligence Convergence Principles (Sprint 11.2)

MLB and NFL may use different source pipelines, but all shared surfaces consume one normalized intelligence contract:

- **Common output contract:** `PlayerIntelligencePayload` with identity, scores, performance evidence, signal drivers, market, cards, weekly movement, capabilities, and algorithm versions
- **Explicit capability declarations:** each league adapter declares `SUPPORTED`, `UNAVAILABLE`, `PENDING`, or `DISABLED` per capability — the frontend never infers capabilities from missing fields
- **League-specific sources may differ:** MLB uses live API + legacy Supabase; NFL uses approved import + local JSON storage
- **Unsupported is better than fabricated:** null scores stay null; pending states use intentional copy
- **Momentum, weekly change, and market movement are distinct:** Momentum Score is a 0–100 intelligence score (not a percentage); Weekly Change is CardSignal Score delta between official weekly snapshots; Market Movement is historical change in stored market observations
- **Frontend surfaces consume normalized intelligence:** Homepage leader rows and Scouting Report load `PlayerIntelligencePayload` through the shared read service — capabilities define support state; `missing_inputs` only explains evidence gaps after support is confirmed

## Offseason Intelligence Principles (Sprint 11.3)

NFL and NBA remain useful during the offseason through verified previous-season context — never fabricated recent form.

- **Prior-season stats provide context, not current momentum:** `previous_season_performance` is stored separately from `recent_performance`; previous-season values are never labeled as current-season production
- **Offseason Signal Drivers replace empty recent-game panels:** Scouting Reports show `{season} Season Snapshot` (NFL) or `{season}–{end} Season Snapshot` (NBA), then Offseason Signal Drivers — not “Recent 3 Games” or “Recent 5 Games” during `OFFSEASON`
- **Verified imports must be clearly sourced:** `PreviousSeasonPerformanceSnapshot` records `source_method`, `source_reference`, and `provider_updated_at`; admin-protected `POST /api/admin/performance/import` and `scripts/import_performance.py` write through durable storage
- **No rumors or fabricated developments:** Signal Drivers require stored, verified evidence; empty driver state uses honest copy
- **Current recommendations require current supporting evidence:** previous-season stats alone cannot trigger a confident BUY; offseason recommendations default to WATCH unless market and driver evidence support HOLD
- **Durable storage preferred:** Supabase `performance_snapshots` table is primary; local JSON warns when ephemeral (Render redeploys)
