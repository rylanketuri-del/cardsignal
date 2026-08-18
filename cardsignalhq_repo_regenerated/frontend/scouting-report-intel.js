/** Compatibility adapter: normalized PlayerIntelligencePayload → Scouting Report intel shape. */

function srMapNormalizedDrivers(drivers = []) {
  return drivers.map((driver) => ({
    title: driver.label || driver.driver_type || "Signal Driver",
    summary: driver.description || "",
    sourceType: driver.source_method || "STORED",
    impact: driver.evidence?.impact || "neutral",
    evidenceQuality: driver.evidence?.quality || "STORED",
    occurredAt: driver.captured_at ? new Date(driver.captured_at).toLocaleDateString() : "Pending",
    driverType: driver.driver_type || "",
  }));
}

function srStatsFromEvidence(evidenceList = []) {
  const stats = {};
  evidenceList.forEach((item) => {
    if (item.metric && item.value != null) {
      stats[item.metric] = item.value;
    }
  });
  if (evidenceList.length) {
    stats.games = stats.games || evidenceList.length;
  }
  return stats;
}

function srHasGames(stats) {
  return Boolean(stats && Number(stats.games) > 0);
}

function srMlbStatsSeason(entry = {}, payload = {}, leagueEvidence = {}) {
  const candidates = [entry.stats_season, leagueEvidence.stats_season, payload.stats_season];
  for (const candidate of candidates) {
    if (srHasGames(candidate)) return candidate;
  }
  return null;
}

function srIntelFromNormalized(payload = {}, entry = {}) {
  const league = String(payload.league || entry.league || "MLB").toUpperCase();
  const isNfl = league === "NFL" || payload.sport === "FOOTBALL";
  const isNba = league === "NBA" || payload.sport === "BASKETBALL";
  const isMlb = league === "MLB" && !isNfl && !isNba;
  const leagueEvidence = payload.league_evidence || {};

  const nflReport = isNfl
    ? (typeof SRNfl !== "undefined" ? SRNfl.srNflMapScoutingReport(entry, { evidence: leagueEvidence, league: "NFL", sport: "FOOTBALL" }) : null)
    : null;
  const nbaReport = isNba
    ? (typeof SRNba !== "undefined" ? SRNba.srNbaMapScoutingReport(entry, { evidence: leagueEvidence, league: "NBA", sport: "BASKETBALL" }) : null)
    : null;

  const recentStats = srStatsFromEvidence(payload.recent_performance || []);
  const seasonStats = srStatsFromEvidence(payload.season_performance || []);
  const previousSeasonStats = srStatsFromEvidence(payload.previous_season_performance || []);

  return {
    normalizedPayload: payload,
    score: payload.card_signal_score,
    performance: payload.performance_score,
    market: payload.market_score,
    collector: payload.collector_score,
    momentum: payload.momentum_score,
    scarcity: payload.scarcity_score,
    evidenceTier: payload.evidence || "INSUFFICIENT",
    recommendation: payload.recommendation,
    hasStoredRecommendation: !!payload.recommendation,
    weeklyChange: payload.weekly_change,
    evidence: leagueEvidence,
    missingInputs: payload.missing_inputs || [],
    capabilities: payload.capabilities || {},
    signalDrivers: payload.signal_drivers || [],
    algorithmVersion: payload.weekly_algorithm_version || payload.scoring_algorithm_version,
    capturedAt: payload.captured_at || payload.updated_at,
    stats7d: nflReport?.recentStats || nbaReport?.recentStats || recentStats || entry.stats_7d || leagueEvidence.nfl_recent_stats || leagueEvidence.nba_recent_stats || null,
    stats30d: nflReport?.seasonStats || nbaReport?.seasonStats || entry.stats_30d || leagueEvidence.nfl_season_stats || leagueEvidence.nba_season_stats || ((isNfl || isNba) ? seasonStats : null),
    statsSeason: isMlb ? srMlbStatsSeason(entry, payload, leagueEvidence) : null,
    previousSeasonStats: previousSeasonStats.length ? previousSeasonStats : (nflReport?.previousSeasonStats || nbaReport?.previousSeasonStats || null),
    previousSeasonLabel: payload.previous_season_label || nflReport?.previousSeasonLabel || nbaReport?.previousSeasonLabel || null,
    previousSeasonHelperText: payload.previous_season_helper_text || nflReport?.previousSeasonHelperText || nbaReport?.previousSeasonHelperText || null,
    previousSeasonSourceSnapshotId: payload.previous_season_source_snapshot_id || null,
    previousSeasonDataQuality: payload.previous_season_data_quality || "INSUFFICIENT",
    seasonLabel: payload.season_label || nbaReport?.seasonLabel || null,
    showRecentPanel: payload.season_phase === "REGULAR_SEASON" || payload.season_phase === "POSTSEASON" || payload.season_phase === "PRESEASON",
    showOffseasonDrivers: payload.season_phase === "OFFSEASON" || payload.season_phase === "PRESEASON",
    offseasonDriverLabel: payload.season_phase === "OFFSEASON" ? "Offseason Signal Drivers" : "Signal Drivers",
    marketSnapshots: leagueEvidence.market_snapshots || entry.market_snapshots || {},
    isNfl,
    isNba,
    isMlb,
    nfl: nflReport,
    nba: nbaReport,
    nflSeasonPhase: payload.season_phase || nflReport?.nflSeasonPhase || null,
    nbaSeasonPhase: nbaReport?.nbaSeasonPhase || null,
    recentWindowLabel: payload.recent_window_label || null,
    seasonPhase: payload.season_phase || null,
    season: payload.season || null,
    mappedDrivers: srMapNormalizedDrivers(payload.signal_drivers || []),
  };
}

const SRIntel = {
  srIntelFromNormalized,
  srMapNormalizedDrivers,
  srStatsFromEvidence,
  srHasGames,
  srMlbStatsSeason,
};

if (typeof window !== "undefined") {
  window.SRIntel = SRIntel;
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = SRIntel;
}
