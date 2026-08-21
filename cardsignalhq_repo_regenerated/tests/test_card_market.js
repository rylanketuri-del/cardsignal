#!/usr/bin/env node
/**
 * Card Market panel: row interaction, representative offer, outbound eBay links.
 * Run: node tests/test_card_market.js
 */
const assert = require("assert");
const fs = require("fs");
const path = require("path");

global.window = global;
global.localStorage = {
  getItem() {
    return null;
  },
  setItem() {},
  removeItem() {},
};

require(path.join(__dirname, "..", "frontend", "scouting-report-metrics.js"));
require(path.join(__dirname, "..", "frontend", "scouting-report-nfl.js"));
require(path.join(__dirname, "..", "frontend", "scouting-report-nba.js"));
require(path.join(__dirname, "..", "frontend", "scouting-report-intel.js"));

const capabilityState = require(path.join(__dirname, "..", "frontend", "capability-state.js"));
global.capabilityStatusCopy = capabilityState.capabilityStatusCopy;
global.deriveSupportedEvidenceQuality = capabilityState.deriveSupportedEvidenceQuality;
global.getCapabilityState = capabilityState.getCapabilityState;

require(path.join(__dirname, "..", "frontend", "weekly-movement.js"));
const WC = require(path.join(__dirname, "..", "frontend", "weekly-convergence.js"));
const CardMarket = require(path.join(__dirname, "..", "frontend", "card-market.js"));
const {
  weeklyCardRowToIntelItem,
  renderCardIntelRow,
  renderCardSection,
  renderScoutingReport,
  closePlayerIntelligenceModal,
  isPlayerIntelligenceModalOpen,
  bindPiModalKeydown,
} = require(path.join(__dirname, "..", "frontend", "app.js"));

let passed = 0;
let failed = 0;

function test(name, fn) {
  try {
    fn();
    passed += 1;
    console.log(`  ok ${name}`);
  } catch (err) {
    failed += 1;
    console.error(`  FAIL ${name}`);
    console.error(`       ${err.message}`);
  }
}

const altuveLegacy = {
  player_name: "Jose Altuve",
  card_label: "Autographs",
  score: 100.0,
  recommendation: "BUY",
  demand_score: 100.0,
  momentum_score: 1.41,
  market_activity_score: 100.0,
  movement: 100.0,
  evidence: { listings_count: 50, avg_price: 141.29 },
};

const ohtaniLegacy = {
  player_name: "Shohei Ohtani",
  card_label: "Bowman Chrome",
  score: 96.0,
  demand_score: 92.0,
  momentum_score: 51.14,
  market_activity_score: 100.0,
  movement: 51.14,
  evidence: { avg_price: 5114.40 },
};

const stewartLegacy = {
  player_name: "Sal Stewart",
  card_label: "PSA 10",
  score: 100.0,
  demand_score: 100,
  movement: 100,
  evidence: { avg_price: 3783.63 },
};

const altuveMarket = {
  player_name: "Jose Altuve",
  card_label: "Autographs",
  score: 100.0,
  recommendation: "BUY",
  demand_score: 100.0,
  evidence: {
    query_name: "auto",
    listings_count: 43,
    avg_price: 304.86,
    representative_offer: {
      source: "ebay",
      external_id: "v1|altuve|0",
      title: "Jose Altuve Autograph Baseball Card",
      image_url: "https://i.ebayimg.com/images/g/altuve/s-l1600.jpg",
      price: 88.0,
      currency: "USD",
      condition: "Ungraded",
      listing_url: "https://www.ebay.com/itm/altuve",
      query_name: "auto",
    },
  },
};

const genuineMover = {
  player_name: "Future Player",
  card_label: "Autographs",
  score: 80,
  movement: 12.34,
  movement_is_historical: true,
  evidence: {
    avg_price: 40,
    listings_count: 12,
    representative_offer: {
      source: "ebay",
      title: "Future Player Autograph",
      image_url: "https://i.ebayimg.com/images/g/future/s-l1600.jpg",
      price: 39.0,
      currency: "USD",
      condition: "Used",
      listing_url: "https://www.ebay.com/itm/future",
      query_name: "auto",
    },
  },
};

const populatedW34CardIntel = {
  trending_cards: [altuveLegacy],
  biggest_movers: [ohtaniLegacy, stewartLegacy],
  buy_low_watch: [altuveLegacy],
  most_chased: [altuveLegacy],
};

function createClassList(initial = "") {
  const set = new Set(String(initial).split(/\s+/).filter(Boolean));
  const api = {
    add(name) { set.add(name); },
    remove(name) { set.delete(name); },
    contains(name) { return set.has(name); },
    toggle(name, force) {
      if (force === true) set.add(name);
      else if (force === false) set.delete(name);
      else if (set.has(name)) set.delete(name);
      else set.add(name);
    },
  };
  return api;
}

function setupCardMarketDom() {
  const listeners = { click: [], keydown: [], documentKeydown: [] };
  const grid = {
    innerHTML: "",
    dataset: {},
    addEventListener(type, fn) {
      listeners[type] = listeners[type] || [];
      listeners[type].push(fn);
    },
  };
  const header = { innerHTML: "" };
  const body = { innerHTML: "" };
  const closeBtn = { focus() { closeBtn.focused = true; } };
  const modal = {
    className: "pi-modal cm-modal hidden",
    classList: createClassList("pi-modal cm-modal hidden"),
    dataset: {},
    attributes: { "aria-hidden": "true" },
    setAttribute(name, value) { this.attributes[name] = value; },
    getAttribute(name) { return this.attributes[name]; },
    addEventListener(type, fn) {
      listeners[`modal-${type}`] = listeners[`modal-${type}`] || [];
      listeners[`modal-${type}`].push(fn);
    },
    querySelector(sel) {
      if (String(sel).includes("cm-modal-close")) return closeBtn;
      return null;
    },
  };
  const piModal = {
    className: "pi-modal hidden",
    classList: createClassList("pi-modal hidden"),
    dataset: { piBound: "1" },
    attributes: { "aria-hidden": "true" },
    setAttribute(name, value) { this.attributes[name] = value; },
    innerHTML: '<header id="pi-modal-header"></header><div id="pi-modal-body"></div>',
  };
  const bodyEl = { classList: createClassList() };
  global.document = {
    getElementById(id) {
      if (id === "quick-intelligence-grid" || id === "card-section-grid") return grid;
      if (id === "card-market-modal") return modal;
      if (id === "cm-modal-header") return header;
      if (id === "cm-modal-body") return body;
      if (id === "player-intelligence-modal") return piModal;
      if (id === "pi-modal-header") return { innerHTML: "" };
      if (id === "pi-modal-body") return { innerHTML: "" };
      return null;
    },
    body: bodyEl,
    addEventListener(type, fn) {
      if (type === "keydown") listeners.documentKeydown.push(fn);
    },
  };
  CardMarket.setup();
  return { grid, modal, header, body, listeners, closeBtn, piModal, bodyEl };
}

function sectionHtml(html, modifier) {
  const match = html.match(
    new RegExp(`<article class="qi-card qi-card--${modifier}[\\s\\S]*?</article>`),
  );
  return match ? match[0] : "";
}

function clickCatalogIndex(listeners, index) {
  const event = {
    preventDefault() { event.prevented = true; },
    target: {
      closest(sel) {
        if (String(sel).includes("data-card-market-index")) {
          return {
            getAttribute: (name) => (name === "data-card-market-index" ? String(index) : null),
            dataset: { cardMarketIndex: String(index) },
            focus() { this.focused = true; },
          };
        }
        return null;
      },
    },
  };
  (listeners.click || []).forEach((fn) => fn(event));
  return event;
}

function keyCatalogIndex(listeners, index, key) {
  const event = {
    key,
    preventDefault() { event.prevented = true; },
    target: {
      closest(sel) {
        if (String(sel).includes("data-card-market-index")) {
          return {
            getAttribute: () => String(index),
            dataset: { cardMarketIndex: String(index) },
            focus() {},
          };
        }
        return null;
      },
    },
  };
  (listeners.keydown || []).forEach((fn) => fn(event));
  return event;
}

function expectedShopSimilar(playerName, category) {
  const url = new URL(CardMarket.EBAY_SEARCH_BASE);
  url.searchParams.set("_nkw", `${playerName} ${category} baseball card`);
  return url.toString();
}

console.log("Card Market tests");

test("clicking a Trending card opens Card Market", () => {
  const { grid, modal, body, listeners } = setupCardMarketDom();
  renderCardSection([], {
    trending_cards: [altuveMarket],
    biggest_movers: [],
    buy_low_watch: [],
    most_chased: [],
  }, { run: { status: "COMPLETED" } });
  assert.ok(sectionHtml(grid.innerHTML, "trending").includes("qi-row--market"));
  clickCatalogIndex(listeners, 0);
  assert.strictEqual(modal.classList.contains("hidden"), false);
  assert.ok(body.innerHTML.includes("Jose Altuve Autograph Baseball Card"));
  assert.ok(body.innerHTML.includes("Avg. active listing"));
});

test("clicking a Buy Low card opens Card Market", () => {
  const { grid, modal, header, listeners } = setupCardMarketDom();
  renderCardSection([], {
    trending_cards: [],
    biggest_movers: [],
    buy_low_watch: [altuveMarket],
    most_chased: [],
  }, { run: { status: "COMPLETED" } });
  assert.ok(sectionHtml(grid.innerHTML, "buy-low").includes("Jose Altuve"));
  clickCatalogIndex(listeners, 0);
  assert.strictEqual(modal.classList.contains("hidden"), false);
  assert.ok(header.innerHTML.includes("Jose Altuve"));
  assert.ok(header.innerHTML.includes("Autographs"));
});

test("clicking a Most Chased card opens Card Market", () => {
  const { modal, body, listeners } = setupCardMarketDom();
  renderCardSection([], {
    trending_cards: [],
    biggest_movers: [],
    buy_low_watch: [],
    most_chased: [altuveMarket],
  }, { run: { status: "COMPLETED" } });
  clickCatalogIndex(listeners, 0);
  assert.strictEqual(modal.classList.contains("hidden"), false);
  assert.ok(body.innerHTML.includes("43 active listings"));
});

test("a genuine future Biggest Mover can open Card Market", () => {
  const { grid, modal, header, listeners } = setupCardMarketDom();
  renderCardSection([], {
    trending_cards: [altuveMarket],
    biggest_movers: [ohtaniLegacy, genuineMover],
    buy_low_watch: [altuveMarket],
    most_chased: [altuveMarket],
  }, { run: { status: "COMPLETED" } });
  const movers = sectionHtml(grid.innerHTML, "movers");
  assert.ok(movers.includes("Future Player · Autographs"));
  assert.ok(!movers.includes("Shohei Ohtani"));
  clickCatalogIndex(listeners, 1);
  assert.strictEqual(modal.classList.contains("hidden"), false);
  assert.ok(header.innerHTML.includes("Future Player"));
});

test("legacy fake Biggest Movers remain filtered", () => {
  const { grid, listeners, modal } = setupCardMarketDom();
  renderCardSection([], populatedW34CardIntel, { run: { status: "COMPLETED" } });
  const movers = sectionHtml(grid.innerHTML, "movers");
  assert.ok(movers.includes("qi-card--pending"));
  assert.ok(!movers.includes("qi-row-name"));
  clickCatalogIndex(listeners, 99);
  assert.ok(modal.classList.contains("hidden"));
});

test("representative image appears in modal", () => {
  const item = weeklyCardRowToIntelItem(altuveMarket);
  const html = CardMarket.renderCardMarketPanel(item);
  assert.ok(html.includes("cm-hero-image-img"));
  assert.ok(html.includes("https://i.ebayimg.com/images/g/altuve/s-l1600.jpg"));
  assert.ok(html.includes("object-fit") || html.includes("cm-hero-image-img"));
});

test("missing image uses placeholder", () => {
  const item = weeklyCardRowToIntelItem({
    player_name: "Jose Altuve",
    card_label: "Autographs",
    score: 80,
    evidence: { avg_price: 20, representative_offer: { source: "ebay", image_url: "" } },
  });
  const html = CardMarket.renderCardMarketPanel(item);
  assert.ok(html.includes("cm-hero-image"));
  assert.ok(!html.includes("<img"));
});

test("javascript image URL uses placeholder", () => {
  const html = CardMarket.renderHeroImage({
    name: "Trap",
    imageUrl: "javascript:alert(1)",
  });
  assert.ok(!html.includes("<img"));
  assert.ok(!html.toLowerCase().includes("javascript:"));
});

test("CardSignal score is shown without %", () => {
  const html = CardMarket.renderCardMarketPanel(weeklyCardRowToIntelItem(altuveMarket));
  assert.ok(html.includes("CARDSIGNAL"));
  assert.ok(html.includes("100.0"));
  assert.ok(!html.includes("100.0%"));
  assert.ok(!html.includes("100%"));
});

test("avg listing uses currency formatting", () => {
  const html = CardMarket.renderCardMarketPanel(weeklyCardRowToIntelItem(altuveMarket));
  assert.ok(html.includes("Avg. active listing"));
  assert.ok(html.includes("$304.86"));
  assert.ok(!html.includes("sale price"));
  assert.ok(!html.includes("sold price"));
});

test("listings_count is labeled as active listings, not sales", () => {
  const html = CardMarket.renderCardMarketPanel(weeklyCardRowToIntelItem(altuveMarket));
  assert.ok(html.includes("43 active listings"));
  assert.ok(html.toLowerCase().includes("market snapshot"));
  assert.ok(!html.toLowerCase().includes("sales"));
  assert.ok(!html.toLowerCase().includes("sold"));
});

test("representative price is distinct from avg listing price", () => {
  const html = CardMarket.renderCardMarketPanel(weeklyCardRowToIntelItem(altuveMarket));
  assert.ok(html.includes("$304.86"));
  assert.ok(html.includes("$88.00"));
  assert.notStrictEqual("$304.86", "$88.00");
  assert.ok(html.includes("Representative listing"));
});

test("valid eBay listing_url creates View on eBay", () => {
  const html = CardMarket.renderMarketplaceOffer(weeklyCardRowToIntelItem(altuveMarket));
  assert.ok(html.includes("View on eBay"));
  assert.ok(html.includes('href="https://www.ebay.com/itm/altuve"'));
  assert.ok(html.includes('target="_blank"'));
  assert.ok(html.includes('rel="noopener noreferrer"'));
});

test("missing listing_url does not break modal", () => {
  const row = {
    player_name: "Jose Altuve",
    card_label: "Autographs",
    score: 100,
    evidence: {
      listings_count: 43,
      avg_price: 304.86,
      representative_offer: {
        source: "ebay",
        title: "Jose Altuve Autograph",
        image_url: "https://i.ebayimg.com/images/g/altuve/s-l1600.jpg",
        price: 88,
        condition: "Ungraded",
        listing_url: "",
        query_name: "auto",
      },
    },
  };
  const html = CardMarket.renderCardMarketPanel(weeklyCardRowToIntelItem(row));
  assert.ok(html.includes("Jose Altuve Autograph"));
  assert.ok(!html.includes("View on eBay"));
  assert.ok(html.includes("Shop Similar on eBay"));
  const { modal, body, listeners } = setupCardMarketDom();
  renderCardSection([], {
    trending_cards: [row],
    biggest_movers: [],
    buy_low_watch: [],
    most_chased: [],
  }, { run: { status: "COMPLETED" } });
  clickCatalogIndex(listeners, 0);
  assert.strictEqual(modal.classList.contains("hidden"), false);
  assert.ok(body.innerHTML.includes("Shop Similar on eBay"));
});

test("invalid and javascript listing URLs are rejected", () => {
  const bad = [
    "javascript:alert(1)",
    "data:text/html,hi",
    "http://www.ebay.com/itm/1",
    "https://evil.example/itm/1",
    "https://www.ebay.com.evil.com/itm/1",
    "https://notebay.com/itm/1",
    "https://ebay.com.attacker.test/itm/1",
  ];
  for (const listing_url of bad) {
    assert.strictEqual(CardMarket.isSafeHttpsEbayListingUrl(listing_url), null, listing_url);
    const html = CardMarket.renderMarketplaceOffer({
      playerName: "Jose Altuve",
      cardLabel: "Autographs",
      representativeOffer: { source: "ebay", listing_url, title: "x" },
    });
    assert.ok(!html.includes("View on eBay"), listing_url);
    assert.ok(!html.toLowerCase().includes("javascript:"), listing_url);
    assert.ok(!html.includes('href="http://www.ebay.com'), listing_url);
  }
  assert.ok(CardMarket.isSafeHttpsEbayListingUrl("https://www.ebay.com/itm/1"));
  assert.ok(CardMarket.isSafeHttpsEbayListingUrl("https://ebay.com/itm/1"));
});

test("Shop Similar generates encoded eBay search URL from player + category", () => {
  const item = weeklyCardRowToIntelItem(altuveMarket);
  const href = CardMarket.buildEbayShopSimilarUrl(item);
  assert.strictEqual(href, expectedShopSimilar("Jose Altuve", "Autographs"));
  assert.ok(href.startsWith("https://www.ebay.com/sch/i.html?"));
  assert.ok(href.includes("_nkw="));
  assert.ok(href.includes("Jose"));
  assert.ok(href.includes("Altuve"));
  assert.ok(href.includes("Autographs"));
  assert.ok(href.includes("baseball"));
  const ohtani = weeklyCardRowToIntelItem({
    player_name: "Shohei Ohtani",
    card_label: "Bowman Chrome",
    evidence: { query_name: "bowman_chrome" },
  });
  assert.strictEqual(
    CardMarket.buildEbayShopSimilarUrl(ohtani),
    expectedShopSimilar("Shohei Ohtani", "Bowman Chrome"),
  );
  const vazquez = CardMarket.buildEbayShopSimilarUrl({
    playerName: "Christian Vázquez",
    cardLabel: "PSA 10",
  });
  assert.strictEqual(vazquez, expectedShopSimilar("Christian Vázquez", "PSA 10"));
  assert.ok(!vazquez.includes(" "));
  const html = CardMarket.renderMarketplaceOffer(item);
  assert.ok(html.includes("Shop Similar on eBay"));
  assert.ok(html.includes(href.replace(/&/g, "&amp;")) || html.includes(href));
});

test("external links use target=_blank + rel=noopener noreferrer", () => {
  const html = CardMarket.renderMarketplaceOffer(weeklyCardRowToIntelItem(altuveMarket));
  const anchors = html.match(/<a\s[^>]+>/g) || [];
  assert.ok(anchors.length >= 2);
  for (const tag of anchors) {
    assert.ok(tag.includes('target="_blank"'), tag);
    assert.ok(tag.includes('rel="noopener noreferrer"'), tag);
  }
});

test("Escape closes Card Market", () => {
  const { modal, listeners } = setupCardMarketDom();
  const opened = CardMarket.open(weeklyCardRowToIntelItem(altuveMarket));
  assert.strictEqual(opened, true);
  assert.strictEqual(modal.classList.contains("hidden"), false);
  CardMarket.onDocumentKeydown({ key: "Escape", preventDefault() {} });
  assert.ok(modal.classList.contains("hidden"));
  assert.strictEqual(modal.getAttribute("aria-hidden"), "true");
  listeners.documentKeydown.forEach((fn) => {
    CardMarket.open(weeklyCardRowToIntelItem(altuveMarket));
    fn({ key: "Escape", preventDefault() {} });
  });
  assert.ok(modal.classList.contains("hidden"));
});

test("keyboard activation works", () => {
  const { modal, header, listeners } = setupCardMarketDom();
  renderCardSection([], {
    trending_cards: [altuveMarket],
    biggest_movers: [],
    buy_low_watch: [],
    most_chased: [],
  }, { run: { status: "COMPLETED" } });
  const rowHtml = renderCardIntelRow(weeklyCardRowToIntelItem(altuveMarket), 0);
  assert.ok(rowHtml.includes('role="button"'));
  assert.ok(rowHtml.includes('tabindex="0"'));
  assert.ok(!rowHtml.includes("<button"));
  keyCatalogIndex(listeners, 0, "Enter");
  assert.strictEqual(modal.classList.contains("hidden"), false);
  assert.ok(header.innerHTML.includes("Jose Altuve"));
  CardMarket.close();
  keyCatalogIndex(listeners, 0, " ");
  assert.strictEqual(modal.classList.contains("hidden"), false);
});

test("existing Scouting Report modal still works", () => {
  const index = fs.readFileSync(path.join(__dirname, "..", "frontend", "index.html"), "utf8");
  assert.ok(index.includes('id="player-intelligence-modal"'));
  assert.ok(index.includes("data-pi-close"));
  assert.ok(index.includes('id="card-market-modal"'));
  assert.ok(index.includes("data-cm-close"));
  const cardMarketPos = index.indexOf("./card-market.js");
  const appPos = index.indexOf("./app.js");
  assert.ok(cardMarketPos >= 0 && appPos > cardMarketPos);
  const entry = {
    player_name: "Jose Altuve",
    position: "2B",
    team: "HOU",
    hotness: { total_score: 80, performance_score: 70, market_score: 75, tag: "WATCH" },
  };
  const html = renderScoutingReport(entry, {
    score: 80,
    recommendation: "WATCH",
    conviction: "Medium",
    risk: "Low",
    time_horizon: "2-4 weeks",
    drivers: [],
  }, [], null);
  assert.ok(typeof html === "string" && html.length > 0);
  assert.strictEqual(typeof closePlayerIntelligenceModal, "function");
  assert.strictEqual(typeof isPlayerIntelligenceModalOpen, "function");
  assert.strictEqual(typeof bindPiModalKeydown, "function");
  const appSrc = fs.readFileSync(path.join(__dirname, "..", "frontend", "app.js"), "utf8");
  assert.ok(appSrc.includes("openPlayerIntelligenceModal"));
  assert.ok(appSrc.includes("CardMarket.isOpen()"));
  assert.ok(appSrc.includes("closePlayerIntelligenceModal"));
});

test("current W34 Biggest Movers pending behavior remains unchanged", () => {
  const { grid } = setupCardMarketDom();
  renderCardSection([], populatedW34CardIntel, { run: { status: "COMPLETED" }, card_intelligence: populatedW34CardIntel });
  const movers = sectionHtml(grid.innerHTML, "movers");
  assert.ok(movers.includes("Weekly movement will appear after the next completed weekly snapshot."));
  assert.ok(!movers.includes("Shohei Ohtani"));
  assert.ok(!movers.includes("Sal Stewart"));
  assert.ok(sectionHtml(grid.innerHTML, "trending").includes("Jose Altuve · Autographs"));
});

test("listing title is escaped and not injected as HTML", () => {
  const html = CardMarket.renderMarketplaceOffer({
    playerName: "Jose Altuve",
    cardLabel: "Autographs",
    representativeOffer: {
      source: "ebay",
      title: `<img src=x onerror="alert(1)">`,
      listing_url: `https://www.ebay.com/itm/1" onclick="alert(1)`,
    },
  });
  assert.ok(html.includes("&lt;img"));
  assert.ok(!html.includes("<img src=x"));
  assert.ok(!html.includes("onerror=\"alert(1)\""));
  const href = CardMarket.isSafeHttpsEbayListingUrl(`https://www.ebay.com/itm/1" onclick="alert(1)`);
  assert.ok(href);
  assert.ok(html.includes("&quot;") || html.includes(CardMarket.escapeAttribute(href)));
});

test("intel item exposes existing market fields without new backend keys", () => {
  const item = weeklyCardRowToIntelItem(altuveMarket);
  assert.strictEqual(item.playerName, "Jose Altuve");
  assert.strictEqual(item.cardLabel, "Autographs");
  assert.strictEqual(item.listingsCount, 43);
  assert.strictEqual(item.price, 304.86);
  assert.strictEqual(item.listingUrl, "https://www.ebay.com/itm/altuve");
  assert.strictEqual(item.representativeOffer.title, "Jose Altuve Autograph Baseball Card");
  assert.strictEqual(item.representativeOffer.price, 88.0);
  assert.strictEqual(item.representativeOffer.condition, "Ungraded");
  assert.strictEqual(item.queryName, "auto");
  assert.strictEqual(item.source, "ebay");
});

test("clickable rows do not nest buttons around the score pill", () => {
  const html = renderCardIntelRow(weeklyCardRowToIntelItem(altuveMarket), 0);
  assert.ok(html.includes("qi-score-pill"));
  assert.ok(html.includes("qi-row-chevron"));
  assert.ok(!html.includes("<button"));
  assert.ok(html.includes('role="button"'));
});

test("disclaimer is present and does not imply CardSignal sells the card", () => {
  const html = CardMarket.renderCardMarketPanel(weeklyCardRowToIntelItem(altuveMarket));
  assert.ok(html.includes(CardMarket.CARD_MARKET_DISCLAIMER));
  assert.ok(!html.toLowerCase().includes("buy now from cardsignal"));
  assert.ok(!html.toLowerCase().includes("cardsignal sells"));
});

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
