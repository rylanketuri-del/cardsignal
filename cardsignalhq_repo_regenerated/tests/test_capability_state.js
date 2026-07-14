/** Tests for capability-state helpers. */

const assert = require("assert");
const {
  getCapabilityState,
  capabilityStatusCopy,
  deriveSupportedEvidenceQuality,
} = require("../frontend/capability-state.js");

function csIntelSafeToNumber(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}
global.csIntelSafeToNumber = csIntelSafeToNumber;

const payload = {
  capabilities: {
    momentum: "SUPPORTED",
    market_snapshots: "PENDING",
    alerts: "DISABLED",
  },
  missing_inputs: ["listing_volume"],
};

console.log("Capability state tests");
assert.strictEqual(getCapabilityState(payload, "momentum"), "SUPPORTED");
assert.strictEqual(getCapabilityState(payload, "market_snapshots"), "PENDING");
assert.strictEqual(getCapabilityState(payload, "alerts"), "DISABLED");
assert.ok(capabilityStatusCopy(payload, "market_snapshots", "Market").includes("pending"));
assert.ok(capabilityStatusCopy(payload, "alerts", "Alerts").includes("not active"));
assert.strictEqual(deriveSupportedEvidenceQuality(payload, "momentum", 55, []), null);
assert.strictEqual(deriveSupportedEvidenceQuality(payload, "market_snapshots", null, []), "PENDING");
assert.strictEqual(deriveSupportedEvidenceQuality(payload, "momentum", null, ["listing_volume"]), "INSUFFICIENT");
console.log("passed");
