/**
 * CardSignal Card Market panel.
 * First live source is eBay; names stay marketplace-generic so later
 * sources (CollX, COMC, dealer inventory) can share this interaction.
 */
const CARD_MARKET_DISCLAIMER =
  "Marketplace listings are provided for discovery. Price and availability may change.";
const CARD_MARKET_TITLE_ID = "cm-modal-title";
const EBAY_SEARCH_BASE = "https://www.ebay.com/sch/i.html";
const EBAY_HOST_PATTERN = /^(?:[a-z0-9-]+\.)*ebay\.com$/i;
const QUERY_NAME_LABELS = {
  broad: "Base Cards",
  bowman_chrome: "Bowman Chrome",
  auto: "Autographs",
  psa10: "PSA 10",
  rookie: "Rookie Cards",
  prizm: "Prizm",
};

let cardMarketCatalog = [];
let cardMarketKeydownBound = false;
let cardMarketLastTrigger = null;

function escapeHtml(value) {
  return String(value == null ? "" : value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function escapeAttribute(value) {
  return escapeHtml(value);
}

function wc() {
  if (typeof WeeklyConvergence !== "undefined") return WeeklyConvergence;
  if (typeof window !== "undefined") return window.WeeklyConvergence || {};
  return {};
}

function formatUsd(value) {
  if (typeof wc().formatUsdMoney === "function") return wc().formatUsdMoney(value);
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function formatScore(value) {
  if (typeof wc().formatCardSignalScore === "function") return wc().formatCardSignalScore(value);
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(1) : "—";
}

function isFiniteNumber(value) {
  if (typeof wc().isFiniteNumber === "function") return wc().isFiniteNumber(value);
  return typeof value === "number" && Number.isFinite(value);
}

function parseFiniteNumber(value) {
  if (isFiniteNumber(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

function marketplaceSourceLabel(source) {
  const key = String(source || "").trim().toLowerCase();
  if (!key) return null;
  if (key === "ebay") return "eBay";
  if (key === "collx") return "CollX";
  if (key === "comc") return "COMC";
  if (key === "dealer" || key === "card_dealer_pro") return "Dealer Inventory";
  return String(source);
}

function humanizeQueryName(queryName) {
  const key = String(queryName || "").trim();
  if (!key) return "";
  if (QUERY_NAME_LABELS[key]) return QUERY_NAME_LABELS[key];
  return key.replace(/_/g, " ").trim();
}

function categoryFromIntelItem(item = {}) {
  const label = String(item.cardLabel || item.card_label || "").trim();
  if (label && label.toLowerCase() !== "card") return label;
  return humanizeQueryName(item.queryName || item.query_name || item.representativeOffer?.query_name);
}

function shopSimilarSportNoun(item = {}) {
  const sport = String(item.sport || item.league || "MLB").trim().toUpperCase();
  if (sport === "NFL" || sport === "FOOTBALL") return "football";
  if (sport === "NBA" || sport === "BASKETBALL") return "basketball";
  return "baseball";
}

function isSafeHttpImageUrl(raw) {
  if (typeof raw !== "string") return null;
  const trimmed = raw.trim();
  if (!trimmed) return null;
  let url;
  try {
    url = new URL(trimmed);
  } catch (_) {
    return null;
  }
  if (url.protocol !== "https:" && url.protocol !== "http:") return null;
  if (url.username || url.password) return null;
  return url.href;
}

function isSafeHttpsEbayListingUrl(raw) {
  if (typeof raw !== "string") return null;
  const trimmed = raw.trim();
  if (!trimmed) return null;
  let url;
  try {
    url = new URL(trimmed);
  } catch (_) {
    return null;
  }
  if (url.protocol !== "https:") return null;
  if (url.username || url.password) return null;
  const host = String(url.hostname || "").replace(/\.$/, "").toLowerCase();
  if (!EBAY_HOST_PATTERN.test(host)) return null;
  return url.href;
}

function buildEbayShopSimilarUrl(item = {}) {
  const playerName = String(item.playerName || item.player_name || "").trim();
  if (!playerName) return null;
  const category = categoryFromIntelItem(item);
  const sportNoun = shopSimilarSportNoun(item);
  const parts = [playerName];
  if (category) parts.push(category);
  parts.push(`${sportNoun} card`);
  const nkw = parts.join(" ").replace(/\s+/g, " ").trim();
  if (!nkw) return null;
  const url = new URL(EBAY_SEARCH_BASE);
  url.searchParams.set("_nkw", nkw);
  return url.toString();
}

function setCatalog(items = []) {
  cardMarketCatalog = Array.isArray(items) ? items.slice() : [];
  return cardMarketCatalog;
}

function getCatalog() {
  return cardMarketCatalog;
}

function getModal() {
  if (typeof document === "undefined") return null;
  return document.getElementById("card-market-modal");
}

function isOpen() {
  const modal = getModal();
  return Boolean(modal && !modal.classList.contains("hidden"));
}

function lockBodyScroll() {
  if (typeof document === "undefined" || !document.body || !document.body.classList) return;
  document.body.classList.add("pi-modal-open");
}

function unlockBodyScroll() {
  if (typeof document === "undefined" || !document.body || !document.body.classList) return;
  const pi = typeof document.getElementById === "function"
    ? document.getElementById("player-intelligence-modal")
    : null;
  if (pi && !pi.classList.contains("hidden")) return;
  document.body.classList.remove("pi-modal-open");
}

function renderHeroImage(item = {}) {
  const imageUrl = isSafeHttpImageUrl(item.imageUrl || item.representativeOffer?.image_url || "");
  const alt = escapeAttribute(item.name || item.playerName || "Card");
  if (!imageUrl) {
    return `<div class="cm-hero-image" aria-hidden="true"></div>`;
  }
  return `
    <div class="cm-hero-image">
      <img
        src="${escapeAttribute(imageUrl)}"
        alt="${alt}"
        class="cm-hero-image-img"
        loading="lazy"
        onerror="this.remove()"
      />
    </div>`;
}

function renderStat(label, valueHtml) {
  return `
    <div class="cm-stat">
      <span class="cm-stat-label">${escapeHtml(label)}</span>
      <span class="cm-stat-value">${valueHtml}</span>
    </div>`;
}

function listingsCountFromItem(item = {}) {
  return parseFiniteNumber(item.listingsCount ?? item.listings_count ?? item.evidence?.listings_count);
}

function avgPriceFromItem(item = {}) {
  return parseFiniteNumber(item.price ?? item.avg_price ?? item.evidence?.avg_price);
}

function scoreFromItem(item = {}) {
  if (item.score != null && item.score !== "—") {
    const asNumber = parseFiniteNumber(item.scoreValue ?? item.score);
    if (asNumber != null) return formatScore(asNumber);
    return escapeHtml(String(item.score));
  }
  return formatScore(item.scoreValue);
}

function externalActionLink(href, label) {
  return `<a class="cm-market-action" href="${escapeAttribute(href)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)} <span aria-hidden="true">↗</span></a>`;
}

function renderMarketplaceOffer(item = {}) {
  const offer = item.representativeOffer || item.representative_offer || null;
  const listingHref = isSafeHttpsEbayListingUrl(offer?.listing_url || item.listingUrl);
  const shopHref = buildEbayShopSimilarUrl(item);
  const actions = [];
  if (listingHref) actions.push(externalActionLink(listingHref, "View on eBay"));
  if (shopHref) actions.push(externalActionLink(shopHref, "Shop Similar on eBay"));

  if (!offer) {
    return `
      <div class="cm-offer cm-offer--empty">
        ${actions.length ? `<div class="cm-actions">${actions.join("")}</div>` : ""}
      </div>`;
  }

  const title = String(offer.title || "").trim();
  const price = parseFiniteNumber(offer.price);
  const condition = String(offer.condition || "").trim();
  const sourceLabel = marketplaceSourceLabel(offer.source || item.source);
  const rows = [];
  if (title) rows.push(`<p class="cm-offer-title">${escapeHtml(title)}</p>`);
  if (price != null) {
    rows.push(`<p class="cm-offer-price">${escapeHtml(formatUsd(price))}</p>`);
  }
  if (condition) {
    rows.push(`<p class="cm-offer-condition">Condition: ${escapeHtml(condition)}</p>`);
  }
  if (sourceLabel) {
    rows.push(`<p class="cm-offer-source">Source: ${escapeHtml(sourceLabel)}</p>`);
  }

  return `
    <section class="cm-offer" aria-label="Representative listing">
      <h3 class="cm-section-title">Representative listing</h3>
      ${rows.join("") || `<p class="cm-offer-empty">Representative listing unavailable.</p>`}
      ${actions.length ? `<div class="cm-actions">${actions.join("")}</div>` : ""}
    </section>`;
}

function renderCardMarketPanel(item = {}) {
  const playerName = String(item.playerName || item.player_name || "Player").trim() || "Player";
  const cardLabel = String(item.cardLabel || item.card_label || "").trim();
  const avgPrice = avgPriceFromItem(item);
  const listingsCount = listingsCountFromItem(item);
  const scoreHtml = scoreFromItem(item);

  const snapshot = listingsCount != null
    ? `<section class="cm-snapshot" aria-label="Market snapshot">
        <h3 class="cm-section-title">Market snapshot</h3>
        <p class="cm-snapshot-copy">${escapeHtml(String(listingsCount))} active listing${listingsCount === 1 ? "" : "s"}</p>
      </section>`
    : "";

  return `
    <div class="cm-panel">
      ${renderHeroImage(item)}
      <div class="cm-stats">
        ${renderStat("CARDSIGNAL", scoreHtml)}
        ${renderStat("Avg. active listing", escapeHtml(formatUsd(avgPrice)))}
      </div>
      ${snapshot}
      ${renderMarketplaceOffer(item)}
      <p class="cm-disclaimer">${escapeHtml(CARD_MARKET_DISCLAIMER)}</p>
    </div>`;
}

function renderCardMarketHeader(item = {}) {
  const playerName = String(item.playerName || item.player_name || "Player").trim() || "Player";
  const cardLabel = String(item.cardLabel || item.card_label || "").trim();
  return `
    <div class="cm-header-main">
      <div class="cm-header-copy">
        <p class="eyebrow pi-modal-kicker">Card Market</p>
        <h2 class="pi-modal-title cm-modal-title" id="${CARD_MARKET_TITLE_ID}">${escapeHtml(playerName)}</h2>
        ${cardLabel ? `<p class="cm-card-label">${escapeHtml(cardLabel)}</p>` : ""}
      </div>
      <button type="button" class="pi-modal-close cm-modal-close" data-cm-close aria-label="Close Card Market">✕</button>
    </div>`;
}

function close() {
  const modal = getModal();
  if (!modal) return;
  modal.classList.add("hidden");
  modal.setAttribute("aria-hidden", "true");
  unlockBodyScroll();
  if (cardMarketLastTrigger && typeof cardMarketLastTrigger.focus === "function") {
    try {
      cardMarketLastTrigger.focus();
    } catch (_) {
      // ignore
    }
  }
  cardMarketLastTrigger = null;
}

function open(item = {}, options = {}) {
  const modal = getModal();
  const header = typeof document !== "undefined" ? document.getElementById("cm-modal-header") : null;
  const body = typeof document !== "undefined" ? document.getElementById("cm-modal-body") : null;
  if (!modal || !header || !body) return false;

  if (typeof closePlayerIntelligenceModal === "function") {
    closePlayerIntelligenceModal();
  }

  cardMarketLastTrigger = options.trigger || null;
  header.innerHTML = renderCardMarketHeader(item);
  body.innerHTML = renderCardMarketPanel(item);

  modal.classList.remove("hidden");
  modal.setAttribute("aria-hidden", "false");
  lockBodyScroll();

  if (typeof requestAnimationFrame === "function") {
    requestAnimationFrame(() => {
      modal.querySelector(".cm-modal-close")?.focus();
    });
  } else {
    modal.querySelector?.(".cm-modal-close")?.focus?.();
  }
  return true;
}

function catalogIndexFromRow(row) {
  if (!row) return null;
  const raw = typeof row.getAttribute === "function"
    ? row.getAttribute("data-card-market-index")
    : (row.dataset && row.dataset.cardMarketIndex);
  if (raw == null || raw === "") return null;
  const index = Number(raw);
  return Number.isInteger(index) ? index : null;
}

function itemFromEvent(event) {
  const target = event?.target;
  if (!target || typeof target.closest !== "function") return { item: null, row: null };
  const row = target.closest("[data-card-market-index]");
  const index = catalogIndexFromRow(row);
  if (index == null) return { item: null, row };
  return { item: cardMarketCatalog[index] || null, row };
}

function onSectionClick(event) {
  const { item, row } = itemFromEvent(event);
  if (!item) return;
  if (typeof event.preventDefault === "function") event.preventDefault();
  open(item, { trigger: row });
}

function onSectionKeydown(event) {
  if (event.key !== "Enter" && event.key !== " ") return;
  const { item, row } = itemFromEvent(event);
  if (!item) return;
  if (typeof event.preventDefault === "function") event.preventDefault();
  open(item, { trigger: row });
}

function onDocumentKeydown(event) {
  if (event.key !== "Escape" || !isOpen()) return;
  if (typeof event.preventDefault === "function") event.preventDefault();
  close();
}

function onModalClick(event) {
  const target = event?.target;
  if (!target || typeof target.closest !== "function") return;
  if (!target.closest("[data-cm-close]")) return;
  if (typeof event.preventDefault === "function") event.preventDefault();
  close();
}

function bindSection(root) {
  if (!root || typeof root.addEventListener !== "function") return;
  if (root.dataset && root.dataset.cmBound === "1") return;
  if (root.dataset) root.dataset.cmBound = "1";
  root.addEventListener("click", onSectionClick);
  root.addEventListener("keydown", onSectionKeydown);
}

function setup() {
  const modal = getModal();
  if (modal && modal.dataset && modal.dataset.cmBound !== "1") {
    modal.dataset.cmBound = "1";
    if (typeof modal.addEventListener === "function") {
      modal.addEventListener("click", onModalClick);
    }
  }
  if (!cardMarketKeydownBound && typeof document !== "undefined" && typeof document.addEventListener === "function") {
    document.addEventListener("keydown", onDocumentKeydown);
    cardMarketKeydownBound = true;
  }
}

const CardMarket = {
  CARD_MARKET_DISCLAIMER,
  CARD_MARKET_TITLE_ID,
  EBAY_SEARCH_BASE,
  escapeHtml,
  escapeAttribute,
  marketplaceSourceLabel,
  humanizeQueryName,
  categoryFromIntelItem,
  isSafeHttpImageUrl,
  isSafeHttpsEbayListingUrl,
  buildEbayShopSimilarUrl,
  setCatalog,
  getCatalog,
  renderHeroImage,
  renderMarketplaceOffer,
  renderCardMarketHeader,
  renderCardMarketPanel,
  open,
  close,
  isOpen,
  setup,
  bindSection,
  onSectionClick,
  onSectionKeydown,
  onDocumentKeydown,
  onModalClick,
};

if (typeof window !== "undefined") {
  window.CardMarket = CardMarket;
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = CardMarket;
}
