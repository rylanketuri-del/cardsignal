#!/usr/bin/env node
/**
 * This Week's Signal MLB hero headshot sharpness.
 * Run: node tests/test_signal_week_hero.js
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
require(path.join(__dirname, "..", "frontend", "weekly-convergence.js"));

const {
  mlbHeadshotUrlFromSourceId,
  mlbSourceIdFromValue,
  getSignalOfWeekHeadshotUrl,
  renderSignalWeekPlayerImage,
  renderLeaderHeadshot,
  renderPlayerHeadshot,
} = require(path.join(__dirname, "..", "frontend", "app.js"));

const PLAYER_A = "660271";
const PLAYER_B = "592450";
const UUID = "9ed6461a-a34b-4205-b55d-4da9dd203796";
const NFL_HEADSHOT = "https://static.www.nfl.com/image/upload/f_auto,q_auto/league/example";
const NBA_HEADSHOT = "https://cdn.nba.com/headshots/nba/latest/1040x760/2544.png";

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

console.log("This Week's Signal hero image tests");

test("mlbHeadshotUrlFromSourceId defaults to w_213", () => {
  const url = mlbHeadshotUrlFromSourceId(PLAYER_A);
  assert.ok(url.includes(`/people/${PLAYER_A}/`));
  assert.ok(url.includes("/w_213,"));
  assert.ok(!url.includes("/w_640,"));
});

test("mlbHeadshotUrlFromSourceId accepts an explicit larger width", () => {
  const url = mlbHeadshotUrlFromSourceId(PLAYER_A, 640);
  assert.ok(url.includes(`/people/${PLAYER_A}/`));
  assert.ok(url.includes("/w_640,"));
  assert.ok(!url.includes("/w_213,"));
});

test("malformed width falls back to w_213 instead of a broken URL", () => {
  const cases = ["nope", "640px", "213.5", -1, 0, 12, 99999, 213.7, Number.NaN, Infinity];
  for (const width of cases) {
    const url = mlbHeadshotUrlFromSourceId(PLAYER_A, width);
    assert.ok(url.includes("/w_213,"), `expected default width for ${String(width)}`);
    assert.ok(url.includes(`/people/${PLAYER_A}/`));
    assert.ok(!url.includes("/w_640,"));
  }
  const objectUrl = mlbHeadshotUrlFromSourceId(PLAYER_A, {});
  const arrayUrl = mlbHeadshotUrlFromSourceId(PLAYER_A, []);
  assert.ok(objectUrl.includes("/w_213,"));
  assert.ok(arrayUrl.includes("/w_213,"));
});

test("UUID input never becomes an MLB image URL", () => {
  assert.strictEqual(mlbSourceIdFromValue(UUID), null);
  assert.strictEqual(mlbHeadshotUrlFromSourceId(UUID), null);
  assert.strictEqual(mlbHeadshotUrlFromSourceId(UUID, 640), null);
  assert.strictEqual(mlbHeadshotUrlFromSourceId(`mlb:${UUID}`), null);
  assert.strictEqual(getSignalOfWeekHeadshotUrl({
    player_name: "Unknown Player",
    source_player_id: UUID,
    player_id: UUID,
    cs_player_id: UUID,
    headshot_url: null,
  }), null);
});

test("hero MLB image resolves to w_640 from source_player_id", () => {
  const stored = mlbHeadshotUrlFromSourceId(PLAYER_A);
  const hero = getSignalOfWeekHeadshotUrl({
    player_name: "Test Hitter",
    source_player_id: PLAYER_A,
    headshot_url: stored,
  });
  assert.ok(hero.includes("/w_640,"));
  assert.ok(hero.includes(`/people/${PLAYER_A}/`));
  assert.ok(!hero.includes("/w_213,"));
});

test("hero rewrites a stored w_213 MLB CDN URL to w_640 without a source id", () => {
  const stored = mlbHeadshotUrlFromSourceId(PLAYER_B);
  assert.ok(stored.includes("/w_213,"));
  const hero = getSignalOfWeekHeadshotUrl({
    player_name: "Another Hitter",
    headshot_url: stored,
  });
  assert.ok(hero.includes("/w_640,"));
  assert.ok(hero.includes(`/people/${PLAYER_B}/`));
  assert.ok(!hero.includes("/w_213,"));
});

test("hero markup uses w_640 and keeps onerror initials fallback", () => {
  const html = renderSignalWeekPlayerImage({
    player_name: "Test Hitter",
    source_player_id: PLAYER_A,
    headshot_url: mlbHeadshotUrlFromSourceId(PLAYER_A),
  });
  assert.ok(html.includes("<img"));
  assert.ok(html.includes("/w_640,"));
  assert.ok(html.includes(`/people/${PLAYER_A}/`));
  assert.ok(!html.includes("/w_213,"));
  assert.ok(html.includes("onerror"));
  assert.ok(html.includes("TH"));
});

test("hero initials fallback remains when no image URL exists", () => {
  const html = renderSignalWeekPlayerImage({ player_name: "Test Hitter" });
  assert.ok(!html.includes("<img"));
  assert.ok(html.includes("TH"));
  assert.ok(html.includes("signal-week-photo-fallback"));
});

test("leaderboard and scouting keep w_213", () => {
  const stored = mlbHeadshotUrlFromSourceId(PLAYER_A);
  const entry = { player_name: "Test Hitter", headshot_url: stored };
  assert.ok(renderLeaderHeadshot(entry).includes("/w_213,"));
  assert.ok(!renderLeaderHeadshot(entry).includes("/w_640,"));
  assert.ok(renderPlayerHeadshot(entry).includes("/w_213,"));
  assert.ok(!renderPlayerHeadshot(entry).includes("/w_640,"));
});

test("non-MLB stored photos are left unchanged", () => {
  assert.strictEqual(getSignalOfWeekHeadshotUrl({
    player_name: "Test QB",
    cs_player_id: "CS-NFL-P-12345",
    source_player_id: "12345",
    league: "NFL",
    headshot_url: NFL_HEADSHOT,
  }), NFL_HEADSHOT);
  assert.strictEqual(getSignalOfWeekHeadshotUrl({
    player_name: "Test Star",
    cs_player_id: "CS-NBA-P-2544",
    source_player_id: "2544",
    league: "NBA",
    headshot_url: NBA_HEADSHOT,
  }), NBA_HEADSHOT);
  const nflHtml = renderSignalWeekPlayerImage({
    player_name: "Test QB",
    cs_player_id: "CS-NFL-P-12345",
    league: "NFL",
    headshot_url: NFL_HEADSHOT,
  });
  assert.ok(nflHtml.includes(NFL_HEADSHOT));
  assert.ok(!nflHtml.includes("img.mlbstatic.com"));
});

test("hero helpers are not player-specific", () => {
  const appSrc = fs.readFileSync(path.join(__dirname, "..", "frontend", "app.js"), "utf8");
  assert.ok(!appSrc.includes("608324"));
  assert.ok(!/Bregman/i.test(appSrc));
  const first = getSignalOfWeekHeadshotUrl({ source_player_id: PLAYER_A, player_name: "A" });
  const second = getSignalOfWeekHeadshotUrl({ source_player_id: PLAYER_B, player_name: "B" });
  assert.ok(first.includes(`/people/${PLAYER_A}/`));
  assert.ok(second.includes(`/people/${PLAYER_B}/`));
  assert.notStrictEqual(first, second);
});

test("featured hero glass does not keep leftover backdrop blur", () => {
  const css = fs.readFileSync(path.join(__dirname, "..", "frontend", "styles.css"), "utf8");
  const leftover = css.match(/\.signal-week-photo-glass\s*\{[^}]*\}/g) || [];
  leftover.forEach((block) => {
    assert.ok(!/backdrop-filter:\s*blur/.test(block), "signal-week-photo-glass must not blur");
  });
  assert.ok(
    /\.featured-signal-banner \.signal-week-photo-glass\s*\{[^}]*backdrop-filter:\s*none/.test(css),
    "featured hero glass must explicitly disable backdrop-filter"
  );
});

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed > 0 ? 1 : 0);
