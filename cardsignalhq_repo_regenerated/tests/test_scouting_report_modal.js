#!/usr/bin/env node
/**
 * Regression: MLB Scouting Report modal data gate for Supabase leaderboard rows.
 * Run: node tests/test_scouting_report_modal.js
 */
const assert = require("assert");
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
require(path.join(__dirname, "..", "frontend", "weekly-convergence.js"));

const {
  loadScoutingReportModel,
  renderScoutingReport,
  renderPlayerHeadshot,
  hasStoredPipelineReportData,
} = require(path.join(__dirname, "..", "frontend", "app.js"));

const JAC_UUID = "91f4f96a-9569-4d0a-8dac-0b65be293350";
const JAC_MLB_ID = "695506";
const UNAVAILABLE = "Stored intelligence is unavailable for this player.";

const jacLeaderboardEntry = {
  player_name: "Jac Caglianone",
  player_id: JAC_UUID,
  rank: 1,
  hotness: {
    performance_score: 78.27,
    market_score: 96.12,
    total_score: 85.41,
    confidence_multiplier: 1.0,
    tag: "HOT",
    reasons: ["elite 7-day OPS"],
  },
  stats_7d: {
    games: 6,
    avg: 0.409,
    home_runs: 2,
    ops: 1.14,
    rbi: 9,
  },
  stats_30d: {
    games: 25,
    avg: 0.312,
    home_runs: 7,
    ops: 0.878,
    rbi: 23,
  },
  stats_season: {
    games: 117,
    avg: 0.276,
    home_runs: 22,
    ops: 0.812,
    rbi: 60,
  },
  market_snapshots: {
    broad: { query_name: "broad", listings_count: 50, avg_price: 17.99 },
  },
};

function jsonResponse(status, body) {
  const ok = status >= 200 && status < 300;
  return {
    ok,
    status,
    json: async () => body,
    text: async () => (typeof body === "string" ? body : JSON.stringify(body)),
  };
}

function installFetchMock() {
  const calls = [];
  global.fetch = async (url) => {
    const href = String(url);
    calls.push(href);
    if (href.includes("/api/players/search")) {
      return jsonResponse(200, [
        {
          player_id: Number(JAC_MLB_ID),
          player_name: "Jac Caglianone",
          sport: "MLB",
          position: "RF",
        },
      ]);
    }
    if (href.includes("/intelligence")) {
      return jsonResponse(404, { detail: "No stored intelligence found" });
    }
    if (href.includes("/signals/weekly")) {
      return jsonResponse(200, { items: [] });
    }
    if (href.includes(`/api/players/${JAC_UUID}`)) {
      return jsonResponse(200, {
        player_name: "Jac Caglianone",
        player_id: JAC_UUID,
        stats_7d: jacLeaderboardEntry.stats_7d,
        stats_30d: jacLeaderboardEntry.stats_30d,
        stats_season: jacLeaderboardEntry.stats_season,
        market_snapshots: jacLeaderboardEntry.market_snapshots,
        hotness: jacLeaderboardEntry.hotness,
        data_source: "supabase",
      });
    }
    return jsonResponse(404, { detail: "not found" });
  };
  return calls;
}

let passed = 0;
let failed = 0;

function test(name, fn) {
  return Promise.resolve()
    .then(fn)
    .then(() => {
      passed += 1;
      console.log(`  ok ${name}`);
    })
    .catch((err) => {
      failed += 1;
      console.error(`  FAIL ${name}`);
      console.error(`       ${err.stack || err.message}`);
    });
}

async function run() {
  console.log("Scouting report modal gate tests");

  await test("pipeline data is recognized on a Supabase-shaped MLB row", () => {
    assert.strictEqual(hasStoredPipelineReportData(jacLeaderboardEntry), true);
  });

  await test("UUID leaderboard row renders without unavailable error", async () => {
    const calls = installFetchMock();
    let model;
    await assert.doesNotReject(async () => {
      model = await loadScoutingReportModel(jacLeaderboardEntry);
    });
    assert.ok(model);
    assert.notStrictEqual(model.intel, null);
    const html = renderScoutingReport(model.player, model.intel, [], model.weeklySnap);
    assert.ok(!String(html).includes(UNAVAILABLE));
    assert.ok(html.includes("sr-report"), "expected Scouting Report root");
    assert.ok(html.includes("Player Snapshot"), "expected Player Snapshot");
    assert.ok(html.includes("sr-snapshot"), "expected snapshot section");
    assert.strictEqual(model.weeklySnap, null);
    assert.strictEqual(model.normalizedPayload, null);

    const intelligenceUrls = calls.filter((url) => url.includes("/intelligence"));
    assert.ok(intelligenceUrls.length >= 1, "expected an MLB intelligence lookup");
    intelligenceUrls.forEach((url) => {
      assert.ok(url.includes(`/MLB/${JAC_MLB_ID}/intelligence`), `expected source id lookup, got ${url}`);
      assert.ok(!url.includes(JAC_UUID), `intelligence URL must not use UUID: ${url}`);
    });

    const weeklyUrls = calls.filter((url) => url.includes("/signals/weekly"));
    weeklyUrls.forEach((url) => {
      assert.ok(!url.includes(JAC_UUID), `weekly URL must not use UUID: ${url}`);
    });
  });

  await test("empty weekly data does not prevent pipeline-backed rendering", async () => {
    installFetchMock();
    const model = await loadScoutingReportModel(jacLeaderboardEntry);
    const html = renderScoutingReport(model.player, model.intel, [], null);
    assert.ok(html.includes("sr-report"));
    assert.ok(html.includes("Player Snapshot"));
    assert.ok(html.includes("Card intelligence pending") || html.includes("Cards"));
  });

  await test("Season Performance uses stats_season games, not stats_30d", async () => {
    installFetchMock();
    const model = await loadScoutingReportModel(jacLeaderboardEntry);
    const html = renderScoutingReport(model.player, model.intel, [], null);
    const season = String(html).match(/<h4 class="sr-panel-title">[^<]*Season Performance<\/h4>[\s\S]*?<\/article>/);
    assert.ok(season, "expected Season Performance panel");
    assert.ok(season[0].includes(">117<"), "expected full-season games");
    assert.ok(!season[0].includes(">25<"), "must not display rolling 30-day games as season");
  });

  await test("missing stats_season is unavailable rather than 30-day fallback", async () => {
    const legacyEntry = { ...jacLeaderboardEntry };
    delete legacyEntry.stats_season;
    const calls = [];
    global.fetch = async (url) => {
      const href = String(url);
      calls.push(href);
      if (href.includes("/api/players/search")) {
        return jsonResponse(200, [{ player_id: Number(JAC_MLB_ID), player_name: "Jac Caglianone", sport: "MLB" }]);
      }
      if (href.includes("/intelligence") || href.includes("/signals/weekly")) {
        return jsonResponse(href.includes("/intelligence") ? 404 : 200, href.includes("/intelligence") ? { detail: "No stored intelligence found" } : { items: [] });
      }
      if (href.includes(`/api/players/${JAC_UUID}`)) {
        return jsonResponse(200, {
          player_name: "Jac Caglianone",
          player_id: JAC_UUID,
          stats_7d: jacLeaderboardEntry.stats_7d,
          stats_30d: jacLeaderboardEntry.stats_30d,
          market_snapshots: jacLeaderboardEntry.market_snapshots,
          hotness: jacLeaderboardEntry.hotness,
          data_source: "supabase",
        });
      }
      return jsonResponse(404, { detail: "not found" });
    };
    const model = await loadScoutingReportModel(legacyEntry);
    const html = renderScoutingReport(model.player, model.intel, [], null);
    const season = String(html).match(/<h4 class="sr-panel-title">[^<]*Season Performance<\/h4>[\s\S]*?<\/article>/);
    assert.ok(season, "expected Season Performance panel");
    assert.ok(season[0].includes("Full-season stats unavailable"));
    assert.ok(!season[0].includes(">25<"));
  });

  await test("older UUID-only row hydrates scouting headshot from resolved MLB ID", async () => {
    installFetchMock();
    const legacyEntry = { ...jacLeaderboardEntry };
    delete legacyEntry.headshot_url;
    delete legacyEntry.source_player_id;
    const model = await loadScoutingReportModel(legacyEntry);
    assert.strictEqual(model.player.source_player_id, JAC_MLB_ID);
    assert.ok(String(model.player.headshot_url).includes(`/people/${JAC_MLB_ID}/`));
    assert.ok(!String(model.player.headshot_url).includes(JAC_UUID));
    const header = renderPlayerHeadshot(model.player);
    assert.ok(header.includes("<img"));
    assert.ok(header.includes(`/people/${JAC_MLB_ID}/`));
    const html = renderScoutingReport(model.player, model.intel, [], null);
    assert.ok(html.includes("sr-report"));
  });

  await test("truly empty player still surfaces unavailable", async () => {
    installFetchMock();
    await assert.rejects(
      () => loadScoutingReportModel({ player_name: "Unknown Player" }),
      (err) => err && err.message === UNAVAILABLE
    );
  });

  console.log(`\n${passed} passed, ${failed} failed`);
  process.exit(failed > 0 ? 1 : 0);
}

run();
