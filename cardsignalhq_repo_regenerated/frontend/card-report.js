/**
 * Card Report — individual collectible research destination.
 * Card Reports explain "Why is THIS card moving?" — never conflated with Player Reports.
 */

const CARD_REPORT_TAGLINE = "Where performance meets the market.";
const CARD_REPORT_ALGO = "WEEKLY_INTELLIGENCE_V1";

const CardReportRouter = {
  CARD_PATH_PREFIX: "/cards/",

  parsePathname(pathname = window.location.pathname) {
    if (!pathname.startsWith(this.CARD_PATH_PREFIX)) return null;
    const encoded = pathname.slice(this.CARD_PATH_PREFIX.length);
    if (!encoded) return null;
    try {
      return decodeURIComponent(encoded);
    } catch (_) {
      return null;
    }
  },

  buildPath(csCardId) {
    return this.CARD_PATH_PREFIX + encodeURIComponent(csCardId);
  },

  navigate(csCardId, { replace = false } = {}) {
    const path = this.buildPath(csCardId);
    const state = { cardReport: csCardId };
    if (replace) {
      window.history.replaceState(state, "", path);
    } else {
      window.history.pushState(state, "", path);
    }
  },

  clearRoute() {
    if (window.location.pathname.startsWith(this.CARD_PATH_PREFIX)) {
      window.history.replaceState({}, "", "/");
    }
  },

  init(onCardRoute) {
    const initial = this.parsePathname();
    if (initial) onCardRoute(initial);

    window.addEventListener("popstate", () => {
      const csCardId = this.parsePathname();
      if (csCardId) {
        onCardRoute(csCardId);
      } else if (typeof closeCardReportModal === "function") {
        closeCardReportModal({ skipRouteClear: true });
      }
    });
  },
};

async function fetchCardReport(csCardId) {
  if (typeof collectorFetch === "function") {
    return collectorFetch(`${API_BASE_URL}/api/cards/${encodeURIComponent(csCardId)}`, {
      context: COLLECTOR_ERROR_CONTEXT.CARD_REPORT,
    });
  }
  const response = await fetch(`${API_BASE_URL}/api/cards/${encodeURIComponent(csCardId)}`);
  if (!response.ok) throw createCollectorApiError(response, await response.text(), COLLECTOR_ERROR_CONTEXT.CARD_REPORT);
  return response.json();
}

async function fetchCardReportHistory(csCardId) {
  if (typeof collectorFetch === "function") {
    return collectorFetch(`${API_BASE_URL}/api/cards/${encodeURIComponent(csCardId)}/history`, {
      context: COLLECTOR_ERROR_CONTEXT.CARD_REPORT,
    });
  }
  const response = await fetch(`${API_BASE_URL}/api/cards/${encodeURIComponent(csCardId)}/history`);
  if (!response.ok) throw createCollectorApiError(response, await response.text(), COLLECTOR_ERROR_CONTEXT.CARD_REPORT);
  return response.json();
}

async function fetchCardReportMarket(csCardId) {
  if (typeof collectorFetch === "function") {
    return collectorFetch(`${API_BASE_URL}/api/cards/${encodeURIComponent(csCardId)}/market`, {
      context: COLLECTOR_ERROR_CONTEXT.CARD_REPORT,
    });
  }
  const response = await fetch(`${API_BASE_URL}/api/cards/${encodeURIComponent(csCardId)}/market`);
  if (!response.ok) throw createCollectorApiError(response, await response.text(), COLLECTOR_ERROR_CONTEXT.CARD_REPORT);
  return response.json();
}

async function fetchCardReportDrivers(csCardId) {
  if (typeof collectorFetch === "function") {
    return collectorFetch(`${API_BASE_URL}/api/cards/${encodeURIComponent(csCardId)}/drivers`, {
      context: COLLECTOR_ERROR_CONTEXT.CARD_REPORT,
    });
  }
  const response = await fetch(`${API_BASE_URL}/api/cards/${encodeURIComponent(csCardId)}/drivers`);
  if (!response.ok) throw createCollectorApiError(response, await response.text(), COLLECTOR_ERROR_CONTEXT.CARD_REPORT);
  return response.json();
}

function cardReportIdentitySource(report = {}) {
  if (report.card_identity) {
    return { identity: report.card_identity };
  }
  return {};
}

function cardReportFormatIdentity(card = {}) {
  const registry = typeof CardRegistry !== "undefined" ? CardRegistry : null;
  if (registry && typeof registry.formatCardIdentityHtml === "function") {
    return registry.formatCardIdentityHtml(card);
  }
  if (typeof formatCardIdentityHtml === "function") {
    return formatCardIdentityHtml(card);
  }
  return null;
}

function cardReportIdentityPending() {
  const registry = typeof CardRegistry !== "undefined" ? CardRegistry : null;
  if (registry && registry.CARD_REGISTRY_PENDING) {
    return registry.CARD_REGISTRY_PENDING;
  }
  return "Registry data pending";
}

function cardReportEvidenceClass(tier = "") {
  const key = String(tier || "").toUpperCase();
  if (key === "HIGH") return "cs-evidence--high";
  if (key === "MEDIUM") return "cs-evidence--medium";
  if (key === "LOW") return "cs-evidence--low";
  return "cs-evidence--insufficient";
}

function renderCardReportDriver(driver = {}) {
  const direction = driver.direction;
  const arrow = direction === "up" ? "⬆" : direction === "down" ? "⬇" : "•";
  const arrowClass = direction ? `cr-driver-arrow--${direction}` : "cr-driver-arrow--neutral";
  return `
    <div class="cr-driver">
      <span class="cr-driver-arrow ${arrowClass}">${arrow}</span>
      <div class="cr-driver-copy">
        <strong>${driver.label || "Signal"}</strong>
        <span>${driver.detail || ""}</span>
      </div>
    </div>`;
}

function renderCardReportHeader(report = {}) {
  const identitySource = cardReportIdentitySource(report);
  const identityHtml = cardReportFormatIdentity(identitySource);
  const identityTitle = identityHtml
    ? ""
    : `<h2 class="cr-header-identity-fallback">${report.card_label || "Card Report"}</h2>`;

  const rec = report.recommendation ? String(report.recommendation).toUpperCase() : "WATCH";
  const recClass = typeof csIntelRecommendationClass === "function"
    ? csIntelRecommendationClass(rec.toLowerCase())
    : "";
  const evidence = report.evidence || "INSUFFICIENT";
  const evidenceClass = cardReportEvidenceClass(evidence);
  const updatedLabel = report.updated_at && typeof formatTimestamp === "function"
    ? formatTimestamp(report.updated_at)
    : (typeof COLLECTOR_COPY !== "undefined" ? COLLECTOR_COPY.UPDATED_PENDING : "Updated timestamp pending");
  const scoreLabel = report.card_score != null && typeof formatScore === "function"
    ? formatScore(report.card_score)
    : (typeof COLLECTOR_COPY !== "undefined" ? COLLECTOR_COPY.CARD_SCORE_PENDING : "CardSignal Card Score pending");
  const playerLink = report.player_name
    ? `<button type="button" class="cr-player-link" data-cr-player-id="${report.player_id || ""}">${report.player_name}</button>`
    : `<span class="cr-player-link cr-player-link--muted">Player link pending — registry data not yet linked.</span>`;

  return `
    <div class="sr-header cr-header">
      <div class="pi-modal-header-main">
        <div class="pi-modal-identity cr-header-identity">
          <div class="cr-header-identity-block">
            ${identityHtml || identityTitle}
            <div class="cr-header-player-row">
              <span class="cr-header-player-label">Player</span>
              ${playerLink}
            </div>
          </div>
          <p class="sr-header-tagline">${CARD_REPORT_TAGLINE}</p>
        </div>
      </div>

      <div class="pi-modal-header-stats sr-header-stats cr-header-stats">
        <div class="pi-modal-stat">
          <span class="pi-modal-stat-value cr-header-score">${scoreLabel}</span>
          <span class="pi-modal-stat-label">CardSignal Card Score</span>
        </div>
        <div class="pi-modal-stat">
          <span class="pi-modal-stat-value cs-recommendation-badge ${recClass} pi-modal-rec-badge">${rec}</span>
          <span class="pi-modal-stat-label">Recommendation</span>
        </div>
        <div class="pi-modal-stat">
          <span class="pi-modal-stat-value cs-evidence-badge ${evidenceClass}">${evidence}</span>
          <span class="pi-modal-stat-label">Evidence</span>
        </div>
      </div>

      <div class="sr-header-meta">
        <span>Updated ${updatedLabel}</span>
        <span class="sr-header-meta-sep" aria-hidden="true">·</span>
        <span class="sr-header-algo">${report.algorithm_version || CARD_REPORT_ALGO}</span>
      </div>

      <div class="pi-modal-header-actions">
        <button type="button" class="pi-modal-close" data-cr-close aria-label="Close card report">✕</button>
      </div>
    </div>`;
}

function renderCardIdentitySection(report = {}) {
  const identitySource = cardReportIdentitySource(report);
  const identityHtml = cardReportFormatIdentity(identitySource);
  const body = identityHtml
    ? `<div class="cr-identity-formatted">${identityHtml}</div>`
    : `<p class="sr-pending">${cardReportIdentityPending()}</p>`;

  return `
    <section class="sr-section cr-section">
      <h3 class="sr-section-title">Card Identity</h3>
      <p class="sr-section-lead">Canonical card identity from the Card Registry when available.</p>
      ${body}
    </section>`;
}

function renderCardSnapshotSection(report = {}) {
  const formatters = typeof srMetricFormatters === "function" ? srMetricFormatters() : {};
  const cardSource = {
    evidence: {
      median_price: report.market?.median_price,
      avg_price: report.market?.average_price,
      listings_count: report.market?.active_listings,
      auction_count: report.market?.auction_count,
    },
    momentum_score: report.momentum_score,
  };
  const metrics = typeof SRMetrics !== "undefined"
    ? SRMetrics.srBuildCardMetrics(cardSource, formatters)
    : {};

  const snapshotItem = (label, value, pending = false, title = "") => {
    const titleAttr = title ? ` title="${title}"` : "";
    const aria = title ? ` aria-label="${title}"` : "";
    return `
    <div class="sr-snapshot-stat">
      <span class="sr-snapshot-stat-value${pending ? " sr-pending--inline" : ""}"${titleAttr}${aria}>${value}</span>
      <span class="sr-snapshot-stat-label">${label}</span>
    </div>`;
  };

  const populationState = typeof ccResolvePopulationDisplay === "function"
    ? ccResolvePopulationDisplay(report.population || {}, report)
    : { display: "Unavailable", title: "Population data pending", pending: true };
  const salesState = typeof ccResolveScarcityField === "function"
    ? ccResolveScarcityField("salesActivity", report.market?.sales_activity)
    : { display: "Unavailable", title: "Sales activity unavailable", pending: true };
  const qualityState = typeof ccResolveScarcityField === "function"
    ? ccResolveScarcityField("dataQuality", report.market?.data_quality)
    : { display: "Unavailable", title: "Data quality unavailable", pending: true };

  return `
    <section class="sr-section cr-section cr-market-snapshot">
      <h3 class="sr-section-title">Card Snapshot</h3>
      <p class="sr-section-lead">Stored market intelligence for this collectible — no recalculated scores.</p>
      <div class="sr-snapshot-grid cr-snapshot-grid">
        ${snapshotItem("Median Price", metrics.medianActivePrice?.display || "Unavailable", metrics.medianActivePrice?.pending !== false, metrics.medianActivePrice?.title || "Median price unavailable")}
        ${snapshotItem("Average Price", metrics.averageActivePrice?.display || "Unavailable", metrics.averageActivePrice?.pending !== false, metrics.averageActivePrice?.title || "Average price unavailable")}
        ${snapshotItem("Active Listings", metrics.activeListings?.display || "Unavailable", metrics.activeListings?.pending !== false, metrics.activeListings?.title || "Listing data unavailable")}
        ${snapshotItem("Population", populationState.display, populationState.pending, populationState.title)}
        ${snapshotItem("Sales Activity", salesState.display, salesState.pending, salesState.title)}
        ${snapshotItem("Data Quality", qualityState.display, qualityState.pending, qualityState.title)}
      </div>
    </section>`;
}

function renderCardPriceHistorySection(report = {}) {
  const history = report.price_history || {};
  const pointCount = (history.series || []).length;

  return `
    <section class="sr-section cr-section">
      <h3 class="sr-section-title">Price History</h3>
      <p class="sr-section-lead">Weekly price snapshots from stored intelligence.</p>
      <div class="cr-price-history-placeholder">
        <p class="cr-price-history-soon">Price history coming soon.</p>
        ${pointCount > 0
    ? `<p class="cr-price-history-meta">${pointCount} weekly snapshot${pointCount === 1 ? "" : "s"} stored · chart adapter pending</p>`
    : `<p class="sr-pending">No price history snapshots yet.</p>`}
      </div>
    </section>`;
}

function renderCardMarketDriversSection(report = {}) {
  const drivers = report.market_drivers || [];
  const body = drivers.length
    ? `<div class="cr-drivers">${drivers.map(renderCardReportDriver).join("")}</div>`
    : `<p class="sr-pending">Market driver data pending.</p>`;

  return `
    <section class="sr-section cr-section">
      <h3 class="sr-section-title">Market Drivers</h3>
      <p class="sr-section-lead">Card-level market signals — separate from player performance drivers.</p>
      ${body}
    </section>`;
}

function renderCardScarcitySection(report = {}) {
  const pop = report.population || {};
  const scarcityScore = pop.scarcity_score ?? report.scarcity_score;
  const scoreState = typeof ccResolveScarcityScoreDisplay === "function"
    ? ccResolveScarcityScoreDisplay(scarcityScore, typeof formatScore === "function" ? formatScore : null)
    : { display: "Unavailable", title: "More population and supply data required", pending: true };
  const populationState = typeof ccResolvePopulationDisplay === "function"
    ? ccResolvePopulationDisplay(pop, report)
    : { display: "Unavailable", title: "Population data pending", pending: true };
  const serialState = typeof ccResolveSerialNumberDisplay === "function"
    ? ccResolveSerialNumberDisplay(pop)
    : { display: "Unavailable", title: "Serial-number data unavailable", pending: true };
  const parallelState = typeof ccResolveScarcityField === "function"
    ? ccResolveScarcityField("parallel", pop.parallel)
    : { display: "Unavailable", title: "Parallel data unavailable", pending: true };
  const printRunState = typeof ccResolveScarcityField === "function"
    ? ccResolveScarcityField("printRun", pop.print_run)
    : { display: "Unavailable", title: "Print-run data unavailable", pending: true };

  const scarcityItem = (label, state) => `
    <div class="sr-snapshot-stat">
      <span class="sr-snapshot-stat-value${state.pending ? " sr-pending--inline" : ""}"${state.title ? ` title="${state.title}" aria-label="${state.title}"` : ""}>${state.display}</span>
      <span class="sr-snapshot-stat-label">${label}</span>
    </div>`;

  const drivers = report.scarcity_drivers || [];
  const driverBody = drivers.length
    ? `<div class="cr-drivers cr-drivers--compact">${drivers.map(renderCardReportDriver).join("")}</div>`
    : "";

  return `
    <section class="sr-section cr-section">
      <h3 class="sr-section-title">Scarcity</h3>
      <p class="sr-section-lead">Population, parallel, and scarcity signals for this collectible.</p>
      <div class="sr-snapshot-grid cr-snapshot-grid">
        ${scarcityItem("Population", populationState)}
        ${scarcityItem("Serial Number", serialState)}
        ${scarcityItem("Parallel", parallelState)}
        ${scarcityItem("Print Run", printRunState)}
        ${scarcityItem("Scarcity Score", scoreState)}
      </div>
      ${driverBody}
    </section>`;
}

function renderCardOutlookSection(report = {}) {
  const rec = report.recommendation ? String(report.recommendation).toUpperCase() : "WATCH";
  const recClass = typeof csIntelRecommendationClass === "function"
    ? csIntelRecommendationClass(rec.toLowerCase())
    : "";
  const evidence = report.evidence || "INSUFFICIENT";
  const evidenceClass = cardReportEvidenceClass(evidence);
  const summary = report.outlook_summary
    || "More verified card-level evidence is required before CardSignal can issue a full outlook.";
  const supportItems = report.outlook_evidence || [];

  const supportBody = supportItems.length
    ? `<ul class="cr-outlook-support">${supportItems.map((item) => `<li>${item}</li>`).join("")}</ul>`
    : `<p class="sr-pending">${evidence === "INSUFFICIENT" ? "Supporting evidence is not available in the current snapshot." : "Supporting evidence pending."}</p>`;

  return `
    <section class="sr-section cr-section cr-outlook">
      <h3 class="sr-section-title">Card Outlook</h3>
      <p class="sr-section-lead">Card-level recommendation based on stored market intelligence only.</p>
      <div class="sr-outlook-grid">
        <div class="sr-outlook-item">
          <span class="sr-outlook-label">Recommendation</span>
          <span class="cs-recommendation-badge ${recClass}">${rec}</span>
        </div>
        <div class="sr-outlook-item">
          <span class="sr-outlook-label">Evidence</span>
          <span class="cs-evidence-badge ${evidenceClass}">${evidence}</span>
        </div>
      </div>
      <p class="cr-outlook-summary">${summary}</p>
      <div class="cr-outlook-supported">
        <p class="cr-outlook-supported-label">Supported by:</p>
        ${supportBody}
      </div>
    </section>`;
}

function renderCardReport(report = {}) {
  return `
    <div class="sr-report cr-report" data-cr-extensions="pending">
      ${renderCardIdentitySection(report)}
      ${renderCardSnapshotSection(report)}
      ${renderCardPriceHistorySection(report)}
      ${renderCardMarketDriversSection(report)}
      ${renderCardScarcitySection(report)}
      ${renderCardOutlookSection(report)}
    </div>`;
}

let crModalReport = null;
let crModalOpen = false;

function isCardReportModalOpen() {
  const modal = document.getElementById("card-report-modal");
  return modal && !modal.classList.contains("hidden");
}

function closeCardReportModal({ skipRouteClear = false } = {}) {
  const modal = document.getElementById("card-report-modal");
  if (!modal) return;

  modal.classList.add("hidden");
  modal.setAttribute("aria-hidden", "true");
  if (typeof unlockBodyScrollForModal === "function") {
    unlockBodyScrollForModal();
  }
  crModalReport = null;
  crModalOpen = false;

  if (!skipRouteClear) {
    CardReportRouter.clearRoute();
  }
}

async function openCardReportModal(csCardId, { updateRoute = true } = {}) {
  const modal = document.getElementById("card-report-modal");
  const header = document.getElementById("cr-modal-header");
  const body = document.getElementById("cr-modal-body");
  if (!modal || !header || !body || !csCardId) return;

  if (typeof isPlayerIntelligenceModalOpen === "function" && isPlayerIntelligenceModalOpen()) {
    closePlayerIntelligenceModal();
  }

  header.innerHTML = `<div class="cr-loading">Loading card report…</div>`;
  body.innerHTML = "";
  modal.classList.remove("hidden");
  modal.setAttribute("aria-hidden", "false");
  if (typeof lockBodyScrollForModal === "function") {
    lockBodyScrollForModal();
  }
  crModalOpen = true;

  if (updateRoute) {
    CardReportRouter.navigate(csCardId);
  }

  try {
    const report = await fetchCardReport(csCardId);
    crModalReport = report;
    header.innerHTML = renderCardReportHeader(report);
    body.innerHTML = renderCardReport(report);
    wireCardReportActions(report);
    requestAnimationFrame(() => {
      modal.querySelector("[data-cr-close]")?.focus();
    });
  } catch (error) {
    const fallback = typeof COLLECTOR_COPY !== "undefined"
      ? COLLECTOR_COPY.CARD_REPORT_UNAVAILABLE
      : "This Card Report could not be loaded.";
    const message = typeof collectorUserMessage === "function"
      ? collectorUserMessage(error, COLLECTOR_ERROR_CONTEXT.CARD_REPORT, fallback)
      : (typeof formatCollectorError === "function" ? formatCollectorError(error, fallback) : fallback);
    header.innerHTML = `
      <div class="sr-header cr-header">
        <div class="pi-modal-header-main">
          <h2 class="cr-header-identity-fallback" id="cr-modal-title">Card Report</h2>
        </div>
        <div class="pi-modal-header-actions">
          <button type="button" class="pi-modal-close" data-cr-close aria-label="Close card report">✕</button>
        </div>
      </div>`;
    body.innerHTML = `<div class="pi-tab-placeholder"><p class="pi-tab-placeholder-copy">${message}</p></div>`;
  }
}

function wireCardReportActions(report = {}) {
  const modal = document.getElementById("card-report-modal");
  if (!modal) return;

  modal.querySelectorAll("[data-cr-close]").forEach((btn) => {
    btn.addEventListener("click", (event) => {
      event.preventDefault();
      closeCardReportModal();
    });
  });

  modal.querySelectorAll(".cr-player-link[data-cr-player-id]").forEach((btn) => {
    btn.addEventListener("click", async (event) => {
      event.preventDefault();
      const playerId = btn.dataset.crPlayerId;
      if (!playerId || typeof openPlayerIntelligenceModal !== "function") return;
      closeCardReportModal({ skipRouteClear: true });
      CardReportRouter.clearRoute();
      const entry = latestEntries.find((e) => String(e.player_id) === String(playerId))
        || { player_id: playerId, player_name: report.player_name };
      await openPlayerIntelligenceModal(entry);
    });
  });
}

function setupCardReportModal() {
  const modal = document.getElementById("card-report-modal");
  if (!modal || modal.dataset.crBound === "1") return;
  modal.dataset.crBound = "1";

  modal.addEventListener("click", (event) => {
    const closeTarget = event.target.closest("[data-cr-close]");
    if (closeTarget) {
      event.preventDefault();
      closeCardReportModal();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && isCardReportModalOpen()) {
      event.preventDefault();
      closeCardReportModal();
    }
  });
}

function setupCardReportRouter() {
  CardReportRouter.init((csCardId) => {
    openCardReportModal(csCardId, { updateRoute: false });
  });
}

function wireCardPanelClicks(root = document) {
  root.querySelectorAll("[data-cs-card-id]").forEach((el) => {
    const csCardId = el.dataset.csCardId;
    if (!csCardId || el.dataset.crClickBound === "1") return;
    el.dataset.crClickBound = "1";
    el.classList.add("cr-clickable");
    el.setAttribute("role", "button");
    el.setAttribute("tabindex", "0");
    el.setAttribute("aria-label", "Open card report");

    const open = () => openCardReportModal(csCardId);
    el.addEventListener("click", open);
    el.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        open();
      }
    });
  });
}

if (typeof window !== "undefined") {
  window.CardReportRouter = CardReportRouter;
  window.openCardReportModal = openCardReportModal;
  window.closeCardReportModal = closeCardReportModal;
  window.setupCardReportModal = setupCardReportModal;
  window.setupCardReportRouter = setupCardReportRouter;
  window.wireCardPanelClicks = wireCardPanelClicks;
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    CardReportRouter,
    renderCardReport,
    renderCardReportHeader,
    cardReportEvidenceClass,
  };
}
