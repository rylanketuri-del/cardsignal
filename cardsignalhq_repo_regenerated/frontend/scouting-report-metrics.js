/**
 * Centralized Scouting Report metric mapping.
 * Each metric maps to exactly one stored source field — no proxy fallbacks.
 */
const SR_STAT_PENDING = "Pending";
const SR_STAT_PENDING_TITLE = "This statistic is not available in the current data snapshot.";

function srSafeToNumber(value) {
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : null;
}

function srPickStoredField(source, fields = []) {
  if (!source || typeof source !== "object") return null;
  for (const field of fields) {
    if (Object.prototype.hasOwnProperty.call(source, field) && source[field] != null && source[field] !== "") {
      return source[field];
    }
  }
  return null;
}

function srResolveMetric(spec, source, formatters = {}) {
  const raw = srPickStoredField(source, spec.source_fields || [spec.source_field].filter(Boolean));
  if (raw == null) {
    return {
      label: spec.display_label,
      display: spec.unavailable_label,
      raw: null,
      pending: true,
    };
  }

  let display = String(raw);
  if (spec.value_type === "money" && formatters.money) {
    display = formatters.money(raw);
  } else if (spec.value_type === "percent" && formatters.percent) {
    display = formatters.percent(raw);
  } else if (spec.value_type === "integer") {
    display = String(Math.round(Number(raw)));
  } else if (spec.value_type === "score" && formatters.score) {
    display = formatters.score(raw);
  } else if (spec.value_type === "decimal3") {
    const n = srSafeToNumber(raw);
    display = n == null ? spec.unavailable_label : n.toFixed(3);
  } else if (spec.value_type === "decimal1") {
    const n = srSafeToNumber(raw);
    display = n == null ? spec.unavailable_label : n.toFixed(1);
  } else if (spec.value_type === "text") {
    display = String(raw);
  }

  return {
    label: spec.display_label,
    display,
    raw,
    pending: false,
  };
}

const SR_MARKET_METRIC_SPECS = {
  medianActivePrice: {
    display_label: "Median Active Price",
    source_fields: ["median_price", "median_active_price"],
    value_type: "money",
    unavailable_label: "Median price pending",
  },
  averageActivePrice: {
    display_label: "Average Active Price",
    source_fields: ["average_price", "avg_price"],
    value_type: "money",
    unavailable_label: "Average price pending",
  },
  activeListings: {
    display_label: "Active Listings",
    source_fields: ["active_listings", "listings_count"],
    value_type: "integer",
    unavailable_label: "Pending",
  },
  auctionCount: {
    display_label: "Auction Count",
    source_fields: ["auction_count"],
    value_type: "integer",
    unavailable_label: "Auction data pending",
  },
  listingsWithBids: {
    display_label: "Listings With Bids",
    source_fields: ["listings_with_bids", "bid_count"],
    value_type: "integer",
    unavailable_label: "Pending",
  },
  marketDepth: {
    display_label: "Market Depth",
    source_fields: ["market_depth"],
    value_type: "text",
    unavailable_label: "Market depth pending",
  },
};

const SR_CARD_METRIC_SPECS = {
  medianActivePrice: {
    display_label: "Median Active Price",
    source_fields: ["median_price", "median_active_price"],
    value_type: "money",
    unavailable_label: "Median price pending",
  },
  averageActivePrice: {
    display_label: "Average Active Price",
    source_fields: ["average_price", "avg_price"],
    value_type: "money",
    unavailable_label: "Average price pending",
  },
  priceMovement7d: {
    display_label: "7-Day Movement",
    source_fields: ["median_price_change_pct", "average_price_change_pct", "price_change_pct"],
    value_type: "percent",
    unavailable_label: "Movement pending",
  },
  momentumScore: {
    display_label: "Momentum Score",
    source_fields: ["momentum_score"],
    value_type: "score",
    unavailable_label: "Pending",
  },
  activeListings: {
    display_label: "Active Listings",
    source_fields: ["active_listings", "listings_count"],
    value_type: "integer",
    unavailable_label: "Pending",
  },
};

const SR_PLAYER_STAT_SPECS = {
  last7d: [
    { label: "AVG", source_field: "avg", value_type: "decimal3" },
    { label: "HR", source_field: "home_runs", value_type: "integer" },
    { label: "RBI", source_field: "rbi", value_type: "integer" },
    { label: "OPS", source_field: "ops", value_type: "decimal3" },
    { label: "Hits", source_field: "hits", value_type: "integer" },
    { label: "Runs", source_field: "runs", value_type: "integer" },
    { label: "SB", source_field: "stolen_bases", value_type: "integer" },
    { label: "BB", source_field: "walks", value_type: "integer" },
    { label: "K Rate", source_field: "strikeout_rate", value_type: "percent", derived: "strikeout_rate" },
  ],
  season: [
    { label: "AVG", source_field: "avg", value_type: "decimal3" },
    { label: "HR", source_field: "home_runs", value_type: "integer" },
    { label: "RBI", source_field: "rbi", value_type: "integer" },
    { label: "OPS", source_field: "ops", value_type: "decimal3" },
    { label: "WAR", source_field: "war", value_type: "decimal1" },
    { label: "Games", source_field: "games", value_type: "integer" },
    { label: "OBP", source_field: "obp", value_type: "decimal3" },
    { label: "SLG", source_field: "slg", value_type: "decimal3" },
  ],
};

function srBuildMarketSource(intel = {}, weeklySnap = null) {
  const safeIntel = intel && typeof intel === "object" ? intel : {};
  const safeWeekly = weeklySnap && typeof weeklySnap === "object" ? weeklySnap : null;
  return {
    ...(safeIntel.evidence || {}),
    ...(safeWeekly?.evidence || {}),
  };
}

function srBuildCardSource(card = {}) {
  return {
    ...(card.evidence || {}),
    momentum_score: card.momentum_score,
    median_price_change_pct: card.median_price_change_pct,
    average_price_change_pct: card.average_price_change_pct,
    price_change_pct: card.price_change_pct,
  };
}

function srFormatPlayerStat(spec, stats = {}, formatters = {}) {
  if (!stats || typeof stats !== "object") {
    return { label: spec.label, display: SR_STAT_PENDING, pending: true, title: SR_STAT_PENDING_TITLE };
  }

  let raw = null;
  if (spec.derived === "strikeout_rate") {
    const ab = srSafeToNumber(stats.at_bats);
    const so = srSafeToNumber(stats.strikeouts);
    if (ab != null && ab > 0 && so != null) {
      raw = (so / ab) * 100;
    }
  } else {
    raw = srPickStoredField(stats, [spec.source_field]);
  }

  if (raw == null) {
    return { label: spec.label, display: SR_STAT_PENDING, pending: true, title: SR_STAT_PENDING_TITLE };
  }

  if (spec.value_type === "integer") {
    return { label: spec.label, display: String(Math.round(Number(raw))), pending: false, title: "" };
  }
  if (spec.value_type === "percent" && formatters.percent) {
    return { label: spec.label, display: formatters.percent(raw), pending: false, title: "" };
  }
  if (spec.value_type === "decimal3") {
    const n = srSafeToNumber(raw);
    return {
      label: spec.label,
      display: n == null ? SR_STAT_PENDING : n.toFixed(3),
      pending: n == null,
      title: n == null ? SR_STAT_PENDING_TITLE : "",
    };
  }
  if (spec.value_type === "decimal1") {
    const n = srSafeToNumber(raw);
    return {
      label: spec.label,
      display: n == null ? SR_STAT_PENDING : n.toFixed(1),
      pending: n == null,
      title: n == null ? SR_STAT_PENDING_TITLE : "",
    };
  }

  return { label: spec.label, display: String(raw), pending: false, title: "" };
}

function srBuildMarketMetrics(intel = {}, weeklySnap = null, formatters = {}) {
  const source = srBuildMarketSource(intel, weeklySnap);
  const metrics = {};
  Object.entries(SR_MARKET_METRIC_SPECS).forEach(([key, spec]) => {
    metrics[key] = srResolveMetric(spec, source, formatters);
  });
  return metrics;
}

function srBuildCardMetrics(card = {}, formatters = {}) {
  const source = srBuildCardSource(card);
  const metrics = {};
  Object.entries(SR_CARD_METRIC_SPECS).forEach(([key, spec]) => {
    metrics[key] = srResolveMetric(spec, source, formatters);
  });
  return metrics;
}

function srBuildMarketSummary(metrics = {}) {
  const parts = [];
  if (!metrics.activeListings?.pending && metrics.activeListings?.raw != null) {
    parts.push(`${metrics.activeListings.display} active listings captured in stored market snapshots`);
  }
  if (!metrics.medianActivePrice?.pending) {
    parts.push(`median active price at ${metrics.medianActivePrice.display}`);
  }
  if (!metrics.averageActivePrice?.pending) {
    parts.push(`average active price at ${metrics.averageActivePrice.display}`);
  }
  return parts.length ? `${parts.join("; ")}.` : "Market history still building.";
}

const SRMetrics = {
  SR_STAT_PENDING,
  SR_STAT_PENDING_TITLE,
  SR_MARKET_METRIC_SPECS,
  SR_CARD_METRIC_SPECS,
  SR_PLAYER_STAT_SPECS,
  srSafeToNumber,
  srPickStoredField,
  srResolveMetric,
  srBuildMarketSource,
  srBuildCardSource,
  srFormatPlayerStat,
  srBuildMarketMetrics,
  srBuildCardMetrics,
  srBuildMarketSummary,
};

if (typeof window !== "undefined") {
  window.SRMetrics = SRMetrics;
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = SRMetrics;
}
