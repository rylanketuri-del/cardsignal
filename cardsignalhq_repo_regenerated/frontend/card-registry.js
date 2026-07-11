/**
 * Card Registry — centralized CardIdentity mapper and formatter.
 * Sprint 9.1B — Card Registry Completion
 */
(function initCardRegistry(global) {
  "use strict";

  const REGISTRY_DATA_PENDING = "Registry data pending";

  const QUERY_REGISTRY_HINTS = {
    bowman_chrome: {
      brand: "Bowman",
      set: "Chrome",
      rookie_flag: true,
    },
    auto: {
      autograph_flag: true,
    },
    psa10: {
      grading_company: "PSA",
      grade: "10",
    },
  };

  function coalesce(...values) {
    for (const value of values) {
      if (value === null || value === undefined) continue;
      if (typeof value === "string" && !value.trim()) continue;
      return value;
    }
    return null;
  }

  function queryNameFromCsCardId(csCardId = "") {
    if (!csCardId.includes(":card:")) return null;
    return csCardId.split(":card:").pop() || null;
  }

  function playerIdFromCsCardId(csCardId = "") {
    const parts = String(csCardId).split(":");
    if (parts.length >= 3 && parts[2] === "card") return parts[1];
    return null;
  }

  function normalizeYear(value) {
    if (value === null || value === undefined) return null;
    const year = Number(value);
    if (!Number.isFinite(year) || year < 1900 || year > 2100) return null;
    return Math.trunc(year);
  }

  function normalizeCardNumber(value) {
    if (value === null || value === undefined) return null;
    const text = String(value).trim();
    if (!text) return null;
    return text.replace(/^#/, "");
  }

  function normalizeGrade(value) {
    if (value === null || value === undefined) return null;
    const text = String(value).trim();
    return text || null;
  }

  function normalizeGradingCompany(value) {
    if (value === null || value === undefined) return null;
    const text = String(value).trim();
    return text ? text.toUpperCase() : null;
  }

  function normalizeBool(value) {
    if (value === null || value === undefined) return null;
    if (typeof value === "boolean") return value;
    if (typeof value === "number") return Boolean(value);
    const text = String(value).trim().toLowerCase();
    if (text === "true" || text === "1" || text === "yes") return true;
    if (text === "false" || text === "0" || text === "no") return false;
    return null;
  }

  function normalizePrice(value) {
    if (value === null || value === undefined) return null;
    const price = Number(value);
    if (!Number.isFinite(price) || price < 0) return null;
    return Math.round(price * 100) / 100;
  }

  function normalizeCount(value) {
    if (value === null || value === undefined) return null;
    const count = Number(value);
    if (!Number.isFinite(count) || count < 0) return null;
    return Math.trunc(count);
  }

  function mergeIdentitySources(...sources) {
    const merged = {};
    sources.forEach((source) => {
      if (!source || typeof source !== "object") return;
      Object.entries(source).forEach(([key, value]) => {
        if (value === null || value === undefined) return;
        if (typeof value === "string" && !value.trim()) return;
        merged[key] = value;
      });
    });
    return merged;
  }

  function hasCollectorIdentity(identity = {}) {
    return !!(identity.year || identity.brand || identity.set);
  }

  function gradeLine(identity = {}) {
    if (identity.grading_company && identity.grade != null) {
      return `${identity.grading_company} ${identity.grade}`.trim();
    }
    if (identity.grading_company) return identity.grading_company;
    if (identity.grade != null) return String(identity.grade);
    if (hasCollectorIdentity(identity)) return "Raw";
    return null;
  }

  function titleLine(identity = {}) {
    const parts = [identity.year, identity.brand, identity.set].filter(
      (part) => part !== null && part !== undefined && part !== ""
    );
    return parts.length ? parts.join(" ") : null;
  }

  /**
   * Resolve a normalized CardIdentity object from any card payload.
   * @param {object} card
   * @returns {object}
   */
  function resolveCardIdentity(card = {}) {
    const evidence = card.evidence || {};
    const explicit = card.identity || card.registry || {};
    const queryName = coalesce(
      evidence.query_name,
      card.query_name,
      queryNameFromCsCardId(card.cs_card_id)
    );
    const hints = QUERY_REGISTRY_HINTS[queryName] || {};
    const merged = mergeIdentitySources(hints, card.registry, card.identity, card);

    const resolvedPlayerId = coalesce(
      merged.player_id,
      card.cs_player_id,
      playerIdFromCsCardId(card.cs_card_id)
    );

    const identity = {
      cs_card_id: card.cs_card_id || null,
      sport: coalesce(merged.sport, card.league, card.sport),
      player_id: resolvedPlayerId != null ? String(resolvedPlayerId) : null,
      player_name: coalesce(merged.player_name, card.player_name),
      year: normalizeYear(coalesce(merged.card_year, merged.year)),
      brand: coalesce(merged.brand),
      set: coalesce(merged.set),
      subset: coalesce(merged.subset),
      parallel: coalesce(merged.parallel),
      variation: coalesce(merged.variation),
      card_number: normalizeCardNumber(merged.card_number),
      rookie_flag: normalizeBool(merged.rookie_flag),
      autograph_flag: normalizeBool(merged.autograph_flag),
      relic_flag: normalizeBool(merged.relic_flag),
      serial_number: coalesce(merged.serial_number),
      grading_company: normalizeGradingCompany(merged.grading_company),
      grade: normalizeGrade(merged.grade),
      population: normalizeCount(merged.population),
      image_url: coalesce(merged.image_url),
      active_listings: normalizeCount(coalesce(merged.active_listings, evidence.listings_count)),
      median_price: normalizePrice(coalesce(merged.median_price, evidence.median_price)),
      average_price: normalizePrice(coalesce(merged.average_price, evidence.avg_price)),
      last_updated: coalesce(merged.last_updated, card.captured_at),
    };

    return Object.fromEntries(
      Object.entries(identity).filter(([, value]) => value !== null && value !== undefined)
    );
  }

  function hasCardRegistryIdentity(card = {}) {
    const identity = resolveCardIdentity(card);
    return hasCollectorIdentity(identity);
  }

  function formatCardIdentityLines(card = {}) {
    const identity = resolveCardIdentity(card);
    if (!hasCollectorIdentity(identity)) {
      return { pending: true, lines: [REGISTRY_DATA_PENDING] };
    }

    const lines = [];
    const title = titleLine(identity);
    if (title) lines.push(title);
    if (identity.parallel) lines.push(String(identity.parallel));
    if (identity.card_number) lines.push(`#${identity.card_number}`);
    const grade = gradeLine(identity);
    if (grade) lines.push(grade);

    return { pending: false, lines, identity };
  }

  function formatCardIdentityHtml(card = {}) {
    const formatted = formatCardIdentityLines(card);
    if (formatted.pending) {
      return `<p class="sr-pending">${REGISTRY_DATA_PENDING}</p>`;
    }

    const identity = formatted.identity;
    const html = [];
    const title = titleLine(identity);
    if (title) html.push(`<p class="sr-card-title">${title}</p>`);
    if (identity.parallel) html.push(`<p class="sr-card-meta">${identity.parallel}</p>`);
    if (identity.card_number) html.push(`<p class="sr-card-number">#${identity.card_number}</p>`);
    const grade = gradeLine(identity);
    if (grade) html.push(`<p class="sr-card-grade">${grade}</p>`);

    return html.length ? html.join("") : `<p class="sr-pending">${REGISTRY_DATA_PENDING}</p>`;
  }

  function formatCardIdentityCompactHtml(card = {}) {
    const formatted = formatCardIdentityLines(card);
    if (formatted.pending) {
      return `<span class="qi-card-identity qi-card-identity--pending">${REGISTRY_DATA_PENDING}</span>`;
    }

    return formatted.lines
      .map((line, index) => {
        const className = index === 0 ? "qi-card-identity-title" : "qi-card-identity-meta";
        return `<span class="qi-card-identity-line ${className}">${line}</span>`;
      })
      .join("");
  }

  const CardRegistry = {
    REGISTRY_DATA_PENDING,
    resolveCardIdentity,
    hasCardRegistryIdentity,
    formatCardIdentityLines,
    formatCardIdentityHtml,
    formatCardIdentityCompactHtml,
    titleLine,
    gradeLine,
  };

  global.CardRegistry = CardRegistry;
})(typeof window !== "undefined" ? window : globalThis);

if (typeof module !== "undefined" && module.exports) {
  module.exports = global.CardRegistry;
}
