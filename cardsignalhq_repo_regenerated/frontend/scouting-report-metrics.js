/**
 * Centralized Scouting Report metric mapping.
 * Each metric maps to exactly one stored source field — no proxy fallbacks.
 */
const SR_STAT_PENDING = "Pending";
const SR_STAT_PENDING_TITLE = "This statistic is not yet available in the current snapshot.";

const SR_PLAYER_SNAPSHOT_KEYS = {
  LAST_7D: "last7d",
  SEASON: "season",
};

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

function srFormatRatePercent(value) {
  const n = srSafeToNumber(value);
  if (n == null) return SR_STAT_PENDING;
  return `${n.toFixed(1)}%`;
}

function srResolveMetric(spec, source, formatters = {}) {
  const raw = srPickStoredField(source, spec.source_fields || [spec.source_field].filter(Boolean));
  if (raw == null) {
    return {
      label: spec.display_label,
      display: spec.unavailable_label,
      raw: null,
      pending: true,
      title: spec.unavailable_label === SR_STAT_PENDING ? SR_STAT_PENDING_TITLE : "",
    };
  }

  let display = String(raw);
  if (spec.value_type === "money" && formatters.money) {
    display = formatters.money(raw);
  } else if (spec.value_type === "percent" && formatters.percent) {
    display = formatters.percent(raw);
  } else if (spec.value_type === "rate_percent") {
    display = srFormatRatePercent(raw);
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

  const pending = display === spec.unavailable_label;
  return {
    label: spec.display_label,
    display,
    raw,
    pending,
    title: pending && spec.unavailable_label === SR_STAT_PENDING ? SR_STAT_PENDING_TITLE : "",
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
    { display_label: "AVG", source_field: "avg", value_type: "decimal3", unavailable_label: SR_STAT_PENDING },
    { display_label: "OBP", source_field: "obp", value_type: "decimal3", unavailable_label: SR_STAT_PENDING },
    { display_label: "SLG", source_field: "slg", value_type: "decimal3", unavailable_label: SR_STAT_PENDING },
    { display_label: "OPS", source_field: "ops", value_type: "decimal3", unavailable_label: SR_STAT_PENDING },
    { display_label: "HR", source_field: "home_runs", value_type: "integer", unavailable_label: SR_STAT_PENDING },
    { display_label: "RBI", source_field: "rbi", value_type: "integer", unavailable_label: SR_STAT_PENDING },
    { display_label: "Runs", source_field: "runs", value_type: "integer", unavailable_label: SR_STAT_PENDING },
    { display_label: "Hits", source_field: "hits", value_type: "integer", unavailable_label: SR_STAT_PENDING },
    { display_label: "SB", source_field: "stolen_bases", value_type: "integer", unavailable_label: SR_STAT_PENDING },
    { display_label: "BB", source_field: "walks", value_type: "integer", unavailable_label: SR_STAT_PENDING },
    { display_label: "Strikeout %", source_field: "strikeout_rate", value_type: "rate_percent", unavailable_label: SR_STAT_PENDING },
  ],
  season: [
    { display_label: "Games", source_field: "games", value_type: "integer", unavailable_label: SR_STAT_PENDING },
    { display_label: "AVG", source_field: "avg", value_type: "decimal3", unavailable_label: SR_STAT_PENDING },
    { display_label: "OBP", source_field: "obp", value_type: "decimal3", unavailable_label: SR_STAT_PENDING },
    { display_label: "SLG", source_field: "slg", value_type: "decimal3", unavailable_label: SR_STAT_PENDING },
    { display_label: "OPS", source_field: "ops", value_type: "decimal3", unavailable_label: SR_STAT_PENDING },
    { display_label: "HR", source_field: "home_runs", value_type: "integer", unavailable_label: SR_STAT_PENDING },
    { display_label: "RBI", source_field: "rbi", value_type: "integer", unavailable_label: SR_STAT_PENDING },
    { display_label: "Runs", source_field: "runs", value_type: "integer", unavailable_label: SR_STAT_PENDING },
    { display_label: "Hits", source_field: "hits", value_type: "integer", unavailable_label: SR_STAT_PENDING },
    { display_label: "WAR", source_field: "war", value_type: "decimal1", unavailable_label: SR_STAT_PENDING },
    { display_label: "SB", source_field: "stolen_bases", value_type: "integer", unavailable_label: SR_STAT_PENDING },
    { display_label: "BB", source_field: "walks", value_type: "integer", unavailable_label: SR_STAT_PENDING },
  ],
};

function srValidatePlayerStatSpecs() {
  const errors = [];
  const last7dFields = new Set();
  const seasonFields = new Set();

  const assertSingleSource = (spec, snapshotKey) => {
    if (!spec.source_field || typeof spec.source_field !== "string") {
      errors.push(`${snapshotKey}.${spec.display_label}: missing source_field`);
      return;
    }
    if (spec.source_fields && spec.source_fields.length) {
      errors.push(`${snapshotKey}.${spec.display_label}: source_fields not allowed on player stats`);
    }
    if (spec.derived) {
      errors.push(`${snapshotKey}.${spec.display_label}: derived stats are forbidden`);
    }
  };

  SR_PLAYER_STAT_SPECS.last7d.forEach((spec) => {
    assertSingleSource(spec, SR_PLAYER_SNAPSHOT_KEYS.LAST_7D);
    last7dFields.add(spec.source_field);

    if (spec.display_label === "AVG" && spec.source_field !== "avg") {
      errors.push("AVG must map to avg, never ops or other proxies");
    }
    if (spec.display_label === "Runs" && spec.source_field !== "runs") {
      errors.push("Runs must map to runs, never hits or other proxies");
    }
    if (spec.display_label === "Strikeout %" && spec.source_field !== "strikeout_rate") {
      errors.push("Strikeout % must map to strikeout_rate only");
    }
    if (spec.source_field === "ops" && spec.display_label !== "OPS") {
      errors.push("ops source_field may only back OPS display label");
    }
    if (spec.source_field === "hits" && spec.display_label !== "Hits") {
      errors.push("hits source_field may only back Hits display label");
    }
  });

  SR_PLAYER_STAT_SPECS.season.forEach((spec) => {
    assertSingleSource(spec, SR_PLAYER_SNAPSHOT_KEYS.SEASON);
    seasonFields.add(spec.source_field);

    if (spec.display_label === "AVG" && spec.source_field !== "avg") {
      errors.push("Season AVG must map to avg, never ops or other proxies");
    }
    if (spec.display_label === "Runs" && spec.source_field !== "runs") {
      errors.push("Season Runs must map to runs, never hits or other proxies");
    }
    if (spec.display_label === "WAR" && spec.source_field !== "war") {
      errors.push("WAR must map to war and must never be synthesized");
    }
    if (spec.source_field === "war" && spec.display_label !== "WAR") {
      errors.push("war source_field may only back WAR display label");
    }
    if (spec.source_field === "ops" && spec.display_label !== "OPS") {
      errors.push("Season ops source_field may only back OPS display label");
    }
    if (spec.source_field === "hits" && spec.display_label !== "Hits") {
      errors.push("Season hits source_field may only back Hits display label");
    }
  });

  if (last7dFields.has("war")) {
    errors.push("Last 7 Days must never include WAR");
  }

  return { valid: errors.length === 0, errors };
}

function srFormatPlayerStat(spec, stats = {}, formatters = {}) {
  return srResolveMetric(spec, stats, formatters);
}

function srBuildPlayerSnapshotStats(snapshotKey, stats = {}, formatters = {}) {
  const specs = SR_PLAYER_STAT_SPECS[snapshotKey] || [];
  return specs.map((spec) => srFormatPlayerStat(spec, stats, formatters));
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
  SR_PLAYER_SNAPSHOT_KEYS,
  SR_MARKET_METRIC_SPECS,
  SR_CARD_METRIC_SPECS,
  SR_PLAYER_STAT_SPECS,
  srSafeToNumber,
  srPickStoredField,
  srFormatRatePercent,
  srResolveMetric,
  srValidatePlayerStatSpecs,
  srBuildMarketSource,
  srBuildCardSource,
  srFormatPlayerStat,
  srBuildPlayerSnapshotStats,
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
