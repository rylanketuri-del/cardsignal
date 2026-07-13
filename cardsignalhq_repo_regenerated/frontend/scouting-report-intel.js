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

function srIntelFromNormalized(payload = {}, entry = {}) {
  const league = String(payload.league || entry.league || "MLB").toUpperCase();
  const isNfl = league === "NFL" || payload.sport === "FOOTBALL";
  const isNba = league === "NBA" || payload.sport === "BASKETBALL";
  const leagueEvidence = payload.league_evidence || {};

  const nflReport = isNfl
    ? (typeof SRNfl !== "undefined" ? SRNfl.srNflMapScoutingReport(entry, { evidence: leagueEvidence, league: "NFL", sport: "FOOTBALL" }) : null)
    : null;
  const nbaReport = isNba
    ? (typeof SRNba !== "undefined" ? SRNba.srNbaMapScoutingReport(entry, { evidence: leagueEvidence, league: "NBA", sport: "BASKETBALL" }) : null)
    : null;

  const recentStats = srStatsFromEvidence(payload.recent_performance || []);
  const seasonStats = srStatsFromEvidence(payload.season_performance || []);

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
    stats30d: nflReport?.seasonStats || nbaReport?.seasonStats || seasonStats || entry.stats_30d || leagueEvidence.nfl_season_stats || leagueEvidence.nba_season_stats || null,
    marketSnapshots: leagueEvidence.market_snapshots || entry.market_snapshots || {},
    isNfl,
    isNba,
    isMlb: league === "MLB" && !isNfl && !isNba,
    nfl: nflReport,
    nba: nbaReport,
    nflSeasonPhase: payload.season_phase || nflReport?.nflSeasonPhase || null,
    nbaSeasonPhase: nbaReport?.nbaSeasonPhase || null,
    recentWindowLabel: payload.recent_window_label || null,
    seasonPhase: payload.season_phase || null,
    mappedDrivers: srMapNormalizedDrivers(payload.signal_drivers || []),
  };
}

if (typeof module !== "undefined") {
  module.exports = {
    srIntelFromNormalized,
    srMapNormalizedDrivers,
    srStatsFromEvidence,
  };
}
