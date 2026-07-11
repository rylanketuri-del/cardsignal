/**
 * Centralized collector-facing copy, unavailable-state helpers, and API error normalization.
 * Sprint 9.7 — consistent terminology, pending language, and safe error messages.
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
  PLAYER_NOT_FOUND: "This report could not be found.",
  CARD_NOT_FOUND: "This report could not be found.",
  REPORT_UNAVAILABLE: "This Scouting Report could not be loaded. Try again after the next weekly refresh.",
  CARD_REPORT_UNAVAILABLE: "This Card Report could not be loaded. Try again after the next weekly refresh.",
  STAT_UNAVAILABLE_SHORT: "Unavailable",
  DATE_RANGE_PENDING: "Date range pending",
};

const COLLECTOR_ERROR_CONTEXT = {
  APP_INIT: "app_init",
  WATCHLIST: "watchlist",
  NOTIFICATIONS: "notifications",
  AUTH_SIGN_IN: "auth_sign_in",
  AUTH_SIGN_UP: "auth_sign_up",
  AUTH_SESSION: "auth_session",
  REPORT: "report",
  CARD_REPORT: "card_report",
  SEARCH: "search",
  GENERIC: "generic",
};

const COLLECTOR_USER_MESSAGES = {
  [COLLECTOR_ERROR_CONTEXT.APP_INIT]:
    "CardSignal could not load the latest market data. Please try again.",
  [COLLECTOR_ERROR_CONTEXT.WATCHLIST]:
    "We couldn't update your watchlist. Please try again.",
  [COLLECTOR_ERROR_CONTEXT.NOTIFICATIONS]:
    "Notifications are temporarily unavailable.",
  [COLLECTOR_ERROR_CONTEXT.AUTH_SIGN_IN]:
    "We couldn't sign you in. Check your details and try again.",
  [COLLECTOR_ERROR_CONTEXT.AUTH_SIGN_UP]:
    "We couldn't create your account. Please try again.",
  [COLLECTOR_ERROR_CONTEXT.AUTH_SESSION]:
    "Your session expired. Please sign in again.",
  [COLLECTOR_ERROR_CONTEXT.REPORT]:
    COLLECTOR_COPY.REPORT_UNAVAILABLE,
  [COLLECTOR_ERROR_CONTEXT.CARD_REPORT]:
    COLLECTOR_COPY.CARD_REPORT_UNAVAILABLE,
  [COLLECTOR_ERROR_CONTEXT.SEARCH]:
    "Search is temporarily unavailable. Please try again.",
  [COLLECTOR_ERROR_CONTEXT.GENERIC]:
    "CardSignal is temporarily unavailable. Please try again.",
  NOT_FOUND: COLLECTOR_COPY.PLAYER_NOT_FOUND,
  RATE_LIMIT: "CardSignal is receiving too many requests. Please try again shortly.",
  SERVER_ERROR: "CardSignal is temporarily unavailable. Please try again.",
  NETWORK: "Check your internet connection and try again.",
};

/** Stat unavailable mapping: label -> { short_label, helper_text, source_field, context } */
const STAT_UNAVAILABLE_MAP = {
  AVG: {
    short_label: "Unavailable",
    helper_text: "Recent batting average unavailable",
    source_field: "avg",
    context: "mlb_avg",
  },
  HR: {
    short_label: "Unavailable",
    helper_text: "Home run total unavailable for this period",
    source_field: "home_runs",
    context: "mlb_hr",
  },
  RBI: {
    short_label: "Unavailable",
    helper_text: "RBI total unavailable for this period",
    source_field: "rbi",
    context: "mlb_rbi",
  },
  OPS: {
    short_label: "Unavailable",
    helper_text: "OPS unavailable for this period",
    source_field: "ops",
    context: "mlb_ops",
  },
  Hits: {
    short_label: "Unavailable",
    helper_text: "Hit total unavailable for this period",
    source_field: "hits",
    context: "mlb_hits",
  },
  Runs: {
    short_label: "Unavailable",
    helper_text: "Runs total unavailable for this period",
    source_field: "runs",
    context: "mlb_runs",
  },
  SB: {
    short_label: "Unavailable",
    helper_text: "Stolen base total unavailable for this period",
    source_field: "stolen_bases",
    context: "mlb_sb",
  },
  BB: {
    short_label: "Unavailable",
    helper_text: "Walk total unavailable for this period",
    source_field: "walks",
    context: "mlb_bb",
  },
  "K Rate": {
    short_label: "Unavailable",
    helper_text: "Strikeout rate unavailable for this period",
    source_field: "strikeout_rate",
    context: "mlb_k_rate",
  },
  WAR: {
    short_label: "Unavailable",
    helper_text: "WAR is not available in the current snapshot",
    source_field: "war",
    context: "mlb_war",
  },
  Games: {
    short_label: "Unavailable",
    helper_text: "Games played unavailable for this period",
    source_field: "games",
    context: "mlb_games",
  },
  OBP: {
    short_label: "Unavailable",
    helper_text: "On-base percentage unavailable for this period",
    source_field: "obp",
    context: "mlb_obp",
  },
  SLG: {
    short_label: "Unavailable",
    helper_text: "Slugging percentage unavailable for this period",
    source_field: "slg",
    context: "mlb_slg",
  },
  "Pass Yards": {
    short_label: "Unavailable",
    helper_text: "Passing yards unavailable for this period",
    source_field: "passing_yards",
    context: "nfl_pass_yards",
  },
  "Pass TD": {
    short_label: "Unavailable",
    helper_text: "Passing touchdowns unavailable for this period",
    source_field: "passing_touchdowns",
    context: "nfl_pass_td",
  },
  INT: {
    short_label: "Unavailable",
    helper_text: "Interceptions unavailable for this period",
    source_field: "interceptions",
    context: "nfl_int",
  },
  "Completion %": {
    short_label: "Unavailable",
    helper_text: "Completion percentage unavailable for this period",
    source_field: "completion_percentage",
    context: "nfl_completion_pct",
  },
  "Passer Rating": {
    short_label: "Unavailable",
    helper_text: "Passer rating unavailable for this period",
    source_field: "passer_rating",
    context: "nfl_passer_rating",
  },
  "Rush Yards": {
    short_label: "Unavailable",
    helper_text: "Rushing yards unavailable for this period",
    source_field: "rushing_yards",
    context: "nfl_rush_yards",
  },
  "Rush TD": {
    short_label: "Unavailable",
    helper_text: "Rushing touchdowns unavailable for this period",
    source_field: "rushing_touchdowns",
    context: "nfl_rush_td",
  },
  "Yards/Carry": {
    short_label: "Unavailable",
    helper_text: "Yards per carry unavailable for this period",
    source_field: "yards_per_carry",
    context: "nfl_ypc",
  },
  Receptions: {
    short_label: "Unavailable",
    helper_text: "Receptions unavailable for this period",
    source_field: "receptions",
    context: "nfl_receptions",
  },
  "Receiving Yards": {
    short_label: "Unavailable",
    helper_text: "Receiving yards unavailable for this period",
    source_field: "receiving_yards",
    context: "nfl_rec_yards",
  },
  "Total TD": {
    short_label: "Unavailable",
    helper_text: "Total touchdowns unavailable for this period",
    source_field: "total_touchdowns",
    context: "nfl_total_td",
  },
  Targets: {
    short_label: "Unavailable",
    helper_text: "Targets unavailable for this period",
    source_field: "targets",
    context: "nfl_targets",
  },
  "Receiving TD": {
    short_label: "Unavailable",
    helper_text: "Receiving touchdowns unavailable for this period",
    source_field: "receiving_touchdowns",
    context: "nfl_rec_td",
  },
  "Catch Rate": {
    short_label: "Unavailable",
    helper_text: "Catch rate unavailable for this period",
    source_field: "catch_rate",
    context: "nfl_catch_rate",
  },
  "Yards/Reception": {
    short_label: "Unavailable",
    helper_text: "Yards per reception unavailable for this period",
    source_field: "yards_per_reception",
    context: "nfl_ypr",
  },
};

const MARKET_METRIC_UNAVAILABLE = {
  activeListings: {
    short_label: "Unavailable",
    helper_text: "Listing data unavailable",
    source_field: "active_listings",
    context: "market_active_listings",
  },
  listingsWithBids: {
    short_label: "Unavailable",
    helper_text: "Bid activity unavailable",
    source_field: "listings_with_bids",
    context: "market_listings_with_bids",
  },
  momentumScore: {
    short_label: "Unavailable",
    helper_text: "Momentum score unavailable",
    source_field: "momentum_score",
    context: "market_momentum_score",
  },
  medianActivePrice: {
    short_label: "Unavailable",
    helper_text: "Median price unavailable — available after the next market snapshot",
    source_field: "median_price",
    context: "market_median_price",
  },
  averageActivePrice: {
    short_label: "Unavailable",
    helper_text: "Average price unavailable — available after the next market snapshot",
    source_field: "average_price",
    context: "market_average_price",
  },
  auctionCount: {
    short_label: "Unavailable",
    helper_text: "Auction data unavailable",
    source_field: "auction_count",
    context: "market_auction_count",
  },
  marketDepth: {
    short_label: "Unavailable",
    helper_text: "Market depth unavailable",
    source_field: "market_depth",
    context: "market_depth",
  },
  priceMovement7d: {
    short_label: "Unavailable",
    helper_text: "Movement unavailable — available after the next market snapshot",
    source_field: "price_change_pct",
    context: "market_price_movement",
  },
};

const CARD_SCARCITY_UNAVAILABLE = {
  population: {
    short_label: "Unavailable",
    helper_text: "Population data pending",
    source_field: "population",
    context: "card_population",
  },
  psaPopulation: {
    short_label: "Unavailable",
    helper_text: "PSA population unavailable",
    source_field: "psa_population",
    context: "card_psa_population",
  },
  serialNumber: {
    short_label: "Unavailable",
    helper_text: "Serial-number data unavailable",
    source_field: "serial_number",
    context: "card_serial_number",
  },
  serialNumberConfirmedAbsent: {
    short_label: "Not serial-numbered",
    helper_text: "Registry confirms this card is not serial-numbered",
    source_field: "serial_number",
    context: "card_not_serial_numbered",
  },
  parallel: {
    short_label: "Unavailable",
    helper_text: "Parallel data unavailable",
    source_field: "parallel",
    context: "card_parallel",
  },
  printRun: {
    short_label: "Unavailable",
    helper_text: "Print-run data unavailable",
    source_field: "print_run",
    context: "card_print_run",
  },
  scarcityScore: {
    short_label: "Unavailable",
    helper_text: "More population and supply data required",
    source_field: "scarcity_score",
    context: "card_scarcity_score",
  },
  salesActivity: {
    short_label: "Unavailable",
    helper_text: "Sales activity unavailable",
    source_field: "sales_activity",
    context: "card_sales_activity",
  },
  dataQuality: {
    short_label: "Unavailable",
    helper_text: "Data quality unavailable",
    source_field: "data_quality",
    context: "card_data_quality",
  },
};

function ccUnavailableEntry(entry) {
  return {
    display: entry.short_label,
    title: entry.helper_text,
    pending: true,
    helper_text: entry.helper_text,
    context: entry.context,
  };
}

function ccResolveStatUnavailable(label, options = {}) {
  const key = String(label || "").trim();
  const mapped = STAT_UNAVAILABLE_MAP[key];
  if (mapped) return ccUnavailableEntry(mapped);
  return {
    display: COLLECTOR_COPY.STAT_UNAVAILABLE_SHORT,
    title: `${key || "Statistic"} unavailable for this period`,
    pending: true,
    helper_text: `${key || "Statistic"} unavailable for this period`,
    context: "stat_generic",
  };
}

function ccResolveMarketMetricUnavailable(metricKey) {
  const mapped = MARKET_METRIC_UNAVAILABLE[metricKey];
  if (mapped) return ccUnavailableEntry(mapped);
  return {
    display: COLLECTOR_COPY.STAT_UNAVAILABLE_SHORT,
    title: "Market data unavailable",
    pending: true,
    helper_text: "Market data unavailable",
    context: "market_generic",
  };
}

function ccResolvePopulationDisplay(pop = {}, report = {}) {
  const grading = String(pop.grading_company || report.grading_company || "").toUpperCase();
  const value = pop.psa_population ?? pop.population;
  if (value != null && value !== "") {
    return { display: String(value), title: "", pending: false };
  }
  const entry = grading === "PSA" ? CARD_SCARCITY_UNAVAILABLE.psaPopulation : CARD_SCARCITY_UNAVAILABLE.population;
  return ccUnavailableEntry(entry);
}

function ccResolveSerialNumberDisplay(pop = {}) {
  if (pop.serial_number != null && pop.serial_number !== "") {
    return { display: String(pop.serial_number), title: "", pending: false };
  }
  if (pop.is_serial_numbered === false || pop.serial_number_status === "NOT_SERIAL_NUMBERED") {
    return ccUnavailableEntry(CARD_SCARCITY_UNAVAILABLE.serialNumberConfirmedAbsent);
  }
  return ccUnavailableEntry(CARD_SCARCITY_UNAVAILABLE.serialNumber);
}

function ccResolveScarcityField(fieldKey, value) {
  if (value != null && value !== "") {
    return { display: String(value), title: "", pending: false };
  }
  const entry = CARD_SCARCITY_UNAVAILABLE[fieldKey];
  return entry ? ccUnavailableEntry(entry) : ccUnavailableEntry(CARD_SCARCITY_UNAVAILABLE.scarcityScore);
}

function ccResolveScarcityScoreDisplay(score, formatScoreFn) {
  if (score != null && Number.isFinite(Number(score))) {
    const formatted = typeof formatScoreFn === "function" ? formatScoreFn(score) : String(score);
    return { display: formatted, title: "", pending: false };
  }
  return ccUnavailableEntry(CARD_SCARCITY_UNAVAILABLE.scarcityScore);
}

function ccSanitizeUserFacingText(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  if (raw.startsWith("{") || raw.startsWith("[") || raw.startsWith("<")) return "";
  if (/traceback|stack trace|exception|sql|postgres|mongodb|internal server/i.test(raw)) return "";
  if (/https?:\/\//i.test(raw) || /\/api\//i.test(raw)) return "";
  if (/bearer\s+|authorization:|password|token/i.test(raw)) return "";
  if (raw.length > 160) return "";
  return raw;
}

function ccParseSafeJsonFields(bodyText) {
  const trimmed = String(bodyText || "").trim();
  if (!trimmed.startsWith("{") && !trimmed.startsWith("[")) return {};
  try {
    const parsed = JSON.parse(trimmed);
    if (!parsed || typeof parsed !== "object") return {};
    const detail = ccSanitizeUserFacingText(parsed.detail);
    const message = ccSanitizeUserFacingText(parsed.message);
    const code = ccSanitizeUserFacingText(parsed.code);
    return { detail, message, code };
  } catch (_) {
    return {};
  }
}

function ccMapStatusToCode(status) {
  if (status === 404) return "NOT_FOUND";
  if (status === 429) return "RATE_LIMIT";
  if (status >= 500) return "SERVER_ERROR";
  if (status === 401 || status === 403) return "AUTH_SESSION";
  if (status >= 400) return "CLIENT_ERROR";
  return "UNKNOWN";
}

function normalizeApiError(response, bodyText = "", context = COLLECTOR_ERROR_CONTEXT.GENERIC) {
  const status = response?.status || 0;
  const code = ccMapStatusToCode(status);
  const parsed = ccParseSafeJsonFields(bodyText);
  const contextMessage = COLLECTOR_USER_MESSAGES[context]
    || COLLECTOR_USER_MESSAGES[COLLECTOR_ERROR_CONTEXT.GENERIC];
  let userMessage = contextMessage;

  if (status === 404) {
    userMessage = COLLECTOR_USER_MESSAGES.NOT_FOUND;
  } else if (status === 429) {
    userMessage = COLLECTOR_USER_MESSAGES.RATE_LIMIT;
  } else if (status >= 500) {
    if (context === COLLECTOR_ERROR_CONTEXT.GENERIC) {
      userMessage = COLLECTOR_USER_MESSAGES.SERVER_ERROR;
    }
  } else if (status === 401 || status === 403) {
    if (context === COLLECTOR_ERROR_CONTEXT.AUTH_SIGN_IN) {
      userMessage = COLLECTOR_USER_MESSAGES[COLLECTOR_ERROR_CONTEXT.AUTH_SIGN_IN];
    } else if (context === COLLECTOR_ERROR_CONTEXT.AUTH_SIGN_UP) {
      userMessage = COLLECTOR_USER_MESSAGES[COLLECTOR_ERROR_CONTEXT.AUTH_SIGN_UP];
    } else {
      userMessage = COLLECTOR_USER_MESSAGES[COLLECTOR_ERROR_CONTEXT.AUTH_SESSION];
    }
  }

  return {
    code,
    status,
    userMessage,
    context,
    retryable: status === 429 || status >= 500,
    parsedCode: parsed.code || null,
  };
}

function createCollectorApiError(response, bodyText = "", context = COLLECTOR_ERROR_CONTEXT.GENERIC) {
  const normalized = normalizeApiError(response, bodyText, context);
  const error = new Error(normalized.userMessage);
  error.name = "CollectorApiError";
  error.code = normalized.code;
  error.status = normalized.status;
  error.userMessage = normalized.userMessage;
  error.context = normalized.context;
  error.retryable = normalized.retryable;
  return error;
}

function createNetworkCollectorError(context = COLLECTOR_ERROR_CONTEXT.GENERIC) {
  const error = new Error(COLLECTOR_USER_MESSAGES.NETWORK);
  error.name = "CollectorApiError";
  error.code = "NETWORK";
  error.status = 0;
  error.userMessage = COLLECTOR_USER_MESSAGES.NETWORK;
  error.context = context;
  error.retryable = true;
  return error;
}

function collectorUserMessage(error, context = COLLECTOR_ERROR_CONTEXT.GENERIC, fallback = null) {
  if (error && error.userMessage) return error.userMessage;
  const base = fallback
    || COLLECTOR_USER_MESSAGES[context]
    || COLLECTOR_USER_MESSAGES[COLLECTOR_ERROR_CONTEXT.GENERIC];
  if (error?.code === "NETWORK" || error?.name === "TypeError") {
    return COLLECTOR_USER_MESSAGES.NETWORK;
  }
  if (error?.status === 404) return COLLECTOR_USER_MESSAGES.NOT_FOUND;
  if (error?.status === 429) return COLLECTOR_USER_MESSAGES.RATE_LIMIT;
  if (error?.status >= 500) return COLLECTOR_USER_MESSAGES.SERVER_ERROR;
  return base;
}

function formatCollectorError(error, fallback = COLLECTOR_COPY.REPORT_UNAVAILABLE) {
  if (error && error.userMessage) return error.userMessage;
  return collectorUserMessage(error, COLLECTOR_ERROR_CONTEXT.REPORT, fallback);
}

function logCollectorError(normalizedOrError, requestContext = "") {
  if (typeof console === "undefined" || typeof console.error !== "function") return;
  const payload = {
    code: normalizedOrError?.code || normalizedOrError?.name || "UNKNOWN",
    status: normalizedOrError?.status || 0,
    context: normalizedOrError?.context || requestContext || "unknown",
  };
  console.error("CardSignal API error", payload);
}

async function collectorFetch(url, options = {}) {
  const context = options.context || COLLECTOR_ERROR_CONTEXT.GENERIC;
  try {
    const response = await fetch(url, options);
    if (!response.ok) {
      const bodyText = await response.text();
      const error = createCollectorApiError(response, bodyText, context);
      logCollectorError(error, context);
      throw error;
    }
    return response.json();
  } catch (error) {
    if (error?.name === "CollectorApiError") throw error;
    const networkError = createNetworkCollectorError(context);
    logCollectorError(networkError, context);
    throw networkError;
  }
}

const CollectorCopy = {
  COLLECTOR_COPY,
  COLLECTOR_ERROR_CONTEXT,
  COLLECTOR_USER_MESSAGES,
  STAT_UNAVAILABLE_MAP,
  MARKET_METRIC_UNAVAILABLE,
  CARD_SCARCITY_UNAVAILABLE,
  ccResolveStatUnavailable,
  ccResolveMarketMetricUnavailable,
  ccResolvePopulationDisplay,
  ccResolveSerialNumberDisplay,
  ccResolveScarcityField,
  ccResolveScarcityScoreDisplay,
  normalizeApiError,
  createCollectorApiError,
  createNetworkCollectorError,
  collectorUserMessage,
  formatCollectorError,
  logCollectorError,
  collectorFetch,
  ccSanitizeUserFacingText,
};

if (typeof window !== "undefined") {
  Object.assign(window, CollectorCopy);
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = CollectorCopy;
}
