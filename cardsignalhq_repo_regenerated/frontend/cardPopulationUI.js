/**
 * Card Population UI — Sprint 8.6
 * Fetches stored PSA population snapshots for Player Intelligence tabs.
 */
(function initCardPopulationUI(global) {
  "use strict";

  const cache = new Map();
  const inflight = new Map();

  const SOURCE_LABELS = {
    official_api: "Live PSA data",
    approved_import: "Imported PSA snapshot",
    manual_beta_seed: "Beta seed data",
  };

  const QUALITY_META = {
    HIGH: { label: "HIGH", description: "Strong population sample", className: "cp-quality--high" },
    MEDIUM: { label: "MEDIUM", description: "Moderate population sample", className: "cp-quality--medium" },
    LOW: { label: "LOW", description: "Limited population sample", className: "cp-quality--low" },
    INSUFFICIENT: { label: "INSUFFICIENT", description: "Not enough data", className: "cp-quality--insufficient" },
  };

  function getCacheKey(entry = {}) {
    return String(entry.player_id || entry.source_player_id || entry.cs_player_id || entry.player_name || "unknown");
  }

  function formatCapturedAt(value) {
    if (!value) return "Population pending";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "Population pending";
    const datePart = date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
    const timePart = date.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
    return `Captured ${datePart} at ${timePart}`;
  }

  function formatCount(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) {
      return "—";
    }
    return new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(Number(value));
  }

  function formatRate(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) {
      return "—";
    }
    return `${(Number(value) * 100).toFixed(1)}%`;
  }

  function sourceLabel(sourceMethod) {
    return SOURCE_LABELS[String(sourceMethod || "").trim()] || "PSA population pending";
  }

  function qualityMeta(quality = "INSUFFICIENT") {
    const key = String(quality || "INSUFFICIENT").toUpperCase();
    return QUALITY_META[key] || QUALITY_META.INSUFFICIENT;
  }

  function renderQualityBadge(quality) {
    const meta = qualityMeta(quality);
    return `<span class="cp-quality-badge ${meta.className}" title="${meta.description}"><span class="cp-quality-badge__label">${meta.label}</span><span class="cp-quality-badge__desc">${meta.description}</span></span>`;
  }

  function renderSourceBadge(sourceMethod) {
    const label = sourceLabel(sourceMethod);
    const modifier = String(sourceMethod || "pending").replace(/[^a-z0-9_-]/gi, "-").toLowerCase();
    return `<span class="cp-source-badge cp-source-badge--${modifier}">${label}</span>`;
  }

  function populationByCardId(payload = {}) {
    const map = new Map();
    for (const card of payload.cards || []) {
      const cardId = card?.card?.cs_card_id || card?.cs_card_id;
      if (cardId) map.set(cardId, card);
    }
    return map;
  }

  function enrichCardRow(row = {}, populationEntry = null) {
    const snapshot = populationEntry?.population_snapshot || null;
    const scarcity = populationEntry?.scarcity || null;
    const movement = populationEntry?.population_movement || null;
    const sourceMethod = populationEntry?.source_method || snapshot?.source_method || null;

    return {
      ...row,
      psa10Pop: snapshot ? formatCount(snapshot.psa_10_population) : "PSA population pending",
      psa9Pop: snapshot ? formatCount(snapshot.psa_9_population) : "PSA population pending",
      totalPsaPop: snapshot ? formatCount(snapshot.total_population) : "PSA population pending",
      gemRate: snapshot ? formatRate(snapshot.gem_rate) : "—",
      populationDataQuality: snapshot?.data_quality || "INSUFFICIENT",
      populationCapturedLabel: snapshot ? formatCapturedAt(snapshot.captured_at) : "PSA population pending",
      populationSourceLabel: sourceLabel(sourceMethod),
      populationSourceMethod: sourceMethod,
      populationTrendLabel: movement?.has_movement
        ? `${movement.population_change >= 0 ? "+" : ""}${formatCount(movement.population_change)} total pop`
        : "Population trend pending",
      populationScarcityScore: scarcity?.overall_scarcity_score ?? null,
      populationScarcityLabel: scarcity?.label || "PSA Population Scarcity",
      populationScarcityConfidence: scarcity?.confidence || "LOW",
      hasPopulationSnapshot: Boolean(snapshot),
      populationDisclaimer: "PSA population reflects graded examples, not total card supply.",
    };
  }

  function buildSignalsPopulationSummary(cards = []) {
    const withPopulation = cards.filter((card) => card.population_snapshot);
    if (!withPopulation.length) {
      return {
        available: false,
        label: "PSA Population Scarcity",
        score: null,
        confidence: "LOW",
        explanation: "PSA population pending for tracked registry cards.",
        sourceLabel: "PSA population pending",
      };
    }

    const scores = withPopulation
      .map((card) => card.scarcity?.overall_scarcity_score)
      .filter((value) => value !== null && value !== undefined);
    const avgScore = scores.length
      ? Math.round(scores.reduce((sum, value) => sum + Number(value), 0) / scores.length)
      : null;

    const qualities = withPopulation.map((card) => card.population_snapshot?.data_quality || "INSUFFICIENT");
    const bestQuality = qualities.includes("HIGH")
      ? "HIGH"
      : qualities.includes("MEDIUM")
        ? "MEDIUM"
        : qualities.includes("LOW")
          ? "LOW"
          : "INSUFFICIENT";

    const sourceMethods = [...new Set(withPopulation.map((card) => card.source_method).filter(Boolean))];
    const sourceText = sourceMethods.length === 1 ? sourceLabel(sourceMethods[0]) : "Mixed PSA sources";

    return {
      available: avgScore !== null,
      label: "PSA Population Scarcity",
      score: avgScore,
      confidence: bestQuality === "HIGH" ? "HIGH" : bestQuality === "MEDIUM" ? "MEDIUM" : "LOW",
      dataQuality: bestQuality,
      explanation:
        "Beta scarcity derived from stored PSA graded-population counts. Lower PSA 10 totals can increase grade scarcity; this is not a complete universal scarcity score.",
      sourceLabel: sourceText,
    };
  }

  async function fetchPlayerCardPopulation(playerId, { force = false } = {}) {
    const key = String(playerId || "");
    if (!key) {
      return { status: "empty", data: null, error: null };
    }

    if (!force && cache.has(key)) {
      return { status: "ready", data: cache.get(key), error: null };
    }

    if (inflight.has(key)) {
      return inflight.get(key);
    }

    const apiBase = (global.APP_CONFIG && global.APP_CONFIG.API_BASE_URL) || global.API_BASE_URL || "";
    const promise = fetch(`${apiBase}/api/players/${encodeURIComponent(key)}/cards/population/latest`)
      .then(async (response) => {
        if (response.status === 404) {
          return { status: "empty", data: null, error: null };
        }
        if (!response.ok) {
          throw new Error(`Population request failed (${response.status})`);
        }
        const data = await response.json();
        cache.set(key, data);
        return { status: "ready", data, error: null };
      })
      .catch((error) => ({ status: "error", data: null, error: String(error.message || error) }))
      .finally(() => {
        inflight.delete(key);
      });

    inflight.set(key, promise);
    return promise;
  }

  global.CardPopulationUI = {
    getCacheKey,
    formatCapturedAt,
    formatCount,
    formatRate,
    sourceLabel,
    renderQualityBadge,
    renderSourceBadge,
    populationByCardId,
    enrichCardRow,
    buildSignalsPopulationSummary,
    fetchPlayerCardPopulation,
  };
})(window);
