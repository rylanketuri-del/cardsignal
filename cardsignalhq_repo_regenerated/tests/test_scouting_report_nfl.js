#!/usr/bin/env node
/**
 * NFL Scouting Report mapper and search navigation tests.
 * Run: node tests/test_scouting_report_nfl.js
 */
const assert = require("assert");
const path = require("path");

const SRNfl = require(path.join(__dirname, "..", "frontend", "scouting-report-nfl.js"));

const {
  srNflResolvePlayerId,
  srNflFormatDateRange,
  srNflMapScoutingReport,
  srNflMapSignalDrivers,
  srNflResolveSearchEntry,
  SR_NFL_PENDING_RANGE,
  SR_NFL_NO_DRIVERS,
} = SRNfl;

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

console.log("NFL Scouting Report tests");

test("every NFL search result exposes stable player_id", () => {
  const entry = { player_id: "TEST-WR-01", source_player_id: "TEST-WR-01", cs_player_id: "CS-NFL-P-TEST-WR-01" };
  assert.strictEqual(srNflResolvePlayerId(entry), "TEST-WR-01");
});

test("date range renders human-readable period", () => {
  const label = srNflFormatDateRange("2026-06-01", "2026-06-22");
  assert.ok(label.includes("Jun"));
  assert.ok(label.includes("2026"));
  assert.ok(!label.includes("T"));
});

test("missing date range shows pending state", () => {
  assert.strictEqual(srNflFormatDateRange(null, null), SR_NFL_PENDING_RANGE);
});

test("captured_at is not used as performance period in mapper", () => {
  const mapped = srNflMapScoutingReport(
    {},
    {
      evidence: {
        nfl_season_phase: "REGULAR_SEASON",
        nfl_season: 2025,
        nfl_recent_window: { period_start: "2026-06-01", period_end: "2026-06-22", games_in_window: 3 },
        nfl_season_window: { period_start: "2026-01-01", period_end: "2026-06-22" },
        nfl_recent_stats: { games_played: 3, passing_yards: 100 },
        nfl_season_stats: { games_played: 8, passing_yards: 900 },
        nfl_signal_drivers: [],
      },
      captured_at: "2026-07-01T12:00:00Z",
    }
  );
  assert.strictEqual(mapped.recentDateRange, srNflFormatDateRange("2026-06-01", "2026-06-22"));
  assert.ok(mapped.seasonWindowLabel.includes("2025"));
});

test("offseason uses previous-season labels", () => {
  const mapped = srNflMapScoutingReport(
    {},
    {
      evidence: {
        nfl_season_phase: "OFFSEASON",
        nfl_season: 2024,
        nfl_season_window: { period_start: "2024-09-01", period_end: "2025-01-15" },
        nfl_season_stats: { games_played: 17 },
        nfl_signal_drivers: [],
      },
    }
  );
  assert.ok(mapped.seasonWindowLabel.includes("Previous Season"));
  assert.strictEqual(mapped.showRecentPanel, false);
});

test("stored NFL drivers render with required fields", () => {
  const drivers = srNflMapSignalDrivers([
    {
      driver_type: "PASSING_SURGE",
      label: "Passing Surge",
      description: "Passing production elevated in recent window.",
      source_method: "APPROVED_IMPORT",
      captured_at: "2026-07-01T00:00:00Z",
      season_phase: "REGULAR_SEASON",
    },
  ]);
  assert.strictEqual(drivers.length, 1);
  assert.strictEqual(drivers[0].title, "Passing Surge");
  assert.strictEqual(drivers[0].sourceType, "APPROVED_IMPORT");
  assert.ok(drivers[0].impact);
  assert.ok(drivers[0].occurredAt);
});

test("unsupported rumor driver shape is excluded", () => {
  const drivers = srNflMapSignalDrivers([
    { driver_type: "TRADE", label: "", description: "rumor", source_method: "UNAVAILABLE" },
  ]);
  assert.strictEqual(drivers.length, 0);
});

test("empty driver state is intentional", () => {
  const mapped = srNflMapScoutingReport({}, { evidence: { nfl_season_phase: "REGULAR_SEASON", nfl_signal_drivers: [] } });
  assert.deepStrictEqual(mapped.signalDrivers, []);
  assert.strictEqual(SR_NFL_NO_DRIVERS, "No verified Signal Drivers are available.");
});

test("same-name NFL players resolve by player_id", () => {
  const matches = [
    { player_id: "TEST-QB-A", source_player_id: "TEST-QB-A", player_name: "Test Player", team: "AAA", position: "QB" },
    { player_id: "TEST-QB-B", source_player_id: "TEST-QB-B", player_name: "Test Player", team: "BBB", position: "QB" },
  ];
  const first = srNflResolveSearchEntry(matches, "TEST-QB-A");
  const second = srNflResolveSearchEntry(matches, "TEST-QB-B");
  assert.strictEqual(first.team, "AAA");
  assert.strictEqual(second.team, "BBB");
});

test("frontend mapper receives stored nfl_season_phase", () => {
  const mapped = srNflMapScoutingReport({}, { evidence: { nfl_season_phase: "PRESEASON", nfl_season: 2025 } });
  assert.strictEqual(mapped.nflSeasonPhase, "PRESEASON");
});

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
