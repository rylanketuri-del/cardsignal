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
console.log("passed");
