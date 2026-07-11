/**
 * Centralized CardSignal card intelligence display helpers.
 * Reads stored card intelligence only — no client-side scoring.
 */
const CS_CARD_INTEL_VERSION = "CARD_INTELLIGENCE_V1";

function csCardSafeToNumber(value) {
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : null;
}

function csCardReportPath(csCardId = "") {
  if (!csCardId) return "";
  return `/cards/${encodeURIComponent(csCardId)}`;
}

function csCardResolveScore(card = {}) {
  return csCardSafeToNumber(card.card_signal_score ?? card.score);
}

function csCardResolveRecommendation(card = {}) {
  const rec = card.recommendation;
  if (!rec) return "WATCH";
  return String(rec).toUpperCase();
}

function csCardResolveEvidenceTier(card = {}) {
  const evidence = card.evidence || {};
  const tier = evidence.evidence_tier || card.evidence_tier;
  if (!tier) {
    const score = csCardResolveScore(card);
    if (score === null) return "INSUFFICIENT";
    return "LOW";
  }
  const key = String(tier).toUpperCase();
  if (key === "HIGH" || key === "MEDIUM" || key === "LOW" || key === "INSUFFICIENT") {
    return key;
  }
  return "INSUFFICIENT";
}

function csCardResolveExplanation(card = {}) {
  const evidence = card.evidence || {};
  if (evidence.explanation) return String(evidence.explanation);
  if (csCardResolveEvidenceTier(card) === "INSUFFICIENT") {
    return "Stored card intelligence is still building for this card.";
  }
  return "Stored card intelligence is still building for this card.";
}

function csCardResolveFactors(card = {}) {
  const evidence = card.evidence || {};
  const factors = evidence.factors;
  return Array.isArray(factors) ? factors : [];
}

function csCardEvidenceClass(tier = "") {
  const key = String(tier || "").toUpperCase();
  if (key === "HIGH") return "cs-evidence--high";
  if (key === "MEDIUM") return "cs-evidence--medium";
  if (key === "LOW") return "cs-evidence--low";
  return "cs-evidence--insufficient";
}

function csCardRecommendationClass(rec = "") {
  const key = String(rec || "").toLowerCase();
  if (key === "buy") return "cs-recommendation--buy";
  if (key === "hold") return "cs-recommendation--hold";
  if (key === "sell") return "cs-recommendation--sell";
  return "cs-recommendation--watch";
}

function csCardSortByScore(cards = []) {
  return [...cards].sort((a, b) => {
    const scoreA = csCardResolveScore(a);
    const scoreB = csCardResolveScore(b);
    if (scoreA === null && scoreB === null) return 0;
    if (scoreA === null) return 1;
    if (scoreB === null) return -1;
    if (scoreB !== scoreA) return scoreB - scoreA;
    return String(a.cs_card_id || "").localeCompare(String(b.cs_card_id || ""));
  });
}

function csCardBuildStoredIntel(card = {}) {
  const evidence = card.evidence || {};
  return {
    csCardId: card.cs_card_id || "",
    cardReportUrl: csCardReportPath(card.cs_card_id),
    score: csCardResolveScore(card),
    recommendation: csCardResolveRecommendation(card),
    evidenceTier: csCardResolveEvidenceTier(card),
    explanation: csCardResolveExplanation(card),
    factors: csCardResolveFactors(card),
    cardLabel: card.card_label || evidence.card_label || null,
    playerName: card.player_name || evidence.player_name || null,
    identity: evidence.identity || card.identity || card.registry || null,
    version: evidence.card_intelligence_version || CS_CARD_INTEL_VERSION,
  };
}

function csCardFormatIdentityHtml(card = {}, intel = null) {
  const stored = intel || csCardBuildStoredIntel(card);
  const identity = stored.identity || {};
  const titleParts = [identity.year, identity.brand, identity.set].filter(
    (part) => part != null && part !== ""
  );

  if (titleParts.length) {
    const lines = [`<p class="sr-card-title">${titleParts.join(" ")}</p>`];
    if (identity.parallel) {
      lines.push(`<p class="sr-card-meta">${identity.parallel}</p>`);
    }
    if (identity.card_number) {
      lines.push(`<p class="sr-card-number">#${identity.card_number}</p>`);
    }
    if (identity.grade) {
      const gradeLine = [identity.grading_company, identity.grade].filter(Boolean).join(" ");
      lines.push(`<p class="sr-card-grade">${gradeLine}</p>`);
    } else if (identity.grading_company) {
      lines.push(`<p class="sr-card-grade">${identity.grading_company}</p>`);
    }
    return lines.join("");
  }

  const label = stored.cardLabel || identity.card_label;
  if (label) {
    const playerSuffix = stored.playerName ? `<span class="sr-card-meta">${stored.playerName}</span>` : "";
    return `<p class="sr-card-title">${label}</p>${playerSuffix}`;
  }

  return null;
}

function csCardRenderFactorChips(factors = []) {
  if (!factors.length) return "";
  return `
    <div class="sr-card-factors" aria-label="Card intelligence factors">
      ${factors
        .map(
          (factor) => `
        <span class="sr-card-factor-chip" data-factor-key="${factor.key || ""}">
          <span class="sr-card-factor-emoji" aria-hidden="true">${factor.emoji || ""}</span>
          <span class="sr-card-factor-label">${factor.label || ""}</span>
        </span>`
        )
        .join("")}
    </div>`;
}

function csCardRenderIntelligencePanel(card = {}, formatScore = (v) => String(v)) {
  const intel = csCardBuildStoredIntel(card);
  const recClass = csCardRecommendationClass(intel.recommendation.toLowerCase());
  const evidenceClass = csCardEvidenceClass(intel.evidenceTier);
  const scoreDisplay = intel.score != null ? formatScore(intel.score) : "Pending";
  const factorsHtml = csCardRenderFactorChips(intel.factors);

  return `
    <div class="sr-card-intel">
      <div class="sr-card-intel-score-row">
        <div class="sr-card-intel-score-block">
          <span class="sr-card-intel-eyebrow">CardSignal Card Score</span>
          <span class="sr-card-intel-score">${scoreDisplay}</span>
        </div>
        <span class="cs-recommendation-badge ${recClass} sr-card-intel-rec">${intel.recommendation}</span>
      </div>
      <p class="sr-card-intel-evidence">
        <span class="sr-evidence-label">Evidence</span>
        <span class="cs-evidence-badge ${evidenceClass}">${intel.evidenceTier}</span>
      </p>
      <p class="sr-card-intel-explanation">
        <span class="sr-evidence-label">Explanation</span>
        ${intel.explanation}
      </p>
      ${factorsHtml}
    </div>`;
}

const CSCardIntelligence = {
  CS_CARD_INTEL_VERSION,
  csCardSafeToNumber,
  csCardReportPath,
  csCardResolveScore,
  csCardResolveRecommendation,
  csCardResolveEvidenceTier,
  csCardResolveExplanation,
  csCardResolveFactors,
  csCardEvidenceClass,
  csCardRecommendationClass,
  csCardSortByScore,
  csCardBuildStoredIntel,
  csCardFormatIdentityHtml,
  csCardRenderFactorChips,
  csCardRenderIntelligencePanel,
};

if (typeof window !== "undefined") {
  window.CSCardIntelligence = CSCardIntelligence;
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = CSCardIntelligence;
}
