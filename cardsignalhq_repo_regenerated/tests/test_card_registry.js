/**
 * Centralized Card Registry tests — single formatter path for all card UI.
 */

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const FRONTEND = path.join(__dirname, "..", "frontend");

function loadRegistry() {
  const code = fs.readFileSync(path.join(FRONTEND, "card-registry.js"), "utf8");
  const sandbox = { window: {}, module: { exports: {} } };
  vm.runInNewContext(code, sandbox);
  return sandbox.window.CardRegistry || sandbox.module.exports;
}

function loadCardReportRenderer() {
  const registryCode = fs.readFileSync(path.join(FRONTEND, "card-registry.js"), "utf8");
  const cardReportCode = fs.readFileSync(path.join(FRONTEND, "card-report.js"), "utf8");
  const sandbox = {
    window: {},
    module: { exports: {} },
    API_BASE_URL: "https://example.test",
    formatScore: (v) => (typeof v === "number" ? v.toFixed(1) : "—"),
    formatTimestamp: (v) => (v ? String(v) : "Pending"),
    csIntelRecommendationClass: () => "cs-recommendation--buy",
    SRMetrics: require(path.join(FRONTEND, "scouting-report-metrics.js")),
    srMetricFormatters: () => ({ money: (v) => `$${v}`, percent: (v) => `${v}%`, score: (v) => String(v) }),
    latestEntries: [],
    fetch: async () => ({ ok: false }),
    document: { addEventListener: () => {}, getElementById: () => null },
    requestAnimationFrame: (fn) => fn(),
    history: { pushState: () => {}, replaceState: () => {} },
    location: { pathname: "/" },
  };
  sandbox.window = sandbox;
  vm.runInNewContext(registryCode, sandbox);
  vm.runInNewContext(cardReportCode, sandbox);
  return sandbox;
}

function testSameIdentityForSameCard() {
  const registry = loadRegistry();
  const card = {
    identity: {
      year: 2023,
      brand: "Bowman",
      set: "Chrome",
      parallel: "Refractor",
      card_number: "BCP-1",
      grade: "10",
      grading_company: "PSA",
      serial_number: "12/99",
    },
  };

  const scoutingHtml = registry.formatCardIdentityHtml(card);
  const ctx = loadCardReportRenderer();
  const reportHtml = ctx.renderCardReport({
    card_identity: card.identity,
    market: {},
    population: {},
    price_history: { series: [] },
    market_drivers: [],
    scarcity_drivers: [],
    recommendation: "WATCH",
    evidence: "INSUFFICIENT",
  });

  assert.ok(scoutingHtml.includes("2023 Bowman Chrome"));
  assert.ok(scoutingHtml.includes("Refractor"));
  assert.ok(scoutingHtml.includes("#BCP-1"));
  assert.ok(scoutingHtml.includes("PSA 10"));
  assert.ok(scoutingHtml.includes("SN 12/99"));
  assert.ok(reportHtml.includes("2023 Bowman Chrome"));
  assert.ok(reportHtml.includes("Refractor"));
  assert.ok(reportHtml.includes("#BCP-1"));
  assert.ok(reportHtml.includes("PSA 10"));
  assert.ok(reportHtml.includes("SN 12/99"));
}

function testCardReportUsesCentralizedFormatter() {
  const cardReportJs = fs.readFileSync(path.join(FRONTEND, "card-report.js"), "utf8");
  assert.ok(cardReportJs.includes("cardReportFormatIdentity"));
  assert.ok(cardReportJs.includes("CardRegistry"));
  assert.ok(!cardReportJs.includes("cr-identity-grid"));
  assert.ok(!cardReportJs.includes('detailRows.push(["Year"'));
}

function testMissingIdentityPendingState() {
  const ctx = loadCardReportRenderer();
  const html = ctx.renderCardReport({
    card_label: "PSA 10",
    market: {},
    population: {},
    price_history: { series: [] },
    market_drivers: [],
    scarcity_drivers: [],
    recommendation: "WATCH",
    evidence: "INSUFFICIENT",
  });
  assert.ok(html.includes("Registry data pending"));
}

function testNoDuplicateNormalizationInCardReport() {
  const cardReportJs = fs.readFileSync(path.join(FRONTEND, "card-report.js"), "utf8");
  assert.ok(!cardReportJs.includes("getCardIdentityFields("));
  assert.ok(!cardReportJs.includes("mapCardRecordToIdentity("));
}

function testRegistryModuleLoadedBeforeApp() {
  const indexHtml = fs.readFileSync(path.join(FRONTEND, "index.html"), "utf8");
  const registryPos = indexHtml.indexOf("card-registry.js");
  const cardReportPos = indexHtml.indexOf("card-report.js");
  const appPos = indexHtml.indexOf("app.js");
  assert.ok(registryPos > -1);
  assert.ok(cardReportPos > registryPos);
  assert.ok(appPos > cardReportPos);
}

function testAppUsesCentralizedRegistry() {
  const appJs = fs.readFileSync(path.join(FRONTEND, "app.js"), "utf8");
  assert.ok(!appJs.includes("function getCardIdentityFields("));
  assert.ok(!appJs.includes("function formatCardIdentityHtml("));
}

function run() {
  testSameIdentityForSameCard();
  testCardReportUsesCentralizedFormatter();
  testMissingIdentityPendingState();
  testNoDuplicateNormalizationInCardReport();
  testRegistryModuleLoadedBeforeApp();
  testAppUsesCentralizedRegistry();
  console.log("All card registry tests passed.");
}

run();
