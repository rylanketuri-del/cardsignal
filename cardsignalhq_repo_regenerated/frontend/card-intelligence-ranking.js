/**
 * Card Intelligence Ranking — centralized sort and display helpers for player card portfolios.
 * Cards are ranked by stored CardSignal Card Score only (never price, grade, or listing count).
 */

const CARD_RANKING_EXPLANATION =
  "Cards are ranked using CardSignal Intelligence, combining player performance, verified market activity, collector demand, and available card-level evidence.";

function cirSafeToNumber(value) {
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : null;
}

function resolveCardSignalScore(card = {}) {
  const score = card.card_signal_score ?? card.score;
  return cirSafeToNumber(score);
}

function resolveCardEvidenceTier(card = {}) {
  const conviction = card.conviction;
  if (!conviction) return "INSUFFICIENT";
  const normalized = String(conviction).trim();
  const mapping = { High: "HIGH", Medium: "MEDIUM", Low: "LOW" };
  return mapping[normalized] || normalized.toUpperCase();
}

function countStoredEvidenceItems(evidence = {}) {
  let count = 0;
  Object.entries(evidence).forEach(([key, value]) => {
    if (key === "tags" && value && typeof value === "object") {
      const tagValues = Object.values(value).filter((v) => v != null && v !== "" && v !== 0);
      count += tagValues.length;
      return;
    }
    if (value == null || value === "") return;
    if (Array.isArray(value)) {
      count += value.length;
      return;
    }
    if (typeof value === "object") {
      const nested = Object.values(value).filter((v) => v != null && v !== "");
      if (nested.length) count += 1;
      return;
    }
    count += 1;
  });
  return count;
}

function computeCardEvidenceStrength(card = {}) {
  const evidence = card.evidence || {};
  const missing = card.missing_inputs || [];
  return countStoredEvidenceItems(evidence) - missing.length;
}

function buildCardIdentityKey(card = {}) {
  const registry = typeof CardRegistry !== "undefined" ? CardRegistry : null;
  const fields = registry && typeof registry.mapCardRecordToIdentity === "function"
    ? registry.mapCardRecordToIdentity(card)
    : (card.identity || card.registry || card);

  const parts = [
    fields.year ?? fields.card_year,
    fields.brand,
    fields.set,
    fields.parallel,
    fields.card_number,
    fields.grade,
  ]
    .filter((part) => part != null && part !== "")
    .map(String);

  if (parts.length) return parts.join("|").toLowerCase();
  return String(card.card_label || "").toLowerCase();
}

function compareRankedCards(a = {}, b = {}) {
  const scoreA = resolveCardSignalScore(a);
  const scoreB = resolveCardSignalScore(b);
  const aNull = scoreA === null;
  const bNull = scoreB === null;

  if (aNull !== bNull) return aNull ? 1 : -1;
  if (!aNull && scoreA !== scoreB) return scoreB - scoreA;

  const evidenceDelta = computeCardEvidenceStrength(b) - computeCardEvidenceStrength(a);
  if (evidenceDelta !== 0) return evidenceDelta;

  const identityDelta = buildCardIdentityKey(a).localeCompare(buildCardIdentityKey(b));
  if (identityDelta !== 0) return identityDelta;

  return String(a.cs_card_id || "").localeCompare(String(b.cs_card_id || ""));
}

function rankPlayerCards(cards = []) {
  return [...cards].sort(compareRankedCards);
}

function buildStoredCardEvidenceText(card = {}) {
  const evidence = card.evidence || {};
  const outlookItems = [
    ...(evidence.outlook_reasons || []),
    ...(evidence.outlook_evidence || []),
    ...(evidence.evidence_items || []),
  ];

  for (const item of outlookItems) {
    if (typeof item === "string" && item.trim()) return item.trim();
    if (item && typeof item === "object") {
      const text = item.label || item.value;
      if (text) return String(text).trim();
    }
  }

  if (evidence.listings_count != null) {
    const count = Number(evidence.listings_count);
    if (Number.isFinite(count)) {
      return `Based on ${count} active listing${count === 1 ? "" : "s"} in stored market snapshots.`;
    }
  }

  return null;
}

function buildStoredCardExplanation(card = {}) {
  const evidence = card.evidence || {};
  if (evidence.outlook_summary) return String(evidence.outlook_summary).trim();

  const outlookItems = [
    ...(evidence.outlook_reasons || []),
    ...(evidence.outlook_evidence || []),
    ...(evidence.evidence_items || []),
  ];

  for (const item of outlookItems) {
    if (typeof item === "string" && item.trim()) return item.trim();
    if (item && typeof item === "object") {
      const text = item.label || item.value;
      if (text) return String(text).trim();
    }
  }

  return null;
}

function buildCardMarketSnapshot(card = {}, formatters = {}) {
  const metrics = typeof SRMetrics !== "undefined" && typeof SRMetrics.srBuildCardMetrics === "function"
    ? SRMetrics.srBuildCardMetrics(card, formatters)
    : null;

  if (!metrics) return "Market snapshot pending.";

  const parts = [];
  if (!metrics.activeListings?.pending && metrics.activeListings?.display) {
    parts.push(`${metrics.activeListings.display} listings`);
  }
  if (!metrics.averageActivePrice?.pending && metrics.averageActivePrice?.display) {
    parts.push(`avg ${metrics.averageActivePrice.display}`);
  }
  if (!metrics.priceMovement7d?.pending && metrics.priceMovement7d?.display) {
    parts.push(`${metrics.priceMovement7d.display} 7d`);
  }

  return parts.length ? parts.join(" · ") : (typeof COLLECTOR_COPY !== "undefined" ? COLLECTOR_COPY.MARKET_SNAPSHOT_PENDING : "Market Snapshot data will appear after stored market snapshots are captured.");
}

const CardIntelligenceRanking = {
  CARD_RANKING_EXPLANATION,
  resolveCardSignalScore,
  resolveCardEvidenceTier,
  computeCardEvidenceStrength,
  buildCardIdentityKey,
  compareRankedCards,
  rankPlayerCards,
  buildStoredCardEvidenceText,
  buildStoredCardExplanation,
  buildCardMarketSnapshot,
};

if (typeof window !== "undefined") {
  window.CardIntelligenceRanking = CardIntelligenceRanking;
  window.CARD_RANKING_EXPLANATION = CARD_RANKING_EXPLANATION;
  window.rankPlayerCards = rankPlayerCards;
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = CardIntelligenceRanking;
}
