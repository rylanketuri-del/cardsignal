#!/usr/bin/env node
/** Node tests for data-confidence.js UI helpers */

const assert = require("assert");
const path = require("path");
const vm = require("vm");

const scriptPath = path.join(__dirname, "..", "frontend", "data-confidence.js");
const script = require("fs").readFileSync(scriptPath, "utf8");
const sandbox = { window: {}, globalThis: {} };
vm.createContext(sandbox);
vm.runInContext(script, sandbox);

const DC = sandbox.window.DataConfidence;
assert(DC, "DataConfidence global should exist");

assert.strictEqual(DC.dcNormalizeFreshness(null), "UNKNOWN");
assert.strictEqual(DC.dcNormalizeFreshness("RECENT"), "RECENT");
assert.strictEqual(DC.dcNormalizeLevel("HIGH"), "HIGH");

const badges = DC.dcRenderHeaderBadges({
  confidence: { confidence_level: "HIGH" },
  freshness: { bucket: "RECENT" },
});
assert(badges.includes("Evidence"), "should render Evidence badge");
assert(badges.includes("Freshness"), "should render Freshness badge");
assert(badges.includes("HIGH"), "should show evidence level");
assert(!badges.includes("%"), "should not expose percentages");

const trust = DC.dcRenderTrustSection({
  trust_summary: {
    verified_using: ["5 player snapshots", "8 market snapshots"],
    latest_update: "42 minutes ago",
    model: "MLB_PLAYER_SIGNAL_V1",
  },
  missing_inputs: [],
});
assert(trust.includes("Why this report?"), "trust section title");
assert(trust.includes("42 minutes ago"), "latest update");
assert(trust.includes("MLB_PLAYER_SIGNAL_V1"), "model version");
assert(!trust.includes("weight"), "no weighting exposed");

console.log("data-confidence.js tests passed");
