#!/usr/bin/env node
/**
 * Card Registry formatter tests — Sprint 9.1B
 * Run: node tests/test_card_registry.js
 */
const assert = require("assert");
const path = require("path");

require(path.join(__dirname, "..", "frontend", "card-registry.js"));

const CardRegistry = global.CardRegistry;

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

console.log("Card Registry tests");

test("bowman chrome resolves collector identity", () => {
  const identity = CardRegistry.resolveCardIdentity({
    cs_card_id: "mlb:660271:card:bowman_chrome",
    evidence: { query_name: "bowman_chrome", avg_price: 25 },
  });
  assert.strictEqual(identity.brand, "Bowman");
  assert.strictEqual(identity.set, "Chrome");
  assert.strictEqual(identity.average_price, 25);
  assert.strictEqual(CardRegistry.titleLine(identity), "Bowman Chrome");
  assert.strictEqual(CardRegistry.gradeLine(identity), "Raw");
});

test("broad query shows registry data pending", () => {
  const formatted = CardRegistry.formatCardIdentityLines({
    cs_card_id: "mlb:660271:card:broad",
    evidence: { query_name: "broad" },
  });
  assert.strictEqual(formatted.pending, true);
  assert.deepStrictEqual(formatted.lines, [CardRegistry.REGISTRY_DATA_PENDING]);
});

test("identity html never uses placeholder query labels", () => {
  const html = CardRegistry.formatCardIdentityHtml({
    cs_card_id: "mlb:660271:card:broad",
    card_label: "Base Cards",
    player_name: "Elly De La Cruz",
    evidence: { query_name: "broad" },
  });
  assert.ok(html.includes(CardRegistry.REGISTRY_DATA_PENDING));
  assert.ok(!html.includes("Base Cards"));
  assert.ok(!html.includes("Elly De La Cruz"));
});

test("homepage compact html renders multi-line identity", () => {
  const html = CardRegistry.formatCardIdentityCompactHtml({
    cs_card_id: "mlb:660271:card:bowman_chrome",
    evidence: { query_name: "bowman_chrome" },
  });
  assert.ok(html.includes("qi-card-identity-title"));
  assert.ok(html.includes("Bowman Chrome"));
  assert.ok(html.includes("Raw"));
});

test("resolveCardIdentity always includes cs_card_id when provided", () => {
  const identity = CardRegistry.resolveCardIdentity({
    cs_card_id: "mlb:660271:card:auto",
    evidence: { query_name: "auto" },
  });
  assert.strictEqual(identity.cs_card_id, "mlb:660271:card:auto");
  assert.strictEqual(identity.autograph_flag, true);
});

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed > 0 ? 1 : 0);
