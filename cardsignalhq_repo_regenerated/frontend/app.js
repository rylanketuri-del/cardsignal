const API_BASE_URL = (window.APP_CONFIG && window.APP_CONFIG.API_BASE_URL) || "https://cardsignal-api.onrender.com";

const SOURCE_URL = `${API_BASE_URL}/api/leaderboard/latest`;

let supabaseClient = null;
let authToken = null;
let currentUser = null;
let latestEntries = [];
let selectedPlayer = null;
let watchlistItems = [];
let playerAlertRules = [];
let notifications = [];
let adminToken = localStorage.getItem('cardchase_admin_token') || '';
let scoreChart = null;
let leaderboardHistoryChart = null;

function tagClass(tag) {
  if (tag === 'BUY LOW') return 'tag buylow';
  return `tag ${String(tag || '').toLowerCase().replace(/\s+/g, '-')}`;
}
function formatScore(value) { return typeof value === 'number' ? value.toFixed(1) : '—'; }
function formatTimestamp(value) { return value ? new Date(value).toLocaleString() : '—'; }
function formatEventLabel(eventType) {
  const map = { hotness_jump: 'HOTNESS JUMP', buy_low: 'BUY LOW', most_chased: 'MOST CHASED', daily_digest: 'DAILY DIGEST' };
  return map[eventType] || String(eventType || 'ALERT').replace(/_/g, ' ').toUpperCase();
}
function toDatetimeLocal(value) {
  if (!value) return '';
  const d = new Date(value); if (Number.isNaN(d.getTime())) return '';
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
function findRule(playerName) { return playerAlertRules.find(item => item.player_name === playerName) || null; }
function renderRuleSummary(rule) {
  if (!rule) return '<span class="rule-chip">Default alerts</span>';
  const parts = [];
  if (rule.alert_on_hotness_jump) parts.push(`jump ≥ ${rule.min_hotness_delta}`);
  if (rule.alert_on_buy_low) parts.push('buy low');
  if (rule.alert_on_most_chased) parts.push('most chased');
  if (rule.muted_until) parts.push(`muted until ${new Date(rule.muted_until).toLocaleString()}`);
  return `<span class="rule-chip">${parts.join(' • ') || 'custom rule'}</span>`;
}

async function apiFetch(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (authToken) headers.Authorization = `Bearer ${authToken}`;
  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
  if (!response.ok) throw new Error(await response.text() || `Request failed for ${path}`);
  return response.json();
}
async function adminFetch(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (adminToken) headers.Authorization = `Bearer ${adminToken}`;
  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
  if (!response.ok) throw new Error(await response.text() || `Admin request failed for ${path}`);
  return response.json();
}
async function fetchPlayer(playerId) { return apiFetch(`/api/players/${playerId}`); }
async function fetchPlayerHistory(playerId) { return apiFetch(`/api/players/${playerId}/history?limit=14`); }
async function fetchLeaderboardHistory() { return apiFetch('/api/history/leaderboard?limit=10'); }
async function fetchPlayerSearch(query) {
  const response = await fetch(`${API_BASE_URL}/api/players/search?q=${encodeURIComponent(query)}`);
  if (!response.ok) return [];
  const data = await response.json();
  return Array.isArray(data) ? data : (data.items || []);
}

function setAuthStatus(message, isError = false) {
  const root = document.getElementById('auth-status');
  root.textContent = message;
  root.style.color = isError ? '#ff9c9c' : '#c9f27b';
}
function setAdminStatus(message, isError = false) {
  const root = document.getElementById('admin-status');
  root.textContent = message;
  root.style.color = isError ? '#ff9c9c' : '#c9f27b';
}

function getHeatLabel(score = 0) {
  if (score >= 95) return "On Fire";
  if (score >= 80) return "Very Hot";
  if (score >= 60) return "Hot";
  if (score >= 40) return "Warming";
  return "Cold";
}

function getHeatClass(score = 0) {
  if (score >= 95) return "heat-fire";
  if (score >= 80) return "heat-red";
  if (score >= 60) return "heat-orange";
  if (score >= 40) return "heat-yellow";
  return "heat-cold";
}

function getPlayerInitials(playerName = "?") {
  return String(playerName)
    .split(" ")
    .map(part => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function getTeamAbbrev(entry = {}) {
  return entry.team || entry.team_abbrev || entry.mlb_team || "MLB";
}

function getSportIcon(entry = {}) {
  const sport = String(entry.sport || "MLB").toUpperCase();

  if (sport === "NFL") return "🏈";
  if (sport === "NBA") return "🏀";
  if (sport === "NHL") return "🏒";
  return "⚾";
}

function renderTeamLogoMarkup(entry = {}) {
  const team = getTeamAbbrev(entry);
  if (entry.team_logo_url) {
    return `<img src="${entry.team_logo_url}" alt="${team}" loading="lazy" class="team-logo-image" />`;
  }
  return getSportIcon(entry);
}

function formatTeamPositionLabel(entry = {}) {
  const team = getTeamAbbrev(entry);
  const parts = [team];
  if (entry.position) parts.push(entry.position);
  return parts.join(" · ");
}

function renderLeaderHeadshot(entry = {}) {
  const initials = getPlayerInitials(entry.player_name);
  if (entry.headshot_url) {
    return `
      <span class="leader-photo">
        <img
          src="${entry.headshot_url}"
          alt="${entry.player_name}"
          loading="lazy"
          class="player-headshot-image"
          onerror="this.remove();this.parentElement.insertAdjacentHTML('beforeend','<span>${initials}</span>')"
        />
      </span>`;
  }
  return `<span class="leader-photo"><span>${initials}</span></span>`;
}

function renderPlayerHeadshot(entry = {}) {
  const initials = getPlayerInitials(entry.player_name);
  if (entry.headshot_url) {
    return `
      <div class="player-headshot-placeholder">
        <img
          src="${entry.headshot_url}"
          alt="${entry.player_name}"
          loading="lazy"
          class="player-headshot-image"
          onerror="this.remove();this.parentElement.insertAdjacentHTML('beforeend','<span>${initials}</span>')"
        />
      </div>`;
  }
  return `<div class="player-headshot-placeholder"><span>${initials}</span></div>`;
}

function buildLeaderboard(entries) {
  return `
    <section class="market-leaders-module sport-section sport-section--mlb" data-sport="mlb">
      <div class="market-leaders-header">
        <div>
          <p class="eyebrow">Live Signals</p>
          <h2>Today’s Leaders</h2>
          <p>Real-time player stat correlation — performance, market demand, and collector momentum.</p>
        </div>
      </div>

      <div class="market-leaders-table">
        <div class="leaders-table-head">
          <span>#</span>
          <span>Player</span>
          <span>Signal</span>
          <span>Performance</span>
          <span>Market</span>
          <span>Trend</span>
          <span>Report</span>
        </div>

        ${entries.map((entry, index) => {
          const score = entry.hotness?.total_score || 0;
          const performance = entry.hotness?.performance_score || 0;
          const market = entry.hotness?.market_score || 0;
          const tag = entry.hotness?.tag || getHeatLabel(score);
          const trend = score >= 60 ? "↑" : "↓";
          const trendClass = score >= 60 ? "trend-up" : "trend-down";
          const teamPosition = formatTeamPositionLabel(entry);

          return `
            <button class="leader-table-row" type="button" data-player-index="${index}">
              <span class="leader-rank-small">${entry.rank || index + 1}</span>

              <span class="leader-profile">
                ${renderLeaderHeadshot(entry)}

                <span>
                  <strong>${entry.player_name} <span>${teamPosition}</span></strong>
                  <em><span class="team-chip">${renderTeamLogoMarkup(entry)}</span> ${tag}</em>
                </span>
              </span>

              <span class="leader-number">${formatScore(score)}</span>
              <span>${formatScore(performance)}</span>
              <span>${formatScore(market)}</span>
              <span class="${trendClass}">${trend} ${Math.abs(score - performance).toFixed(1)}</span>
              <span class="leader-report-pill">View Report</span>
            </button>
          `;
        }).join("")}
      </div>
    </section>
  `;
}

function getCollectorGrade(score = 0) {
  if (score >= 90) return "A+";
  if (score >= 80) return "A";
  if (score >= 70) return "B+";
  if (score >= 60) return "B";
  if (score >= 50) return "C+";
  return "Watch";
}

function getMarketOutlook(score = 0, market = 0) {
  if (score >= 75 && market >= 70) return "Bullish";
  if (score >= 60 || market >= 65) return "Constructive";
  if (score >= 45) return "Neutral";
  return "Watchlist";
}

function buildCollectorInsight(entry) {
  const score = entry.hotness?.total_score || 0;
  const market = entry.hotness?.market_score || 0;
  const performance = entry.hotness?.performance_score || 0;
  const tag = entry.hotness?.tag || "WATCH";

  if (market >= 80 && performance >= 55) {
    return `${entry.player_name} is showing one of the stronger collector profiles on the board today. Market demand is leading the signal, while recent performance remains supportive enough to keep momentum intact. Premium parallels and graded cards should be watched closely if this demand holds.`;
  }

  if (market >= 75 && performance < 55) {
    return `${entry.player_name} is being driven primarily by collector demand rather than recent stat production. That can create opportunity, but it also means the signal may be more sensitive to short-term market swings. Treat this as a ${tag.toLowerCase()} profile until performance catches up.`;
  }

  if (performance >= 70 && market < 60) {
    return `${entry.player_name} has the kind of performance profile that can attract collectors quickly if the card market starts reacting. This is a potential early-watch candidate where stats may be moving before demand fully prices in.`;
  }

  if (score >= 60) {
    return `${entry.player_name} remains relevant on today’s CardSignal board with a balanced mix of performance and market activity. The signal is not overheated yet, but the profile is strong enough to keep on the collector radar.`;
  }

  return `${entry.player_name} is currently more of a watchlist candidate than an aggressive chase. The data shows some activity, but the collector signal needs either stronger performance or clearer market demand before moving higher.`;
}

function getCollectorGrade(score = 0) {
  if (score >= 90) return "A+";
  if (score >= 80) return "A";
  if (score >= 70) return "B+";
  if (score >= 60) return "B";
  if (score >= 50) return "C+";
  return "Watch";
}

function getMarketOutlook(score = 0, market = 0) {
  if (score >= 75 && market >= 70) return "Bullish";
  if (score >= 60 || market >= 65) return "Constructive";
  if (score >= 45) return "Neutral";
  return "Watchlist";
}

function buildCollectorInsight(entry) {
  const score = entry.hotness?.total_score || 0;
  const market = entry.hotness?.market_score || 0;
  const performance = entry.hotness?.performance_score || 0;
  const tag = entry.hotness?.tag || "WATCH";

  if (market >= 80 && performance >= 55) {
    return `${entry.player_name} is showing one of the stronger collector profiles on the board today. Market demand is leading the signal, while recent performance remains supportive enough to keep momentum intact. Premium parallels and graded cards should be watched closely if this demand holds.`;
  }

  if (market >= 75 && performance < 55) {
    return `${entry.player_name} is being driven primarily by collector demand rather than recent stat production. That can create opportunity, but it also means the signal may be more sensitive to short-term market swings. Treat this as a ${tag.toLowerCase()} profile until performance catches up.`;
  }

  if (performance >= 70 && market < 60) {
    return `${entry.player_name} has the kind of performance profile that can attract collectors quickly if the card market starts reacting. This is a potential early-watch candidate where stats may be moving before demand fully prices in.`;
  }

  if (score >= 60) {
    return `${entry.player_name} remains relevant on today’s CardSignal board with a balanced mix of performance and market activity. The signal is not overheated yet, but the profile is strong enough to keep on the collector radar.`;
  }

  return `${entry.player_name} is currently more of a watchlist candidate than an aggressive chase. The data shows some activity, but the collector signal needs either stronger performance or clearer market demand before moving higher.`;
}

const csIntelCache = new Map();
function csIntelSafeToNumber(value) {
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : null;
}
function csIntelClamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}
function csIntelHashToUint32(str = "") {
  let h = 2166136261;
  for (let i = 0; i < str.length; i += 1) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}
function csIntelMulberry32(seed) {
  let t = seed >>> 0;
  return function rng() {
    t += 0x6D2B79F5;
    let x = t;
    x = Math.imul(x ^ (x >>> 15), x | 1);
    x ^= x + Math.imul(x ^ (x >>> 7), x | 61);
    return ((x ^ (x >>> 14)) >>> 0) / 4294967296;
  };
}
function csIntelPickConfidenceTier(rng) {
  if (rng >= 0.66) return "HIGH";
  if (rng >= 0.33) return "MEDIUM";
  return "LOW";
}
function csIntelFormatPercent(value) {
  const n = csIntelSafeToNumber(value);
  if (n === null) return "—";
  const sign = n >= 0 ? "+" : "";
  return `${sign}${n.toFixed(1)}%`;
}
function csIntelFormatMoney(value) {
  const n = csIntelSafeToNumber(value);
  if (n === null) return "—";
  return `$${n.toFixed(2)}`;
}
function csIntelBetaPreviewBadge() {
  return `<span class="cs-beta-preview" title="Live market intelligence coming soon.">Beta Preview</span>`;
}

/* Signal Center — unified intelligence row (player report) */
function renderIntelRow(item, { metricLabel = "7-day", showThumb = true } = {}) {
  const thumb = showThumb
    ? `<div class="cs-intel-row-thumb" aria-hidden="true"></div>`
    : "";
  return `
    <div class="cs-intel-row">
      ${thumb}
      <div class="cs-intel-row-copy">
        <div class="cs-intel-row-title">${item.name}</div>
        <div class="cs-intel-row-sub">${csIntelFormatMoney(item.price)}</div>
      </div>
      <div class="cs-intel-row-metric">
        <strong>${item.movement}</strong>
        <span>${metricLabel}</span>
      </div>
    </div>
  `;
}

function parseMovementPercent(movement = "") {
  const n = parseFloat(String(movement).replace(/[^0-9.\-+]/g, ""));
  return Number.isFinite(n) ? n : 0;
}

function movementClass(movement = "") {
  const n = parseMovementPercent(movement);
  if (n > 0.01) return "metric-up";
  if (n < -0.01) return "metric-down";
  return "metric-flat";
}

/* Landing page — compact card intelligence row */
function renderCardIntelRow(item) {
  const moveClass = movementClass(item.movement);
  const upsideClass = movementClass(item.upside);

  return `
    <div class="card-intel-row">
      <div class="card-intel-row-thumb" aria-hidden="true"></div>
      <div class="card-intel-row-body">
        <div class="card-intel-row-name">${item.name}</div>
        <div class="card-intel-row-metrics">
          <span class="card-intel-metric">
            <em>price</em>
            <strong>${csIntelFormatMoney(item.price)}</strong>
          </span>
          <span class="card-intel-metric">
            <em>7-day move</em>
            <strong class="${moveClass}">${item.movement}</strong>
          </span>
          <span class="card-intel-metric">
            <em>score</em>
            <strong>${item.score ?? "—"}</strong>
          </span>
          <span class="card-intel-metric">
            <em>upside</em>
            <strong class="${upsideClass}">${item.upside ?? "—"}</strong>
          </span>
        </div>
      </div>
    </div>
  `;
}

function renderCardIntelBox({ title, modifier, items }) {
  return `
    <article class="card-intel-box card-intel-box--${modifier}">
      <h3 class="card-intel-box-title">${title}</h3>
      <div class="card-intel-box-list">
        ${items.slice(0, 3).map((item) => renderCardIntelRow(item)).join("")}
      </div>
    </article>
  `;
}

function getCardSectionEntry(entries = []) {
  return getSignalOfWeekTopEntry(entries) || entries[0] || getSignalOfWeekPlaceholderEntry();
}

function renderCardSection(entries = []) {
  const root = document.getElementById("card-section-grid");
  if (!root) return;

  const entry = getCardSectionEntry(entries);
  const intel = csIntelGetPlaceholders(entry);

  root.innerHTML = `
    ${renderCardIntelBox({
      title: "Trending Cards",
      modifier: "trending",
      items: intel.trendingCards,
    })}
    ${renderCardIntelBox({
      title: "Biggest Movers",
      modifier: "movers",
      items: intel.biggestMovers,
    })}
    ${renderCardIntelBox({
      title: "Buy Low Opportunities",
      modifier: "buy-low",
      items: intel.buyLowOpportunities,
    })}
    ${renderCardIntelBox({
      title: "Most Chased",
      modifier: "chased",
      items: intel.mostChased,
    })}
  `;
}

/* Signal Center — player identity row with headshot for featured sections */
function renderFeaturedSignalCard(entry, { label, metricValue, metricCaption }) {
  const initials = getPlayerInitials(entry.player_name);
  const photo = entry.headshot_url
    ? `<img src="${entry.headshot_url}" alt="" loading="lazy" class="player-headshot-image" onerror="this.remove();this.parentElement.insertAdjacentHTML('beforeend','<span>${initials}</span>')" />`
    : `<span>${initials}</span>`;

  return `
    <div class="featured-signal-inner">
      <div class="featured-signal-photo">${photo}</div>
      <div class="featured-signal-copy">
        <div class="featured-signal-label">${label}</div>
        <div class="featured-signal-name">${entry.player_name || "—"}</div>
        <div class="featured-signal-team">
          <span class="team-logo-placeholder">${renderTeamLogoMarkup(entry)}</span>
          ${getTeamAbbrev(entry)}
        </div>
      </div>
      <div class="featured-signal-metric">
        <strong>${metricValue}</strong>
        <span>${metricCaption}</span>
      </div>
    </div>
  `;
}

function showChartPlaceholder(canvasId, placeholderId, show) {
  const canvas = document.getElementById(canvasId);
  const placeholder = document.getElementById(placeholderId);
  if (canvas) canvas.classList.toggle("hidden", show);
  if (placeholder) placeholder.classList.toggle("hidden", !show);
}
function csIntelGetPlaceholders(entry) {
  const key = String(entry?.player_id ?? entry?.player_name ?? "unknown");
  if (csIntelCache.has(key)) return csIntelCache.get(key);

  const storageKey = `cs_intel_placeholders_v1_${key}`;
  try {
    const raw = sessionStorage.getItem(storageKey);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed && parsed.confidenceTier) {
        csIntelCache.set(key, parsed);
        return parsed;
      }
    }
  } catch (_) {
    // ignore
  }

  const seed = csIntelHashToUint32(key);
  const rng = csIntelMulberry32(seed);

  const confidenceTier = csIntelPickConfidenceTier(rng());

  // 0-100 "premium" placeholder scales (used when backend fields are missing).
  const performance = csIntelClamp(22 + rng() * 78, 0, 100);
  const market = csIntelClamp(18 + rng() * 82, 0, 100);
  const collector = csIntelClamp(market * 0.62 + performance * 0.38 + (rng() - 0.5) * 12, 0, 100);
  const momentum = csIntelClamp(((performance + market) / 2) * 0.92 + (rng() - 0.5) * 18, 0, 100);

  const score = csIntelClamp(performance * 0.5 + market * 0.4 + momentum * 0.1 + (rng() - 0.5) * 10, 0, 100);

  const trendingNamePool = [
    "Auric Spark",
    "Copper Drift",
    "Midnight Prospect",
    "Golden Curve",
    "Sable Surge",
    "Emerald Lift",
    "Nova Demand",
    "Ivory Velocity",
    "Crimson Shelf",
    "Sterling Swing",
  ];

  const moverNamePool = [
    "1st Bowman Auto",
    "Rookie Patch Parallel",
    "Bowman Chrome Mojo",
    "Vintage Select /25",
    "Topps Chrome Sapphire",
    "Heritage Black Gold",
    "Bowman Draft Gold",
    "Stadium Club Red Ink",
    "Prizm Draft Stars",
    "Museum Collection Gem",
  ];

  const buyLowNamePool = [
    "Low-Ask Bowman Chrome",
    "Undervalued Rookie Parallel",
    "Quiet Liquidity Lot",
    "Discounted Card Slice",
    "Value Pocket Prospect",
    "Supportive Supply Window",
    "Stable Demand, Soft Prices",
    "Inked Rookie Deal",
    "Surprisingly Priced Parallel",
    "Buyer-Ready Bargain",
  ];

  const chasedNamePool = [
    "Hot Case Break",
    "Chase-Grade Parallel",
    "Bid-War Magnet",
    "Collector Pressure Lot",
    "Velocity Surge Card",
    "Momentum Mirror",
    "Rising Demand Select",
    "Premium Parallels Feed",
    "Frictionless Chase Copy",
    "Scarcity-Driven Target",
  ];

  function pickThree(pool, { bias = 0, priceMin = 8, priceMax = 230, moveMin = 4, moveMax = 30 } = {}) {
    const used = new Set();
    const out = [];
    while (out.length < 3 && used.size < pool.length) {
      const idx = Math.floor(rng() * pool.length);
      if (used.has(idx)) continue;
      used.add(idx);
      const price = priceMin + rng() * (priceMax - priceMin);
      const magnitude = moveMin + rng() * (moveMax - moveMin);
      // bias shifts expectation, but we still allow direction changes.
      const direction = rng() > 0.5 ? 1 : -1;
      const move = (direction * magnitude) + bias + (rng() - 0.5) * 5;
      out.push({
        name: pool[idx],
        price,
        movement: csIntelFormatPercent(move),
        score: Math.round(40 + rng() * 55),
        upside: csIntelFormatPercent((rng() - 0.35) * 28),
      });
    }
    return out;
  }

  const trendingCards = pickThree(trendingNamePool, {
    bias: (market - 50) / 8 + (momentum - 50) / 10,
    priceMin: 12,
    priceMax: 260,
    moveMin: 8,
    moveMax: 28,
  });

  const biggestMovers = pickThree(moverNamePool, {
    bias: (performance - 50) / 10,
    priceMin: 15,
    priceMax: 310,
    moveMin: 10,
    moveMax: 38,
  });

  const buyLowOpportunities = pickThree(buyLowNamePool, {
    bias: -6 + (market < 50 ? 3 : -2),
    priceMin: 9,
    priceMax: 170,
    moveMin: 4,
    moveMax: 22,
  });

  const mostChased = pickThree(chasedNamePool, {
    bias: 5 + (momentum - 50) / 10,
    priceMin: 18,
    priceMax: 360,
    moveMin: 8,
    moveMax: 36,
  });

  const aiReasonPool = [
    "Collector demand is increasing faster than current market pricing.",
    "Performance momentum suggests a continued lift in buyer interest over the next 7 days.",
    "Market liquidity remains supportive while supply tightens on recent listings.",
    "Trading velocity is rising faster than average price, creating a favorable buy window.",
    "Recent chase pressure indicates higher willingness to pay for comparable lots soon.",
  ];

  const aiReason = aiReasonPool[Math.floor(rng() * aiReasonPool.length)] || aiReasonPool[0];

  const placeholders = {
    confidenceTier,
    performance: csIntelClamp(performance, 0, 100),
    market: csIntelClamp(market, 0, 100),
    collector: csIntelClamp(collector, 0, 100),
    momentum: csIntelClamp(momentum, 0, 100),
    score: csIntelClamp(score, 0, 100),
    trendingCards,
    biggestMovers,
    buyLowOpportunities,
    mostChased,
    aiRecommendation: {
      action: "BUY",
      confidence: confidenceTier,
      reason: aiReason,
    },
  };

  csIntelCache.set(key, placeholders);
  try {
    sessionStorage.setItem(storageKey, JSON.stringify(placeholders));
  } catch (_) {
    // ignore
  }
  return placeholders;
}

function renderPlayerDetail(entry) {
  selectedPlayer = entry;

  const hotness = entry.hotness || {};
  const placeholders = csIntelGetPlaceholders(entry);

  // Keep all placeholder intelligence data centralized in one object.
  // If backend values exist, we overwrite the corresponding fields.
  const intel = {
    ...placeholders,
    performance: csIntelSafeToNumber(hotness.performance_score) ?? placeholders.performance,
    market: csIntelSafeToNumber(hotness.market_score) ?? placeholders.market,
    collector: csIntelSafeToNumber(hotness.collector_score) ?? placeholders.collector,
    momentum: csIntelSafeToNumber(hotness.momentum_score) ?? placeholders.momentum,
    score: csIntelSafeToNumber(hotness.total_score) ?? placeholders.score,
    confidenceTier: placeholders.confidenceTier,
  };

  const confidenceTier = intel.confidenceTier;
  const team = getTeamAbbrev(entry);
  const position = entry.position || "—";

  const ai = intel.aiRecommendation;

  // Keep layout resilient: never assume backend provides optional arrays/fields.
  const scoreConfidenceClass =
    confidenceTier === "HIGH" ? "cs-confidence--high" : confidenceTier === "MEDIUM" ? "cs-confidence--medium" : "cs-confidence--low";

  const progressRow = (label, value, colorClass) => {
    const v = csIntelClamp(Number(value) || 0, 0, 100);
    return `
      <div class="cs-progress-row">
        <div class="cs-progress-top">
          <span class="cs-progress-label">${label}</span>
          <span class="cs-progress-value">${formatScore(v)}</span>
        </div>
        <div class="cs-progress-track" aria-hidden="true">
          <span class="cs-progress-fill ${colorClass}" style="width:${v}%"></span>
        </div>
      </div>
    `;
  };

  const confidenceBadge = `<div class="cs-confidence-badge ${scoreConfidenceClass}">${confidenceTier}</div>`;

  return `
    <article class="player-report player-report--cardsignal-intel">
      <div class="cs-intel-hero player-report-hero">
        <div class="player-report-identity cs-intel-identity">
          ${renderPlayerHeadshot(entry)}

          <div class="cs-intel-identity-copy">
            <p class="eyebrow">CardSignal Intelligence</p>
            <h2 class="cs-intel-name">${entry.player_name}</h2>

            <div class="cs-intel-subline" aria-label="Player team and position">
              <span class="cs-intel-chip">
                <span class="team-logo-placeholder">${renderTeamLogoMarkup(entry)}</span>
                ${team}
              </span>
              <span class="cs-intel-chip cs-intel-chip--muted">${position}</span>
            </div>
          </div>
        </div>

        <button id="watchlist-toggle-btn" class="player-save-btn">
          ${currentUser ? "Save to watchlist" : "Sign in to save"}
        </button>
      </div>

      <section class="cs-intel-score-card">
        <div class="cs-section-head">
          <div>
            <p class="eyebrow">CardSignal Score</p>
          </div>
          <div class="cs-section-head-right">
            ${csIntelBetaPreviewBadge()}
            <div class="cs-confidence-wrap">
              ${confidenceBadge}
              <small class="cs-confidence-label">Confidence</small>
            </div>
          </div>
        </div>

        <div class="cs-score-large">
          <span>${formatScore(intel.score)}</span>
        </div>
      </section>

      <section class="cs-intel-breakdown">
        <div class="cs-section-head">
          <h3 class="cs-section-title">Signal Breakdown</h3>
          <div class="cs-section-head-right">${csIntelBetaPreviewBadge()}</div>
        </div>

        <div class="cs-progress-list">
          ${progressRow("Performance", intel.performance, "cs-progress-fill--performance")}
          ${progressRow("Market", intel.market, "cs-progress-fill--market")}
          ${progressRow("Collector", intel.collector, "cs-progress-fill--collector")}
          ${progressRow("Momentum", intel.momentum, "cs-progress-fill--momentum")}
        </div>
      </section>

      <section class="cs-premium-card cs-premium-card--ai">
        <div class="cs-premium-head">
          <h3 class="cs-premium-title">AI Recommendation</h3>
          ${csIntelBetaPreviewBadge()}
        </div>

        <div class="cs-ai-block cs-ai-block--compact">
          <div class="cs-ai-inline">
            <span class="cs-ai-action-compact cs-ai-action-compact--${ai.action.toLowerCase()}">${ai.action}</span>
            <div class="cs-confidence-badge ${scoreConfidenceClass}">${ai.confidence}</div>
          </div>
          <div class="cs-ai-reason cs-ai-reason--compact">
            <p>${ai.reason}</p>
          </div>
        </div>
      </section>
    </article>
  `;
}

function renderNotifications(items, summary) {
  const root = document.getElementById('notifications-list');
  document.getElementById('notif-summary').textContent = `Notifications: ${summary?.total ?? 0}`;
  document.getElementById('notif-unread').textContent = `Unread: ${summary?.unread ?? 0}`;
  if (!items?.length) return root.innerHTML = 'No notifications yet.';
  root.innerHTML = items.map(item => `
    <div class="notification-item ${item.read_at ? '' : 'unread'}">
      <div>
        <div><span class="${tagClass(formatEventLabel(item.event_type))}">${formatEventLabel(item.event_type)}</span></div>
        <div class="notification-title">${item.title}</div>
        <div class="notification-message">${item.message}</div>
        <div class="notification-meta">${formatTimestamp(item.created_at)}</div>
      </div>
      ${item.read_at ? '' : `<button class="ghost small mark-read-btn" data-id="${item.id}">Mark read</button>`}
    </div>`).join('');
  root.querySelectorAll('.mark-read-btn').forEach(btn => btn.addEventListener('click', async () => {
    await apiFetch('/api/notifications/read', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ notification_id: Number(btn.dataset.id) }) });
    await loadNotifications();
  }));
}

function syncRuleForm() {
  const select = document.getElementById('rule-player-name');
  if (!select) return;
  if (!watchlistItems.length) {
    select.innerHTML = '<option value="">Save a watchlist player first</option>';
    return;
  }
  const current = select.value;
  select.innerHTML = watchlistItems.map(item => `<option value="${item.player_name}">${item.player_name}</option>`).join('');
  if (current && watchlistItems.some(item => item.player_name === current)) select.value = current;
  const playerName = select.value || watchlistItems[0]?.player_name;
  const rule = findRule(playerName);
  document.getElementById('rule-hotness').checked = rule?.alert_on_hotness_jump ?? true;
  document.getElementById('rule-buy-low').checked = rule?.alert_on_buy_low ?? true;
  document.getElementById('rule-chased').checked = rule?.alert_on_most_chased ?? false;
  document.getElementById('rule-min-delta').value = rule?.min_hotness_delta ?? 8;
  document.getElementById('rule-muted-until').value = toDatetimeLocal(rule?.muted_until);
}

async function loadRules() {
  if (!currentUser || !authToken) { playerAlertRules = []; syncRuleForm(); return; }
  try { playerAlertRules = (await apiFetch('/api/watchlist/rules')).items || []; } catch (_) { playerAlertRules = []; }
  syncRuleForm();
}

async function loadWatchlist() {
  const root = document.getElementById('watchlist-items');
  if (!currentUser || !authToken) { root.innerHTML = 'Sign in to save players.'; return; }
  try {
    watchlistItems = (await apiFetch('/api/watchlist')).items || [];
    if (!watchlistItems.length) { root.innerHTML = 'No saved players yet.'; syncRuleForm(); return; }
    root.innerHTML = watchlistItems.map(item => `
      <div class="watchlist-item"><div><div class="watchlist-name">${item.player_name}</div>${renderRuleSummary(findRule(item.player_name))}</div>
      <button class="ghost small remove-watchlist" data-player-name="${item.player_name}">Remove</button></div>`).join('');
    root.querySelectorAll('.remove-watchlist').forEach(btn => btn.addEventListener('click', async () => {
      await apiFetch(`/api/watchlist/${encodeURIComponent(btn.dataset.playerName)}`, { method: 'DELETE' });
      await apiFetch(`/api/watchlist/rules/${encodeURIComponent(btn.dataset.playerName)}`, { method: 'DELETE' }).catch(() => null);
      await Promise.all([loadRules(), loadWatchlist()]);
    }));
    syncRuleForm();
  } catch (error) { root.innerHTML = `<div class="detail-empty">${error.message}</div>`; }
}

async function loadAlerts() {
  if (!currentUser || !authToken) return;
  try {
    const data = await apiFetch('/api/alerts');
    document.getElementById('alert-hotness').checked = data.hotness_jump_enabled;
    document.getElementById('alert-buy-low').checked = data.buy_low_enabled;
    document.getElementById('alert-chased').checked = data.most_chased_enabled;
    document.getElementById('alert-digest').checked = data.daily_digest_enabled;
  } catch (_) {}
}

async function loadNotifications() {
  const root = document.getElementById('notifications-list');
  if (!currentUser || !authToken) {
    root.innerHTML = 'Sign in to load notifications.';
    document.getElementById('notif-summary').textContent = 'Notifications: —';
    document.getElementById('notif-unread').textContent = 'Unread: —';
    return;
  }
  try {
    const payload = await apiFetch('/api/notifications');
    notifications = payload.items || [];
    renderNotifications(notifications, payload.summary || {});
  } catch (error) { root.innerHTML = `<div class="detail-empty">${error.message}</div>`; }
}
function destroyChart(instance) {
  if (instance) instance.destroy();
}

function getChartOptions(title = "") {
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: {
      duration: 900,
      easing: "easeOutQuart",
    },
    plugins: {
      legend: {
        position: "bottom",
        labels: {
          usePointStyle: true,
          boxWidth: 8,
          padding: 18,
          color: "#7D7873",
          font: {
            size: 12,
            weight: "600",
          },
        },
      },
      tooltip: {
        backgroundColor: "#0F0F10",
        titleColor: "#F7F5F2",
        bodyColor: "#F1ECE5",
        borderColor: "#BB8455",
        borderWidth: 1,
        padding: 12,
        cornerRadius: 12,
      },
      title: {
        display: !!title,
        text: title,
        color: "#1D1D1F",
        font: {
          size: 14,
          weight: "700",
        },
        padding: {
          bottom: 16,
        },
      },
    },
    scales: {
      x: {
        grid: {
          display: false,
        },
        ticks: {
          color: "#7D7873",
          maxRotation: 0,
          font: {
            size: 11,
          },
        },
      },
      y: {
        beginAtZero: true,
        max: 100,
        grid: {
          color: "rgba(220, 214, 206, 0.65)",
        },
        ticks: {
          color: "#7D7873",
          font: {
            size: 11,
          },
        },
      },
    },
  };
}

async function renderScoreHistory(playerId) {
  const canvas = document.getElementById("score-history-chart");
  if (!canvas || !playerId) return;

  try {
    const payload = await fetchPlayerHistory(playerId);
    const items = payload.items || [];

    destroyChart(scoreChart);

    if (!items.length) {
      showChartPlaceholder("score-history-chart", "score-history-placeholder", true);
      return;
    }

    showChartPlaceholder("score-history-chart", "score-history-placeholder", false);

    scoreChart = new Chart(canvas, {
      type: "line",
      data: {
        labels: items.map(item =>
          new Date(item.created_at).toLocaleDateString(undefined, {
            month: "short",
            day: "numeric",
          })
        ),
        datasets: [
          {
            label: "CardSignal",
            data: items.map(item => Number(item.total_score || 0)),
            borderColor: "#BB8455",
            backgroundColor: "rgba(187, 132, 85, 0.10)",
            borderWidth: 2.5,
            tension: 0.35,
            fill: true,
            pointRadius: 3,
            pointHoverRadius: 5,
          },
          {
            label: "Performance",
            data: items.map(item => Number(item.performance_score || 0)),
            borderColor: "#708A72",
            backgroundColor: "rgba(112, 138, 114, 0.08)",
            borderWidth: 2,
            tension: 0.35,
            fill: false,
            pointRadius: 2,
            pointHoverRadius: 4,
          },
          {
            label: "Market",
            data: items.map(item => Number(item.market_score || 0)),
            borderColor: "#8A6747",
            backgroundColor: "rgba(138, 103, 71, 0.08)",
            borderWidth: 2,
            tension: 0.35,
            fill: false,
            pointRadius: 2,
            pointHoverRadius: 4,
          },
        ],
      },
      options: getChartOptions("Selected Player Signal History"),
    });
  } catch (error) {
    console.error("Score history chart error:", error);
  }
}

async function renderLeaderboardHistory() {
  const canvas = document.getElementById("leaderboard-history-chart");
  if (!canvas) return;

  try {
    const payload = await fetchLeaderboardHistory();
    const items = payload.items || [];

    destroyChart(leaderboardHistoryChart);

    if (!items.length) {
      showChartPlaceholder("leaderboard-history-chart", "leaderboard-history-placeholder", true);
      return;
    }

    showChartPlaceholder("leaderboard-history-chart", "leaderboard-history-placeholder", false);

    leaderboardHistoryChart = new Chart(canvas, {
      type: "bar",
      data: {
        labels: items.map(item =>
          new Date(item.created_at).toLocaleDateString(undefined, {
            month: "short",
            day: "numeric",
          })
        ),
        datasets: [
          {
            label: "Top CardSignal Score",
            data: items.map(item => Number(item.leaders?.[0]?.total_score || 0)),
            backgroundColor: "rgba(187, 132, 85, 0.75)",
            borderColor: "#BB8455",
            borderWidth: 1,
            borderRadius: 10,
          },
        ],
      },
      options: getChartOptions("Market Trend"),
    });
  } catch (error) {
    console.error("Leaderboard history chart error:", error);
  }
}

function wirePlayerActions() {
  const watchBtn = document.getElementById('watchlist-toggle-btn');
  if (watchBtn) {
    watchBtn.addEventListener('click', async () => {
      if (!selectedPlayer) return;
      if (!currentUser || !authToken) return setAuthStatus('Sign in first to save players.', true);
      try {
        await apiFetch('/api/watchlist', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ player_id: selectedPlayer.player_id, player_name: selectedPlayer.player_name }) });
        setAuthStatus(`${selectedPlayer.player_name} saved to your watchlist.`);
        await Promise.all([loadWatchlist(), loadRules()]);
      } catch (error) { setAuthStatus(error.message, true); }
    });
  }
}

async function selectPlayer(entry) {
  const detailRoot = document.getElementById('player-detail');
  try {
    const player = entry.player_id ? await fetchPlayer(entry.player_id) : entry;
    detailRoot.innerHTML = renderPlayerDetail(player);
    wirePlayerActions();
    await renderScoreHistory(player.player_id);
  } catch (error) {
    detailRoot.innerHTML = `<div class="detail-empty">${error.message}</div>`;
  }
}

async function bootstrapSupabase() {
  const { data, error } = await fetch(`${API_BASE_URL}/api/config`).then(res => res.json()).then(json => ({ data: json }));
  if (error || !data?.supabase_url || !data?.supabase_anon_key || !window.supabase) return;
  supabaseClient = window.supabase.createClient(data.supabase_url, data.supabase_anon_key);
  const sessionData = await supabaseClient.auth.getSession();
  authToken = sessionData.data.session?.access_token || null;
  currentUser = sessionData.data.session?.user || null;
  if (currentUser) setAuthStatus(`Signed in as ${currentUser.email || currentUser.id}`);
}

function bindAuthActions() {
  document.getElementById('sign-up-btn').addEventListener('click', async () => {
    if (!supabaseClient) return setAuthStatus('Supabase auth is not configured.', true);
    const email = document.getElementById('auth-email').value.trim();
    const password = document.getElementById('auth-password').value;
    const { error } = await supabaseClient.auth.signUp({ email, password });
    setAuthStatus(error ? error.message : 'Check your email to confirm your account.', !!error);
  });
  document.getElementById('sign-in-btn').addEventListener('click', async () => {
    if (!supabaseClient) return setAuthStatus('Supabase auth is not configured.', true);
    const email = document.getElementById('auth-email').value.trim();
    const password = document.getElementById('auth-password').value;
    const { data, error } = await supabaseClient.auth.signInWithPassword({ email, password });
    if (error) return setAuthStatus(error.message, true);
    authToken = data.session?.access_token || null;
    currentUser = data.user || null;
    setAuthStatus(`Signed in as ${currentUser?.email || currentUser?.id}`);
    await Promise.all([loadRules(), loadWatchlist(), loadAlerts(), loadNotifications()]);
  });
  document.getElementById('sign-out-btn').addEventListener('click', async () => {
    if (!supabaseClient) return;
    await supabaseClient.auth.signOut();
    authToken = null; currentUser = null; watchlistItems = []; playerAlertRules = [];
    setAuthStatus('Signed out.');
    await Promise.all([loadWatchlist(), loadRules(), loadNotifications()]);
  });
  document.getElementById('alerts-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!currentUser || !authToken) return setAuthStatus('Sign in first to save alerts.', true);
    try {
      await apiFetch('/api/alerts', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
        hotness_jump_enabled: document.getElementById('alert-hotness').checked,
        buy_low_enabled: document.getElementById('alert-buy-low').checked,
        most_chased_enabled: document.getElementById('alert-chased').checked,
        daily_digest_enabled: document.getElementById('alert-digest').checked,
      })});
      setAuthStatus('Alert preferences saved.');
    } catch (error) { setAuthStatus(error.message, true); }
  });
  document.getElementById('rule-player-name').addEventListener('change', syncRuleForm);
  document.getElementById('player-rule-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!currentUser || !authToken) return setAuthStatus('Sign in first to save player rules.', true);
    const playerName = document.getElementById('rule-player-name').value;
    if (!playerName) return setAuthStatus('Save a watchlist player first.', true);
    try {
      await apiFetch(`/api/watchlist/rules/${encodeURIComponent(playerName)}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
        min_hotness_delta: Number(document.getElementById('rule-min-delta').value || '8'),
        alert_on_hotness_jump: document.getElementById('rule-hotness').checked,
        alert_on_buy_low: document.getElementById('rule-buy-low').checked,
        alert_on_most_chased: document.getElementById('rule-chased').checked,
        muted_until: document.getElementById('rule-muted-until').value ? new Date(document.getElementById('rule-muted-until').value).toISOString() : null,
      })});
      setAuthStatus(`Saved rule for ${playerName}.`);
      await Promise.all([loadRules(), loadWatchlist()]);
    } catch (error) { setAuthStatus(error.message, true); }
  });
  document.getElementById('rule-delete-btn').addEventListener('click', async () => {
    if (!currentUser || !authToken) return setAuthStatus('Sign in first to manage player rules.', true);
    const playerName = document.getElementById('rule-player-name').value;
    if (!playerName) return;
    await apiFetch(`/api/watchlist/rules/${encodeURIComponent(playerName)}`, { method: 'DELETE' });
    setAuthStatus(`Cleared custom rule for ${playerName}.`);
    await Promise.all([loadRules(), loadWatchlist()]);
  });
  document.getElementById('read-all-btn').addEventListener('click', async () => {
    if (!currentUser || !authToken) return setAuthStatus('Sign in first to manage notifications.', true);
    await apiFetch('/api/notifications/read-all', { method: 'POST' });
    await loadNotifications();
  });
}

function bindAdminActions() {
  document.getElementById('admin-token-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    adminToken = document.getElementById('admin-token').value.trim();
    localStorage.setItem('cardchase_admin_token', adminToken);
    await loadAdmin();
  });
  document.getElementById('admin-settings-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    try {
      await adminFetch('/api/admin/settings', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
        tracked_players_csv: document.getElementById('admin-tracked-players-csv').value,
        hotness_jump_threshold: Number(document.getElementById('admin-hotness-threshold').value || '8'),
        daily_digest_hour_utc: Number(document.getElementById('admin-digest-hour').value || '13'),
      })});
      setAdminStatus('Admin settings saved.');
      await loadAdmin();
    } catch (error) { setAdminStatus(error.message, true); }
  });
  document.getElementById('admin-player-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    try {
      await adminFetch('/api/admin/tracked-players', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
        player_name: document.getElementById('admin-player-name').value,
        notes: document.getElementById('admin-player-notes').value,
        active: document.getElementById('admin-player-active').checked,
      })});
      setAdminStatus('Tracked player saved.');
      event.target.reset();
      document.getElementById('admin-player-active').checked = true;
      await loadAdmin();
    } catch (error) { setAdminStatus(error.message, true); }
  });
}

async function loadAdmin() {
  if (!adminToken) return setAdminStatus('Admin tools locked.');
  try {
    const payload = await adminFetch('/api/admin/settings');
    const settings = payload.settings || {};
    document.getElementById('admin-token').value = adminToken;
    document.getElementById('admin-tracked-players-csv').value = settings.tracked_players_csv || '';
    document.getElementById('admin-hotness-threshold').value = settings.hotness_jump_threshold ?? 8;
    document.getElementById('admin-digest-hour').value = settings.daily_digest_hour_utc ?? 13;
    const listRoot = document.getElementById('admin-tracked-players');
    const items = payload.tracked_players || [];
    listRoot.innerHTML = items.length ? items.map(item => `
      <div class="watchlist-item"><div><div class="watchlist-name">${item.player_name}</div><div class="muted">${item.notes || 'No notes'} • ${item.active ? 'active' : 'inactive'}</div></div>
      <button class="ghost small admin-delete-player" data-player-name="${item.player_name}">Delete</button></div>`).join('') : 'No tracked players yet.';
    listRoot.querySelectorAll('.admin-delete-player').forEach(btn => btn.addEventListener('click', async () => {
      await adminFetch(`/api/admin/tracked-players/${encodeURIComponent(btn.dataset.playerName)}`, { method: 'DELETE' });
      await loadAdmin();
    }));
    setAdminStatus('Admin tools unlocked.');
  } catch (error) { setAdminStatus(error.message, true); }
}
/* ==========================================================
   Signal Center — UI Render Helpers
   (Dashboard nav label retained; page structured as Signal Center)
   ========================================================== */

function calculateMarketPulse(entries) {
  if (!entries || !entries.length) return 0;

  const total = entries.reduce(
    (sum, player) => sum + (player.hotness?.total_score || 0),
    0
  );

  return Math.round(total / entries.length);
}

function getTopMovers(entries, limit = 10) {
  return [...entries]
    .sort((a, b) => (b.hotness?.total_score || 0) - (a.hotness?.total_score || 0))
    .slice(0, limit);
}

function renderMarketPulse(entries) {
  const safeEntries = Array.isArray(entries) ? entries : [];
  const pulseCard = document.querySelector(".market-pulse-card");
  if (!pulseCard) return;

  const generatedAt = new Date().toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
  });

  if (!safeEntries.length) {
    pulseCard.innerHTML = `
      <div class="market-pulse-top">
        <div class="market-pulse-title-group">
          <div>
            <div class="label">Market Pulse</div>
            <h2>Today\'s Card Market</h2>
          </div>
          <span class="market-pulse-updated-pill">Updated ${generatedAt}</span>
        </div>
        <span class="market-status">Active</span>
      </div>

      <div class="market-pulse-body--compact">
        <div class="market-pulse-score-compact">
          <span>—</span>
          <small>CardSignal Pulse</small>
        </div>
        <div class="market-pulse-metrics-inline">
          <div class="market-pulse-metric-chip"><strong>—</strong><span>Performance</span></div>
          <div class="market-pulse-metric-chip"><strong>—</strong><span>Demand</span></div>
          <div class="market-pulse-metric-chip"><strong>—</strong><span>Top Signal</span></div>
        </div>
      </div>

      <div class="pulse-movers pulse-movers--top10">
        <div class="label">Top 10 Movers</div>
        <div class="pulse-mover-row"><span>—</span><strong>—</strong></div>
      </div>
    `;
    return;
  }

  const pulse = calculateMarketPulse(safeEntries);
  const topMovers = getTopMovers(safeEntries, 10);
  const avgPerformance = Math.round(
    safeEntries.reduce((sum, p) => sum + (p.hotness?.performance_score || 0), 0) / safeEntries.length
  );
  const avgMarket = Math.round(
    safeEntries.reduce((sum, p) => sum + (p.hotness?.market_score || 0), 0) / safeEntries.length
  );
  const strongest = safeEntries[0] || {};

  pulseCard.innerHTML = `
    <div class="market-pulse-top">
      <div class="market-pulse-title-group">
        <div>
          <div class="label">Market Pulse</div>
          <h2>Today\'s Card Market</h2>
        </div>
        <span class="market-pulse-updated-pill">Updated ${generatedAt}</span>
      </div>
      <span class="market-status">Active</span>
    </div>

    <div class="market-pulse-body--compact">
      <div class="market-pulse-score-compact">
        <span>${pulse}</span>
        <small>CardSignal Pulse</small>
      </div>
      <div class="market-pulse-metrics-inline">
        <div class="market-pulse-metric-chip"><strong>${avgPerformance}</strong><span>Performance</span></div>
        <div class="market-pulse-metric-chip"><strong>${avgMarket}</strong><span>Demand</span></div>
        <div class="market-pulse-metric-chip"><strong>${formatScore(strongest.hotness?.total_score)}</strong><span>Top Signal</span></div>
      </div>
    </div>

    <div class="pulse-movers pulse-movers--top10">
      <div class="label">Top 10 Movers</div>
      ${topMovers.map(player => `
        <div class="pulse-mover-row">
          <span>${player.player_name}</span>
          <strong>${formatScore(player.hotness?.total_score)}</strong>
        </div>
      `).join("")}
    </div>
  `;
}

function getSignalOfWeekPlaceholderEntry() {
  return {
    player_id: null,
    player_name: "Signal of the Week",
    position: "—",
    team: "MLB",
    mlb_team: "MLB",
    team_abbrev: "MLB",
    headshot_url: null,
    action_photo_url: null,
    hotness: {
      total_score: 92.3,
      market_score: 78,
      performance_score: 70,
      collector_score: 80,
      momentum_score: 68,
      tag: "HOTNESS JUMP",
    },
  };
}

function getSignalOfWeekTopEntry(entries = []) {
  if (!Array.isArray(entries) || !entries.length) return null;

  // Choose the highest CardSignal total_score currently loaded in the leaderboard.
  let best = null;
  let bestScore = -Infinity;

  for (const entry of entries) {
    const score = entry?.hotness?.total_score;
    const n = typeof score === "number" ? score : Number(score);
    if (!Number.isFinite(n)) continue;
    if (n > bestScore) {
      bestScore = n;
      best = entry;
    }
  }

  return best || entries[0] || null;
}

function getSignalOfWeekActionPhotoUrl(entry = {}) {
  return (
    entry?.action_photo_url ||
    entry?.player_action_photo_url ||
    entry?.action_photo_headshot_url ||
    entry?.player_action_headshot_url ||
    null
  );
}

function getSignalOfWeekHeadshotUrl(entry = {}) {
  return entry?.headshot_url || entry?.photo_url || entry?.player_photo_url || null;
}

function renderSignalWeekPlayerImage(entry = {}) {
  const initials = getPlayerInitials(entry.player_name);
  const actionUrl = getSignalOfWeekActionPhotoUrl(entry);
  const headshotUrl = getSignalOfWeekHeadshotUrl(entry);
  const imageUrl = actionUrl || headshotUrl;
  const imageKind = actionUrl ? "action" : "headshot";

  if (imageUrl) {
    return `
      <div class="player-image-stage signal-week-photo-stage player-image-stage--${imageKind}" data-image-kind="${imageKind}">
        <div class="player-image-backdrop" aria-hidden="true"></div>
        <img
          src="${imageUrl}"
          alt="${entry.player_name}"
          loading="lazy"
          class="player-image player-image--${imageKind} signal-week-photo-image"
          onerror="this.remove();this.closest('.player-image-stage').insertAdjacentHTML('beforeend','<span class=&quot;player-image-fallback signal-week-photo-fallback&quot;>${initials}</span>')"
        />
        <div class="player-image-glass signal-week-photo-glass" aria-hidden="true"></div>
      </div>`;
  }

  return `
    <div class="player-image-stage signal-week-photo-stage player-image-stage--placeholder" data-image-kind="placeholder">
      <div class="player-image-backdrop" aria-hidden="true"></div>
      <span class="player-image-fallback signal-week-photo-fallback">${initials}</span>
      <div class="player-image-glass signal-week-photo-glass" aria-hidden="true"></div>
    </div>`;
}

function clampToOneSentence(text = "") {
  const t = String(text || "").trim();
  if (!t) return "";
  return t.split(/(?<=[.!?])\s+/)[0] || t;
}

function getSignalOfWeekStatus(entry = {}) {
  const tag = String(entry?.hotness?.tag || "").toUpperCase();
  const score = Number(entry?.hotness?.total_score || 0);
  const momentum = Number(entry?.hotness?.momentum_score || 50);

  // Map existing backend semantics to the requested pill vocabulary.
  if (tag.includes("COOL")) return { label: "COOLING", emoji: "❄️", className: "signal-week-status--cooling" };
  if (score >= 80 || tag.includes("HOT") || tag.includes("JUMP")) return { label: "HOT", emoji: "🔥", className: "signal-week-status--hot" };
  if (tag.includes("BUY") || tag.includes("RISING") || momentum >= 60) {
    return { label: "RISING", emoji: "📈", className: "signal-week-status--rising" };
  }
  return { label: "RISING", emoji: "📈", className: "signal-week-status--rising" };
}

function computeSignalOfWeekMovement(entry = {}) {
  const hotness = entry?.hotness || {};
  const momentum = Number(hotness.momentum_score ?? NaN);
  const market = Number(hotness.market_score ?? NaN);
  const performance = Number(hotness.performance_score ?? NaN);

  let delta = 0;

  // Use momentum_score when available (0..100-ish), convert it to a small week movement.
  if (Number.isFinite(momentum)) {
    // momentum 50 => 0; momentum 60 => +2.0-ish; momentum 70 => +4.0-ish.
    delta = (momentum - 50) / 2.5;
  } else if (Number.isFinite(market) && Number.isFinite(performance)) {
    // Derive a direction from market vs performance.
    delta = (market - performance) / 6;
  }

  // Keep the UI tidy even if upstream data is noisy.
  delta = Math.max(-25, Math.min(25, delta));

  const arrow = delta > 0.01 ? "↑" : delta < -0.01 ? "↓" : "→";
  const signed = delta > 0 ? `+${delta.toFixed(1)}` : delta < 0 ? `${delta.toFixed(1)}` : `+0.0`;

  return { arrow, signed };
}

function renderSignalOfTheWeek(entries = []) {
  const card = document.querySelector(".signal-of-week-card");
  if (!card) return;

  const topEntry = getSignalOfWeekTopEntry(entries);
  const entry = topEntry || getSignalOfWeekPlaceholderEntry();

  const score = Number(entry?.hotness?.total_score ?? 0);
  const movement = computeSignalOfWeekMovement(entry);

  const placeholderKeyEntry = entry?.player_id
    ? entry
    : {
      player_id: "signal_of_week_placeholder",
      player_name: entry?.player_name || "Signal of the Week",
    };

  const placeholders = csIntelGetPlaceholders(placeholderKeyEntry);
  const aiReason = placeholders?.aiRecommendation?.reason || "Collector demand is accelerating faster than market pricing.";
  const aiReasonSentence = clampToOneSentence(aiReason) || "Collector demand is accelerating faster than market pricing.";

  const confidenceTier = placeholders?.confidenceTier || "MEDIUM";
  const aiAction = confidenceTier === "HIGH" ? "BUY" : confidenceTier === "MEDIUM" ? "HOLD" : "SELL";

  const team = getTeamAbbrev(entry);
  const position = entry.position || "—";
  const moveClass = movement.signed.startsWith("+") ? "metric-up" : movement.signed.startsWith("-") ? "metric-down" : "metric-flat";

  card.innerHTML = `
    <div class="signal-week-banner">
      <div class="signal-week-media">
        ${renderSignalWeekPlayerImage(entry)}
      </div>

      <div class="signal-week-content">
        <div class="signal-week-label">Signal of the Week</div>
        <div class="signal-week-primary">
          <div class="signal-week-identity">
            <div class="signal-week-name">${entry.player_name || "—"}</div>
            <div class="signal-week-meta">
              <span class="signal-week-team-logo">${renderTeamLogoMarkup(entry)}</span>
              <span class="signal-week-team-name">${team}</span>
              <span class="signal-week-meta-sep" aria-hidden="true">·</span>
              <span class="signal-week-position">${position}</span>
            </div>
          </div>

          <div class="signal-week-stats">
            <div class="signal-week-stat">
              <span class="signal-week-stat-value">${formatScore(score)}</span>
              <span class="signal-week-stat-label">CardSignal Score</span>
            </div>
            <div class="signal-week-stat">
              <span class="signal-week-stat-value ${moveClass}">${movement.arrow} ${movement.signed}</span>
              <span class="signal-week-stat-label">Weekly Movement</span>
            </div>
          </div>
        </div>

        <div class="signal-week-insight">
          <div class="signal-week-ai-row">
            <span class="signal-week-ai-label">AI Recommendation</span>
            <span class="signal-week-ai-pill signal-week-ai-pill--${aiAction.toLowerCase()}">${aiAction}</span>
          </div>
          <p class="signal-week-reason">${aiReasonSentence}</p>
        </div>
      </div>

      <div class="signal-week-action">
        <button
          class="signal-week-cta primary"
          type="button"
          id="signal-of-the-week-view-report"
          aria-label="View report for ${entry.player_name || "player"}"
        >
          View Report
        </button>
      </div>
    </div>
  `;

  const btn = document.getElementById("signal-of-the-week-view-report");
  if (btn) {
    btn.onclick = async () => {
      await selectPlayer(entry);
      document.getElementById("player-detail")?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    };
  }
}

/* Signal Center — main dashboard render pipeline */
function renderSignalCenter(entries) {
  renderSignalOfTheWeek(entries);
  renderCardSection(entries);
}

/** @deprecated Use renderSignalCenter — kept as alias for compatibility */
function renderDashboardV2(entries) {
  renderSignalCenter(entries);
}

/* ==========================================================
   Sprint 4.6 — Universal Player Search Polish
   ========================================================== */

let searchDebounceTimer = null;
let searchRequestId = 0;
let cachedBackendSearchResults = [];
let searchIsLoading = false;
let searchHighlightIndex = -1;
let currentSearchMatches = [];

function normalizeSearchText(value) {
  return String(value || "").trim().toLowerCase();
}

function filterLatestEntries(query) {
  const needle = normalizeSearchText(query);
  if (!needle) return [];

  return latestEntries.filter((entry) => {
    const name = normalizeSearchText(entry.player_name);
    const team = normalizeSearchText(getTeamAbbrev(entry));
    const position = normalizeSearchText(entry.position);
    return name.includes(needle) || team.includes(needle) || position.includes(needle);
  });
}

function isLeaderboardPlayer(entry = {}) {
  return latestEntries.some((item) => String(item.player_id) === String(entry.player_id));
}

function mergeSearchResults(localMatches, backendMatches) {
  const seen = new Set();
  const merged = [];

  for (const entry of localMatches) {
    const id = entry.player_id;
    if (id != null) seen.add(String(id));
    merged.push(entry);
  }

  for (const entry of backendMatches) {
    const id = String(entry.player_id || "");
    if (id && seen.has(id)) continue;
    if (id) seen.add(id);
    merged.push(entry);
  }

  return merged;
}

function getMergedSearchMatches(query) {
  return mergeSearchResults(filterLatestEntries(query), cachedBackendSearchResults);
}

function renderSearchResultHeadshot(entry = {}) {
  const initials = getPlayerInitials(entry.player_name);
  if (entry.headshot_url) {
    return `
      <span class="search-result-photo">
        <img
          src="${entry.headshot_url}"
          alt=""
          loading="lazy"
          class="player-headshot-image"
          onerror="this.remove();this.parentElement.insertAdjacentHTML('beforeend','<span>${initials}</span>')"
        />
      </span>`;
  }
  return `<span class="search-result-photo"><span>${initials}</span></span>`;
}

function renderSearchResultBadge(entry) {
  const isTop20 = isLeaderboardPlayer(entry);
  const label = isTop20 ? "Top 20" : "MLB Search";
  const modifier = isTop20 ? "top20" : "mlb";
  return `<span class="player-search-result-badge player-search-result-badge--${modifier}">${label}</span>`;
}

function applySearchHighlight() {
  const root = document.getElementById("player-search-results");
  if (!root) return;

  const buttons = [...root.querySelectorAll(".player-search-result")];
  buttons.forEach((button, index) => {
    button.classList.toggle("player-search-result--highlighted", index === searchHighlightIndex);
  });

  if (searchHighlightIndex >= 0 && buttons[searchHighlightIndex]) {
    buttons[searchHighlightIndex].scrollIntoView({ block: "nearest" });
  }
}

function renderSearchResults(matches, query, { loading = false } = {}) {
  const root = document.getElementById("player-search-results");
  if (!root) return;

  if (!normalizeSearchText(query)) {
    root.classList.add("hidden");
    root.innerHTML = "";
    currentSearchMatches = [];
    searchHighlightIndex = -1;
    return;
  }

  currentSearchMatches = matches;
  root.classList.remove("hidden");

  if (!matches.length && loading) {
    searchHighlightIndex = -1;
    root.innerHTML = `<div class="player-search-status player-search-loading">Searching player pool...</div>`;
    return;
  }

  if (!matches.length && !loading) {
    searchHighlightIndex = -1;
    root.innerHTML = `<div class="player-search-status player-search-empty">No player found.</div>`;
    return;
  }

  if (searchHighlightIndex >= matches.length) {
    searchHighlightIndex = matches.length - 1;
  }

  let html = matches.map((entry, index) => {
    const scored = isLeaderboardPlayer(entry);
    const score = entry.hotness?.total_score || 0;
    const team = getTeamAbbrev(entry);
    const position = entry.position || "—";
    const scoreMarkup = scored
      ? `<strong>${formatScore(score)}</strong><small>CardSignal</small>`
      : `<strong class="search-score-unscored">Not scored yet</strong><small>CardSignal</small>`;
    const highlighted = index === searchHighlightIndex ? " player-search-result--highlighted" : "";

    return `
      <button
        class="player-search-result${scored ? "" : " player-search-result--unscored"}${highlighted}"
        type="button"
        role="option"
        aria-selected="${index === searchHighlightIndex ? "true" : "false"}"
        data-player-id="${entry.player_id || ""}"
        data-is-leaderboard="${scored ? "1" : "0"}"
      >
        ${renderSearchResultHeadshot(entry)}
        <span class="player-search-result-copy">
          <strong>${entry.player_name}</strong>
          <span class="player-search-result-meta">
            <span>${team} · ${position}</span>
            ${renderSearchResultBadge(entry)}
          </span>
        </span>
        <span class="player-search-result-score">
          ${scoreMarkup}
        </span>
      </button>
    `;
  }).join("");

  if (loading) {
    html += `<div class="player-search-status player-search-loading">Searching player pool...</div>`;
  }

  root.innerHTML = html;
}

function closePlayerSearch() {
  const input = document.getElementById("player-search-input");
  const root = document.getElementById("player-search-results");

  clearTimeout(searchDebounceTimer);
  searchRequestId += 1;
  cachedBackendSearchResults = [];
  searchIsLoading = false;
  currentSearchMatches = [];
  searchHighlightIndex = -1;

  if (input) input.value = "";
  if (root) {
    root.classList.add("hidden");
    root.innerHTML = "";
  }
}

function scrollToPlayerReport() {
  const target = document.querySelector(".player-report-shell") || document.getElementById("player-detail");
  target?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function highlightLeaderboardPlayer(entry) {
  const index = latestEntries.indexOf(entry);
  if (index < 0) return;

  const leaderboardRoot = document.getElementById("leaderboard-table");
  if (!leaderboardRoot) return;

  const leaderRows = [...leaderboardRoot.querySelectorAll(".leader-table-row")];
  leaderRows.forEach((row) => row.classList.remove("active"));
  if (leaderRows[index]) leaderRows[index].classList.add("active");
}

async function handleSearchResultSelect(entry) {
  closePlayerSearch();
  highlightLeaderboardPlayer(entry);
  await selectPlayer(entry);
  scrollToPlayerReport();
}

function renderLightweightPlayerDetail(entry) {
  return renderPlayerDetail(entry);
}

async function handleBackendOnlyPlayerSelect(entry) {
  closePlayerSearch();
  selectedPlayer = entry;

  const detailRoot = document.getElementById("player-detail");
  detailRoot.innerHTML = renderLightweightPlayerDetail(entry);
  wirePlayerActions();

  destroyChart(scoreChart);
  showChartPlaceholder("score-history-chart", "score-history-placeholder", true);
  const canvas = document.getElementById("score-history-chart");
  if (canvas) {
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
  }

  const leaderboardRoot = document.getElementById("leaderboard-table");
  leaderboardRoot?.querySelectorAll(".leader-table-row.active").forEach((row) => row.classList.remove("active"));

  scrollToPlayerReport();
}

async function handleSearchResultPick(entry) {
  if (isLeaderboardPlayer(entry)) {
    await handleSearchResultSelect(entry);
  } else {
    await handleBackendOnlyPlayerSelect(entry);
  }
}

function scheduleBackendPlayerSearch(query) {
  const needle = normalizeSearchText(query);
  clearTimeout(searchDebounceTimer);

  if (needle.length < 2) {
    searchIsLoading = false;
    return;
  }

  const requestId = ++searchRequestId;
  searchIsLoading = true;
  renderSearchResults(getMergedSearchMatches(query), query, { loading: true });

  searchDebounceTimer = setTimeout(async () => {
    try {
      const backendResults = await fetchPlayerSearch(query);
      if (requestId !== searchRequestId) return;
      cachedBackendSearchResults = backendResults;
    } catch (_) {
      if (requestId !== searchRequestId) return;
      cachedBackendSearchResults = [];
    } finally {
      if (requestId !== searchRequestId) return;
      searchIsLoading = false;
      renderSearchResults(getMergedSearchMatches(query), query, { loading: false });
    }
  }, 250);
}

function updatePlayerSearchResults(query) {
  const needle = normalizeSearchText(query);
  if (needle.length < 2) {
    cachedBackendSearchResults = [];
    searchIsLoading = false;
    searchHighlightIndex = -1;
    renderSearchResults(getMergedSearchMatches(query), query, { loading: false });
    return;
  }

  searchHighlightIndex = -1;
  renderSearchResults(getMergedSearchMatches(query), query, { loading: searchIsLoading });
  scheduleBackendPlayerSearch(query);
}

function setupPlayerSearch() {
  const input = document.getElementById("player-search-input");
  const module = document.getElementById("player-search-module");
  const results = document.getElementById("player-search-results");
  if (!input || !module || !results) return;

  input.addEventListener("input", () => {
    const query = input.value;
    if (!normalizeSearchText(query)) {
      closePlayerSearch();
      return;
    }
    updatePlayerSearchResults(query);
  });

  input.addEventListener("focus", () => {
    if (normalizeSearchText(input.value)) {
      updatePlayerSearchResults(input.value);
    }
  });

  input.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closePlayerSearch();
      return;
    }

    const selectableCount = currentSearchMatches.length;
    if (!selectableCount) return;

    if (event.key === "ArrowDown") {
      event.preventDefault();
      searchHighlightIndex = Math.min(searchHighlightIndex + 1, selectableCount - 1);
      if (searchHighlightIndex < 0) searchHighlightIndex = 0;
      applySearchHighlight();
      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      searchHighlightIndex = Math.max(searchHighlightIndex - 1, 0);
      applySearchHighlight();
      return;
    }

    if (event.key === "Enter" && searchHighlightIndex >= 0) {
      event.preventDefault();
      const entry = currentSearchMatches[searchHighlightIndex];
      if (entry) handleSearchResultPick(entry);
    }
  });

  results.addEventListener("click", async (event) => {
    const button = event.target.closest(".player-search-result");
    if (!button) return;

    const playerId = button.dataset.playerId;
    const entry = currentSearchMatches.find((item) => String(item.player_id || "") === playerId)
      || currentSearchMatches.find((item) => item.player_name === button.querySelector("strong")?.textContent);
    if (!entry) return;

    await handleSearchResultPick(entry);
  });

  document.addEventListener("click", (event) => {
    if (!event.target.closest("#player-search-module")) closePlayerSearch();
  });
}

async function init() {
  const status = document.getElementById('load-status');

  try {
    status.textContent = 'Starting app...';

    document.getElementById('api-hint').textContent = `API: ${API_BASE_URL}`;
    document.getElementById('admin-token').value = adminToken;

    status.textContent = 'Connecting auth...';
    await bootstrapSupabase();

    status.textContent = 'Binding controls...';
    bindAuthActions();
    bindAdminActions();

    status.textContent = 'Loading leaderboard...';
    const payload = await fetch(SOURCE_URL).then(res => {
      if (!res.ok) throw new Error(`Could not load ${SOURCE_URL}.`);
      return res.json();
    });

    const entries = payload.items || [];
    latestEntries = entries;
    setupPlayerSearch();

    status.textContent = 'Rendering Signal Center...';
    renderSignalCenter(entries);

    const leaderboardRoot = document.getElementById('leaderboard-table');
    if (entries.length) {
      leaderboardRoot.innerHTML = buildLeaderboard(entries);

      const leaderRows = [...leaderboardRoot.querySelectorAll('.leader-table-row')];

      leaderRows.forEach((row, index) => {
        row.addEventListener('click', async () => {
          leaderRows.forEach(r => r.classList.remove('active'));
          row.classList.add('active');
          await selectPlayer(entries[index]);
        });
      });

      if (leaderRows[0]) leaderRows[0].classList.add('active');

      await selectPlayer(entries[0]);
    } else {
      leaderboardRoot.innerHTML = `<div class="detail-empty">Leaderboard unavailable.</div>`;
    }
    await renderLeaderboardHistory();

    status.textContent = `Loaded ${entries.length} players from ${payload.data_source || 'api'}`;

    if (currentUser) {
      await Promise.all([loadRules(), loadWatchlist(), loadAlerts(), loadNotifications()]);
    }

    if (adminToken) await loadAdmin();

  } catch (error) {
    console.error("CardSignal load error:", error);

    status.textContent = `Load failed: ${error.message}`;
    status.style.color = '#9A6656';

    // Graceful fallback: still show Signal of the Week and card section.
    try {
      renderSignalOfTheWeek([]);
      renderCardSection([]);
    } catch (_) {}

    const leaderboardRoot = document.getElementById('leaderboard-table');
    if (leaderboardRoot) {
      leaderboardRoot.innerHTML =
        `<div class="detail-empty">Load failed: ${error.message}</div>`;
    }
  }
}

init();
