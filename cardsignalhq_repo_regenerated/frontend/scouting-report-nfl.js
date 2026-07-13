/**
 * Centralized NFL Scouting Report mapper.
 * Maps stored backend fields only — no browser-derived season phase or fabricated drivers.
 */

const SR_NFL_PENDING_RANGE = "Date range pending";
const SR_NFL_NO_DRIVERS = "No verified NFL Signal Drivers are available yet.";

const SR_NFL_DRIVER_IMPACT = {
  THREE_GAME_FORM: "Recent form",
  PASSING_SURGE: "Passing production",
  TOUCHDOWN_STREAK: "Touchdown production",
  TARGET_VOLUME: "Target volume",
  RECEIVING_SURGE: "Receiving production",
  RUSHING_SURGE: "Rushing production",
  ROLE_EXPANSION: "Role change",
  STARTER_CHANGE: "Role change",
  INJURY: "Availability risk",
  INJURY_RETURN: "Return to play",
  DEPTH_CHART_CHANGE: "Depth chart",
  CONTRACT_EXTENSION: "Contract",
  TRADE: "Team change",
  MILESTONE: "Milestone",
  PLAYOFF_PERFORMANCE: "Postseason form",
  FREE_AGENT_SIGNING: "Roster move",
  DRAFT_SELECTION: "Roster move",
  TRAINING_CAMP_ROLE: "Camp role",
  INJURY_RECOVERY: "Injury recovery",
  VERIFIED_TEAM_DEVELOPMENT: "Team development",
};

function srNflSafeString(value) {
  if (value == null || value === "") return null;
  return String(value);
}

function srNflParseDate(value) {
  if (!value) return null;
  const raw = String(value).slice(0, 10);
  const parts = raw.split("-").map(Number);
  if (parts.length !== 3 || parts.some((n) => !Number.isFinite(n))) return null;
  return new Date(parts[0], parts[1] - 1, parts[2]);
}

function srNflFormatMonthDay(date) {
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function srNflFormatDateRange(start, end) {
  const startDate = srNflParseDate(start);
  const endDate = srNflParseDate(end);
  if (!startDate && !endDate) return SR_NFL_PENDING_RANGE;
  if (startDate && endDate) {
    if (startDate.getTime() === endDate.getTime()) {
      return `${srNflFormatMonthDay(startDate)}, ${startDate.getFullYear()}`;
    }
    if (startDate.getFullYear() === endDate.getFullYear()) {
      return `${srNflFormatMonthDay(startDate)}–${srNflFormatMonthDay(endDate)}, ${startDate.getFullYear()}`;
    }
    return `${srNflFormatMonthDay(startDate)}, ${startDate.getFullYear()}–${srNflFormatMonthDay(endDate)}, ${endDate.getFullYear()}`;
  }
  const single = startDate || endDate;
  return `${srNflFormatMonthDay(single)}, ${single.getFullYear()}`;
}

function srNflResolvePlayerId(entry = {}) {
  return srNflSafeString(entry.player_id || entry.source_player_id) || null;
}

function srNflIsNflEntry(entry = {}) {
  const league = String(entry.league || entry.sport || "").toUpperCase();
  const csId = String(entry.cs_player_id || "");
  return league === "NFL" || league === "FOOTBALL" || csId.startsWith("CS-NFL-P-");
}

function srNflRecentWindowLabel(phase) {
  if (phase === "OFFSEASON") return "Previous Season Context";
  if (phase === "PRESEASON") return "Preseason Snapshot";
  return "Recent 3 Games";
}

function srNflSeasonWindowLabel(phase, season) {
  if (phase === "OFFSEASON") return season ? `${season} Season Snapshot` : "Previous Season Snapshot";
  if (phase === "PRESEASON") return season ? `Prior Season Snapshot (${season})` : "Prior Season Snapshot";
  if (phase === "POSTSEASON") return season ? `Season Snapshot (${season}, Postseason)` : "Season Snapshot";
  return season ? `Season Snapshot (${season})` : "Season Snapshot";
}

function srNflOffseasonDriverLabel() {
  return "Offseason Signal Drivers";
}

function srNflShouldShowRecentPanel(phase) {
  return phase === "REGULAR_SEASON" || phase === "POSTSEASON" || phase === "PRESEASON";
}

function srNflShouldShowOffseasonDrivers(phase) {
  return phase === "OFFSEASON" || phase === "PRESEASON";
}

function srNflMapSignalDriver(driver = {}) {
  const title = srNflSafeString(driver.label);
  const summary = srNflSafeString(driver.description);
  const sourceType = srNflSafeString(driver.source_method);
  const occurredAt = srNflSafeString(driver.captured_at);
  const evidenceQuality = srNflSafeString(driver.season_phase) || "STORED";
  const impact = SR_NFL_DRIVER_IMPACT[driver.driver_type] || "Verified development";
  if (!title || !summary || !sourceType || sourceType === "UNAVAILABLE" || driver.verified === false) return null;
  return {
    title,
    summary,
    impact,
    evidenceQuality,
    occurredAt: occurredAt ? srNflFormatDateRange(occurredAt, occurredAt) : SR_NFL_PENDING_RANGE,
    sourceType,
  };
}

function srNflMapSignalDrivers(rawDrivers = []) {
  if (!Array.isArray(rawDrivers)) return [];
  return rawDrivers.map(srNflMapSignalDriver).filter(Boolean);
}

function srNflMapScoutingReport(entry = {}, weeklySnap = null) {
  const evidence = weeklySnap?.evidence || entry.evidence || {};
  const phase = evidence.nfl_season_phase || entry.nfl_season_phase || "UNKNOWN";
  const season = evidence.nfl_season || entry.nfl_season || weeklySnap?.season || entry.season || null;
  const recentWindow = evidence.nfl_recent_window || entry.nfl_recent_window || null;
  const seasonWindow = evidence.nfl_season_window || entry.nfl_season_window || null;
  const playerId = srNflResolvePlayerId(entry);
  const csPlayerId = entry.cs_player_id || (playerId ? `CS-NFL-P-${playerId}` : null);

  return {
    playerId,
    csPlayerId,
    nflSeasonPhase: phase,
    season,
    recentWindowLabel: srNflRecentWindowLabel(phase),
    seasonWindowLabel: srNflSeasonWindowLabel(phase, season),
    showRecentPanel: srNflShouldShowRecentPanel(phase),
    recentDateRange: srNflFormatDateRange(recentWindow?.period_start, recentWindow?.period_end),
    seasonDateRange: srNflFormatDateRange(seasonWindow?.period_start, seasonWindow?.period_end),
    gamesInWindow: recentWindow?.games_in_window ?? recentWindow?.games_played ?? null,
    recentDataQuality: recentWindow?.data_quality || evidence.nfl_data_quality || "INSUFFICIENT",
    seasonDataQuality: seasonWindow?.data_quality || "INSUFFICIENT",
    recentStats: evidence.nfl_recent_stats || entry.nfl_recent_stats || null,
    seasonStats: evidence.nfl_season_stats || entry.nfl_season_stats || null,
    previousSeasonStats: evidence.previous_season_performance || entry.previous_season_performance || null,
    previousSeasonLabel: evidence.previous_season_label || (season ? `${season} Season Snapshot` : "Previous Season Snapshot"),
    offseasonDriverLabel: srNflOffseasonDriverLabel(),
    showOffseasonDrivers: srNflShouldShowOffseasonDrivers(phase),
    signalDrivers: srNflMapSignalDrivers(evidence.nfl_signal_drivers || evidence.signal_drivers || entry.nfl_signal_drivers || []),
    performancePeriodNote: "Performance period",
    updatedNote: "Updated",
  };
}

function srNflResolveSearchEntry(matches = [], playerId = "") {
  const needle = String(playerId || "");
  if (!needle) return null;
  return matches.find((item) => String(srNflResolvePlayerId(item) || "") === needle) || null;
}

const SRNfl = {
  SR_NFL_PENDING_RANGE,
  SR_NFL_NO_DRIVERS,
  srNflResolvePlayerId,
  srNflIsNflEntry,
  srNflFormatDateRange,
  srNflMapScoutingReport,
  srNflMapSignalDrivers,
  srNflResolveSearchEntry,
  srNflRecentWindowLabel,
  srNflSeasonWindowLabel,
};

if (typeof window !== "undefined") {
  window.SRNfl = SRNfl;
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = SRNfl;
}
