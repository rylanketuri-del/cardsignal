/**
 * Daily/weekly homepage convergence.
 * Weekly identity/evidence stays authoritative; daily CardSignal/Market
 * scores fill in only when the matching weekly score is null.
 */
const CARD_INTEL_AWAITING_REFRESH = "Card intelligence will appear after the next weekly refresh.";
const CARD_INTEL_MARKET_UNAVAILABLE = "Card intelligence is unavailable this week because market evidence was not captured.";
const CARD_INTEL_MOVEMENT_PENDING = "Weekly movement will appear after the next completed weekly snapshot.";
const CARD_SCORE_LABEL = "CARDSIGNAL";
const AVG_LISTING_LABEL = "Avg. listing";

function isFiniteNumber(value) {
  return typeof value === "number" && Number.isFinite(value);
}

function formatScore(value) {
  return isFiniteNumber(value) ? value.toFixed(1) : "—";
}

function firstFiniteNumber(...values) {
  for (const value of values) {
    if (isFiniteNumber(value)) return value;
  }
  return null;
}

function playerMatchKeys(entry = {}) {
  const keys = [];
  const sourceId = entry.source_player_id || entry.player_id;
  if (sourceId != null && String(sourceId).trim() !== "") {
    keys.push(`id:${String(sourceId).trim().toLowerCase()}`);
  }
  const name = String(entry.player_name || "").trim().toLowerCase();
  if (name) keys.push(`name:${name}`);
  return keys;
}

function indexDailyLeaderboard(items = []) {
  const byKey = {};
  for (const item of items || []) {
    for (const key of playerMatchKeys(item)) {
      if (!byKey[key]) byKey[key] = item;
    }
  }
  return byKey;
}

function weeklyLeaderToEntry(leader = {}) {
  const total = leader.score;
  return {
    player_id: leader.source_player_id || leader.cs_player_id,
    cs_player_id: leader.cs_player_id,
    source_player_id: leader.source_player_id,
    player_name: leader.player_name,
    rank: leader.rank,
    team: leader.team,
    position: leader.position,
    headshot_url: leader.headshot_url,
    team_logo_url: leader.team_logo_url,
    weekly_change: leader.weekly_change,
    league: leader.league,
    sport: leader.sport,
    capabilities: leader.capabilities || leader.intelligence?.capabilities || {},
    intelligence: leader.intelligence || null,
    status: leader.status,
    card_signal_score: total,
    hotness: {
      total_score: total,
      performance_score: leader.performance,
      market_score: leader.market,
      momentum_score: leader.momentum,
      collector_score: leader.collector,
      confidence_multiplier: 1,
      tag: leader.status || leader.recommendation || "WATCH",
      reasons: [],
    },
    recommendation: leader.recommendation,
    conviction: leader.conviction,
  };
}

function mergeWeeklyLeaderWithDaily(weeklyLeader, dailyByKey = {}) {
  const weeklyEntry = weeklyLeaderToEntry(weeklyLeader);
  let daily = null;
  for (const key of playerMatchKeys(weeklyEntry)) {
    if (dailyByKey[key]) {
      daily = dailyByKey[key];
      break;
    }
  }
  const dailyHotness = daily?.hotness || {};
  const total = firstFiniteNumber(weeklyEntry.hotness.total_score, dailyHotness.total_score);
  const performance = firstFiniteNumber(
    weeklyEntry.hotness.performance_score,
    dailyHotness.performance_score,
  );
  const market = firstFiniteNumber(weeklyEntry.hotness.market_score, dailyHotness.market_score);
  weeklyEntry.hotness = {
    ...weeklyEntry.hotness,
    total_score: total,
    performance_score: performance,
    market_score: market,
  };
  weeklyEntry.card_signal_score = total;
  if (daily) {
    weeklyEntry.stats_7d = weeklyEntry.stats_7d || daily.stats_7d;
    weeklyEntry.stats_30d = weeklyEntry.stats_30d || daily.stats_30d;
    weeklyEntry.stats_season = weeklyEntry.stats_season || daily.stats_season;
    weeklyEntry.market_snapshots = weeklyEntry.market_snapshots || daily.market_snapshots;
    if (!weeklyEntry.headshot_url && daily.headshot_url) {
      weeklyEntry.headshot_url = daily.headshot_url;
    }
    if (!weeklyEntry.source_player_id && daily.source_player_id) {
      weeklyEntry.source_player_id = daily.source_player_id;
    }
  }
  return weeklyEntry;
}

function convergeWeeklyLeadersWithDaily(weeklyLeaders = [], dailyItems = []) {
  if (!Array.isArray(weeklyLeaders) || weeklyLeaders.length === 0) {
    return Array.isArray(dailyItems) ? dailyItems.slice() : [];
  }
  const dailyByKey = indexDailyLeaderboard(dailyItems);
  return weeklyLeaders.map((leader) => mergeWeeklyLeaderWithDaily(leader, dailyByKey));
}

function mergeAllSportLeaders(mlbLeaders = [], nflLeaders = [], nbaLeaders = [], dailyByLeague = {}) {
  const mlb = convergeWeeklyLeadersWithDaily(mlbLeaders, dailyByLeague.MLB || dailyByLeague.mlb || []);
  const nfl = convergeWeeklyLeadersWithDaily(nflLeaders, dailyByLeague.NFL || dailyByLeague.nfl || []);
  const nba = convergeWeeklyLeadersWithDaily(nbaLeaders, dailyByLeague.NBA || dailyByLeague.nba || []);
  const combined = [
    ...mlb.map((e) => ({ ...e, sport: "MLB", league: "MLB" })),
    ...nfl.map((e) => ({ ...e, sport: "FOOTBALL", league: "NFL" })),
    ...nba.map((e) => ({ ...e, sport: "BASKETBALL", league: "NBA" })),
  ];
  return combined
    .filter((e) => e.card_signal_score != null || e.hotness?.total_score != null)
    .sort((a, b) => {
      const aScore = a.card_signal_score ?? a.hotness?.total_score ?? -1;
      const bScore = b.card_signal_score ?? b.hotness?.total_score ?? -1;
      return bScore - aScore;
    });
}

function weeklyRunCompleted(weeklyPayload) {
  const status = String(weeklyPayload?.run?.status || "").toUpperCase();
  return status === "COMPLETED" || status === "PARTIAL";
}

function cardSectionsAreEmpty(cardIntel) {
  if (!cardIntel || typeof cardIntel !== "object") return true;
  return ["trending_cards", "biggest_movers", "buy_low_watch", "most_chased"]
    .every((key) => !Array.isArray(cardIntel[key]) || cardIntel[key].length === 0);
}

function cardIntelEmptyStateCopy(weeklyPayload = {}) {
  if (weeklyRunCompleted(weeklyPayload) && cardSectionsAreEmpty(weeklyPayload.card_intelligence)) {
    return CARD_INTEL_MARKET_UNAVAILABLE;
  }
  return CARD_INTEL_AWAITING_REFRESH;
}

function isHistoricalCardMovement(row = {}) {
  if (!row || typeof row !== "object") return false;
  if (row.movement_is_historical === true) return true;
  const status = String(row.movement_status || "").trim().toLowerCase();
  if (status === "calculated" || status === "historical") return true;
  const type = String(row.movement_type || "").trim().toLowerCase();
  return type === "price_change_pct" || type === "historical";
}

function hasGenuineHistoricalCardMovement(row = {}) {
  return isHistoricalCardMovement(row) && isFiniteNumber(row.movement);
}

function filterHistoricalCardMovers(rows = []) {
  if (!Array.isArray(rows)) return [];
  return rows.filter((row) => hasGenuineHistoricalCardMovement(row));
}

function formatCardRowMovement(row = {}) {
  if (!hasGenuineHistoricalCardMovement(row)) {
    return "—";
  }
  const n = row.movement;
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(1)}%`;
}

function formatUsdMoney(value) {
  if (!isFiniteNumber(value)) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function formatAvgListingPrice(value) {
  if (!isFiniteNumber(value)) return `${AVG_LISTING_LABEL} —`;
  return `${AVG_LISTING_LABEL} ${formatUsdMoney(value)}`;
}

function formatCardSignalScore(value) {
  return isFiniteNumber(value) ? value.toFixed(1) : "—";
}

const WeeklyConvergence = {
  CARD_INTEL_AWAITING_REFRESH,
  CARD_INTEL_MARKET_UNAVAILABLE,
  CARD_INTEL_MOVEMENT_PENDING,
  CARD_SCORE_LABEL,
  AVG_LISTING_LABEL,
  isFiniteNumber,
  formatScore,
  firstFiniteNumber,
  playerMatchKeys,
  indexDailyLeaderboard,
  weeklyLeaderToEntry,
  mergeWeeklyLeaderWithDaily,
  convergeWeeklyLeadersWithDaily,
  mergeAllSportLeaders,
  weeklyRunCompleted,
  cardSectionsAreEmpty,
  cardIntelEmptyStateCopy,
  isHistoricalCardMovement,
  hasGenuineHistoricalCardMovement,
  filterHistoricalCardMovers,
  formatCardRowMovement,
  formatUsdMoney,
  formatAvgListingPrice,
  formatCardSignalScore,
};

if (typeof window !== "undefined") {
  window.WeeklyConvergence = WeeklyConvergence;
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = WeeklyConvergence;
}
