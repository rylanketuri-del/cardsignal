#!/usr/bin/env node
/**
 * Routing and navigation tests for Sprint 10.1.
 * Run: node tests/test_routing.js
 */
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const routingSrc = fs.readFileSync(path.join(__dirname, "..", "frontend", "routing.js"), "utf8");

const listeners = [];
const sandbox = {
  window: {
    location: { hash: "" },
    history: {
      pushState() {},
      replaceState() {},
      back() {},
    },
    addEventListener(name, fn) {
      if (name === "popstate") listeners.push(fn);
    },
    CardSignalRouting: null,
  },
};

vm.createContext(sandbox);
vm.runInContext(routingSrc, sandbox);
const CardSignalRouting = sandbox.window.CardSignalRouting;

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

console.log("Routing tests");

test("normalize home route", () => {
  assert.strictEqual(CardSignalRouting.normalizeHash("#/").type, "home");
  assert.strictEqual(CardSignalRouting.normalizeHash("").type, "home");
});

test("normalize player route", () => {
  const route = CardSignalRouting.normalizeHash("#/player/mlb:12345");
  assert.strictEqual(route.type, "player");
  assert.strictEqual(route.playerId, "mlb:12345");
});

test("normalize card route", () => {
  const route = CardSignalRouting.normalizeHash("#/player/mlb:1/card/cs-card-9");
  assert.strictEqual(route.type, "card");
  assert.strictEqual(route.playerId, "mlb:1");
  assert.strictEqual(route.cardId, "cs-card-9");
});

test("invalid route is flagged", () => {
  const route = CardSignalRouting.normalizeHash("#/unknown/path");
  assert.strictEqual(route.type, "invalid");
});

test("buildHash round trip for player", () => {
  const hash = CardSignalRouting.buildHash({ type: "player", playerId: "abc" });
  const route = CardSignalRouting.normalizeHash(hash);
  assert.strictEqual(route.type, "player");
  assert.strictEqual(route.playerId, "abc");
});

test("popstate listener registered", () => {
  assert.ok(listeners.length >= 1);
});

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
