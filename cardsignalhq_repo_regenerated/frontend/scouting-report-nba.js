/**
 * Centralized NBA Scouting Report mapper.
 * Maps stored backend fields only — no browser-derived season phase or fabricated drivers.
 */

const SR_NBA_PENDING_RANGE = "Date range pending";
const SR_NBA_NO_DRIVERS = "No verified NBA Signal Drivers are available yet.";

const SR_NBA_DRIVER_IMPACT = {
  HOT_STREAK: "Recent form",
  ROLE_EXPANSION: "Role change",
  STARTER_CHANGE: "Role change",
  MINUTES_SURGE: "Playing time",
  TRADE: "Team change",
  CONTRACT: "Contract",
  INJURY: "Availability risk",
  INJURY_RETURN: "Return to play",
  ALL_STAR_SELECTION: "All-Star recognition",
  PLAYOFF_PERFORMANCE: "Postseason form",
};

function srNbaSafeString(value) {
  if (value == null || value === "") return null;
  return String(value);
}

function srNbaParseDate(value) {
  if (!value) return null;
  const raw = String(value).slice(0, 10);
  const parts = raw.split("-").map(Number);
  if (parts.length !== 3 || parts.some((n) => !Number.isFinite(n))) return null;
  return new Date(parts[0], parts[1] - 1, parts[2]);
}

function srNbaFormatMonthDay(date) {
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function srNbaFormatDateRange(start, end) {
  const startDate = srNbaParseDate(start);
  const endDate = srNbaParseDate(end);
  if (!startDate && !endDate) return SR_NBA_PENDING_RANGE;
  if (startDate && endDate) {
    if (startDate.getTime() === endDate.getTime()) {
      return `${srNbaFormatMonthDay(startDate)}, ${startDate.getFullYear()}`;
    }
    if (startDate.getFullYear() === endDate.getFullYear()) {
      return `${srNbaFormatMonthDay(startDate)}–${srNbaFormatMonthDay(endDate)}, ${startDate.getFullYear()}`;
    }
    return `${srNbaFormatMonthDay(startDate)}, ${startDate.getFullYear()}–${srNbaFormatMonthDay(endDate)}, ${endDate.getFullYear()}`;
  }
  const single = startDate || endDate;
  return `${srNbaFormatMonthDay(single)}, ${single.getFullYear()}`;
}

function srNbaResolvePlayerId(entry = {}) {
  return srNbaSafeString(entry.player_id || entry.source_player_id) || null;
}

function srNbaIsNbaEntry(entry = {}) {
  const league = String(entry.league || entry.sport || "").toUpperCase();
  const csId = String(entry.cs_player_id || "");
  return league === "NBA" || league === "BASKETBALL" || csId.startsWith("CS-NBA-P-");
}

function srNbaRecentWindowLabel(phase, windowValue = 5) {
  if (phase === "OFFSEASON") return "Previous Season Context";
  if (phase === "PRESEASON") return "Preseason Performance";
  return `Recent ${windowValue} Games`;
}

function srNbaSeasonWindowLabel(phase, season, storedLabel) {
  if (storedLabel) return storedLabel;
  if (phase === "OFFSEASON") {
    return "Previous Season Performance";
  }
  if (phase === "PRESEASON") {
    return season != null && season !== "" ? `${season} Season Performance` : "Previous Season Performance";
  }
  if (season != null && season !== "") {
    return `${season} Season Performance`;
  }
  return "Season Performance";
}

function srNbaOffseasonDriverLabel() {
  return "Offseason Signal Drivers";
}

function srNbaOffseasonHelperText(phase, hasLabel) {
  if (phase === "OFFSEASON" && hasLabel) return "Most recently completed season";
  return null;
}

function srNbaShouldShowRecentPanel(phase) {
  return phase === "REGULAR_SEASON" || phase === "POSTSEASON" || phase === "PRESEASON";
}

function srNbaMapSignalDriver(driver = {}) {
  const title = srNbaSafeString(driver.label);
  const summary = srNbaSafeString(driver.description);
  const sourceType = srNbaSafeString(driver.source_method);
  const occurredAt = srNbaSafeString(driver.captured_at);
  const evidenceQuality = srNbaSafeString(driver.season_phase) || "STORED";
  const impact = SR_NBA_DRIVER_IMPACT[driver.driver_type] || "Verified development";
  if (!title || !summary || !sourceType || sourceType === "UNAVAILABLE" || driver.verified === false) return null;
  return {
    title,
    summary,
    impact,
    evidenceQuality,
    occurredAt: occurredAt ? srNbaFormatDateRange(occurredAt, occurredAt) : SR_NBA_PENDING_RANGE,
    sourceType,
  };
}

function srNbaMapSignalDrivers(rawDrivers = []) {
  if (!Array.isArray(rawDrivers)) return [];
  return rawDrivers.map(srNbaMapSignalDriver).filter(Boolean);
}

function srNbaMapScoutingReport(entry = {}, weeklySnap = null) {
  const evidence = weeklySnap?.evidence || entry.evidence || {};
  const phase = evidence.nba_season_phase || entry.nba_season_phase || evidence.season_phase || "UNKNOWN";
  const season = evidence.nba_season || entry.nba_season || weeklySnap?.season || entry.season || null;
  const storedPrevLabel = evidence.previous_season_label || entry.previous_season_label || null;
  const storedSeasonLabel = evidence.season_performance_label || null;
  const canonicalLabel = evidence.season_label || entry.season_label || null;
  const recentWindow = evidence.nba_recent_window || entry.nba_recent_window || null;
  const seasonWindow = evidence.nba_season_window || entry.nba_season_window || null;
  const windowValue = recentWindow?.recent_window_value || 5;
  const playerId = srNbaResolvePlayerId(entry);
  const csPlayerId = entry.cs_player_id || (playerId ? `CS-NBA-P-${playerId}` : null);
  const offseasonLabel = storedPrevLabel
    || (canonicalLabel ? `${canonicalLabel} Season Performance` : null);
  const seasonWindowLabel = phase === "OFFSEASON"
    ? srNbaSeasonWindowLabel(phase, season, offseasonLabel)
    : srNbaSeasonWindowLabel(phase, season, storedSeasonLabel || (canonicalLabel ? `${canonicalLabel} Season Performance` : null));

  return {
    playerId,
    csPlayerId,
    nbaSeasonPhase: phase,
    season,
    seasonLabel: canonicalLabel,
    recentWindowLabel: srNbaRecentWindowLabel(phase, windowValue),
    seasonWindowLabel,
    showRecentPanel: srNbaShouldShowRecentPanel(phase),
    recentDateRange: srNbaFormatDateRange(recentWindow?.period_start, recentWindow?.period_end),
    seasonDateRange: srNbaFormatDateRange(seasonWindow?.period_start, seasonWindow?.period_end),
    gamesInWindow: recentWindow?.games_in_window ?? recentWindow?.games_played ?? null,
    recentDataQuality: recentWindow?.data_quality || evidence.nba_data_quality || "INSUFFICIENT",
    seasonDataQuality: seasonWindow?.data_quality || "INSUFFICIENT",
    recentStats: evidence.nba_recent_stats || entry.nba_recent_stats || null,
    seasonStats: evidence.nba_season_stats || entry.nba_season_stats || null,
    previousSeasonStats: evidence.previous_season_performance || entry.previous_season_performance || null,
    previousSeasonLabel: offseasonLabel || (phase === "OFFSEASON" ? seasonWindowLabel : null),
    previousSeasonHelperText: evidence.previous_season_helper_text || srNbaOffseasonHelperText(phase, !!offseasonLabel || !!canonicalLabel),
    offseasonDriverLabel: srNbaOffseasonDriverLabel(),
    showOffseasonDrivers: phase === "OFFSEASON" || phase === "PRESEASON",
    signalDrivers: srNbaMapSignalDrivers(evidence.nba_signal_drivers || evidence.signal_drivers || entry.nba_signal_drivers || []),
    performancePeriodNote: "Performance period",
    updatedNote: "Updated",
  };
}

function srNbaResolveSearchEntry(matches = [], playerId = "") {
  const needle = String(playerId || "");
  if (!needle) return null;
  return matches.find((item) => String(srNbaResolvePlayerId(item) || "") === needle) || null;
}

const SRNba = {
  SR_NBA_PENDING_RANGE,
  SR_NBA_NO_DRIVERS,
  srNbaResolvePlayerId,
  srNbaIsNbaEntry,
  srNbaFormatDateRange,
  srNbaMapScoutingReport,
  srNbaMapSignalDrivers,
  srNbaResolveSearchEntry,
  srNbaRecentWindowLabel,
  srNbaSeasonWindowLabel,
};

if (typeof window !== "undefined") {
  window.SRNba = SRNba;
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = SRNba;
}
