/**
 * Card Market UI — Sprint 8.4
 * Fetches stored card-market snapshots and prepares Cards/Market tab view models.
 */
(function initCardMarketUI(global) {
  "use strict";

  const cache = new Map();
  const inflight = new Map();

  const QUALITY_META = {
    HIGH: { label: "HIGH", description: "Strong listing sample", className: "cm-quality--high" },
    MEDIUM: { label: "MEDIUM", description: "Moderate listing sample", className: "cm-quality--medium" },
    LOW: { label: "LOW", description: "Limited listing sample", className: "cm-quality--low" },
    INSUFFICIENT: { label: "INSUFFICIENT", description: "Not enough data", className: "cm-quality--insufficient" },
  };

  const DEPTH_META = {
    HIGH: { label: "HIGH", className: "cm-depth--high" },
    MEDIUM: { label: "MEDIUM", className: "cm-depth--medium" },
    LOW: { label: "LOW", className: "cm-depth--low" },
    INSUFFICIENT: { label: "INSUFFICIENT", className: "cm-depth--insufficient" },
  };

  function getCacheKey(entry = {}) {
    return String(entry.player_id || entry.source_player_id || entry.cs_player_id || entry.player_name || "unknown");
  }

  function formatMoney(value, currency = "USD") {
    if (value === null || value === undefined || Number.isNaN(Number(value))) {
      return "Snapshot pending";
    }
    try {
      return new Intl.NumberFormat(undefined, {
        style: "currency",
        currency: currency || "USD",
        maximumFractionDigits: 2,
      }).format(Number(value));
    } catch (_) {
      return `$${Number(value).toFixed(2)}`;
    }
  }

  function formatCapturedAt(value) {
    if (!value) return "Snapshot pending";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "Snapshot pending";
    const datePart = date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
    const timePart = date.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
    return `Captured ${datePart} at ${timePart}`;
  }

  function qualityMeta(quality = "INSUFFICIENT") {
    const key = String(quality || "INSUFFICIENT").toUpperCase();
    return QUALITY_META[key] || QUALITY_META.INSUFFICIENT;
  }

  function depthMeta(depth = "INSUFFICIENT") {
    const key = String(depth || "INSUFFICIENT").toUpperCase();
    return DEPTH_META[key] || DEPTH_META.INSUFFICIENT;
  }

  function renderQualityBadge(quality) {
    const meta = qualityMeta(quality);
    return `<span class="cm-quality-badge ${meta.className}" title="${meta.description}"><span class="cm-quality-badge__label">${meta.label}</span><span class="cm-quality-badge__desc">${meta.description}</span></span>`;
  }

  function renderDepthBadge(depth) {
    const meta = depthMeta(depth);
    return `<span class="cm-depth-badge ${meta.className}">${meta.label}</span>`;
  }

  function cardDisplayName(card = {}) {
    const year = card.year || "";
    const setName = card.set_name || "";
    const cardName = card.card_name || "";
    const parts = [year, setName, cardName].filter(Boolean);
    return parts.join(" ") || "Card";
  }

  function cardSubtitle(card = {}) {
    const bits = [card.parallel, card.grade, card.grading_company].filter(Boolean);
    return bits.join(" · ") || "Active listing snapshot";
  }

  function enrichCardRow(card = {}) {
    const snap = card.market_snapshot || null;
    const currency = snap?.currency || "USD";
    return {
      ...card,
      name: cardDisplayName(card),
      subtitle: cardSubtitle(card),
      medianPrice: snap ? formatMoney(snap.median_price, currency) : "Snapshot pending",
      averagePrice: snap ? formatMoney(snap.average_price, currency) : "Snapshot pending",
      activeListings: snap ? String(snap.active_listing_count ?? 0) : "—",
      auctions: snap ? String(snap.auction_count ?? 0) : "—",
      movement: "Movement pending",
      dataQuality: snap?.data_quality || "INSUFFICIENT",
      capturedLabel: snap ? formatCapturedAt(snap.captured_at) : "Snapshot pending",
      hasSnapshot: Boolean(snap),
      activityScore: snap
        ? (snap.active_listing_count || 0) + (snap.auction_count || 0) * 2 + (snap.total_bid_count || 0)
        : 0,
      chaseScore: snap
        ? (snap.listings_with_bids || 0) * 3 + (snap.total_bid_count || 0)
        : 0,
    };
  }

  function sortCards(cards, compareFn) {
    return [...cards].sort(compareFn).slice(0, 3);
  }

  function buildCardSections(cards = []) {
    const rows = cards.map(enrichCardRow);
    const withSnapshots = rows.filter((row) => row.hasSnapshot);

    const trending = sortCards(withSnapshots.length ? withSnapshots : rows, (a, b) => b.activityScore - a.activityScore);
    const mostChased = sortCards(withSnapshots.length ? withSnapshots : rows, (a, b) => b.chaseScore - a.chaseScore);
    const biggestMovers = sortCards(rows, (a, b) => (b.hasSnapshot ? 1 : 0) - (a.hasSnapshot ? 1 : 0));
    const buyLow = sortCards(rows, (a, b) => (a.hasSnapshot ? 1 : 0) - (b.hasSnapshot ? 1 : 0)).map((row) => ({
      ...row,
      movement: "Requires price-history confirmation",
      betaNote: true,
    }));

    return {
      trendingCards: trending,
      biggestMovers,
      buyLowOpportunities: buyLow,
      mostChased,
      observedCount: withSnapshots.length,
      totalCards: rows.length,
    };
  }

  function buildMarketSummary(playerName, aggregate = {}, cards = []) {
    const name = playerName || "This player";
    const observed = Number(aggregate.cards_observed || 0);
    const totalListings = Number(aggregate.total_active_listings || 0);
    const totalBin = Number(aggregate.total_buy_it_now || 0);
    const totalAuctions = Number(aggregate.total_auctions || 0);

    if (!observed || !totalListings) {
      return `${name} does not yet have enough stored active-listing observations to summarize card-market depth.`;
    }

    const depthWord = String(aggregate.market_depth || "INSUFFICIENT").toLowerCase();
    let inventoryNote = "with mixed listing formats across tracked cards.";
    if (totalBin > totalAuctions * 2) {
      inventoryNote = "with most inventory concentrated in Buy It Now listings.";
    } else if (totalAuctions >= totalBin) {
      inventoryNote = "with notable auction activity across tracked cards.";
    }

    return `${name} currently has ${depthWord} active listing depth across ${observed} tracked card${observed === 1 ? "" : "s"}, ${inventoryNote}`;
  }

  function buildMarketView(payload = {}, playerName = "") {
    const aggregate = payload.aggregate || {};
    const cards = payload.cards || [];
    const currency = cards.find((card) => card.market_snapshot)?.market_snapshot?.currency || "USD";

    return {
      cardsObserved: aggregate.cards_observed ?? 0,
      totalActiveListings: aggregate.total_active_listings ?? 0,
      totalAuctions: aggregate.total_auctions ?? 0,
      totalBuyItNow: aggregate.total_buy_it_now ?? 0,
      listingsWithBids: aggregate.listings_with_bids ?? 0,
      totalBids: aggregate.total_bids ?? 0,
      medianActivePrice: formatMoney(aggregate.median_active_price, currency),
      averageActivePrice: formatMoney(aggregate.average_active_price, currency),
      marketDepth: aggregate.market_depth || "INSUFFICIENT",
      dataQuality: aggregate.data_quality || "INSUFFICIENT",
      capturedLabel: aggregate.most_recent_captured_at
        ? formatCapturedAt(aggregate.most_recent_captured_at)
        : "Snapshot pending",
      summary: buildMarketSummary(playerName, aggregate, cards),
      hasSnapshots: (aggregate.cards_observed || 0) > 0,
    };
  }

  function hasSnapshots(payload) {
    return Boolean(payload?.aggregate?.cards_observed || payload?.cards?.some((card) => card.market_snapshot));
  }

  async function fetchPlayerCardMarket(playerId, { force = false } = {}) {
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
        const response = await fetch(`${apiBase}/api/players/${encodeURIComponent(playerId)}/cards/market/latest`);
        if (!response.ok) {
          throw new Error(`Card-market request failed (${response.status})`);
        }
        const data = await response.json();
        cache.set(key, data);
        return { status: hasSnapshots(data) ? "success" : "empty", data };
      } catch (error) {
        return { status: "error", error: error.message || "Card-market intelligence is temporarily unavailable." };
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

  function buildRegistryFallbackSections(entry = {}) {
    const registry = CardRegistry.getPlayerCardRegistry(entry);
    const baseRows = registry.slice(0, 6).map((card) => {
      const row = CardMarketUI.enrichCardRow({
        year: card.year || CardRegistry.extractCardYear(card.set),
        manufacturer: card.manufacturer,
        set_name: card.set_name || CardRegistry.extractSetName(card.set),
        card_name: card.card_name || card.card,
        parallel: card.parallel,
        grade: card.grade,
        grading_company: card.grading_company,
        market_snapshot: null,
      });
      return row;
    });
    return {
      trendingCards: baseRows.slice(0, 3),
      biggestMovers: baseRows.slice(0, 3).map((row) => ({ ...row, movement: "Movement pending" })),
      buyLowOpportunities: baseRows.slice(0, 3).map((row) => ({
        ...row,
        movement: "Requires price-history confirmation",
        betaNote: true,
      })),
      mostChased: baseRows.slice(3, 6).length ? baseRows.slice(3, 6) : baseRows.slice(0, 3),
    };
  }

  global.CardMarketUI = {
    getCacheKey,
    formatMoney,
    formatCapturedAt,
    qualityMeta,
    depthMeta,
    renderQualityBadge,
    renderDepthBadge,
    buildCardSections,
    buildMarketView,
    hasSnapshots,
    fetchPlayerCardMarket,
    clearCacheForPlayer,
    enrichCardRow,
    cardDisplayName,
    buildRegistryFallbackSections,
  };
})(typeof window !== "undefined" ? window : globalThis);
