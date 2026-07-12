/**
 * Shared collector-facing not-found states for Scouting Report and Card Report routes.
 */
(function initCardSignalNotFound(global) {
  const NOT_FOUND_CONFIG = {
    player: {
      title: "Player report not found",
      body: "We couldn't find this player in CardSignal's current data.",
      eyebrow: "Scouting Report",
    },
    card: {
      title: "Card report not found",
      body: "We couldn't find this card in the CardSignal registry.",
      eyebrow: "Card Report",
    },
  };

  function buildNotFoundActions(entityType, options = {}) {
    const actions = [];
    if (entityType === "card" && options.hasParentPlayer) {
      actions.push({ action: "back-scouting", label: "Back to Scouting Report", primary: false });
    }
    actions.push({ action: "home", label: "Return to Signal Center", primary: true });
    actions.push({ action: "search", label: "Search players", primary: false });
    return actions;
  }

  function renderReportNotFound(entityType, options = {}) {
    const config = NOT_FOUND_CONFIG[entityType] || NOT_FOUND_CONFIG.player;
    const actions = buildNotFoundActions(entityType, options);

    return `
      <div class="report-not-found" role="alert" aria-labelledby="report-not-found-title">
        <p class="eyebrow">${config.eyebrow}</p>
        <h2 id="report-not-found-title" class="report-not-found-title" tabindex="-1">${config.title}</h2>
        <p class="report-not-found-body">${config.body}</p>
        <div class="report-not-found-actions">
          ${actions.map((item) => `
            <button
              type="button"
              class="report-not-found-btn ${item.primary ? "primary" : "ghost"}"
              data-not-found-action="${item.action}"
            >${item.label}</button>`).join("")}
        </div>
      </div>`;
  }

  global.CardSignalNotFound = {
    NOT_FOUND_CONFIG,
    buildNotFoundActions,
    renderReportNotFound,
  };
})(window);
