#!/usr/bin/env node
/**
 * Homepage activation + daily/weekly score convergence.
 */
const assert = require("assert");
const fs = require("fs");
const path = require("path");

const WC = require(path.join(__dirname, "..", "frontend", "weekly-convergence.js"));
const {
  weeklyLeaderToEntry,
  mergeAllSportLeaders,
  convergeWeeklyLeadersWithDaily,
  formatScore,
  CARD_INTEL_AWAITING_REFRESH,
  CARD_INTEL_MARKET_UNAVAILABLE,
  cardIntelEmptyStateCopy,
} = WC;

const BREGMAN_HEADSHOT = "https://img.mlbstatic.com/mlb-photos/image/upload/w_213,q_100/v1/people/608324/headshot/67/current";

function hasGenuineWeeklyIntelligence(payload = {}) {
  return Boolean(payload.run) && Array.isArray(payload.todays_leaders) && payload.todays_leaders.length > 0;
}

let passed = 0;
let failed = 0;

function test(name, fn) {
  try {
    fn();
    passed += 1;
    console.log(`  ok ${name}`);
  } catch (err) {
    failed += 1;
    console.error(`  FAIL ${name}`);
    console.error(`       ${err.message}`);
  }
}

console.log("Homepage activation tests");

test("NFL without persisted weekly intelligence is not activated", () => {
  const payload = { run: null, todays_leaders: [] };
  assert.strictEqual(hasGenuineWeeklyIntelligence(payload), false);
  const merged = mergeAllSportLeaders([], payload.todays_leaders, []);
  assert.deepStrictEqual(merged, []);
});

test("NFL with genuine persisted weekly intelligence activates ALL view", () => {
  const nflLeader = {
    cs_player_id: "CS-NFL-P-12345",
    source_player_id: "12345",
    player_name: "Test QB",
    league: "NFL",
    sport: "FOOTBALL",
    rank: 1,
    score: 72.5,
    performance: 70.0,
    market: 75.0,
    recommendation: "WATCH",
  };
  const payload = { run: { status: "COMPLETED", league: "NFL" }, todays_leaders: [nflLeader] };
  assert.strictEqual(hasGenuineWeeklyIntelligence(payload), true);
  const merged = mergeAllSportLeaders([], payload.todays_leaders, []);
  assert.strictEqual(merged.length, 1);
  assert.strictEqual(merged[0].player_name, "Test QB");
  assert.strictEqual(merged[0].hotness.total_score, 72.5);
});

test("NBA without persisted weekly intelligence is not activated", () => {
  const payload = { run: null, todays_leaders: [] };
  assert.strictEqual(hasGenuineWeeklyIntelligence(payload), false);
});

test("NBA with genuine persisted weekly intelligence preserves season label", () => {
  const nbaLeader = {
    cs_player_id: "CS-NBA-P-2544",
    source_player_id: "2544",
    player_name: "Test Star",
    league: "NBA",
    sport: "BASKETBALL",
    rank: 1,
    score: 68.0,
    performance: 65.0,
    market: 71.0,
    recommendation: "WATCH",
    intelligence: {
      season_label: "2025–26",
      previous_season_label: "2025–26 Season Performance",
      previous_season_helper_text: "Most recently completed season",
    },
  };
  const payload = { run: { status: "COMPLETED", league: "NBA" }, todays_leaders: [nbaLeader] };
  assert.strictEqual(hasGenuineWeeklyIntelligence(payload), true);
  const merged = mergeAllSportLeaders([], [], payload.todays_leaders);
  assert.strictEqual(merged.length, 1);
  assert.strictEqual(merged[0].league, "NBA");
  assert.strictEqual(payload.todays_leaders[0].intelligence.season_label, "2025–26");
  assert.strictEqual(
    payload.todays_leaders[0].intelligence.previous_season_label,
    "2025–26 Season Performance"
  );
});

test("invalid incomplete record is excluded from merged leaders", () => {
  const incomplete = {
    cs_player_id: "CS-NFL-P-99999",
    source_player_id: "99999",
    player_name: "Pending Player",
    league: "NFL",
    sport: "FOOTBALL",
    rank: 2,
    score: null,
    performance: null,
    market: null,
    recommendation: null,
  };
  const merged = mergeAllSportLeaders([], [incomplete], []);
  assert.strictEqual(merged.length, 0);
});

test("null score is not coerced to zero", () => {
  const entry = weeklyLeaderToEntry({ score: null, player_name: "No Score" });
  assert.strictEqual(entry.hotness.total_score, null);
  assert.strictEqual(entry.card_signal_score, null);
  assert.strictEqual(formatScore(entry.hotness.total_score), "—");
  assert.notStrictEqual(formatScore(entry.hotness.total_score), "0.0");
});

test("daily Bregman scores fill weekly null Signal/Market", () => {
  const daily = [{
    player_name: "Alex Bregman",
    source_player_id: "608324",
    headshot_url: BREGMAN_HEADSHOT,
    stats_season: { games: 123, home_runs: 16 },
    hotness: { total_score: 87.04, performance_score: 81.25, market_score: 95.73 },
  }];
  const weekly = [{
    player_name: "Alex Bregman",
    source_player_id: "608324",
    headshot_url: BREGMAN_HEADSHOT,
    score: null,
    performance: 81.25,
    market: null,
    team: "HOU",
    position: "3B",
  }];
  const merged = convergeWeeklyLeadersWithDaily(weekly, daily);
  assert.strictEqual(merged.length, 1);
  assert.strictEqual(merged[0].hotness.total_score, 87.04);
  assert.strictEqual(merged[0].hotness.market_score, 95.73);
  assert.strictEqual(merged[0].hotness.performance_score, 81.25);
  assert.strictEqual(formatScore(merged[0].hotness.total_score), "87.0");
  assert.strictEqual(formatScore(merged[0].hotness.market_score), "95.7");
  assert.notStrictEqual(formatScore(merged[0].hotness.total_score), "0.0");
  assert.notStrictEqual(formatScore(merged[0].hotness.market_score), "0.0");
  assert.strictEqual(merged[0].headshot_url, BREGMAN_HEADSHOT);
  assert.strictEqual(merged[0].stats_season.games, 123);
  assert.strictEqual(merged[0].team, "HOU");
  assert.strictEqual(merged[0].position, "3B");
});

test("weekly valid score replaces daily score when present", () => {
  const daily = [{
    player_name: "Alex Bregman",
    source_player_id: "608324",
    hotness: { total_score: 87.04, performance_score: 81.25, market_score: 95.73 },
  }];
  const weekly = [{
    player_name: "Alex Bregman",
    source_player_id: "608324",
    score: 91.2,
    performance: 82.0,
    market: 88.5,
  }];
  const merged = convergeWeeklyLeadersWithDaily(weekly, daily);
  assert.strictEqual(merged[0].hotness.total_score, 91.2);
  assert.strictEqual(merged[0].hotness.market_score, 88.5);
  assert.strictEqual(merged[0].hotness.performance_score, 82.0);
});

test("NFL/NBA weekly null scores stay null and render as em dash", () => {
  const nfl = convergeWeeklyLeadersWithDaily([{
    player_name: "Emanuel Wilson",
    source_player_id: "123",
    score: null,
    performance: null,
    market: null,
  }], []);
  assert.strictEqual(nfl[0].hotness.total_score, null);
  assert.strictEqual(nfl[0].hotness.market_score, null);
  assert.strictEqual(formatScore(nfl[0].hotness.total_score), "—");
  const allView = mergeAllSportLeaders([], [{
    player_name: "Emanuel Wilson",
    source_player_id: "123",
    score: null,
    market: null,
  }], []);
  assert.strictEqual(allView.length, 0);
});

test("no weekly run uses awaiting-refresh card copy", () => {
  assert.strictEqual(cardIntelEmptyStateCopy({}), CARD_INTEL_AWAITING_REFRESH);
  assert.strictEqual(cardIntelEmptyStateCopy({ run: null, card_intelligence: null }), CARD_INTEL_AWAITING_REFRESH);
});

test("completed weekly run with empty card sections uses market-unavailable copy", () => {
  const payload = {
    run: { status: "COMPLETED", cards_processed: 0, market_snapshots_created: 0 },
    card_intelligence: {
      trending_cards: [],
      biggest_movers: [],
      buy_low_watch: [],
      most_chased: [],
    },
  };
  const copy = cardIntelEmptyStateCopy(payload);
  assert.strictEqual(copy, CARD_INTEL_MARKET_UNAVAILABLE);
  assert.ok(!copy.toLowerCase().includes("next weekly refresh"));
});

test("partial weekly run with empty card sections uses market-unavailable copy", () => {
  const copy = cardIntelEmptyStateCopy({
    run: { status: "PARTIAL" },
    card_intelligence: { trending_cards: [], biggest_movers: [], buy_low_watch: [], most_chased: [] },
  });
  assert.strictEqual(copy, CARD_INTEL_MARKET_UNAVAILABLE);
});

test("app.js converges weekly leaders with daily scores and does not coerce leaderboard nulls", () => {
  const app = fs.readFileSync(path.join(__dirname, "..", "frontend", "app.js"), "utf8");
  assert.ok(app.includes("WeeklyConvergence.convergeWeeklyLeadersWithDaily"));
  assert.ok(app.includes("const score = entry.hotness?.total_score;"));
  assert.ok(app.includes("const market = entry.hotness?.market_score;"));
  assert.ok(app.includes("cardIntelEmptyStateCopy"));
});

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
