#!/usr/bin/env node
/**
 * Focused tests for CardSignal card intelligence display (Release v0.11.0).
 * Run: node tests/test_card_intelligence.js
 */
const assert = require("assert");
const path = require("path");

const CSCardIntelligence = require(path.join(__dirname, "..", "frontend", "card-intelligence.js"));

const {
  csCardBuildStoredIntel,
  csCardResolveEvidenceTier,
  csCardResolveRecommendation,
  csCardSortByScore,
  csCardReportPath,
  csCardRenderIntelligencePanel,
} = CSCardIntelligence;

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

console.log("Card intelligence display tests");

test("card score resolves from stored card_signal_score", () => {
  const intel = csCardBuildStoredIntel({ card_signal_score: 96.8, recommendation: "BUY" });
  assert.strictEqual(intel.score, 96.8);
  assert.strictEqual(intel.recommendation, "BUY");
});

test("missing recommendation falls back to WATCH", () => {
  assert.strictEqual(csCardResolveRecommendation({}), "WATCH");
});

test("insufficient evidence when score and tier absent", () => {
  assert.strictEqual(csCardResolveEvidenceTier({}), "INSUFFICIENT");
  assert.strictEqual(
    csCardResolveEvidenceTier({ evidence: { evidence_tier: "HIGH" } }),
    "HIGH"
  );
});

test("cards sort by CardSignal Card Score descending", () => {
  const sorted = csCardSortByScore([
    { cs_card_id: "mlb:1:card:broad", card_signal_score: 70 },
    { cs_card_id: "mlb:1:card:psa10", card_signal_score: 96.8 },
    { cs_card_id: "mlb:1:card:auto", card_signal_score: 82.1 },
  ]);
  assert.strictEqual(sorted[0].cs_card_id, "mlb:1:card:psa10");
  assert.strictEqual(sorted[1].cs_card_id, "mlb:1:card:auto");
});

test("card report path is prepared without navigation", () => {
  assert.strictEqual(csCardReportPath("mlb:682829:card:psa10"), "/cards/mlb%3A682829%3Acard%3Apsa10");
  const intel = csCardBuildStoredIntel({ cs_card_id: "mlb:682829:card:psa10" });
  assert.ok(intel.cardReportUrl.includes("/cards/"));
});

test("intelligence panel renders score recommendation evidence explanation", () => {
  const html = csCardRenderIntelligencePanel(
    {
      card_signal_score: 96.4,
      recommendation: "BUY",
      evidence: {
        evidence_tier: "HIGH",
        explanation: "Supported by strong recent offensive production and improving auction demand.",
        factors: [{ emoji: "🔥", label: "Strong Performance", key: "strong_performance" }],
      },
    },
    (v) => Number(v).toFixed(1)
  );
  assert.ok(html.includes("CardSignal Card Score"));
  assert.ok(html.includes("96.4"));
  assert.ok(html.includes("BUY"));
  assert.ok(html.includes("HIGH"));
  assert.ok(html.includes("Supported by"));
  assert.ok(html.includes("Strong Performance"));
});

test("factor chips omitted when not in stored evidence", () => {
  const html = csCardRenderIntelligencePanel(
    { card_signal_score: 50, recommendation: "WATCH", evidence: { evidence_tier: "LOW", explanation: "Limited by soft collector demand." } },
    (v) => String(v)
  );
  assert.ok(!html.includes("sr-card-factor-chip"));
});

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed > 0 ? 1 : 0);
