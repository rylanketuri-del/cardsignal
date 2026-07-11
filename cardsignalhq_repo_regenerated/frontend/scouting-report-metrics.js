/**
 * Centralized Scouting Report metric mapping.
 * Each metric maps to exactly one stored source field — no proxy fallbacks.
 */
let CC = null;
try {
  CC = require("./collector-copy.js");
} catch (_) {
  CC = null;
}

function srCollectorCopy() {
  if (CC) return CC;
  if (typeof window !== "undefined" && typeof window.ccResolveStatUnavailable === "function") {
    return {
      ccResolveStatUnavailable: window.ccResolveStatUnavailable,
      ccResolveMarketMetricUnavailable: window.ccResolveMarketMetricUnavailable,
    };
  }
  return null;
}

const SR_STAT_UNAVAILABLE = CC?.ccResolveStatUnavailable
  ? CC.ccResolveStatUnavailable("AVG")
  : { display: "Unavailable", title: "Statistic unavailable for this period", pending: true };
const SR_STAT_PENDING = SR_STAT_UNAVAILABLE.display;
const SR_STAT_PENDING_TITLE = SR_STAT_UNAVAILABLE.title;

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

function srResolveMetric(spec, source, formatters = {}, metricKey = null) {
  const raw = srPickStoredField(source, spec.source_fields || [spec.source_field].filter(Boolean));
  if (raw == null) {
    const copy = srCollectorCopy();
    const unavailable = metricKey && copy?.ccResolveMarketMetricUnavailable
      ? copy.ccResolveMarketMetricUnavailable(metricKey)
      : {
        display: spec.unavailable_label || SR_STAT_PENDING,
        title: spec.unavailable_title || SR_STAT_PENDING_TITLE,
        pending: true,
      };
    return {
      label: spec.display_label,
      display: unavailable.display,
      title: unavailable.title || unavailable.helper_text || "",
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
    unavailable_label: "Unavailable",
    unavailable_title: "Listing data unavailable",
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
    unavailable_label: "Unavailable",
    unavailable_title: "Bid activity unavailable",
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
    unavailable_label: "Unavailable",
    unavailable_title: "Momentum score unavailable",
  },
  activeListings: {
    display_label: "Active Listings",
    source_fields: ["active_listings", "listings_count"],
    value_type: "integer",
    unavailable_label: "Unavailable",
    unavailable_title: "Listing data unavailable",
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

const SR_NFL_STAT_SPECS = {
  QB: {
    recent: [
      { label: "Pass Yards", source_field: "passing_yards", value_type: "integer" },
      { label: "Pass TD", source_field: "passing_touchdowns", value_type: "integer" },
      { label: "INT", source_field: "interceptions", value_type: "integer" },
      { label: "Completion %", source_field: "completion_percentage", value_type: "decimal1" },
      { label: "Passer Rating", source_field: "passer_rating", value_type: "decimal1" },
      { label: "Rush Yards", source_field: "rushing_yards", value_type: "integer" },
    ],
    season: [
      { label: "Pass Yards", source_field: "passing_yards", value_type: "integer" },
      { label: "Pass TD", source_field: "passing_touchdowns", value_type: "integer" },
      { label: "INT", source_field: "interceptions", value_type: "integer" },
      { label: "Completion %", source_field: "completion_percentage", value_type: "decimal1" },
      { label: "Passer Rating", source_field: "passer_rating", value_type: "decimal1" },
      { label: "Rush Yards", source_field: "rushing_yards", value_type: "integer" },
    ],
  },
  RB: {
    recent: [
      { label: "Rush Yards", source_field: "rushing_yards", value_type: "integer" },
      { label: "Rush TD", source_field: "rushing_touchdowns", value_type: "integer" },
      { label: "Yards/Carry", source_field: "yards_per_carry", value_type: "decimal1" },
      { label: "Receptions", source_field: "receptions", value_type: "integer" },
      { label: "Receiving Yards", source_field: "receiving_yards", value_type: "integer" },
      { label: "Total TD", source_field: "total_touchdowns", value_type: "integer" },
    ],
    season: [
      { label: "Rush Yards", source_field: "rushing_yards", value_type: "integer" },
      { label: "Rush TD", source_field: "rushing_touchdowns", value_type: "integer" },
      { label: "Yards/Carry", source_field: "yards_per_carry", value_type: "decimal1" },
      { label: "Receptions", source_field: "receptions", value_type: "integer" },
      { label: "Receiving Yards", source_field: "receiving_yards", value_type: "integer" },
      { label: "Total TD", source_field: "total_touchdowns", value_type: "integer" },
    ],
  },
  WR: {
    recent: [
      { label: "Targets", source_field: "targets", value_type: "integer" },
      { label: "Receptions", source_field: "receptions", value_type: "integer" },
      { label: "Receiving Yards", source_field: "receiving_yards", value_type: "integer" },
      { label: "Receiving TD", source_field: "receiving_touchdowns", value_type: "integer" },
      { label: "Catch Rate", source_field: "catch_rate", value_type: "decimal1" },
      { label: "Yards/Reception", source_field: "yards_per_reception", value_type: "decimal1" },
    ],
    season: [
      { label: "Targets", source_field: "targets", value_type: "integer" },
      { label: "Receptions", source_field: "receptions", value_type: "integer" },
      { label: "Receiving Yards", source_field: "receiving_yards", value_type: "integer" },
      { label: "Receiving TD", source_field: "receiving_touchdowns", value_type: "integer" },
      { label: "Catch Rate", source_field: "catch_rate", value_type: "decimal1" },
      { label: "Yards/Reception", source_field: "yards_per_reception", value_type: "decimal1" },
    ],
  },
  TE: {
    recent: [
      { label: "Targets", source_field: "targets", value_type: "integer" },
      { label: "Receptions", source_field: "receptions", value_type: "integer" },
      { label: "Receiving Yards", source_field: "receiving_yards", value_type: "integer" },
      { label: "Receiving TD", source_field: "receiving_touchdowns", value_type: "integer" },
      { label: "Catch Rate", source_field: "catch_rate", value_type: "decimal1" },
      { label: "Yards/Reception", source_field: "yards_per_reception", value_type: "decimal1" },
    ],
    season: [
      { label: "Targets", source_field: "targets", value_type: "integer" },
      { label: "Receptions", source_field: "receptions", value_type: "integer" },
      { label: "Receiving Yards", source_field: "receiving_yards", value_type: "integer" },
      { label: "Receiving TD", source_field: "receiving_touchdowns", value_type: "integer" },
      { label: "Catch Rate", source_field: "catch_rate", value_type: "decimal1" },
      { label: "Yards/Reception", source_field: "yards_per_reception", value_type: "decimal1" },
    ],
  },
};

function srResolveNflPositionGroup(position = "") {
  const pos = String(position || "").toUpperCase();
  if (pos === "QB") return "QB";
  if (pos === "RB" || pos === "FB") return "RB";
  if (pos === "WR") return "WR";
  if (pos === "TE") return "TE";
  return null;
}

function srGetNflStatSpecs(position = "") {
  const group = srResolveNflPositionGroup(position);
  if (!group || !SR_NFL_STAT_SPECS[group]) return null;
  return SR_NFL_STAT_SPECS[group];
}

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
  const copy = srCollectorCopy();
  const unavailable = copy?.ccResolveStatUnavailable
    ? copy.ccResolveStatUnavailable(spec.label)
    : { display: SR_STAT_PENDING, title: SR_STAT_PENDING_TITLE, pending: true };

  if (!stats || typeof stats !== "object") {
    return { label: spec.label, display: unavailable.display, pending: true, title: unavailable.title };
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
    return { label: spec.label, display: unavailable.display, pending: true, title: unavailable.title };
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
      display: n == null ? unavailable.display : n.toFixed(3),
      pending: n == null,
      title: n == null ? unavailable.title : "",
    };
  }
  if (spec.value_type === "decimal1") {
    const n = srSafeToNumber(raw);
    return {
      label: spec.label,
      display: n == null ? unavailable.display : n.toFixed(1),
      pending: n == null,
      title: n == null ? unavailable.title : "",
    };
  }

  return { label: spec.label, display: String(raw), pending: false, title: "" };
}

function srBuildMarketMetrics(intel = {}, weeklySnap = null, formatters = {}) {
  const source = srBuildMarketSource(intel, weeklySnap);
  const metrics = {};
  Object.entries(SR_MARKET_METRIC_SPECS).forEach(([key, spec]) => {
    metrics[key] = srResolveMetric(spec, source, formatters, key);
  });
  return metrics;
}

function srBuildCardMetrics(card = {}, formatters = {}) {
  const source = srBuildCardSource(card);
  const metrics = {};
  Object.entries(SR_CARD_METRIC_SPECS).forEach(([key, spec]) => {
    metrics[key] = srResolveMetric(spec, source, formatters, key);
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
  SR_NFL_STAT_SPECS,
  srResolveNflPositionGroup,
  srGetNflStatSpecs,
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
