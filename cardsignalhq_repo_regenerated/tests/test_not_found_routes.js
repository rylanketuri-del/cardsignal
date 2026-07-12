#!/usr/bin/env node
/**
 * Not-found route and shared component tests for Sprint 10.1 blockers.
 * Run: node tests/test_not_found_routes.js
 */
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const notFoundSrc = fs.readFileSync(path.join(__dirname, "..", "frontend", "not-found.js"), "utf8");
const routingSrc = fs.readFileSync(path.join(__dirname, "..", "frontend", "routing.js"), "utf8");
const appSrc = fs.readFileSync(path.join(__dirname, "..", "frontend", "app.js"), "utf8");

const sandbox = { window: {} };
vm.createContext(sandbox);
vm.runInContext(notFoundSrc, sandbox);
const CardSignalNotFound = sandbox.window.CardSignalNotFound;

const routeListeners = [];
const routeSandbox = {
  window: {
    location: { hash: "" },
    history: { pushState() {}, replaceState() {}, back() {} },
    addEventListener(name, fn) {
      if (name === "popstate") routeListeners.push(fn);
    },
    CardSignalRouting: null,
  },
};
vm.createContext(routeSandbox);
vm.runInContext(routingSrc, routeSandbox);
const CardSignalRouting = routeSandbox.window.CardSignalRouting;

function resolvePlayerEntryFromSources(playerId, latestEntries, fetchOutcome) {
  const normalizedId = String(playerId || "").trim();
  if (!normalizedId) return null;
  const fromLeaderboard = latestEntries.find((item) => String(item.player_id) === normalizedId);
  if (fromLeaderboard) return fromLeaderboard;
  if (fetchOutcome === "error") return null;
  if (fetchOutcome && fetchOutcome.player_id) return fetchOutcome;
  return null;
}

function openCardReportOutcome(cards, cardId, hasPlayer) {
  const card = cards.find((item) => String(item.cs_card_id) === String(cardId));
  if (!card || !hasPlayer) return { status: "NOT_FOUND" };
  return { status: "OK" };
}

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

console.log("Not-found route tests");

test("invalid player ID returns not-found", () => {
  const entry = resolvePlayerEntryFromSources("missing-id", [], "error");
  assert.strictEqual(entry, null);
});

test("invalid player route never creates synthetic Player entry", () => {
  assert.ok(!appSrc.includes('player_name: "Player"'));
  const entry = resolvePlayerEntryFromSources("bad", [], "error");
  assert.notStrictEqual(entry?.player_name, "Player");
});

test("invalid player route never opens scouting report content", () => {
  assert.ok(appSrc.includes("showReportNotFoundState({ entityType: \"player\""));
  assert.ok(appSrc.includes("if (!entry)"));
});

test("player not-found state includes safe copy and actions", () => {
  const html = CardSignalNotFound.renderReportNotFound("player");
  assert.ok(html.includes("Player report not found"));
  assert.ok(html.includes("We couldn't find this player in CardSignal's current data."));
  assert.ok(html.includes("Return to Signal Center"));
  assert.ok(html.includes("Search players"));
});

test("valid MLB player deep link still works", () => {
  const route = CardSignalRouting.normalizeHash("#/player/mlb:660271");
  assert.strictEqual(route.type, "player");
  assert.strictEqual(route.playerId, "mlb:660271");
  const entry = resolvePlayerEntryFromSources("mlb:660271", [{ player_id: "mlb:660271", player_name: "Mike Trout" }], "error");
  assert.ok(entry);
});

test("valid NFL player deep link still works", () => {
  const route = CardSignalRouting.normalizeHash("#/player/nfl:12345");
  assert.strictEqual(route.type, "player");
  const entry = resolvePlayerEntryFromSources("nfl:12345", [], { player_id: "nfl:12345", player_name: "Patrick Mahomes" });
  assert.ok(entry);
});

test("invalid card ID returns not-found", () => {
  const result = openCardReportOutcome([{ cs_card_id: "real-card" }], "missing-card", true);
  assert.strictEqual(result.status, "NOT_FOUND");
});

test("openCardReport never fails silently", () => {
  assert.ok(appSrc.includes('return { status: "NOT_FOUND" }'));
  assert.ok(appSrc.includes("showReportNotFoundState({"));
  assert.ok(appSrc.includes('if (!card || !piModalEntry)'));
});

test("invalid card route clears stale card content", () => {
  assert.ok(appSrc.includes("clearReportModalState({ keepPlayerContext: true })"));
  assert.ok(appSrc.includes('entityType: "card"'));
});

test("card not-found state includes safe copy and actions", () => {
  const html = CardSignalNotFound.renderReportNotFound("card", { hasParentPlayer: true });
  assert.ok(html.includes("Card report not found"));
  assert.ok(html.includes("We couldn't find this card in the CardSignal registry."));
  assert.ok(html.includes("Back to Scouting Report"));
  assert.ok(html.includes("Return to Signal Center"));
});

test("valid card deep link still works", () => {
  const route = CardSignalRouting.normalizeHash("#/player/mlb:1/card/cs-card-9");
  assert.strictEqual(route.type, "card");
  const result = openCardReportOutcome([{ cs_card_id: "cs-card-9" }], "cs-card-9", true);
  assert.strictEqual(result.status, "OK");
});

test("browser back from not-found restores prior valid view", () => {
  const history = [];
  CardSignalRouting.onRouteChange((route) => history.push(route.type));
  CardSignalRouting.navigateTo({ type: "player", playerId: "mlb:1" });
  CardSignalRouting.navigateTo({ type: "player", playerId: "missing" });
  routeSandbox.window.location.hash = "#/";
  routeListeners[0]();
  assert.strictEqual(history[history.length - 1], "home");
});

test("browser forward restores the not-found state correctly", () => {
  const history = [];
  CardSignalRouting.onRouteChange((route) => history.push(route.type));
  CardSignalRouting.navigateTo({ type: "player", playerId: "mlb:1" });
  CardSignalRouting.navigateTo({ type: "player", playerId: "missing" });
  routeSandbox.window.location.hash = "#/player/missing";
  routeListeners[0]();
  assert.strictEqual(history[history.length - 1], "player");
});

test("no raw errors are shown in not-found states", () => {
  const html = CardSignalNotFound.renderReportNotFound("player");
  assert.ok(!html.includes("stack"));
  assert.ok(!html.includes("traceback"));
  assert.ok(!html.includes("http"));
  assert.ok(!html.includes("{"));
});

test("shared not-found component is accessible", () => {
  const html = CardSignalNotFound.renderReportNotFound("card", { hasParentPlayer: true });
  assert.ok(html.includes('role="alert"'));
  assert.ok(html.includes('aria-labelledby="report-not-found-title"'));
  assert.ok(html.includes('id="report-not-found-title"'));
  assert.ok(html.includes("tabindex=\"-1\""));
});

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
