#!/usr/bin/env node
/**
 * Card Intelligence Ranking tests (Release v0.13.1 / Sprint 9.6).
 * Run: node tests/test_card_intelligence_ranking.js
 */
const assert = require("assert");
const path = require("path");

const CardRegistry = require(path.join(__dirname, "..", "frontend", "card-registry.js"));
const SRMetrics = require(path.join(__dirname, "..", "frontend", "scouting-report-metrics.js"));
const CardIntelligenceRanking = require(path.join(__dirname, "..", "frontend", "card-intelligence-ranking.js"));

global.CardRegistry = CardRegistry;
global.SRMetrics = SRMetrics;

const {
  rankPlayerCards,
  resolveCardSignalScore,
  computeCardEvidenceStrength,
  buildCardIdentityKey,
  buildStoredCardEvidenceText,
  buildStoredCardExplanation,
  buildCardMarketSnapshot,
  CARD_RANKING_EXPLANATION,
} = CardIntelligenceRanking;

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

console.log("Card Intelligence Ranking tests");

test("sorts by CardSignal Card Score descending", () => {
  const cards = [
    { cs_card_id: "mlb:1:card:auto", card_signal_score: 55, evidence: { listings_count: 2 } },
    { cs_card_id: "mlb:1:card:psa10", card_signal_score: 82, evidence: { listings_count: 4 } },
    { cs_card_id: "mlb:1:card:broad", card_signal_score: 71, evidence: { listings_count: 3 } },
  ];
  const ranked = rankPlayerCards(cards);
  assert.deepStrictEqual(
    ranked.map((c) => c.cs_card_id),
    ["mlb:1:card:psa10", "mlb:1:card:broad", "mlb:1:card:auto"]
  );
});

test("cards without scores rank after scored cards", () => {
  const cards = [
    { cs_card_id: "mlb:1:card:auto", card_signal_score: null, evidence: {} },
    { cs_card_id: "mlb:1:card:psa10", card_signal_score: 60, evidence: { listings_count: 1 } },
  ];
  const ranked = rankPlayerCards(cards);
  assert.strictEqual(ranked[0].cs_card_id, "mlb:1:card:psa10");
  assert.strictEqual(ranked[1].cs_card_id, "mlb:1:card:auto");
});

test("tie-breaks by stronger evidence, then identity, then cs_card_id", () => {
  const cards = [
    {
      cs_card_id: "mlb:1:card:bowman_chrome",
      card_signal_score: 70,
      card_label: "Bowman Chrome",
      evidence: { listings_count: 2 },
      missing_inputs: ["population"],
    },
    {
      cs_card_id: "mlb:1:card:auto",
      card_signal_score: 70,
      card_label: "Autographs",
      evidence: { listings_count: 2, outlook_reasons: ["listing volume increased"] },
      missing_inputs: [],
    },
    {
      cs_card_id: "mlb:1:card:broad",
      card_signal_score: 70,
      card_label: "Base Cards",
      evidence: { listings_count: 2, outlook_reasons: ["listing volume increased"] },
      missing_inputs: [],
    },
  ];
  const ranked = rankPlayerCards(cards);
  assert.strictEqual(ranked[0].cs_card_id, "mlb:1:card:auto");
  assert.strictEqual(ranked[1].cs_card_id, "mlb:1:card:broad");
  assert.strictEqual(ranked[2].cs_card_id, "mlb:1:card:bowman_chrome");
});

test("identity tie-break uses registry fields when present", () => {
  const cards = [
    {
      cs_card_id: "mlb:1:card:z",
      card_signal_score: 65,
      evidence: { listings_count: 1 },
      identity: { year: 2024, brand: "Topps", set: "Chrome" },
    },
    {
      cs_card_id: "mlb:1:card:a",
      card_signal_score: 65,
      evidence: { listings_count: 1 },
      identity: { year: 2023, brand: "Bowman", set: "Chrome" },
    },
  ];
  const ranked = rankPlayerCards(cards);
  assert.strictEqual(ranked[0].cs_card_id, "mlb:1:card:a");
  assert.strictEqual(ranked[1].cs_card_id, "mlb:1:card:z");
  assert.ok(buildCardIdentityKey(cards[1]).localeCompare(buildCardIdentityKey(cards[0])) < 0);
});

test("ranking is deterministic across repeated sorts", () => {
  const cards = [
    { cs_card_id: "mlb:1:card:c", card_signal_score: 50, evidence: { listings_count: 1 } },
    { cs_card_id: "mlb:1:card:a", card_signal_score: 50, evidence: { listings_count: 1 } },
    { cs_card_id: "mlb:1:card:b", card_signal_score: 50, evidence: { listings_count: 1 } },
  ];
  const first = rankPlayerCards(cards).map((c) => c.cs_card_id);
  const second = rankPlayerCards([...cards].reverse()).map((c) => c.cs_card_id);
  assert.deepStrictEqual(first, second);
});

test("does not sort by price or listing count", () => {
  const cards = [
    {
      cs_card_id: "mlb:1:card:expensive",
      card_signal_score: 40,
      evidence: { listings_count: 100, avg_price: 500 },
    },
    {
      cs_card_id: "mlb:1:card:cheap",
      card_signal_score: 90,
      evidence: { listings_count: 1, avg_price: 5 },
    },
  ];
  const ranked = rankPlayerCards(cards);
  assert.strictEqual(ranked[0].cs_card_id, "mlb:1:card:cheap");
});

test("stored explanation uses outlook fields only", () => {
  const withSummary = buildStoredCardExplanation({
    evidence: { outlook_summary: "Stored analyst summary." },
  });
  assert.strictEqual(withSummary, "Stored analyst summary.");

  const withReason = buildStoredCardExplanation({
    evidence: { outlook_reasons: ["listing volume increased"] },
  });
  assert.strictEqual(withReason, "listing volume increased");

  const missing = buildStoredCardExplanation({ evidence: { listings_count: 3 } });
  assert.strictEqual(missing, null);
});

test("stored evidence text never fabricates ranking reasons", () => {
  const text = buildStoredCardEvidenceText({
    evidence: { listings_count: 4 },
  });
  assert.ok(text.includes("4 active listings"));

  const empty = buildStoredCardEvidenceText({ evidence: {} });
  assert.strictEqual(empty, null);
});

test("market snapshot uses stored card metrics only", () => {
  const snapshot = buildCardMarketSnapshot(
    {
      evidence: { listings_count: 8, avg_price: 42.5 },
      median_price_change_pct: 3.1,
    },
    formatters
  );
  assert.ok(snapshot.includes("8 listings"));
  assert.ok(snapshot.includes("avg $42.50"));
  assert.ok(snapshot.includes("+3.1%"));
});

test("ranking explanation copy is informational", () => {
  assert.ok(CARD_RANKING_EXPLANATION.includes("CardSignal Intelligence"));
  assert.ok(!CARD_RANKING_EXPLANATION.toLowerCase().includes("weight"));
});

test("resolveCardSignalScore reads score and card_signal_score", () => {
  assert.strictEqual(resolveCardSignalScore({ card_signal_score: 72.4 }), 72.4);
  assert.strictEqual(resolveCardSignalScore({ score: 61 }), 61);
  assert.strictEqual(resolveCardSignalScore({}), null);
});

test("evidence strength subtracts missing inputs", () => {
  const weaker = computeCardEvidenceStrength({
    evidence: { listings_count: 2 },
    missing_inputs: ["population", "median_price"],
  });
  const stronger = computeCardEvidenceStrength({
    evidence: { listings_count: 2, outlook_reasons: ["valid signal"] },
    missing_inputs: [],
  });
  assert.ok(stronger > weaker);
});

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed > 0 ? 1 : 0);
