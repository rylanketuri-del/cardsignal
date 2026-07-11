/**
 * Weekly movement formatting for Signal Center homepage surfaces.
 * Weekly Movement / Trend may only display stored weekly_change values.
 */
const WM_PENDING_LEADERBOARD = "Pending";
const WM_PENDING_FEATURED = "Movement pending";
const WM_LABEL_OFFICIAL = "This Week's Signal";
const WM_LABEL_CURRENT = "Current Featured Signal";
const WM_MOVEMENT_NOTE = "Weekly movement will appear after the next completed weekly snapshot.";

function hasStoredWeeklyChange(entry = {}) {
  return entry != null && entry.weekly_change != null && Number.isFinite(Number(entry.weekly_change));
}

function formatWeeklyMovement(entry = {}, options = {}) {
  const pendingLabel = options.pendingLabel || WM_PENDING_LEADERBOARD;

  if (!hasStoredWeeklyChange(entry)) {
    return { pending: true, label: pendingLabel, arrow: "", signed: "" };
  }

  const delta = Number(entry.weekly_change);

  if (Math.abs(delta) < 0.005) {
    return { pending: false, isZero: true, label: "No change", arrow: "", signed: "" };
  }

  const arrow = delta > 0 ? "↑" : "↓";
  const signed = delta > 0 ? `+${delta.toFixed(1)}` : `${delta.toFixed(1)}`;
  return { pending: false, isZero: false, label: `${arrow} ${signed}`, arrow, signed };
}

function weeklyMovementClass(movement = {}) {
  if (movement.pending) return "metric-pending";
  if (movement.isZero) return "metric-flat";
  if (movement.signed.startsWith("+")) return "metric-up";
  if (movement.signed.startsWith("-")) return "metric-down";
  return "metric-flat";
}

function renderWeeklyMovementLabel(movement = {}) {
  if (movement.pending || movement.isZero) return movement.label;
  return `${movement.arrow} ${movement.signed}`;
}

function getFeaturedSignalLabel(hasOfficialWeeklySelection) {
  return hasOfficialWeeklySelection ? WM_LABEL_OFFICIAL : WM_LABEL_CURRENT;
}

function usesOfficialWeeklyLeaders(weeklyIntelligence = null) {
  return Array.isArray(weeklyIntelligence?.todays_leaders) && weeklyIntelligence.todays_leaders.length > 0;
}

function hasCompletedOfficialWeeklyRun(weeklyIntelligence = null) {
  return !!(weeklyIntelligence?.run?.completed_at || weeklyIntelligence?.run?.id);
}

function shouldShowWeeklyMovementNote(weeklyIntelligence = null) {
  return !usesOfficialWeeklyLeaders(weeklyIntelligence);
}

function resolveFeaturedSignalPresentation({ hasOfficialSelection = false, entry = null } = {}) {
  const showWeeklyMovement = hasOfficialSelection;
  return {
    label: getFeaturedSignalLabel(hasOfficialSelection),
    showWeeklyMovement,
    movement: showWeeklyMovement
      ? formatWeeklyMovement(entry, { pendingLabel: WM_PENDING_FEATURED })
      : null,
  };
}

const WeeklyMovement = {
  WM_PENDING_LEADERBOARD,
  WM_PENDING_FEATURED,
  WM_LABEL_OFFICIAL,
  WM_LABEL_CURRENT,
  WM_MOVEMENT_NOTE,
  hasStoredWeeklyChange,
  formatWeeklyMovement,
  weeklyMovementClass,
  renderWeeklyMovementLabel,
  getFeaturedSignalLabel,
  usesOfficialWeeklyLeaders,
  hasCompletedOfficialWeeklyRun,
  shouldShowWeeklyMovementNote,
  resolveFeaturedSignalPresentation,
};

if (typeof window !== "undefined") {
  window.WeeklyMovement = WeeklyMovement;
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = WeeklyMovement;
}
