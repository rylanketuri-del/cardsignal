/**
 * Card Report frontend tests — router, rendering, and static guards.
 */

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const REPO_ROOT = path.resolve(__dirname, "..");
const FRONTEND = path.join(REPO_ROOT, "frontend");

function loadCardReportModule() {
  const metricsCode = fs.readFileSync(path.join(FRONTEND, "scouting-report-metrics.js"), "utf8");
  const cardReportCode = fs.readFileSync(path.join(FRONTEND, "card-report.js"), "utf8");

  const sandbox = {
    window: {},
    module: { exports: {} },
    API_BASE_URL: "https://example.test",
    formatScore: (v) => (typeof v === "number" ? v.toFixed(1) : "—"),
    formatTimestamp: (v) => (v ? String(v) : "Pending"),
    csIntelRecommendationClass: () => "cs-recommendation--buy",
    formatCardIdentityHtml: () => "<p class=\"sr-card-title\">2023 Bowman Chrome</p>",
    getCardIdentityFields: () => ({ year: 2023, brand: "Bowman", set: "Chrome" }),
    srMetricFormatters: () => ({ money: (v) => `$${v}`, percent: (v) => `${v}%`, score: (v) => String(v) }),
    SRMetrics: require(path.join(REPO_ROOT, "tests", "..", "frontend", "scouting-report-metrics.js")),
    latestEntries: [],
    fetch: async () => ({ ok: false }),
    document: { addEventListener: () => {}, getElementById: () => null },
    requestAnimationFrame: (fn) => fn(),
    history: { pushState: () => {}, replaceState: () => {} },
    location: { pathname: "/" },
  };
  sandbox.window = sandbox;

  vm.runInNewContext(metricsCode, sandbox);
  vm.runInNewContext(cardReportCode, sandbox);

  return sandbox;
}

function testRouterParsePathname() {
  const ctx = loadCardReportModule();
  const router = ctx.CardReportRouter;
  const csCardId = "mlb:660271:card:psa10";
  const encoded = encodeURIComponent(csCardId);
  const parsed = router.parsePathname(`/cards/${encoded}`);
  assert.strictEqual(parsed, csCardId);
  assert.strictEqual(router.parsePathname("/"), null);
  assert.strictEqual(router.parsePathname("/api/health"), null);
}

function testRouterBuildPath() {
  const ctx = loadCardReportModule();
  const csCardId = "mlb:660271:card:psa10";
  const built = ctx.CardReportRouter.buildPath(csCardId);
  assert.strictEqual(built, `/cards/${encodeURIComponent(csCardId)}`);
}

function testRenderCardReportHeader() {
  const ctx = loadCardReportModule();
  const html = ctx.renderCardReportHeader({
    cs_card_id: "mlb:660271:card:psa10",
    player_name: "Aaron Judge",
    player_id: "660271",
    card_label: "PSA 10",
    card_score: 72.5,
    recommendation: "BUY",
    evidence: "MEDIUM",
    updated_at: "2026-07-08T12:00:00Z",
    algorithm_version: "WEEKLY_INTELLIGENCE_V1",
  });
  assert.ok(html.includes("CardSignal Score"));
  assert.ok(html.includes("Where performance meets the market."));
  assert.ok(html.includes("Aaron Judge"));
  assert.ok(html.includes("BUY"));
  assert.ok(html.includes("MEDIUM"));
}

function testRenderCardReportSections() {
  const ctx = loadCardReportModule();
  const html = ctx.renderCardReport({
    card_label: "PSA 10",
    card_identity: { year: 2023, brand: "Bowman", set: "Chrome", grade: "10", grading_company: "PSA" },
    market: { median_price: null, average_price: 145, active_listings: 12, data_quality: "Complete" },
    population: { psa_population: 8 },
    price_history: { series: [{ period_label: "Week 28" }], status: "coming_soon" },
    market_drivers: [{ label: "Active Listings", detail: "12 active listings" }],
    scarcity_drivers: [{ label: "PSA 10 Listings", detail: "8 PSA 10 listings" }],
    recommendation: "BUY",
    evidence: "MEDIUM",
    outlook_summary: "Stored market inputs support BUY.",
    outlook_evidence: ["improving demand"],
  });
  assert.ok(html.includes("Card Identity"));
  assert.ok(html.includes("Card Snapshot"));
  assert.ok(html.includes("Price history coming soon."));
  assert.ok(html.includes("Market Drivers"));
  assert.ok(html.includes("Scarcity"));
  assert.ok(html.includes("Card Outlook"));
}

function testCardReportEvidenceClass() {
  const ctx = loadCardReportModule();
  assert.strictEqual(ctx.cardReportEvidenceClass("HIGH"), "cs-evidence--high");
  assert.strictEqual(ctx.cardReportEvidenceClass("INSUFFICIENT"), "cs-evidence--insufficient");
}

function testCardReportModuleLoadedBeforeApp() {
  const indexHtml = fs.readFileSync(path.join(FRONTEND, "index.html"), "utf8");
  const cardReportPos = indexHtml.indexOf("card-report.js");
  const appPos = indexHtml.indexOf("app.js");
  assert.ok(cardReportPos > -1, "card-report.js must be in index.html");
  assert.ok(appPos > cardReportPos, "card-report.js must load before app.js");
}

function testNoFabricatedCardNamesInCardReport() {
  const cardReportJs = fs.readFileSync(path.join(FRONTEND, "card-report.js"), "utf8");
  assert.ok(!cardReportJs.includes("Placeholder Card"));
  assert.ok(!cardReportJs.includes("Sample Card"));
}

function run() {
  testRouterParsePathname();
  testRouterBuildPath();
  testRenderCardReportHeader();
  testRenderCardReportSections();
  testCardReportEvidenceClass();
  testCardReportModuleLoadedBeforeApp();
  testNoFabricatedCardNamesInCardReport();
  console.log("All card report tests passed.");
}

run();
