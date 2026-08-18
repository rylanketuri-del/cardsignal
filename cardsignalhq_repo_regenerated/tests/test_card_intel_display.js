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
  renderCardSection,
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

const stewartLegacy = {
  player_name: "Sal Stewart",
  card_label: "PSA 10",
  score: 100.0,
  demand_score: 100,
  movement: 100,
  evidence: { avg_price: 3783.63 },
};

const ohtaniAutographLegacy = {
  player_name: "Shohei Ohtani",
  card_label: "Autographs",
  score: 93.0,
  demand_score: 90.0,
  momentum_score: 47.15,
  movement: 47.15,
  evidence: { avg_price: 4714.60 },
};

const w34LegacyMovers = [ohtaniLegacy, ohtaniAutographLegacy, stewartLegacy];

const populatedW34CardIntel = {
  trending_cards: [altuveLegacy],
  biggest_movers: w34LegacyMovers,
  buy_low_watch: [altuveLegacy],
  most_chased: [altuveLegacy],
};

function mockCardGrid() {
  const el = { innerHTML: "" };
  global.document = {
    getElementById(id) {
      if (id === "quick-intelligence-grid" || id === "card-section-grid") return el;
      return null;
    },
  };
  return el;
}

function sectionHtml(html, modifier) {
  const match = html.match(
    new RegExp(`<article class="qi-card qi-card--${modifier}[\\s\\S]*?</article>`),
  );
  return match ? match[0] : "";
}

test("legacy Biggest Movers row with momentum_score and no historical marker is filtered out", () => {
  const row = { movement: 51.14, momentum_score: 51.14 };
  assert.strictEqual(WC.isHistoricalCardMovement(row), false);
  assert.strictEqual(WC.hasGenuineHistoricalCardMovement(row), false);
  assert.deepStrictEqual(WC.filterHistoricalCardMovers([row]), []);
});

test("legacy Biggest Movers row with demand_score 100 and no historical marker is filtered out", () => {
  const row = { movement: 100, demand_score: 100 };
  assert.strictEqual(WC.isHistoricalCardMovement(row), false);
  assert.strictEqual(WC.hasGenuineHistoricalCardMovement(row), false);
  assert.deepStrictEqual(WC.filterHistoricalCardMovers([row]), []);
});

test("future genuine historical mover remains and renders +12.3%", () => {
  const row = {
    player_name: "Future Player",
    card_label: "Autographs",
    score: 80,
    movement: 12.34,
    movement_is_historical: true,
    evidence: { avg_price: 40 },
  };
  assert.strictEqual(WC.hasGenuineHistoricalCardMovement(row), true);
  assert.deepStrictEqual(WC.filterHistoricalCardMovers([row]), [row]);
  assert.strictEqual(WC.formatCardRowMovement(row), "+12.3%");
  const item = weeklyCardRowToIntelItem(row);
  assert.strictEqual(item.movement, "+12.3%");
  const html = renderCardIntelRow(item);
  assert.ok(html.includes("+12.3%"));
});

test("future genuine negative mover with movement_status calculated remains and renders -8.3%", () => {
  const row = {
    player_name: "Future Player",
    card_label: "PSA 10",
    score: 70,
    movement: -8.27,
    movement_status: "calculated",
    evidence: { avg_price: 30 },
  };
  assert.strictEqual(WC.hasGenuineHistoricalCardMovement(row), true);
  assert.deepStrictEqual(WC.filterHistoricalCardMovers([row]), [row]);
  assert.strictEqual(WC.formatCardRowMovement(row), "-8.3%");
  const item = weeklyCardRowToIntelItem(row);
  assert.strictEqual(item.movement, "-8.3%");
  const html = renderCardIntelRow(item);
  assert.ok(html.includes("-8.3%"));
});

test("numeric movement alone is not enough to keep a Biggest Mover", () => {
  const row = { movement: 51.14 };
  assert.deepStrictEqual(WC.filterHistoricalCardMovers([row]), []);
  assert.strictEqual(WC.formatCardRowMovement(row), "—");
});

test("W34-style Biggest Movers array of only legacy rows becomes empty", () => {
  assert.deepStrictEqual(WC.filterHistoricalCardMovers(w34LegacyMovers), []);
});

test("empty Biggest Movers UI shows weekly snapshot pending copy", () => {
  const grid = mockCardGrid();
  renderCardSection([], populatedW34CardIntel, { run: { status: "COMPLETED" }, card_intelligence: populatedW34CardIntel });
  const movers = sectionHtml(grid.innerHTML, "movers");
  assert.ok(movers.includes("qi-card--pending"));
  assert.ok(movers.includes("Weekly movement will appear after the next completed weekly snapshot."));
  assert.ok(!movers.includes("Shohei Ohtani"));
  assert.ok(!movers.includes("Sal Stewart"));
  assert.ok(!movers.includes("qi-row-name"));
});

test("Trending Cards are not filtered merely because they lack historical movement", () => {
  const grid = mockCardGrid();
  renderCardSection([], populatedW34CardIntel, { run: { status: "COMPLETED" } });
  const trending = sectionHtml(grid.innerHTML, "trending");
  assert.ok(trending.includes("Jose Altuve · Autographs"));
  assert.ok(trending.includes("qi-move"));
  assert.ok(trending.includes("—"));
  assert.ok(!trending.includes("+100.0%"));
  assert.deepStrictEqual(
    (populatedW34CardIntel.trending_cards || []).map((row) => weeklyCardRowToIntelItem(row).name),
    ["Jose Altuve · Autographs"],
  );
});

test("Buy Low Watch is not filtered merely because it lacks historical movement", () => {
  const grid = mockCardGrid();
  renderCardSection([], populatedW34CardIntel, { run: { status: "COMPLETED" } });
  const buyLow = sectionHtml(grid.innerHTML, "buy-low");
  assert.ok(buyLow.includes("Jose Altuve · Autographs"));
  assert.ok(!buyLow.includes("qi-card--pending"));
});

test("Most Chased is not filtered merely because it lacks historical movement", () => {
  const grid = mockCardGrid();
  renderCardSection([], populatedW34CardIntel, { run: { status: "COMPLETED" } });
  const chased = sectionHtml(grid.innerHTML, "chased");
  assert.ok(chased.includes("Jose Altuve · Autographs"));
  assert.ok(!chased.includes("qi-card--pending"));
});

test("currency formatting uses USD grouping and two decimals", () => {
  assert.strictEqual(WC.formatUsdMoney(5114.4), "$5,114.40");
  assert.strictEqual(WC.formatUsdMoney(4714.6), "$4,714.60");
  assert.strictEqual(WC.formatUsdMoney(3783.63), "$3,783.63");
  assert.strictEqual(WC.formatUsdMoney(1335.35), "$1,335.35");
  assert.strictEqual(WC.formatUsdMoney(141.29), "$141.29");
  assert.strictEqual(WC.formatUsdMoney(125), "$125.00");
  assert.strictEqual(WC.formatAvgListingPrice(5114.4), "Avg. listing $5,114.40");
  assert.strictEqual(weeklyCardRowToIntelItem(ohtaniLegacy).priceLabel, "Avg. listing $5,114.40");
  assert.strictEqual(weeklyCardRowToIntelItem(ohtaniAutographLegacy).priceLabel, "Avg. listing $4,714.60");
  assert.strictEqual(weeklyCardRowToIntelItem(stewartLegacy).priceLabel, "Avg. listing $3,783.63");
  const html = renderCardIntelRow(weeklyCardRowToIntelItem(ohtaniLegacy));
  assert.ok(html.includes("Avg. listing $5,114.40"));
  assert.ok(!html.includes("$5114.40"));
});

test("future genuine mover still appears in Biggest Movers after filtering mixed legacy rows", () => {
  const genuine = {
    player_name: "Future Player",
    card_label: "Autographs",
    score: 80,
    movement: 12.34,
    movement_is_historical: true,
    evidence: { avg_price: 40 },
  };
  const mixed = [ohtaniLegacy, genuine, stewartLegacy];
  const kept = WC.filterHistoricalCardMovers(mixed);
  assert.strictEqual(kept.length, 1);
  assert.strictEqual(kept[0], genuine);
  const grid = mockCardGrid();
  renderCardSection([], {
    ...populatedW34CardIntel,
    biggest_movers: mixed,
  }, { run: { status: "COMPLETED" } });
  const movers = sectionHtml(grid.innerHTML, "movers");
  assert.ok(movers.includes("Future Player · Autographs"));
  assert.ok(movers.includes("+12.3%"));
  assert.ok(!movers.includes("Shohei Ohtani"));
  assert.ok(!movers.includes("Sal Stewart"));
});

test("app.js filters Biggest Movers only at the display boundary", () => {
  const src = fs.readFileSync(path.join(__dirname, "..", "frontend", "app.js"), "utf8");
  assert.ok(src.includes("filterHistoricalCardMovers"));
  assert.ok(src.includes('box.key === "biggest_movers"'));
  assert.ok(!src.includes("filterHistoricalCardMovers(stored.trending_cards"));
  assert.ok(!src.includes("filterHistoricalCardMovers(stored.buy_low_watch"));
  assert.ok(!src.includes("filterHistoricalCardMovers(stored.most_chased"));
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
