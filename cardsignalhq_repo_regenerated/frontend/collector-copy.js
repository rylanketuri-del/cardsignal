/**
 * Centralized collector-facing copy for Scouting Reports, Card Reports, and pending states.
 * Sprint 9.7 — consistent terminology and explanatory pending language.
 */

const COLLECTOR_COPY = {
  REGISTRY_PENDING: "Registry data pending",
  NO_SIGNAL_DRIVERS: "No verified Signal Drivers are available.",
  SIGNAL_DRIVERS_LEAD:
    "Verified performance and market evidence that shaped this week's CardSignal Score.",
  WEEKLY_MOVEMENT_PENDING: "Weekly movement will appear after the next completed snapshot.",
  PERFORMANCE_PENDING: "Performance data will appear after the next completed snapshot.",
  CARD_INTEL_PENDING: "Card intelligence will appear after the next weekly refresh.",
  MARKET_SNAPSHOT_PENDING: "Market Snapshot data will appear after stored market snapshots are captured.",
  MARKET_HISTORY_PENDING: "Market history still building — snapshots will populate after the next weekly refresh.",
  EVIDENCE_PENDING: "Evidence will appear when stored market snapshots are available.",
  RISK_PENDING: "Risk assessment pending — requires more stored signal evidence.",
  HORIZON_PENDING: "Time horizon will appear after the next completed snapshot.",
  UPDATED_PENDING: "Updated timestamp pending",
  CARD_SCORE_PENDING: "CardSignal Card Score pending",
  PLAYER_NOT_FOUND: "This player is not in the CardSignal registry yet.",
  CARD_NOT_FOUND: "This card report is not available in the current registry.",
  REPORT_UNAVAILABLE: "This Scouting Report could not be loaded. Try again after the next weekly refresh.",
  CARD_REPORT_UNAVAILABLE: "This Card Report could not be loaded. Try again after the next weekly refresh.",
};

function formatCollectorError(error, fallback = COLLECTOR_COPY.REPORT_UNAVAILABLE) {
  const raw = String(error?.message || error || "").trim();
  if (!raw) return fallback;
  if (raw.startsWith("{") || raw.startsWith("[") || /traceback|stack trace/i.test(raw)) {
    return fallback;
  }
  if (raw.length > 180) return fallback;
  return raw;
}

if (typeof window !== "undefined") {
  window.COLLECTOR_COPY = COLLECTOR_COPY;
  window.formatCollectorError = formatCollectorError;
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { COLLECTOR_COPY, formatCollectorError };
}
