#!/usr/bin/env node
/**
 * Focused tests for homepage weekly movement formatting.
 * Run: node tests/test_weekly_movement.js
 */
const assert = require("assert");
const path = require("path");

const WM = require(path.join(__dirname, "..", "frontend", "weekly-movement.js"));

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

console.log("Weekly movement tests");

test("missing weekly_change renders Movement pending for featured surfaces", () => {
  const movement = WM.formatWeeklyMovement({}, { pendingLabel: WM.WM_PENDING_FEATURED });
  assert.strictEqual(movement.pending, true);
  assert.strictEqual(movement.label, "Movement pending");
});

test("missing weekly_change does not render an up/down arrow", () => {
  const movement = WM.formatWeeklyMovement({ hotness: { momentum_score: 88 } });
  assert.strictEqual(movement.pending, true);
  assert.strictEqual(movement.arrow, "");
  assert.ok(!movement.label.includes("↑"));
  assert.ok(!movement.label.includes("↓"));
});

test("real weekly_change renders correctly", () => {
  const movement = WM.formatWeeklyMovement({ weekly_change: 4.2 });
  assert.strictEqual(movement.pending, false);
  assert.strictEqual(WM.renderWeeklyMovementLabel(movement), "↑ +4.2");
});

test("real zero weekly_change is not treated as missing", () => {
  const movement = WM.formatWeeklyMovement({ weekly_change: 0 });
  assert.strictEqual(movement.pending, false);
  assert.strictEqual(movement.isZero, true);
  assert.strictEqual(movement.label, "No change");
  assert.strictEqual(movement.arrow, "");
  assert.notStrictEqual(movement.label, "Pending");
  assert.notStrictEqual(movement.label, "Movement pending");
});

test("momentum_score is never used as weekly movement", () => {
  const movement = WM.formatWeeklyMovement({
    hotness: {
      momentum_score: 92,
      market_score: 80,
      performance_score: 55,
    },
  });
  assert.strictEqual(movement.pending, true);
  assert.strictEqual(WM.renderWeeklyMovementLabel(movement), "Pending");
});

test("market/performance differences are never used as weekly movement", () => {
  const movement = WM.formatWeeklyMovement({
    hotness: {
      market_score: 95,
      performance_score: 40,
    },
  });
  assert.strictEqual(movement.pending, true);
  assert.ok(!WM.renderWeeklyMovementLabel(movement).includes("+"));
});

test("file-backed leaderboard data without weekly snapshots displays no fabricated trend", () => {
  const weeklyIntelligence = { run: null, todays_leaders: [] };
  assert.strictEqual(WM.shouldShowWeeklyMovementNote(weeklyIntelligence), true);
  const movement = WM.formatWeeklyMovement({ player_name: "Test Player", hotness: { total_score: 90 } });
  assert.strictEqual(movement.label, "Pending");
  assert.strictEqual(movement.arrow, "");
});

test("latest completed official weekly snapshot remains the preferred source", () => {
  const weeklyIntelligence = {
    run: { id: "run-1", completed_at: "2026-07-08T10:00:00Z" },
    todays_leaders: [{ player_name: "Player A", weekly_change: 2.5 }],
  };
  assert.strictEqual(WM.usesOfficialWeeklyLeaders(weeklyIntelligence), true);
  assert.strictEqual(WM.hasCompletedOfficialWeeklyRun(weeklyIntelligence), true);
  assert.strictEqual(WM.shouldShowWeeklyMovementNote(weeklyIntelligence), false);
});

test("Current Featured Signal labeling is used for non-weekly fallback data", () => {
  const presentation = WM.resolveFeaturedSignalPresentation({
    hasOfficialSelection: false,
    entry: { player_name: "Player A", hotness: { total_score: 88 } },
  });
  assert.strictEqual(presentation.label, "Current Featured Signal");
  assert.strictEqual(presentation.showWeeklyMovement, false);
  assert.strictEqual(presentation.movement, null);
});

test("This Week's Signal labeling is used only with stored weekly selection", () => {
  const presentation = WM.resolveFeaturedSignalPresentation({
    hasOfficialSelection: true,
    entry: { weekly_change: 1.5, hotness: { total_score: 91 } },
  });
  assert.strictEqual(presentation.label, "This Week's Signal");
  assert.strictEqual(presentation.showWeeklyMovement, true);
  assert.strictEqual(WM.renderWeeklyMovementLabel(presentation.movement), "↑ +1.5");
});

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed > 0 ? 1 : 0);
