#!/usr/bin/env node
/**
 * Homepage activation helpers — mirrors app.js weekly leader mapping/filter rules.
 */
const assert = require("assert");

function weeklyLeaderToEntry(leader = {}) {
  return {
    player_id: leader.source_player_id || leader.cs_player_id,
    cs_player_id: leader.cs_player_id,
    source_player_id: leader.source_player_id,
    player_name: leader.player_name,
    rank: leader.rank,
    league: leader.league,
    sport: leader.sport,
    weekly_change: leader.weekly_change,
    recommendation: leader.recommendation,
    card_signal_score: leader.score,
    hotness: {
      total_score: leader.score,
      performance_score: leader.performance,
      market_score: leader.market,
    },
  };
}

function mergeAllSportLeaders(mlbLeaders = [], nflLeaders = [], nbaLeaders = []) {
  const combined = [
    ...mlbLeaders.map((e) => ({ ...weeklyLeaderToEntry(e), sport: "MLB", league: "MLB" })),
    ...nflLeaders.map((e) => ({ ...weeklyLeaderToEntry(e), sport: "FOOTBALL", league: "NFL" })),
    ...nbaLeaders.map((e) => ({ ...weeklyLeaderToEntry(e), sport: "BASKETBALL", league: "NBA" })),
  ];
  return combined
    .filter((e) => e.card_signal_score != null || e.hotness?.total_score != null)
    .sort((a, b) => {
      const aScore = a.card_signal_score ?? a.hotness?.total_score ?? -1;
      const bScore = b.card_signal_score ?? b.hotness?.total_score ?? -1;
      return bScore - aScore;
    });
}

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

test("NBA with genuine persisted weekly intelligence activates", () => {
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
  };
  const payload = { run: { status: "COMPLETED", league: "NBA" }, todays_leaders: [nbaLeader] };
  assert.strictEqual(hasGenuineWeeklyIntelligence(payload), true);
  const merged = mergeAllSportLeaders([], [], payload.todays_leaders);
  assert.strictEqual(merged.length, 1);
  assert.strictEqual(merged[0].league, "NBA");
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
});

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
