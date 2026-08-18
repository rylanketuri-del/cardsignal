/** Tests for normalized scouting report adapter. */

const assert = require("assert");
const {
  srIntelFromNormalized,
  srMapNormalizedDrivers,
} = require("../frontend/scouting-report-intel.js");

const payload = {
  league: "MLB",
  sport: "MLB",
  cs_player_id: "mlb:1",
  source_player_id: "1",
  player_name: "Test Player",
  card_signal_score: 72,
  performance_score: 68,
  market_score: 60,
  momentum_score: 55,
  recommendation: "HOLD",
  evidence: "MEDIUM",
  weekly_change: 2.5,
  capabilities: { recent_form: "SUPPORTED", signal_drivers: "SUPPORTED" },
  signal_drivers: [{
    driver_type: "POWER_PRODUCTION",
    label: "Power Production",
    description: "3 HR in 7 days",
    source_method: "mlb_stats_api",
    captured_at: "2026-07-08T12:00:00Z",
    evidence: {},
  }],
  recent_performance: [{ metric: "ops", value: 1.05, label: "OPS" }],
  league_evidence: {},
};

console.log("Scouting report intel tests");
const intel = srIntelFromNormalized(payload, { player_name: "Test Player" });
assert.strictEqual(intel.isMlb, true);
assert.strictEqual(intel.score, 72);
assert.strictEqual(intel.mappedDrivers.length, 1);
assert.strictEqual(intel.capabilities.recent_form, "SUPPORTED");
assert.ok(!intel.isNfl);
assert.strictEqual(intel.statsSeason, null);
console.log("  ok normalized MLB payload maps without inventing season stats");

const seasonIntel = srIntelFromNormalized(
  {
    ...payload,
    season_performance: [
      { metric: "ops", value: 0.902, label: "OPS (Season)" },
      { metric: "games", value: 123, label: "Games (Season)" },
    ],
    league_evidence: {
      stats_season: { games: 123, avg: 0.255, home_runs: 16, rbi: 61, ops: 0.807 },
    },
  },
  {
    player_name: "Test Player",
    stats_30d: { games: 27, avg: 0.321, home_runs: 7, rbi: 20, ops: 0.902 },
    stats_season: { games: 123, avg: 0.255, home_runs: 16, rbi: 61, ops: 0.807 },
  }
);
assert.strictEqual(seasonIntel.statsSeason.games, 123);
assert.strictEqual(seasonIntel.stats30d.games, 27);
assert.notStrictEqual(seasonIntel.statsSeason.games, seasonIntel.stats30d.games);
console.log("  ok MLB statsSeason comes from stats_season, not stats_30d");

const noFallback = srIntelFromNormalized(
  {
    ...payload,
    season_performance: [
      { metric: "ops", value: 0.902, label: "OPS (30-Day Window)" },
      { metric: "home_runs", value: 7, label: "Home Runs (30-Day Window)" },
    ],
  },
  {
    player_name: "Test Player",
    stats_30d: { games: 27, avg: 0.321, home_runs: 7, rbi: 20, ops: 0.902 },
  }
);
assert.strictEqual(noFallback.statsSeason, null);
assert.strictEqual(noFallback.stats30d.games, 27);
console.log("  ok missing stats_season does not fall back to stats_30d");

console.log("passed");
