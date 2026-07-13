/** Capability state helpers — capabilities define support; missing_inputs explain gaps. */

function getCapabilityState(payload, capabilityName) {
  const caps = payload?.capabilities || {};
  return caps[capabilityName] || "UNAVAILABLE";
}

function capabilityStatusCopy(payload, capabilityName, supportedCopy, options = {}) {
  const state = getCapabilityState(payload, capabilityName);
  if (state === "PENDING") {
    return options.pendingCopy || `${supportedCopy} — pending until required stored history is available.`;
  }
  if (state === "UNAVAILABLE") {
    return options.unavailableCopy || `${supportedCopy} — unavailable for this league.`;
  }
  if (state === "DISABLED") {
    return options.disabledCopy || `${supportedCopy} — not active for this league.`;
  }
  return supportedCopy;
}

function deriveSupportedEvidenceQuality(payload, capabilityName, score, missingInputs = []) {
  const state = getCapabilityState(payload, capabilityName);
  if (state === "PENDING") return "PENDING";
  if (state === "UNAVAILABLE") return "UNAVAILABLE";
  if (state === "DISABLED") return "DISABLED";
  if (score == null) return "INSUFFICIENT";
  const numeric = typeof globalThis.csIntelSafeToNumber === "function"
    ? globalThis.csIntelSafeToNumber(score)
    : Number(score);
  if (!Number.isFinite(numeric)) return "INSUFFICIENT";
  return null;
}

if (typeof module !== "undefined") {
  module.exports = {
    getCapabilityState,
    capabilityStatusCopy,
    deriveSupportedEvidenceQuality,
  };
}
