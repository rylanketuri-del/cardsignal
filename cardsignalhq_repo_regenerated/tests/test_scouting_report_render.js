#!/usr/bin/env node
/**
 * Regression: MLB Scouting Report body can render without throwing.
 * Run: node tests/test_scouting_report_render.js
 */
const assert = require("assert");
const path = require("path");

global.window = global;
global.localStorage = {
  getItem() {
    return null;
  },
  setItem() {},
  removeItem() {},
};

require(path.join(__dirname, "..", "frontend", "scouting-report-metrics.js"));
require(path.join(__dirname, "..", "frontend", "scouting-report-nfl.js"));
require(path.join(__dirname, "..", "frontend", "scouting-report-nba.js"));
require(path.join(__dirname, "..", "frontend", "scouting-report-intel.js"));

const capabilityState = require(path.join(__dirname, "..", "frontend", "capability-state.js"));
global.capabilityStatusCopy = capabilityState.capabilityStatusCopy;
global.deriveSupportedEvidenceQuality = capabilityState.deriveSupportedEvidenceQuality;
global.getCapabilityState = capabilityState.getCapabilityState;

const { renderScoutingReport } = require(path.join(__dirname, "..", "frontend", "app.js"));

const mlbEntry = {
  player_id: "660271",
  player_name: "Test Hitter",
  position: "SS",
  league: "MLB",
  sport: "MLB",
};

const mlbIntel = {
  score: 72.4,
  performance: 68,
  market: 61,
  collector: 55,
  momentum: 50,
  scarcity: 42,
  evidenceTier: "MEDIUM",
  recommendation: "HOLD",
  hasStoredRecommendation: true,
  weeklyChange: 2.5,
  evidence: {},
  missingInputs: [],
  capabilities: {
    recent_form: "SUPPORTED",
    market_snapshots: "SUPPORTED",
    momentum: "SUPPORTED",
    card_intelligence: "SUPPORTED",
  },
  signalDrivers: [],
  mappedDrivers: [],
  algorithmVersion: "WEEKLY_INTELLIGENCE_V1",
  capturedAt: "2026-08-17T12:00:00Z",
  stats7d: { games: 6, avg: 0.32, home_runs: 3, ops: 1.05, rbi: 8 },
  stats30d: { games: 22, avg: 0.29, home_runs: 8, ops: 0.89, rbi: 24 },
  marketSnapshots: {},
  isNfl: false,
  isNba: false,
  isMlb: true,
  nfl: null,
  nba: null,
  seasonPhase: "REGULAR_SEASON",
  showRecentPanel: true,
};

console.log("Scouting report render tests");

let html;
assert.doesNotThrow(() => {
  html = renderScoutingReport(mlbEntry, mlbIntel);
}, "renderScoutingReport should render an MLB player without throwing");

assert.strictEqual(typeof html, "string");
assert.ok(html.includes("sr-report"), "expected Scouting Report root");
assert.ok(html.includes("sr-snapshot"), "expected Player Snapshot section");
assert.ok(html.includes("Player Snapshot"), "expected Player Snapshot title");
assert.ok(html.includes("Why This Signal"), "expected Why This Signal section");
assert.ok(html.includes("Cards"), "expected Cards section");
assert.ok(html.includes("Market"), "expected Market section");
assert.ok(html.includes("Signal Analysis"), "expected Signal Analysis section");
assert.ok(html.includes("CardSignal Outlook"), "expected Outlook section");

console.log("  ok renderScoutingReport renders MLB player without throwing");
console.log("passed");
