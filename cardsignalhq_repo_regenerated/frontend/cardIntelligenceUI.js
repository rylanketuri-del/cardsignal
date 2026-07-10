/**
 * Card Intelligence UI — Sprint 8.7
 * Fetches synthesized card intelligence and prepares modal tab view models.
 */
(function initCardIntelligenceUI(global) {
  "use strict";

  const cache = new Map();
  const inflight = new Map();

  const RECOMMENDATION_CLASS = {
    BUY: "cs-recommendation--buy",
    HOLD: "cs-recommendation--hold",
    SELL: "cs-recommendation--sell",
    WATCH: "cs-recommendation--watch",
  };

  const CONVICTION_CLASS = {
    HIGH: "cs-conviction--high",
    MEDIUM: "cs-conviction--medium",
    LOW: "cs-conviction--low",
    INSUFFICIENT: "cs-conviction--insufficient",
  };

  function getCacheKey(entry = {}) {
    return String(entry.player_id || entry.source_player_id || entry.cs_player_id || entry.player_name || "unknown");
  }

  function formatScore(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) {
      return "Score pending";
    }
    return Number(value).toFixed(0);
  }

  function formatPercent(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) {
      return "—";
    }
    const n = Number(value);
    const sign = n > 0 ? "+" : "";
    return `${sign}${n.toFixed(1)}%`;
  }

  function recommendationClass(recommendation = "WATCH") {
    return RECOMMENDATION_CLASS[String(recommendation || "WATCH").toUpperCase()] || RECOMMENDATION_CLASS.WATCH;
  }

  function convictionClass(conviction = "INSUFFICIENT") {
    return CONVICTION_CLASS[String(conviction || "INSUFFICIENT").toUpperCase()] || CONVICTION_CLASS.INSUFFICIENT;
  }

  function intelligenceByCardId(payload = {}) {
    const map = new Map();
    for (const card of payload.cards || []) {
      if (card?.cs_card_id) {
        map.set(card.cs_card_id, card);
      }
    }
    return map;
  }

  function enrichCardRow(row = {}, intelligence = null) {
    if (!intelligence) {
      return {
        ...row,
        cardSignalScore: null,
        cardSignalScoreLabel: "Score pending",
        recommendation: "WATCH",
        conviction: "INSUFFICIENT",
        dataQualityLabel: row.dataQuality || "INSUFFICIENT",
        missingInputs: ["card_intelligence"],
        hasIntelligence: false,
      };
    }

    return {
      ...row,
      cardSignalScore: intelligence.card_signal_score,
      cardSignalScoreLabel: intelligence.card_signal_score != null ? formatScore(intelligence.card_signal_score) : "Score pending",
      recommendation: intelligence.recommendation || "WATCH",
      conviction: intelligence.conviction || "INSUFFICIENT",
      risk: intelligence.risk || "UNKNOWN",
      marketActivityScore: intelligence.market_activity_score,
      demandScore: intelligence.demand_score,
      momentumScore: intelligence.momentum_score,
      scarcityScore: intelligence.scarcity_score,
      evidence: intelligence.evidence || [],
      missingInputs: intelligence.missing_inputs || [],
      algorithmVersion: intelligence.algorithm_version,
      dataQualityLabel: intelligence.market_data_quality || row.dataQuality || "INSUFFICIENT",
      psa10Pop: intelligence.psa_10_population != null ? String(intelligence.psa_10_population) : row.psa10Pop,
      hasIntelligence: true,
      hasFullScore: intelligence.has_full_score === true,
    };
  }

  function buildSignalDimension(label, score, evidence = [], quality = "INSUFFICIENT", missing = []) {
    const hasScore = score !== null && score !== undefined && !Number.isNaN(Number(score));
    const relatedEvidence = evidence.filter((item) => {
      const type = String(item.type || "").toUpperCase();
      if (label === "Market Activity") return type === "MARKET";
      if (label === "Demand") return type === "DEMAND";
      if (label === "Momentum") return type === "MOMENTUM";
      if (label === "Scarcity") return type === "SCARCITY" || type === "POPULATION";
      return false;
    });

    const evidenceSummary = relatedEvidence.length
      ? relatedEvidence.slice(0, 2).map((item) => `${item.label}: ${item.value}`).join(" · ")
      : hasScore
        ? "Derived from stored observations."
        : "More history required";

    return {
      label,
      score: hasScore ? Number(score) : null,
      scoreLabel: hasScore ? formatScore(score) : "Score pending",
      evidenceSummary,
      quality,
      missingExplanation: hasScore ? "" : (missing[0] || "More history required"),
      hasScore,
    };
  }

  function aggregateSignalDimensions(cards = []) {
    const withScores = cards.filter((card) => card.card_signal_score != null);
    const source = withScores.length ? withScores : cards;
    if (!source.length) {
      return {
        marketActivity: buildSignalDimension("Market Activity", null, [], "INSUFFICIENT", ["card_intelligence"]),
        demand: buildSignalDimension("Demand", null, [], "INSUFFICIENT", ["card_intelligence"]),
        momentum: buildSignalDimension("Momentum", null, [], "INSUFFICIENT", ["card_intelligence"]),
        scarcity: buildSignalDimension("Scarcity", null, [], "INSUFFICIENT", ["card_intelligence"]),
        cardLevelNote: "Card-level signals are separate from the player-level CardSignal Score.",
      };
    }

    const avg = (key) => {
      const values = source.map((card) => card[key]).filter((v) => v !== null && v !== undefined);
      if (!values.length) return null;
      return values.reduce((sum, v) => sum + Number(v), 0) / values.length;
    };

    const allEvidence = source.flatMap((card) => card.evidence || []);
    const qualities = source.map((card) => card.market_data_quality || "INSUFFICIENT");
    const aggregateQuality = qualities.includes("HIGH")
      ? "HIGH"
      : qualities.includes("MEDIUM")
        ? "MEDIUM"
        : qualities.includes("LOW")
          ? "LOW"
          : "INSUFFICIENT";

    return {
      marketActivity: buildSignalDimension(
        "Market Activity",
        avg("market_activity_score"),
        allEvidence,
        aggregateQuality,
        source[0]?.missing_inputs || []
      ),
      demand: buildSignalDimension(
        "Demand",
        avg("demand_score"),
        allEvidence,
        aggregateQuality,
        source[0]?.missing_inputs || []
      ),
      momentum: buildSignalDimension(
        "Momentum",
        avg("momentum_score"),
        allEvidence,
        aggregateQuality,
        source[0]?.missing_inputs || []
      ),
      scarcity: buildSignalDimension(
        "Scarcity",
        avg("scarcity_score"),
        allEvidence,
        source[0]?.population_data_quality || aggregateQuality,
        source[0]?.missing_inputs || []
      ),
      cardLevelNote: "Card-level signals are separate from the player-level CardSignal Score.",
    };
  }

  function pickLeadCard(cards = []) {
    const scored = cards.filter((card) => card.card_signal_score != null);
    if (!scored.length) return cards[0] || null;
    return scored.reduce((best, card) =>
      (card.card_signal_score > (best?.card_signal_score ?? -1) ? card : best), scored[0]);
  }

  function buildForecastView(payload = {}) {
    const cards = payload.cards || [];
    const lead = pickLeadCard(cards);
    const summary = payload.summary || {};

    if (!lead) {
      return {
        recommendation: "WATCH",
        conviction: "INSUFFICIENT",
        risk: "UNKNOWN",
        timeHorizon: "Not available",
        evidence: [],
        missingInputs: ["card_intelligence"],
        algorithmVersion: payload.algorithm_version || "CARD_INTELLIGENCE_V1",
        summaryText: "More market history is needed before CardSignal can issue a full card recommendation.",
        playerSummary: summary,
        disclaimer: payload.disclaimer,
        hasData: false,
      };
    }

    const evidence = lead.evidence || [];
    const summaryText = lead.card_signal_score != null
      ? `Synthesized from ${summary.cards_with_sufficient_evidence || 0} card${summary.cards_with_sufficient_evidence === 1 ? "" : "s"} with sufficient evidence. Highest card signal: ${formatScore(summary.highest_card_signal)}.`
      : "More market history is needed before CardSignal can issue a full card recommendation.";

    return {
      recommendation: lead.recommendation || "WATCH",
      conviction: lead.conviction || "INSUFFICIENT",
      risk: lead.risk || "UNKNOWN",
      timeHorizon: lead.time_horizon || "Not available",
      evidence,
      missingInputs: lead.missing_inputs || [],
      algorithmVersion: lead.algorithm_version || payload.algorithm_version,
      summaryText,
      playerSummary: summary,
      disclaimer: payload.disclaimer,
      hasData: true,
      leadCardId: lead.cs_card_id,
    };
  }

  function buildPlayerSummaryView(summary = {}) {
    return {
      highestCardSignal: summary.highest_card_signal != null ? formatScore(summary.highest_card_signal) : "Score pending",
      strongestMarketActivity: summary.strongest_market_activity != null ? formatScore(summary.strongest_market_activity) : "Score pending",
      strongestScarcity: summary.strongest_scarcity != null ? formatScore(summary.strongest_scarcity) : "Score pending",
      mostBidActivity: summary.most_bid_activity != null ? String(summary.most_bid_activity) : "—",
      cardsWithEvidence: summary.cards_with_sufficient_evidence ?? 0,
      cardsPending: summary.cards_pending_evidence ?? 0,
      totalCards: summary.total_cards ?? 0,
    };
  }

  function buildMarketMovementSummary(cards = []) {
    const movement7d = cards
      .map((card) => card.market_movement_7d)
      .filter((m) => m && m.has_movement !== false && m.median_price_change_pct != null);
    const movement30d = cards
      .map((card) => card.market_movement_30d)
      .filter((m) => m && m.has_movement !== false && m.median_price_change_pct != null);

    const avgPct = (items) => {
      if (!items.length) return null;
      const total = items.reduce((sum, item) => sum + Number(item.median_price_change_pct || 0), 0);
      return total / items.length;
    };

    return {
      movement7dLabel: movement7d.length ? formatPercent(avgPct(movement7d)) : "Movement pending",
      movement30dLabel: movement30d.length ? formatPercent(avgPct(movement30d)) : "Movement pending",
      cardsWith7d: movement7d.length,
      cardsWith30d: movement30d.length,
    };
  }

  function renderEvidenceList(evidence = []) {
    if (!evidence.length) {
      return `<p class="ci-evidence-empty">More history required</p>`;
    }
    return `
      <ul class="ci-evidence-list">
        ${evidence.map((item) => `
          <li class="ci-evidence-item ci-evidence-item--${String(item.impact || "unknown").toLowerCase()}">
            <span class="ci-evidence-type">${item.type || "SIGNAL"}</span>
            <span class="ci-evidence-label">${item.label}</span>
            <span class="ci-evidence-value">${item.value}</span>
            <span class="ci-evidence-quality">${item.quality || "INSUFFICIENT"}</span>
          </li>
        `).join("")}
      </ul>
    `;
  }

  function renderSignalDimensionBlock(dimension = {}) {
    const width = dimension.hasScore ? Math.max(4, Math.min(100, dimension.score)) : 0;
    return `
      <section class="cs-premium-card pi-signal-detail pi-signal-detail--card-level">
        <div class="cs-premium-head">
          <h3 class="cs-premium-title">${dimension.label}</h3>
          <span class="pi-signal-detail-score">${dimension.scoreLabel}</span>
        </div>
        <div class="cs-progress-track pi-signal-detail-bar" aria-hidden="true">
          <span class="cs-progress-fill cs-progress-fill--market" style="width:${width}%"></span>
        </div>
        <p class="pi-signal-detail-copy">${dimension.evidenceSummary}</p>
        <p class="pi-signal-detail-meta">
          <span class="cm-quality-badge cm-quality--${String(dimension.quality || "insufficient").toLowerCase()}">${dimension.quality}</span>
          ${dimension.missingExplanation ? `<span class="pi-signal-missing">${dimension.missingExplanation}</span>` : ""}
        </p>
      </section>
    `;
  }

  async function fetchPlayerCardIntelligence(playerId, { force = false } = {}) {
    const key = String(playerId);
    if (!force && cache.has(key)) {
      return { status: "success", data: cache.get(key) };
    }
    if (!force && inflight.has(key)) {
      return inflight.get(key);
    }

    const request = (async () => {
      try {
        const apiBase = (global.APP_CONFIG && global.APP_CONFIG.API_BASE_URL) || "https://cardsignal-api.onrender.com";
        const response = await fetch(`${apiBase}/api/players/${encodeURIComponent(playerId)}/card-intelligence`);
        if (!response.ok) {
          throw new Error(`Card intelligence request failed (${response.status})`);
        }
        const data = await response.json();
        cache.set(key, data);
        const hasCards = Array.isArray(data.cards) && data.cards.length > 0;
        return { status: hasCards ? "success" : "empty", data };
      } catch (error) {
        return { status: "error", error: error.message || "Card intelligence is temporarily unavailable." };
      } finally {
        inflight.delete(key);
      }
    })();

    inflight.set(key, request);
    return request;
  }

  function clearCacheForPlayer(playerId) {
    cache.delete(String(playerId));
  }

  global.CardIntelligenceUI = {
    getCacheKey,
    formatScore,
    formatPercent,
    recommendationClass,
    convictionClass,
    intelligenceByCardId,
    enrichCardRow,
    aggregateSignalDimensions,
    buildForecastView,
    buildPlayerSummaryView,
    buildMarketMovementSummary,
    renderEvidenceList,
    renderSignalDimensionBlock,
    fetchPlayerCardIntelligence,
    clearCacheForPlayer,
  };
})(typeof window !== "undefined" ? window : globalThis);
