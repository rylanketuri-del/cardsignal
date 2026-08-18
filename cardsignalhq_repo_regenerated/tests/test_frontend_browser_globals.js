#!/usr/bin/env node
/**
 * Browser-global namespace guards for Scouting Report scripts.
 * Run: node tests/test_frontend_browser_globals.js
 */
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const FRONTEND = path.join(__dirname, "..", "frontend");

const NAMESPACES = [
  { name: "SRIntel", file: "scouting-report-intel.js" },
  { name: "SRMetrics", file: "scouting-report-metrics.js" },
  { name: "SRNfl", file: "scouting-report-nfl.js" },
  { name: "SRNba", file: "scouting-report-nba.js" },
  { name: "WeeklyMovement", file: "weekly-movement.js" },
  { name: "WeeklyConvergence", file: "weekly-convergence.js" },
];

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

function loadClassicScript(filename) {
  const source = fs.readFileSync(path.join(FRONTEND, filename), "utf8");
  const window = {};
  const sandbox = {
    window,
    Date,
    console,
  };
  vm.runInNewContext(source, sandbox);
  return sandbox.window;
}

console.log("Frontend browser-global tests");

test("classic-script load of scouting-report-intel.js creates window.SRIntel", () => {
  const win = loadClassicScript("scouting-report-intel.js");
  assert.ok(win.SRIntel, "expected window.SRIntel after classic-script load");
  assert.strictEqual(typeof win.SRIntel.srIntelFromNormalized, "function");
  assert.strictEqual(typeof win.SRIntel.srMapNormalizedDrivers, "function");
  assert.strictEqual(typeof win.SRIntel.srStatsFromEvidence, "function");
});

NAMESPACES.forEach((ns) => {
  test(`${ns.file} assigns window.${ns.name}`, () => {
    const source = fs.readFileSync(path.join(FRONTEND, ns.file), "utf8");
    assert.ok(
      source.includes(`window.${ns.name} = ${ns.name}`),
      `${ns.file} must attach window.${ns.name}`
    );
  });

  test(`app.js uses ${ns.name} and ${ns.file} is loaded before it`, () => {
    const app = fs.readFileSync(path.join(FRONTEND, "app.js"), "utf8");
    const index = fs.readFileSync(path.join(FRONTEND, "index.html"), "utf8");
    assert.ok(app.includes(`${ns.name}.`), `app.js must reference ${ns.name}.*`);
    const filePos = index.indexOf(ns.file);
    const appPos = index.indexOf("./app.js");
    assert.ok(filePos >= 0, `index.html must include ${ns.file}`);
    assert.ok(appPos > filePos, `${ns.file} must load before app.js`);
  });
});

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed > 0 ? 1 : 0);
