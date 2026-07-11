#!/usr/bin/env node
/**
 * Focused tests for Scouting Report metric mapping (Release v0.10.3).
 * Run: node tests/test_scouting_report_metrics.js
 */
const assert = require("assert");
const path = require("path");

const SRMetrics = require(path.join(__dirname, "..", "frontend", "scouting-report-metrics.js"));

const {
  srBuildMarketMetrics,
  srBuildCardMetrics,
  srFormatPlayerStat,
  srBuildPlayerSnapshotStats,
  srValidatePlayerStatSpecs,
  SR_STAT_PENDING,
  SR_STAT_PENDING_TITLE,
  SR_PLAYER_SNAPSHOT_KEYS,
  SR_MARKET_METRIC_SPECS,
  SR_CARD_METRIC_SPECS,
  SR_PLAYER_STAT_SPECS,
} = SRMetrics;

const formatters = {
  money: (v) => `$${Number(v).toFixed(2)}`,
  percent: (v) => `${Number(v) >= 0 ? "+" : ""}${Number(v).toFixed(1)}%`,
  score: (v) => Number(v).toFixed(1),
};

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

console.log("Scouting Report metrics tests");

test("player stat spec validation passes", () => {
  const result = srValidatePlayerStatSpecs();
  assert.strictEqual(result.valid, true, result.errors.join("; "));
});

test("AVG never maps to OPS and Runs never maps to Hits", () => {
  const avg7d = SR_PLAYER_STAT_SPECS.last7d.find((s) => s.display_label === "AVG");
  const runs7d = SR_PLAYER_STAT_SPECS.last7d.find((s) => s.display_label === "Runs");
  const warSeason = SR_PLAYER_STAT_SPECS.season.find((s) => s.display_label === "WAR");
  assert.strictEqual(avg7d.source_field, "avg");
  assert.notStrictEqual(avg7d.source_field, "ops");
  assert.strictEqual(runs7d.source_field, "runs");
  assert.notStrictEqual(runs7d.source_field, "hits");
  assert.strictEqual(warSeason.source_field, "war");
  assert.ok(!SR_PLAYER_STAT_SPECS.last7d.some((s) => s.source_field === "war"));
});

test("no player stat uses derived or multi-source fields", () => {
  [...SR_PLAYER_STAT_SPECS.last7d, ...SR_PLAYER_STAT_SPECS.season].forEach((spec) => {
    assert.ok(!spec.derived, `${spec.display_label} must not be derived`);
    assert.ok(!spec.source_fields, `${spec.display_label} must use a single source_field`);
  });
});

test("Last 7 Days includes all supported MLB fields", () => {
  const labels = SR_PLAYER_STAT_SPECS.last7d.map((s) => s.display_label);
  assert.deepStrictEqual(labels, [
    "AVG", "OBP", "SLG", "OPS", "HR", "RBI", "Runs", "Hits", "SB", "BB", "Strikeout %",
  ]);
});

test("Season Snapshot includes all supported MLB fields", () => {
  const labels = SR_PLAYER_STAT_SPECS.season.map((s) => s.display_label);
  assert.deepStrictEqual(labels, [
    "Games", "AVG", "OBP", "SLG", "OPS", "HR", "RBI", "Runs", "Hits", "WAR", "SB", "BB",
  ]);
});

test("snapshotCount is never presented as Auction Count", () => {
  const metrics = srBuildMarketMetrics(
    { evidence: { snapshotCount: 12, listings_count: 40 } },
    { evidence: { snapshot_count: 5 } },
    formatters
  );
  assert.strictEqual(metrics.auctionCount.label, "Auction Count");
  assert.strictEqual(metrics.auctionCount.display, "Auction data pending");
  assert.strictEqual(metrics.auctionCount.pending, true);
  assert.ok(!metrics.auctionCount.display.includes("12"));
  assert.ok(!metrics.auctionCount.display.includes("5"));
});

test("auction_count displays stored value when present", () => {
  const metrics = srBuildMarketMetrics({ evidence: { auction_count: 7 } }, null, formatters);
  assert.strictEqual(metrics.auctionCount.display, "7");
  assert.strictEqual(metrics.auctionCount.pending, false);
});

test("momentum_score is never formatted as a percentage in card metrics", () => {
  const metrics = srBuildCardMetrics(
    { momentum_score: 68, evidence: { avg_price: 25 } },
    formatters
  );
  assert.strictEqual(metrics.momentumScore.label, "Momentum Score");
  assert.strictEqual(metrics.momentumScore.display, "68.0");
  assert.ok(!metrics.momentumScore.display.includes("%"));
  assert.strictEqual(metrics.priceMovement7d.display, "Movement pending");
  assert.strictEqual(metrics.priceMovement7d.pending, true);
});

test("7-Day Movement uses stored price change fields only", () => {
  const metrics = srBuildCardMetrics(
    { median_price_change_pct: 4.2, momentum_score: 80 },
    formatters
  );
  assert.strictEqual(metrics.priceMovement7d.display, "+4.2%");
  assert.strictEqual(metrics.priceMovement7d.pending, false);
  assert.strictEqual(metrics.momentumScore.display, "80.0");
});

test("Median Active Price is pending when median_price is absent", () => {
  const market = srBuildMarketMetrics(
    { evidence: { avg_price: 42.5, listings_count: 18 } },
    null,
    formatters
  );
  assert.strictEqual(market.medianActivePrice.display, "Median price pending");
  assert.strictEqual(market.medianActivePrice.pending, true);
  assert.strictEqual(market.averageActivePrice.display, "$42.50");
  assert.strictEqual(market.averageActivePrice.pending, false);

  const card = srBuildCardMetrics({ evidence: { avg_price: 30 } }, formatters);
  assert.strictEqual(card.medianActivePrice.display, "Median price pending");
  assert.strictEqual(card.averageActivePrice.display, "$30.00");
});

test("Median Active Price uses stored median_price when present", () => {
  const metrics = srBuildMarketMetrics({ evidence: { median_price: 55.25 } }, null, formatters);
  assert.strictEqual(metrics.medianActivePrice.display, "$55.25");
  assert.strictEqual(metrics.medianActivePrice.pending, false);
});

test("Market Depth is pending when no stored value exists", () => {
  const metrics = srBuildMarketMetrics(
    { evidence: { listings_count: 100, avg_price: 20 } },
    null,
    formatters
  );
  assert.strictEqual(metrics.marketDepth.display, "Market depth pending");
  assert.strictEqual(metrics.marketDepth.pending, true);
  assert.ok(!["Deep", "Moderate", "Thin"].includes(metrics.marketDepth.display));
});

test("Market Depth uses stored market_depth when present", () => {
  const metrics = srBuildMarketMetrics({ evidence: { market_depth: "Moderate" } }, null, formatters);
  assert.strictEqual(metrics.marketDepth.display, "Moderate");
  assert.strictEqual(metrics.marketDepth.pending, false);
});

test("missing WAR, Runs, and Strikeout % show Pending rather than dash, zero, or derived values", () => {
  const stats = {
    games: 82,
    avg: 0.285,
    obp: 0.35,
    slg: 0.47,
    home_runs: 12,
    rbi: 40,
    ops: 0.82,
    hits: 90,
    stolen_bases: 5,
    walks: 20,
    at_bats: 100,
    strikeouts: 20,
  };

  const seasonStats = srBuildPlayerSnapshotStats(SR_PLAYER_SNAPSHOT_KEYS.SEASON, stats, formatters);
  const last7dStats = srBuildPlayerSnapshotStats(SR_PLAYER_SNAPSHOT_KEYS.LAST_7D, stats, formatters);

  const war = seasonStats.find((s) => s.label === "WAR");
  const runsSeason = seasonStats.find((s) => s.label === "Runs");
  const runs7d = last7dStats.find((s) => s.label === "Runs");
  const kRate = last7dStats.find((s) => s.label === "Strikeout %");

  assert.strictEqual(war.display, SR_STAT_PENDING);
  assert.strictEqual(war.pending, true);
  assert.strictEqual(runsSeason.display, SR_STAT_PENDING);
  assert.strictEqual(runs7d.display, SR_STAT_PENDING);
  assert.strictEqual(kRate.display, SR_STAT_PENDING);
  assert.notStrictEqual(kRate.display, "20.0%");
  assert.notStrictEqual(war.display, "—");
  assert.notStrictEqual(runs7d.display, "0");
});

test("stored strikeout_rate displays without movement sign prefix", () => {
  const kRate = srFormatPlayerStat(
    SR_PLAYER_STAT_SPECS.last7d.find((s) => s.display_label === "Strikeout %"),
    { strikeout_rate: 22.4 },
    formatters
  );
  assert.strictEqual(kRate.display, "22.4%");
  assert.strictEqual(kRate.pending, false);
  assert.ok(!kRate.display.startsWith("+"));
});

test("real zero values still display as 0", () => {
  const stats = {
    games: 10,
    avg: 0.2,
    obp: 0.3,
    slg: 0.4,
    home_runs: 0,
    rbi: 0,
    ops: 0.6,
    runs: 0,
    war: 0,
    hits: 0,
    stolen_bases: 0,
    walks: 0,
    strikeout_rate: 0,
  };

  const hr = srFormatPlayerStat(
    SR_PLAYER_STAT_SPECS.last7d.find((s) => s.display_label === "HR"),
    stats,
    formatters
  );
  const runs = srFormatPlayerStat(
    SR_PLAYER_STAT_SPECS.last7d.find((s) => s.display_label === "Runs"),
    stats,
    formatters
  );
  const war = srFormatPlayerStat(
    SR_PLAYER_STAT_SPECS.season.find((s) => s.display_label === "WAR"),
    stats,
    formatters
  );
  assert.strictEqual(hr.display, "0");
  assert.strictEqual(runs.display, "0");
  assert.strictEqual(war.display, "0.0");
  assert.strictEqual(hr.pending, false);
  assert.strictEqual(runs.pending, false);
  assert.strictEqual(war.pending, false);
});

test("pending tooltip copy matches sprint spec", () => {
  const stat = srFormatPlayerStat(
    SR_PLAYER_STAT_SPECS.season.find((s) => s.display_label === "WAR"),
    {},
    formatters
  );
  assert.strictEqual(stat.title, SR_STAT_PENDING_TITLE);
  assert.strictEqual(SR_STAT_PENDING_TITLE, "This statistic is not yet available in the current snapshot.");
});

test("Last 7 Days and Season never cross-fallback in snapshot builder", () => {
  const stats7d = { games: 5, avg: 0.31, obp: 0.38, slg: 0.5, ops: 0.88, home_runs: 2, rbi: 6, hits: 8, stolen_bases: 1, walks: 3 };
  const stats30d = { games: 40, avg: 0.27, obp: 0.34, slg: 0.44, ops: 0.78, home_runs: 10, rbi: 30, hits: 42, stolen_bases: 4, walks: 15, war: 2.1 };

  const last7d = srBuildPlayerSnapshotStats(SR_PLAYER_SNAPSHOT_KEYS.LAST_7D, stats7d, formatters);
  const season = srBuildPlayerSnapshotStats(SR_PLAYER_SNAPSHOT_KEYS.SEASON, stats30d, formatters);

  assert.ok(!last7d.some((s) => s.label === "WAR"));
  assert.strictEqual(season.find((s) => s.label === "WAR").display, "2.1");
  assert.strictEqual(last7d.find((s) => s.label === "AVG").display, "0.310");
  assert.strictEqual(season.find((s) => s.label === "AVG").display, "0.270");
  assert.strictEqual(last7d.find((s) => s.label === "Strikeout %").display, SR_STAT_PENDING);
});

test("unavailable values never cause rendering errors", () => {
  assert.doesNotThrow(() => srBuildMarketMetrics(null, undefined, formatters));
  assert.doesNotThrow(() => srBuildCardMetrics(undefined, formatters));
  assert.doesNotThrow(() =>
    SR_PLAYER_STAT_SPECS.last7d.forEach((spec) => srFormatPlayerStat(spec, null, formatters))
  );
  const market = srBuildMarketMetrics({}, null, formatters);
  Object.values(market).forEach((metric) => {
    assert.ok(typeof metric.display === "string");
    assert.ok(metric.display.length > 0);
  });
});

test("metric specs forbid proxy source fields", () => {
  assert.deepStrictEqual(SR_MARKET_METRIC_SPECS.auctionCount.source_fields, ["auction_count"]);
  assert.ok(!SR_MARKET_METRIC_SPECS.auctionCount.source_fields.includes("snapshotCount"));
  assert.ok(!SR_CARD_METRIC_SPECS.priceMovement7d.source_fields.includes("momentum_score"));
  assert.ok(!SR_MARKET_METRIC_SPECS.medianActivePrice.source_fields.includes("avg_price"));
});

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed > 0 ? 1 : 0);
