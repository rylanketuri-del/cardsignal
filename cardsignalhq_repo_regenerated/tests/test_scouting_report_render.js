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

require(path.join(__dirname, "..", "frontend", "weekly-movement.js"));
require(path.join(__dirname, "..", "frontend", "weekly-convergence.js"));

const {
  renderScoutingReport,
  renderPlayerSnapshot,
  renderPlayerHeadshot,
  renderLeaderHeadshot,
  renderFeaturedSignalCard,
  buildStoredPlayerIntel,
  mlbHeadshotUrlFromSourceId,
} = require(path.join(__dirname, "..", "frontend", "app.js"));

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
  statsSeason: { games: 123, avg: 0.255, home_runs: 16, ops: 0.807, rbi: 61, obp: 0.346, slg: 0.407 },
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

function seasonPanelHtml(html) {
  const match = String(html).match(/<h4 class="sr-panel-title">[^<]*Season Performance<\/h4>[\s\S]*?<\/article>/);
  assert.ok(match, "expected Season Performance panel");
  return match[0];
}

function last7PanelHtml(html) {
  const match = String(html).match(/<h4 class="sr-panel-title">Last 7 Days<\/h4>[\s\S]*?<\/article>/);
  assert.ok(match, "expected Last 7 Days panel");
  return match[0];
}

const splitWindowsIntel = {
  ...mlbIntel,
  stats7d: { games: 7, avg: 0.32, home_runs: 3, ops: 1.05, rbi: 8 },
  stats30d: { games: 27, avg: 0.321, home_runs: 7, ops: 0.902, rbi: 20 },
  statsSeason: { games: 123, avg: 0.255, home_runs: 16, ops: 0.807, rbi: 61, obp: 0.346, slg: 0.407 },
};

const splitHtml = renderScoutingReport(mlbEntry, splitWindowsIntel);
const seasonPanel = seasonPanelHtml(splitHtml);
const last7Panel = last7PanelHtml(splitHtml);
assert.ok(seasonPanel.includes(">123<"), "Season Performance must display full-season games");
assert.ok(!seasonPanel.includes(">27<"), "Season Performance must not display rolling 30-day games");
assert.ok(last7Panel.includes("Last 7 Days"), "Last 7 Days panel must remain");
assert.ok(last7Panel.includes("0.320"), "Last 7 Days must still use 7-day AVG");
console.log("  ok Season Performance displays 123 games, never 27");

const missingSeasonIntel = {
  ...mlbIntel,
  stats7d: { games: 7, avg: 0.32, home_runs: 3, ops: 1.05, rbi: 8 },
  stats30d: { games: 27, avg: 0.321, home_runs: 7, ops: 0.902, rbi: 20 },
  statsSeason: null,
};
const missingHtml = renderPlayerSnapshot(missingSeasonIntel, mlbEntry);
assert.ok(missingHtml.includes("Full-season stats unavailable"), "missing stats_season must be honest");
assert.ok(!missingHtml.includes(">27<"), "missing stats_season must not fall back to stats_30d games");
console.log("  ok missing stats_season shows unavailable instead of 30-day fallback");

const storedIntel = buildStoredPlayerIntel({
  ...mlbEntry,
  stats_7d: splitWindowsIntel.stats7d,
  stats_30d: splitWindowsIntel.stats30d,
  stats_season: splitWindowsIntel.statsSeason,
  hotness: { total_score: 72.4, performance_score: 68, market_score: 61, tag: "RISING" },
});
assert.strictEqual(storedIntel.statsSeason.games, 123);
assert.strictEqual(storedIntel.stats30d.games, 27);
const storedSeason = seasonPanelHtml(renderPlayerSnapshot(storedIntel, mlbEntry));
assert.ok(storedSeason.includes(">123<"));
assert.ok(!storedSeason.includes(">27<"));
console.log("  ok stored leaderboard intel reads stats_season, not stats_30d");

const bregmanUrl = mlbHeadshotUrlFromSourceId("608324");
assert.ok(bregmanUrl.includes("/people/608324/"));
assert.ok(bregmanUrl.includes("/w_213,"), "default MLB headshot width must remain w_213");
assert.ok(!bregmanUrl.includes("/w_640,"), "default helper must not emit hero width");
assert.strictEqual(mlbHeadshotUrlFromSourceId("9ed6461a-a34b-4205-b55d-4da9dd203796"), null);
assert.strictEqual(mlbHeadshotUrlFromSourceId("mlb:9ed6461a-a34b-4205-b55d-4da9dd203796"), null);
console.log("  ok UUID is never used to construct an MLB photo URL");
console.log("  ok mlbHeadshotUrlFromSourceId defaults to w_213");

const withPhoto = { player_name: "Alex Bregman", headshot_url: bregmanUrl };
assert.ok(renderLeaderHeadshot(withPhoto).includes("<img"));
assert.ok(renderLeaderHeadshot(withPhoto).includes("/people/608324/"));
assert.ok(renderLeaderHeadshot(withPhoto).includes("/w_213,"));
assert.ok(!renderLeaderHeadshot(withPhoto).includes("/w_640,"));
assert.ok(renderPlayerHeadshot(withPhoto).includes("<img"));
assert.ok(renderPlayerHeadshot(withPhoto).includes("/people/608324/"));
assert.ok(renderPlayerHeadshot(withPhoto).includes("/w_213,"));
assert.ok(!renderPlayerHeadshot(withPhoto).includes("/w_640,"));
assert.ok(renderFeaturedSignalCard(withPhoto, { label: "Featured Signal", metricValue: "85", metricCaption: "Score" }).includes("<img"));
assert.ok(renderFeaturedSignalCard(withPhoto, { label: "Featured Signal", metricValue: "85", metricCaption: "Score" }).includes("/people/608324/"));
assert.ok(renderFeaturedSignalCard(withPhoto, { label: "Featured Signal", metricValue: "85", metricCaption: "Score" }).includes("/w_213,"));
console.log("  ok featured/leader/scouting render img when headshot_url exists");
console.log("  ok leaderboard/scouting continue using w_213");

const withoutPhoto = { player_name: "Alex Bregman" };
assert.ok(!renderLeaderHeadshot(withoutPhoto).includes("<img"));
assert.ok(renderLeaderHeadshot(withoutPhoto).includes("AB"));
assert.ok(!renderPlayerHeadshot(withoutPhoto).includes("<img"));
assert.ok(renderPlayerHeadshot(withoutPhoto).includes("AB"));
assert.ok(!renderFeaturedSignalCard(withoutPhoto, { label: "Featured Signal", metricValue: "85", metricCaption: "Score" }).includes("<img"));
console.log("  ok initials fallback still works when headshot_url is missing");

console.log("passed");
