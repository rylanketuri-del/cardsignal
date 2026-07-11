#!/usr/bin/env node
/**
 * Focused tests for Scouting Report metric mapping (Release v0.10.2).
 * Run: node tests/test_scouting_report_metrics.js
 */
const assert = require("assert");
const path = require("path");

const SRMetrics = require(path.join(__dirname, "..", "frontend", "scouting-report-metrics.js"));

const {
  srBuildMarketMetrics,
  srBuildCardMetrics,
  srFormatPlayerStat,
  SR_STAT_PENDING,
  SR_MARKET_METRIC_SPECS,
  SR_CARD_METRIC_SPECS,
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

test("snapshotCount is never presented as Auction Count", () => {
  const metrics = srBuildMarketMetrics(
    { evidence: { snapshotCount: 12, listings_count: 40 } },
    { evidence: { snapshot_count: 5 } },
    formatters
  );
  assert.strictEqual(metrics.auctionCount.label, "Auction Count");
  assert.strictEqual(metrics.auctionCount.display, "Unavailable");
  assert.strictEqual(metrics.auctionCount.title, "Auction data unavailable");
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
  assert.strictEqual(metrics.priceMovement7d.display, "Unavailable");
  assert.strictEqual(metrics.priceMovement7d.title, "Movement unavailable — available after the next market snapshot");
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

test("Median Active Price is unavailable when median_price is absent", () => {
  const market = srBuildMarketMetrics(
    { evidence: { avg_price: 42.5, listings_count: 18 } },
    null,
    formatters
  );
  assert.strictEqual(market.medianActivePrice.display, "Unavailable");
  assert.ok(market.medianActivePrice.title.includes("Median price unavailable"));
  assert.strictEqual(market.medianActivePrice.pending, true);
  assert.strictEqual(market.averageActivePrice.display, "$42.50");
  assert.strictEqual(market.averageActivePrice.pending, false);

  const card = srBuildCardMetrics({ evidence: { avg_price: 30 } }, formatters);
  assert.strictEqual(card.medianActivePrice.display, "Unavailable");
  assert.strictEqual(card.averageActivePrice.display, "$30.00");
});

test("Median Active Price uses stored median_price when present", () => {
  const metrics = srBuildMarketMetrics({ evidence: { median_price: 55.25 } }, null, formatters);
  assert.strictEqual(metrics.medianActivePrice.display, "$55.25");
  assert.strictEqual(metrics.medianActivePrice.pending, false);
});

test("Market Depth is unavailable when no stored value exists", () => {
  const metrics = srBuildMarketMetrics(
    { evidence: { listings_count: 100, avg_price: 20 } },
    null,
    formatters
  );
  assert.strictEqual(metrics.marketDepth.display, "Unavailable");
  assert.strictEqual(metrics.marketDepth.title, "Market depth unavailable");
  assert.strictEqual(metrics.marketDepth.pending, true);
  assert.ok(!["Deep", "Moderate", "Thin"].includes(metrics.marketDepth.display));
});

test("Market Depth uses stored market_depth when present", () => {
  const metrics = srBuildMarketMetrics({ evidence: { market_depth: "Moderate" } }, null, formatters);
  assert.strictEqual(metrics.marketDepth.display, "Moderate");
  assert.strictEqual(metrics.marketDepth.pending, false);
});

test("missing WAR and Runs show Unavailable with context rather than dash or zero", () => {
  const stats = { games: 82, avg: 0.285, home_runs: 12, rbi: 40, ops: 0.82 };
  const war = srFormatPlayerStat(
    SRMetrics.SR_PLAYER_STAT_SPECS.season.find((s) => s.label === "WAR"),
    stats,
    formatters
  );
  const runs = srFormatPlayerStat(
    SRMetrics.SR_PLAYER_STAT_SPECS.last7d.find((s) => s.label === "Runs"),
    { ...stats, at_bats: 100, strikeouts: 20 },
    formatters
  );
  assert.strictEqual(war.display, SR_STAT_PENDING);
  assert.strictEqual(war.title, "WAR is not available in the current snapshot");
  assert.strictEqual(war.pending, true);
  assert.strictEqual(runs.display, SR_STAT_PENDING);
  assert.strictEqual(runs.title, "Runs total unavailable for this period");
  assert.strictEqual(runs.pending, true);
  assert.notStrictEqual(war.display, "—");
  assert.notStrictEqual(runs.display, "0");
  assert.notStrictEqual(war.display, "Pending");
});

test("real zero values still display as 0", () => {
  const stats = {
    games: 10,
    avg: 0.2,
    home_runs: 0,
    rbi: 0,
    ops: 0.6,
    runs: 0,
    war: 0,
    hits: 0,
    stolen_bases: 0,
    walks: 0,
    at_bats: 20,
    strikeouts: 0,
  };
  const hr = srFormatPlayerStat(
    SRMetrics.SR_PLAYER_STAT_SPECS.last7d.find((s) => s.label === "HR"),
    stats,
    formatters
  );
  const runs = srFormatPlayerStat(
    SRMetrics.SR_PLAYER_STAT_SPECS.last7d.find((s) => s.label === "Runs"),
    stats,
    formatters
  );
  const war = srFormatPlayerStat(
    SRMetrics.SR_PLAYER_STAT_SPECS.season.find((s) => s.label === "WAR"),
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

test("unavailable values never cause rendering errors", () => {
  assert.doesNotThrow(() => srBuildMarketMetrics(null, undefined, formatters));
  assert.doesNotThrow(() => srBuildCardMetrics(undefined, formatters));
  assert.doesNotThrow(() =>
    SRMetrics.SR_PLAYER_STAT_SPECS.last7d.forEach((spec) =>
      srFormatPlayerStat(spec, null, formatters)
    )
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
