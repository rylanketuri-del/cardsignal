#!/usr/bin/env node
/**
 * Sprint 9.7 verification — pending-state copy and API error normalization.
 * Run: node tests/test_sprint_97_verification.js
 */
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const REPO_ROOT = path.resolve(__dirname, "..");
const FRONTEND = path.join(REPO_ROOT, "frontend");

const CC = require(path.join(FRONTEND, "collector-copy.js"));
const SRMetrics = require(path.join(FRONTEND, "scouting-report-metrics.js"));

const {
  srBuildMarketMetrics,
  srBuildCardMetrics,
  srFormatPlayerStat,
  SR_STAT_PENDING,
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

function loadCardReportSandbox() {
  const collectorCode = fs.readFileSync(path.join(FRONTEND, "collector-copy.js"), "utf8");
  const registryCode = fs.readFileSync(path.join(FRONTEND, "card-registry.js"), "utf8");
  const metricsCode = fs.readFileSync(path.join(FRONTEND, "scouting-report-metrics.js"), "utf8");
  const cardReportCode = fs.readFileSync(path.join(FRONTEND, "card-report.js"), "utf8");
  const sandbox = {
    window: {},
    module: { exports: {} },
    API_BASE_URL: "https://example.test",
    formatScore: (v) => (typeof v === "number" ? v.toFixed(1) : "—"),
    formatTimestamp: (v) => (v ? String(v) : "Unavailable"),
    csIntelRecommendationClass: () => "cs-recommendation--buy",
    srMetricFormatters: () => formatters,
    SRMetrics,
    latestEntries: [],
    fetch: async () => ({ ok: false }),
    document: { addEventListener: () => {}, getElementById: () => null },
    requestAnimationFrame: (fn) => fn(),
    history: { pushState: () => {}, replaceState: () => {} },
    location: { pathname: "/" },
  };
  sandbox.window = sandbox;
  vm.runInNewContext(collectorCode, sandbox);
  vm.runInNewContext(registryCode, sandbox);
  vm.runInNewContext(metricsCode, sandbox);
  vm.runInNewContext(cardReportCode, sandbox);
  return sandbox;
}

console.log("Sprint 9.7 verification tests");

// --- Pending states ---

test("1. Player Snapshot stats do not show bare generic Pending", () => {
  assert.notStrictEqual(SR_STAT_PENDING, "Pending");
  const war = srFormatPlayerStat(
    SRMetrics.SR_PLAYER_STAT_SPECS.season.find((s) => s.label === "WAR"),
    { games: 82, avg: 0.285 },
    formatters
  );
  assert.strictEqual(war.display, "Unavailable");
  assert.strictEqual(war.title, "WAR is not available in the current snapshot");
  assert.ok(!war.display.match(/^Pending$/));
});

test("2. Market metrics activeListings, listingsWithBids, momentumScore use specific copy", () => {
  const market = srBuildMarketMetrics({}, null, formatters);
  assert.strictEqual(market.activeListings.display, "Unavailable");
  assert.strictEqual(market.activeListings.title, "Listing data unavailable");
  assert.strictEqual(market.listingsWithBids.display, "Unavailable");
  assert.strictEqual(market.listingsWithBids.title, "Bid activity unavailable");

  const card = srBuildCardMetrics({}, formatters);
  assert.strictEqual(card.momentumScore.display, "Unavailable");
  assert.strictEqual(card.momentumScore.title, "Momentum score unavailable");
  assert.ok(!card.momentumScore.display.includes("%"));
  assert.ok(!card.momentumScore.label.toLowerCase().includes("movement"));
});

test("3. Card Report scarcity fields use field-specific unavailable copy", () => {
  const ctx = loadCardReportSandbox();
  const html = ctx.renderCardReport({
    card_label: "PSA 10",
    population: {},
    market: {},
    recommendation: "BUY",
    evidence: "MEDIUM",
  });
  assert.ok(html.includes('title="Population data pending"') || html.includes('aria-label="Population data pending"'));
  assert.ok(html.includes('title="Serial-number data unavailable"') || html.includes('aria-label="Serial-number data unavailable"'));
  assert.ok(html.includes('title="Parallel data unavailable"') || html.includes('aria-label="Parallel data unavailable"'));
  assert.ok(html.includes('title="Print-run data unavailable"') || html.includes('aria-label="Print-run data unavailable"'));
  assert.ok(
    html.includes('title="More population and supply data required"')
      || html.includes('aria-label="More population and supply data required"')
  );
  assert.ok(!html.match(/>\s*Pending\s*</));
});

test("4. Missing serial number is not Not serial-numbered unless explicitly confirmed", () => {
  const missing = CC.ccResolveSerialNumberDisplay({});
  assert.strictEqual(missing.display, "Unavailable");
  assert.strictEqual(missing.title, "Serial-number data unavailable");
  assert.notStrictEqual(missing.display, "Not serial-numbered");

  const confirmed = CC.ccResolveSerialNumberDisplay({ is_serial_numbered: false });
  assert.strictEqual(confirmed.display, "Not serial-numbered");
  assert.strictEqual(confirmed.title, "Registry confirms this card is not serial-numbered");
});

test("5. Real zero values still display correctly", () => {
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
  const war = srFormatPlayerStat(
    SRMetrics.SR_PLAYER_STAT_SPECS.season.find((s) => s.label === "WAR"),
    stats,
    formatters
  );
  assert.strictEqual(hr.display, "0");
  assert.strictEqual(war.display, "0.0");
  assert.strictEqual(hr.pending, false);
  assert.strictEqual(war.pending, false);
});

// --- Error handling ---

test("6. Raw JSON response is never rendered to users", () => {
  const raw = '{"detail":"column players.foo does not exist","trace":"internal"}';
  const error = CC.createCollectorApiError({ status: 500 }, raw, CC.COLLECTOR_ERROR_CONTEXT.GENERIC);
  assert.ok(!error.userMessage.includes("column players"));
  assert.ok(!error.userMessage.includes("{"));
  assert.strictEqual(error.userMessage, CC.COLLECTOR_USER_MESSAGES.SERVER_ERROR);
});

test("7. Raw HTML response is never rendered to users", () => {
  const raw = "<html><body>502 Bad Gateway nginx</body></html>";
  const error = CC.createCollectorApiError({ status: 502 }, raw, CC.COLLECTOR_ERROR_CONTEXT.GENERIC);
  assert.ok(!error.userMessage.includes("<html>"));
  assert.ok(!error.userMessage.includes("nginx"));
});

test("8. Stack traces are never rendered to users", () => {
  const raw = "Traceback (most recent call last):\n  File main.py";
  const error = CC.createCollectorApiError({ status: 500 }, raw, CC.COLLECTOR_ERROR_CONTEXT.GENERIC);
  assert.ok(!error.userMessage.toLowerCase().includes("traceback"));
  assert.ok(!error.userMessage.includes("main.py"));
});

test("9. App init uses safe collector-facing copy", () => {
  const appJs = fs.readFileSync(path.join(FRONTEND, "app.js"), "utf8");
  assert.ok(appJs.includes("COLLECTOR_ERROR_CONTEXT.APP_INIT"));
  assert.ok(appJs.includes("safeUserMessage(error, COLLECTOR_ERROR_CONTEXT.APP_INIT)"));
  assert.ok(!appJs.includes("Load failed: ${error.message}"));
  const error = CC.createCollectorApiError({ status: 503 }, "service unavailable", CC.COLLECTOR_ERROR_CONTEXT.APP_INIT);
  assert.strictEqual(
    error.userMessage,
    "CardSignal could not load the latest market data. Please try again."
  );
});

test("10. Watchlist uses safe collector-facing copy", () => {
  const appJs = fs.readFileSync(path.join(FRONTEND, "app.js"), "utf8");
  assert.ok(appJs.includes("safeUserMessage(error, COLLECTOR_ERROR_CONTEXT.WATCHLIST)"));
  const error = CC.createCollectorApiError({ status: 500 }, "db error", CC.COLLECTOR_ERROR_CONTEXT.WATCHLIST);
  assert.strictEqual(error.userMessage, "We couldn't update your watchlist. Please try again.");
});

test("11. Notifications use safe collector-facing copy", () => {
  const appJs = fs.readFileSync(path.join(FRONTEND, "app.js"), "utf8");
  assert.ok(appJs.includes("safeUserMessage(error, COLLECTOR_ERROR_CONTEXT.NOTIFICATIONS)"));
  const error = CC.createCollectorApiError({ status: 500 }, "db error", CC.COLLECTOR_ERROR_CONTEXT.NOTIFICATIONS);
  assert.strictEqual(error.userMessage, "Notifications are temporarily unavailable.");
});

test("12. Auth flows use safe collector-facing copy", () => {
  const appJs = fs.readFileSync(path.join(FRONTEND, "app.js"), "utf8");
  assert.ok(appJs.includes("safeAuthErrorMessage(COLLECTOR_ERROR_CONTEXT.AUTH_SIGN_IN)"));
  assert.ok(appJs.includes("safeAuthErrorMessage(COLLECTOR_ERROR_CONTEXT.AUTH_SIGN_UP)"));
  assert.ok(!appJs.includes("setAuthStatus(error.message"));
  assert.strictEqual(
    CC.COLLECTOR_USER_MESSAGES[CC.COLLECTOR_ERROR_CONTEXT.AUTH_SIGN_IN],
    "We couldn't sign you in. Check your details and try again."
  );
});

test("13. 404, 429, 5xx, and network errors map correctly", () => {
  const notFound = CC.createCollectorApiError({ status: 404 }, "{}", CC.COLLECTOR_ERROR_CONTEXT.REPORT);
  assert.strictEqual(notFound.userMessage, "This report could not be found.");

  const rateLimit = CC.createCollectorApiError({ status: 429 }, "{}", CC.COLLECTOR_ERROR_CONTEXT.GENERIC);
  assert.strictEqual(rateLimit.userMessage, CC.COLLECTOR_USER_MESSAGES.RATE_LIMIT);

  const server = CC.createCollectorApiError({ status: 503 }, "{}", CC.COLLECTOR_ERROR_CONTEXT.GENERIC);
  assert.strictEqual(server.userMessage, CC.COLLECTOR_USER_MESSAGES.SERVER_ERROR);

  const network = CC.createNetworkCollectorError(CC.COLLECTOR_ERROR_CONTEXT.GENERIC);
  assert.strictEqual(network.userMessage, CC.COLLECTOR_USER_MESSAGES.NETWORK);
});

test("14. Scouting Report and Card Report errors still use formatCollectorError", () => {
  const appJs = fs.readFileSync(path.join(FRONTEND, "app.js"), "utf8");
  const cardReportJs = fs.readFileSync(path.join(FRONTEND, "card-report.js"), "utf8");
  assert.ok(appJs.includes("formatCollectorError(error"));
  assert.ok(cardReportJs.includes("collectorUserMessage(error, COLLECTOR_ERROR_CONTEXT.CARD_REPORT"));
  const reportError = CC.formatCollectorError(
    CC.createCollectorApiError({ status: 500 }, "{}", CC.COLLECTOR_ERROR_CONTEXT.REPORT)
  );
  assert.strictEqual(reportError, CC.COLLECTOR_COPY.REPORT_UNAVAILABLE);
});

test("15. Sensitive tokens/credentials are never logged", () => {
  const logs = [];
  const original = console.error;
  console.error = (...args) => logs.push(args);
  try {
    const err = CC.createCollectorApiError(
      { status: 401 },
      '{"access_token":"secret-bearer-token","password":"x"}',
      CC.COLLECTOR_ERROR_CONTEXT.AUTH_SESSION
    );
    CC.logCollectorError(err, "auth");
    const serialized = JSON.stringify(logs);
    assert.ok(!serialized.includes("secret-bearer-token"));
    assert.ok(!serialized.includes("password"));
    const payload = logs.find((entry) => Array.isArray(entry) && entry[1]?.code);
    assert.ok(payload, "expected structured log payload");
    assert.strictEqual(payload[1].code, "AUTH_SESSION");
    assert.strictEqual(payload[1].status, 401);
  } finally {
    console.error = original;
  }
});

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed > 0 ? 1 : 0);
