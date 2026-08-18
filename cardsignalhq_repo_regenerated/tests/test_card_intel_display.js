#!/usr/bin/env node
/**
 * Homepage card-intelligence display: no fake % movement.
 * Run: node tests/test_card_intel_display.js
 */
const assert = require("assert");
const fs = require("fs");
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
const WC = require(path.join(__dirname, "..", "frontend", "weekly-convergence.js"));
const {
  weeklyCardRowToIntelItem,
  renderCardIntelRow,
} = require(path.join(__dirname, "..", "frontend", "app.js"));

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

const altuveLegacy = {
  player_name: "Jose Altuve",
  card_label: "Autographs",
  score: 100.0,
  recommendation: "BUY",
  demand_score: 100.0,
  momentum_score: 1.41,
  market_activity_score: 100.0,
  movement: 100.0,
  evidence: { listings_count: 50, avg_price: 141.29 },
};

const ohtaniLegacy = {
  player_name: "Shohei Ohtani",
  card_label: "Bowman Chrome",
  score: 96.0,
  demand_score: 92.0,
  momentum_score: 51.14,
  market_activity_score: 100.0,
  movement: 51.14,
  evidence: { avg_price: 5114.40 },
};

console.log("Card intelligence display tests");

test("legacy W34 Altuve row does not render +100.0%", () => {
  assert.strictEqual(WC.isHistoricalCardMovement(altuveLegacy), false);
  assert.strictEqual(WC.formatCardRowMovement(altuveLegacy), "—");
  const item = weeklyCardRowToIntelItem(altuveLegacy);
  assert.strictEqual(item.movement, "—");
  assert.ok(!item.movement.includes("%"));
  assert.ok(!item.movement.includes("100.0"));
  const html = renderCardIntelRow(item);
  assert.ok(!html.includes("+100.0%"));
  assert.ok(!html.includes("+100%"));
});

test("legacy Ohtani row does not render +51.1%", () => {
  assert.strictEqual(WC.formatCardRowMovement(ohtaniLegacy), "—");
  const item = weeklyCardRowToIntelItem(ohtaniLegacy);
  assert.strictEqual(item.movement, "—");
  const html = renderCardIntelRow(item);
  assert.ok(!html.includes("+51.1%"));
  assert.ok(!html.includes("+51.14%"));
});

test("genuine historical movement renders +12.3%", () => {
  const row = {
    player_name: "Future Player",
    card_label: "Autographs",
    score: 80,
    movement: 12.34,
    movement_status: "calculated",
    movement_is_historical: true,
    movement_type: "price_change_pct",
    evidence: { avg_price: 40 },
  };
  assert.strictEqual(WC.formatCardRowMovement(row), "+12.3%");
  const item = weeklyCardRowToIntelItem(row);
  assert.strictEqual(item.movement, "+12.3%");
  const html = renderCardIntelRow(item);
  assert.ok(html.includes("+12.3%"));
});

test("genuine negative historical movement renders -8.3%", () => {
  const row = {
    player_name: "Future Player",
    card_label: "PSA 10",
    score: 70,
    movement: -8.27,
    movement_status: "calculated",
    movement_is_historical: true,
    evidence: { avg_price: 30 },
  };
  assert.strictEqual(WC.formatCardRowMovement(row), "-8.3%");
  const item = weeklyCardRowToIntelItem(row);
  assert.strictEqual(item.movement, "-8.3%");
});

test("movement never falls back to demand_score or momentum_score", () => {
  const row = {
    player_name: "Jose Altuve",
    card_label: "Autographs",
    score: 100,
    demand_score: 100,
    momentum_score: 1.41,
    evidence: { avg_price: 141.29 },
  };
  assert.strictEqual(WC.formatCardRowMovement(row), "—");
  const src = fs.readFileSync(path.join(__dirname, "..", "frontend", "app.js"), "utf8");
  assert.ok(!src.includes("row.momentum_score != null ? row.momentum_score : row.demand_score"));
  assert.ok(src.includes("WeeklyConvergence.formatCardRowMovement(row)"));
});

test("price is labeled Avg. listing", () => {
  const item = weeklyCardRowToIntelItem(altuveLegacy);
  assert.strictEqual(item.priceLabel, "Avg. listing $141.29");
  const html = renderCardIntelRow(item);
  assert.ok(html.includes("Avg. listing $141.29"));
  assert.ok(!html.includes("Avg. listing $141.29%") && !html.includes("$141.29%"));
});

test("right-side pill is CARDSIGNAL score without a percent sign", () => {
  const item = weeklyCardRowToIntelItem(altuveLegacy);
  assert.strictEqual(item.score, "100.0");
  assert.strictEqual(item.scoreLabel, "CARDSIGNAL");
  assert.ok(!item.score.includes("%"));
  const html = renderCardIntelRow(item);
  assert.ok(html.includes("CARDSIGNAL"));
  assert.ok(html.includes("100.0"));
  assert.ok(!html.includes("100.0%"));
});

test("app.js card module copy is truthful", () => {
  const src = fs.readFileSync(path.join(__dirname, "..", "frontend", "app.js"), "utf8");
  assert.ok(src.includes("Cards showing the strongest current market activity."));
  assert.ok(src.includes("The sharpest weekly price and demand movement."));
  assert.ok(src.includes("Cards meeting CardSignal's current BUY criteria."));
  assert.ok(src.includes("Card categories with the strongest premium-market concentration."));
  assert.ok(!src.includes("Cards gaining the most attention across the market."));
  assert.ok(!src.includes("Potential value spots before the broader market reacts."));
  assert.ok(!src.includes("The cards and players collectors are chasing hardest."));
  assert.ok(src.includes("biggest_movers"));
  assert.ok(src.includes("CARD_INTEL_MOVEMENT_PENDING") || src.includes("WM_MOVEMENT_NOTE"));
});

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
