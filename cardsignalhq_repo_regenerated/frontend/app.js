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
let piModalEntry = null;
let piModalIntel = null;
let piModalWeeklySnap = null;
let piModalCards = [];
let piModalKeydownHandler = null;
let weeklyIntelligence = null;
let nflWeeklyIntelligence = null;
let nflDataAvailable = false;
let nbaWeeklyIntelligence = null;
let nbaDataAvailable = false;
let activeSportFilter = 'all';
const SCOUTING_REPORT_ALGO = "WEEKLY_INTELLIGENCE_V1";
const playerIntelligenceCache = new Map();

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
async function fetchWeeklyLatest(league = 'MLB') {
  const response = await fetch(`${API_BASE_URL}/api/weekly/latest?league=${encodeURIComponent(league)}`);
  if (!response.ok) return null;
  return response.json();
}
async function fetchPlayerWeeklySignals(playerId) {
  return apiFetch(`/api/players/${playerId}/signals/weekly?limit=12`);
}
async function fetchPlayerIntelligence(league, playerId) {
  const cacheKey = `${String(league).toUpperCase()}:${playerId}`;
  if (playerIntelligenceCache.has(cacheKey)) {
    return playerIntelligenceCache.get(cacheKey);
  }
  const response = await fetch(`${API_BASE_URL}/api/players/${encodeURIComponent(league)}/${encodeURIComponent(playerId)}/intelligence`);
  if (!response.ok) {
    throw new Error(`Intelligence unavailable for ${league} player ${playerId}`);
  }
  const payload = await response.json();
  playerIntelligenceCache.set(cacheKey, payload);
  return payload;
}

async function fetchCardWeeklyIntelligence(csCardId) {
  return apiFetch(`/api/cards/${encodeURIComponent(csCardId)}/intelligence/weekly?limit=2`);
}
async function fetchPlayerSearch(query, sport = null) {
  const filter = sport || activeSportFilter;
  const endpoints = [];
  if (filter === 'all' || filter === 'mlb') {
    endpoints.push(fetch(`${API_BASE_URL}/api/players/search?q=${encodeURIComponent(query)}&sport=MLB`).then((r) => (r.ok ? r.json() : [])));
  }
  if ((filter === 'all' || filter === 'nfl') && nflDataAvailable) {
    endpoints.push(fetch(`${API_BASE_URL}/api/nfl/players/search?q=${encodeURIComponent(query)}`).then((r) => (r.ok ? r.json() : [])));
  }
  if ((filter === 'all' || filter === 'nba') && nbaDataAvailable) {
    endpoints.push(fetch(`${API_BASE_URL}/api/nba/players/search?q=${encodeURIComponent(query)}`).then((r) => (r.ok ? r.json() : [])));
  }
  if (!endpoints.length) return [];
  const batches = await Promise.all(endpoints);
  return batches.flat().filter(Boolean);
}

async function fetchNflPlayer(playerId) {
  const response = await fetch(`${API_BASE_URL}/api/nfl/players/${encodeURIComponent(playerId)}`);
  if (!response.ok) throw new Error("NFL player not found.");
  return response.json();
}

async function fetchNflPerformance(playerId) {
  const response = await fetch(`${API_BASE_URL}/api/nfl/players/${encodeURIComponent(playerId)}/performance`);
  if (!response.ok) return null;
  return response.json();
}

async function fetchNbaPlayer(playerId) {
  const response = await fetch(`${API_BASE_URL}/api/nba/players/${encodeURIComponent(playerId)}`);
  if (!response.ok) throw new Error("NBA player not found.");
  return response.json();
}

async function fetchNbaPerformance(playerId) {
  const response = await fetch(`${API_BASE_URL}/api/nba/players/${encodeURIComponent(playerId)}/performance`);
  if (!response.ok) return null;
  return response.json();
}

function resolveSearchEntryByPlayerId(matches, playerId) {
  const needle = String(playerId || "");
  if (!needle) return null;
  return matches.find((item) => {
    const nflId = SRNfl.srNflResolvePlayerId(item);
    const nbaId = SRNba.srNbaResolvePlayerId(item);
    return String(nflId || nbaId || item.player_id || "") === needle;
  }) || null;
}

async function fetchNbaStatus() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/nba/status`);
    if (!response.ok) return { available: false };
    return response.json();
  } catch (_) {
    return { available: false };
  }
}

async function fetchNflStatus() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/nfl/status`);
    if (!response.ok) return { available: false };
    return response.json();
  } catch (_) {
    return { available: false };
  }
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

function weeklyLeaderToEntry(leader = {}) {
  return {
    player_id: leader.source_player_id || leader.cs_player_id,
    cs_player_id: leader.cs_player_id,
    source_player_id: leader.source_player_id,
    player_name: leader.player_name,
    rank: leader.rank,
    team: leader.team,
    position: leader.position,
    headshot_url: leader.headshot_url,
    team_logo_url: leader.team_logo_url,
    weekly_change: leader.weekly_change,
    league: leader.league,
    sport: leader.sport,
    capabilities: leader.capabilities || leader.intelligence?.capabilities || {},
    intelligence: leader.intelligence || null,
    status: leader.status,
    hotness: {
      total_score: leader.score,
      performance_score: leader.performance,
      market_score: leader.market,
      momentum_score: leader.momentum,
      collector_score: leader.collector,
      confidence_multiplier: 1,
      tag: leader.status || leader.recommendation || 'WATCH',
      reasons: [],
    },
    recommendation: leader.recommendation,
    conviction: leader.conviction,
  };
}

function signalOfWeekToEntry(signal = {}) {
  if (!signal || !signal.player_name) return null;
  return {
    player_id: signal.source_player_id || signal.cs_player_id,
    player_name: signal.player_name,
    rank: signal.rank,
    team: signal.team,
    position: signal.position,
    headshot_url: signal.headshot_url,
    team_logo_url: signal.team_logo_url,
    hotness: {
      total_score: signal.score,
      performance_score: signal.evidence?.performance_score,
      market_score: signal.evidence?.market_score,
      momentum_score: signal.evidence?.momentum_score,
      confidence_multiplier: 1,
      tag: signal.status || 'RISING',
      reasons: [],
    },
    weekly_change: signal.weekly_change,
    recommendation: signal.recommendation,
    conviction: signal.conviction,
    signal_of_week_reason: signal.reason,
  };
}

function weeklyCardRowToIntelItem(row = {}) {
  const label = row.card_label || 'Card';
  const player = row.player_name || 'Player';
  const movementValue = row.movement != null ? row.movement
    : (row.momentum_score != null ? row.momentum_score : row.demand_score);
  return {
    name: `${player} · ${label}`,
    price: row.evidence?.avg_price ?? null,
    movement: movementValue != null ? `${movementValue > 0 ? '+' : ''}${Number(movementValue).toFixed(1)}%` : '—',
    score: row.score != null ? Number(row.score).toFixed(1) : '—',
  };
}

function renderWeeklyRefreshNote() {
  const hero = document.getElementById('signal-center-hero');
  if (!hero) return;
  let note = document.getElementById('weekly-refresh-note');
  if (!note) {
    note = document.createElement('p');
    note.id = 'weekly-refresh-note';
    note.className = 'weekly-refresh-note section-desc';
    hero.appendChild(note);
  }
  const nextRefresh = weeklyIntelligence?.next_refresh;
  const nextLabel = nextRefresh
    ? new Date(nextRefresh).toLocaleString(undefined, { weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
    : null;
  note.textContent = nextLabel
    ? `Updated weekly on Tuesdays · Next refresh ${nextLabel}`
    : 'Updated weekly on Tuesdays';
}

function buildLeaderboard(entries) {
  const movementNote = WeeklyMovement.shouldShowWeeklyMovementNote(weeklyIntelligence)
    ? `<p class="section-desc weekly-movement-note">${WeeklyMovement.WM_MOVEMENT_NOTE}</p>`
    : "";

  return `
    <section class="market-leaders-module sport-section sport-section--mlb" data-sport="mlb">
      <div class="market-leaders-header">
        <div>
          <h2 class="leaders-section-title">Today's Leaders</h2>
          <p class="section-desc">${SECTION_DESCRIPTIONS.leaders}</p>
          ${movementNote}
        </div>
      </div>

      <div class="market-leaders-scroll">
        <div class="market-leaders-table">
          <div class="leaders-table-head">
            <span>Rank</span>
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
            const movement = WeeklyMovement.formatWeeklyMovement(entry);
            const moveClass = WeeklyMovement.weeklyMovementClass(movement);
            const team = getTeamAbbrev(entry);
            const position = entry.position || "—";

            return `
              <button class="leader-table-row" type="button" data-player-index="${index}">
                <span class="leader-rank-small">${entry.rank || index + 1}</span>
                <span class="leader-player-cell">
                  <span class="leader-photo-cell">${renderLeaderHeadshot(entry)}</span>
                  <span class="leader-team-logo-cell">${renderTeamLogoMarkup(entry)}</span>
                  <span class="leader-player-copy">
                    <span class="leader-player-name">${entry.player_name}</span>
                    <span class="leader-player-meta">${team} · ${position}</span>
                  </span>
                </span>
                <span class="leader-number">${formatScore(score)}</span>
                <span class="leader-metric">${formatScore(performance)}</span>
                <span class="leader-metric">${formatScore(market)}</span>
                <span class="leader-trend ${moveClass}">${WeeklyMovement.renderWeeklyMovementLabel(movement)}</span>
                <span class="leader-report-pill">View Report</span>
              </button>
            `;
          }).join("")}
        </div>
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
function csIntelPickConvictionTier(rng) {
  if (rng >= 0.66) return "HIGH";
  if (rng >= 0.33) return "MEDIUM";
  return "LOW";
}

function csIntelRecommendationFromTier(tier) {
  if (tier === "HIGH") return "BUY";
  if (tier === "MEDIUM") return "HOLD";
  return "SELL";
}

function csIntelRecommendationClass(action = "") {
  const key = String(action || "").toLowerCase();
  if (key === "buy") return "cs-recommendation--buy";
  if (key === "hold") return "cs-recommendation--hold";
  if (key === "sell") return "cs-recommendation--sell";
  if (key === "watch") return "cs-recommendation--watch";
  return "";
}

function csIntelConvictionClass(tier = "") {
  if (tier === "HIGH") return "cs-conviction--high";
  if (tier === "MEDIUM") return "cs-conviction--medium";
  return "cs-conviction--low";
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

function formatConvictionTier(tier = "") {
  const key = String(tier || "").toUpperCase();
  if (key === "HIGH") return "High";
  if (key === "MEDIUM") return "Medium";
  return "Low";
}

function getCardSignalLabel(score = 0) {
  const n = Number(score) || 0;
  if (n >= 80) return "Hot";
  if (n >= 65) return "Rising";
  if (n >= 50) return "Watch";
  return "Quiet";
}

function getCardSignalLabelClass(score = 0) {
  const label = getCardSignalLabel(score).toLowerCase();
  if (label === "hot") return "pi-signal-label--hot";
  if (label === "rising") return "pi-signal-label--rising";
  if (label === "watch") return "pi-signal-label--watch";
  return "pi-signal-label--quiet";
}

function getSignalExplanation(type, score, entry = {}) {
  const n = csIntelClamp(Number(score) || 0, 0, 100);
  const name = entry.player_name || "This player";

  if (type === "performance") {
    if (n >= 75) return `${name}'s recent on-field production is among the stronger profiles on the board.`;
    if (n >= 55) return `${name}'s performance trend is supportive, though not yet a dominant driver of the signal.`;
    return `${name}'s recent stats are lagging, which may limit how far collector demand can carry the signal.`;
  }

  if (type === "market") {
    if (n >= 75) return `Card-market activity for ${name} is elevated, with pricing and listing velocity both trending up.`;
    if (n >= 55) return `Market pricing for ${name} shows constructive movement without signs of overheating yet.`;
    return `Market activity around ${name}'s cards remains muted relative to peers on the leaderboard.`;
  }

  if (type === "collector") {
    if (n >= 75) return `Collector demand for ${name} is accelerating faster than typical, suggesting growing chase pressure.`;
    if (n >= 55) return `Collector interest in ${name} is steady, with selective buying on key parallels and rookies.`;
    return `Collector demand for ${name} is still building and may need a catalyst before moving higher.`;
  }

  if (n >= 75) return `Momentum indicators suggest ${name}'s signal could continue strengthening over the next few weeks.`;
  if (n >= 55) return `${name}'s momentum is positive but not yet at a breakout pace.`;
  return `Momentum for ${name} appears to be cooling, which may temper near-term upside.`;
}

function buildWhySignalMatters(entry, intel) {
  const name = entry.player_name || "This player";
  const score = intel.score || 0;
  const status = getSignalOfWeekStatus(entry);
  const recommendation = csIntelRecommendationFromTier(intel.convictionTier);

  if (recommendation === "BUY" && score >= 70) {
    return `${name}'s CardSignal Score reflects a favorable blend of performance and collector demand. The ${status.label.toLowerCase()} status suggests buyers may still have a window before pricing fully catches up.`;
  }

  if (recommendation === "HOLD") {
    return `${name} sits in a balanced signal zone where neither performance nor market activity is decisively leading. This profile may reward patience until a clearer catalyst emerges.`;
  }

  if (status.label === "COOLING") {
    return `${name}'s signal is cooling, which may indicate fading chase pressure or softer market pricing. Watch for whether performance can re-ignite collector interest.`;
  }

  return `${name}'s current CardSignal profile suggests caution — the score reflects weaker alignment across performance, market, and momentum inputs.`;
}

function buildMarketPlaceholders(entry, intel) {
  const key = String(entry?.player_id ?? entry?.player_name ?? "unknown");
  const seed = csIntelHashToUint32(`${key}_market`);
  const rng = csIntelMulberry32(seed);

  const avgSale = 18 + rng() * 185 + (intel.market / 100) * 45;
  const salesVolume = Math.round(4 + rng() * 38 + (intel.momentum / 100) * 12);
  const activeListings = Math.round(12 + rng() * 95 + (intel.collector / 100) * 20);
  const priceMove = ((intel.momentum - 50) / 2.5) + (rng() - 0.5) * 4;

  let liquidity = "Moderate";
  if (intel.market >= 70 && salesVolume >= 20) liquidity = "High";
  else if (intel.market < 45 || salesVolume < 10) liquidity = "Low";

  const name = entry.player_name || "This player";
  let summary = `${name}'s card market shows steady activity with pricing that has not fully reacted to recent signal movement.`;
  if (liquidity === "High") {
    summary = `${name}'s card market is active with supportive liquidity, suggesting buyers and sellers are both engaged at current levels.`;
  } else if (liquidity === "Low") {
    summary = `${name}'s card market appears thin, which may amplify price swings on individual sales.`;
  }

  return {
    avgSale,
    salesVolume,
    activeListings,
    priceMove,
    liquidity,
    summary,
  };
}

function getRiskLevel(intel) {
  const conviction = String(intel.convictionTier || "").toUpperCase();
  const score = intel.score || 0;
  if (conviction === "HIGH" && score >= 75) return "Low";
  if (conviction === "LOW" || score < 45) return "High";
  return "Medium";
}

function buildForecastSummary(entry, intel) {
  const name = entry.player_name || "This player";
  const recommendation = csIntelRecommendationFromTier(intel.convictionTier).toLowerCase();

  if (recommendation === "buy") {
    return `Over the next 2–4 weeks, ${name}'s profile suggests continued collector interest could lift card values, though outcomes are never guaranteed.`;
  }

  if (recommendation === "sell") {
    return `Over the next 2–4 weeks, ${name}'s signal may face headwinds as momentum and market inputs soften relative to recent peaks.`;
  }

  return `Over the next 2–4 weeks, ${name}'s signal appears balanced — the data suggests holding current positions while watching for a clearer directional catalyst.`;
}

function buildForecastReasons(entry, intel) {
  const reasons = [];
  const performance = intel.performance || 0;
  const market = intel.market || 0;
  const collector = intel.collector || 0;
  const momentum = intel.momentum || 0;

  if (performance >= 60) {
    reasons.push("Recent performance suggests strengthening buyer interest.");
  } else if (performance < 45) {
    reasons.push("Recent performance may weigh on near-term collector sentiment.");
  }

  if (collector >= 60) {
    reasons.push("Collector demand appears to be accelerating.");
  } else if (collector < 45) {
    reasons.push("Collector demand could remain soft without a performance catalyst.");
  }

  if (market < 55 && momentum >= 55) {
    reasons.push("Market pricing may not have fully reacted to recent signal movement.");
  } else if (market >= 65) {
    reasons.push("Market pricing already reflects elevated activity around key cards.");
  }

  if (momentum >= 60) {
    reasons.push("Momentum indicators suggest the signal could continue building.");
  }

  if (reasons.length < 3) {
    reasons.push("Supply on recent listings appears limited relative to typical volume.");
  }

  if (reasons.length < 4) {
    reasons.push("The overall signal mix suggests measured positioning rather than aggressive chasing.");
  }

  return reasons.slice(0, 4);
}

const SECTION_DESCRIPTIONS = {
  leaders: "The strongest collector signals across tracked players this week.",
  trending: "Cards gaining the most attention across the market.",
  movers: "The sharpest weekly price and demand movement.",
  buyLow: "Potential value spots before the broader market reacts.",
  chased: "The cards and players collectors are chasing hardest.",
};

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

/* Landing page — Quick Intelligence grid row */
function renderCardIntelRow(item) {
  const moveClass = movementClass(item.movement);

  return `
    <div class="qi-row">
      <div class="qi-row-thumb" aria-hidden="true"></div>
      <div class="qi-row-body">
        <span class="qi-row-name">${item.name}</span>
        <div class="qi-row-metrics">
          <span class="qi-price">${csIntelFormatMoney(item.price)}</span>
          <span class="qi-move ${moveClass}">${item.movement}</span>
          <span class="qi-score-pill">${item.score ?? "—"}</span>
        </div>
      </div>
    </div>
  `;
}

function renderCardIntelBox({ title, modifier, description, items }) {
  return `
    <article class="qi-card qi-card--${modifier}">
      <h3 class="qi-card-title">${title}</h3>
      <p class="qi-card-desc">${description}</p>
      <div class="qi-card-list">
        ${items.slice(0, 3).map((item) => renderCardIntelRow(item)).join("")}
      </div>
    </article>
  `;
}

function renderCardIntelPendingBox({ title, modifier, description }) {
  return `
    <article class="qi-card qi-card--${modifier} qi-card--pending">
      <h3 class="qi-card-title">${title}</h3>
      <p class="qi-card-desc">${description}</p>
      <p class="qi-pending-copy">Card intelligence will appear after the next weekly refresh.</p>
    </article>
  `;
}

function getCardSectionEntry(entries = []) {
  return getSignalOfWeekTopEntry(entries) || entries[0] || getSignalOfWeekPlaceholderEntry();
}

function renderCardSection(entries = [], cardIntel = null) {
  const root = document.getElementById("quick-intelligence-grid")
    || document.getElementById("card-section-grid");
  if (!root) return;

  const stored = cardIntel || weeklyIntelligence?.card_intelligence;
  const boxes = [
    { title: "Trending Cards", modifier: "trending", description: SECTION_DESCRIPTIONS.trending, key: "trending_cards" },
    { title: "Biggest Movers", modifier: "movers", description: SECTION_DESCRIPTIONS.movers, key: "biggest_movers" },
    { title: "Buy Low Watch", modifier: "buy-low", description: SECTION_DESCRIPTIONS.buyLow, key: "buy_low_watch" },
    { title: "Most Chased", modifier: "chased", description: SECTION_DESCRIPTIONS.chased, key: "most_chased" },
  ];

  if (stored) {
    root.innerHTML = boxes.map((box) => {
      const rows = (stored[box.key] || []).map(weeklyCardRowToIntelItem);
      if (!rows.length) {
        return renderCardIntelPendingBox(box);
      }
      return renderCardIntelBox({ ...box, items: rows });
    }).join("");
    return;
  }

  root.innerHTML = boxes.map((box) => renderCardIntelPendingBox(box)).join("");
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
      if (parsed && (parsed.convictionTier || parsed.confidenceTier)) {
        if (!parsed.convictionTier && parsed.confidenceTier) {
          parsed.convictionTier = parsed.confidenceTier;
        }
        csIntelCache.set(key, parsed);
        return parsed;
      }
    }
  } catch (_) {
    // ignore
  }

  const seed = csIntelHashToUint32(key);
  const rng = csIntelMulberry32(seed);

  const convictionTier = csIntelPickConvictionTier(rng());

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
    convictionTier,
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
      action: csIntelRecommendationFromTier(convictionTier),
      conviction: convictionTier,
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

function formatEvidenceTier(tier = "") {
  const key = String(tier || "").toUpperCase();
  if (key === "HIGH") return "HIGH";
  if (key === "MEDIUM") return "MEDIUM";
  if (key === "LOW") return "LOW";
  if (key === "INSUFFICIENT") return "INSUFFICIENT";
  return "INSUFFICIENT";
}

function csIntelEvidenceClass(tier = "") {
  const key = String(tier || "").toUpperCase();
  if (key === "HIGH") return "cs-evidence--high";
  if (key === "MEDIUM") return "cs-evidence--medium";
  if (key === "LOW") return "cs-evidence--low";
  return "cs-evidence--insufficient";
}

function formatStatValue(value, { decimals = 3, suffix = "", pending = "—" } = {}) {
  const n = csIntelSafeToNumber(value);
  if (n === null) return pending;
  return `${n.toFixed(decimals)}${suffix}`;
}

function formatStatCount(value, pending = "—") {
  const n = csIntelSafeToNumber(value);
  if (n === null) return pending;
  return String(Math.round(n));
}

function looksLikeUuid(value) {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(String(value || "").trim());
}

function mlbSourceIdFromValue(value) {
  if (value == null || value === "") return null;
  const raw = String(value).trim();
  if (looksLikeUuid(raw)) return null;
  if (/^mlb:/i.test(raw)) {
    const inner = raw.slice(4);
    return /^\d+$/.test(inner) ? inner : null;
  }
  return /^\d+$/.test(raw) ? raw : null;
}

function normalizeCsPlayerId(entry = {}) {
  const explicitCs = entry.cs_player_id ? String(entry.cs_player_id) : "";
  if (explicitCs.startsWith("CS-NFL-P-") || explicitCs.startsWith("CS-NBA-P-")) return explicitCs;
  const fromCs = mlbSourceIdFromValue(explicitCs);
  if (fromCs) return `mlb:${fromCs}`;

  const mlbId = mlbSourceIdFromValue(entry.source_player_id) || mlbSourceIdFromValue(entry.player_id);
  if (mlbId && !isNflEntry(entry) && !isNbaEntry(entry)) return `mlb:${mlbId}`;

  const pid = entry.cs_player_id || entry.player_id || entry.source_player_id;
  if (!pid) return null;
  const raw = String(pid);
  if (looksLikeUuid(raw)) return null;
  if (raw.startsWith("CS-NFL-P-") || raw.startsWith("CS-NBA-P-") || raw.includes(":")) return raw;
  const league = String(entry.league || entry.sport || "").toUpperCase();
  if (league === "NFL" || league === "FOOTBALL") return `CS-NFL-P-${raw}`;
  if (league === "NBA" || league === "BASKETBALL") return `CS-NBA-P-${raw}`;
  return `mlb:${raw}`;
}

function hasStoredPipelineReportData(player = {}) {
  if (!player || typeof player !== "object") return false;
  const hotness = player.hotness || {};
  const hasHotness = hotness.total_score != null || hotness.performance_score != null || hotness.market_score != null;
  const hasStats = Boolean(player.stats_7d || player.stats_30d);
  const snapshots = player.market_snapshots;
  const hasMarket = Boolean(snapshots && typeof snapshots === "object" && Object.keys(snapshots).length);
  return Boolean(player.player_name && (hasHotness || hasStats || hasMarket));
}

async function resolveMlbSourcePlayerId(entry = {}) {
  const direct = mlbSourceIdFromValue(entry.source_player_id) || mlbSourceIdFromValue(entry.player_id);
  if (direct) return direct;
  const name = String(entry.player_name || "").trim();
  if (name.length < 2) return null;
  try {
    const matches = await fetchPlayerSearch(name, "mlb");
    const list = Array.isArray(matches) ? matches : [];
    const needle = name.toLowerCase();
    const exact = list.find((item) => String(item.player_name || "").trim().toLowerCase() === needle);
    if (!exact) return null;
    return mlbSourceIdFromValue(exact.source_player_id || exact.player_id);
  } catch (_) {
    return null;
  }
}

async function loadScoutingReportModel(entry) {
  let player = entry;
  const nflPlayerId = SRNfl.srNflResolvePlayerId(entry);
  const nbaPlayerId = SRNba.srNbaResolvePlayerId(entry);
  if (isNflEntry(entry) && nflPlayerId) {
    try {
      player = await fetchNflPlayer(nflPlayerId);
    } catch (_) {
      player = { ...entry, player_id: nflPlayerId };
    }
  } else if (isNbaEntry(entry) && nbaPlayerId) {
    try {
      player = await fetchNbaPlayer(nbaPlayerId);
    } catch (_) {
      player = { ...entry, player_id: nbaPlayerId };
    }
  } else if (entry.player_id && !isNflEntry(entry) && !isNbaEntry(entry)) {
    try {
      player = { ...entry, ...(await fetchPlayer(entry.player_id)) };
    } catch (_) {
      player = entry;
    }
  }

  let normalizedPayload = entry.intelligence || player.intelligence || null;
  const league = resolvePlayerLeague(player, null, normalizedPayload);
  const isMlb = league === "MLB" && !isNflEntry(player) && !isNbaEntry(player);

  if (isMlb) {
    const mlbSourceId = await resolveMlbSourcePlayerId(player);
    if (mlbSourceId) {
      player = {
        ...player,
        source_player_id: String(mlbSourceId),
        cs_player_id: player.cs_player_id && !looksLikeUuid(player.cs_player_id)
          ? player.cs_player_id
          : `mlb:${mlbSourceId}`,
      };
    }
  }

  const playerKey = isMlb
    ? (mlbSourceIdFromValue(player.source_player_id) || mlbSourceIdFromValue(player.player_id))
    : (player.source_player_id || player.player_id || player.cs_player_id);

  if (!normalizedPayload && playerKey) {
    try {
      normalizedPayload = await fetchPlayerIntelligence(league, playerKey);
    } catch (_) {
      normalizedPayload = null;
    }
  }

  let weeklySnap = null;
  const weeklyPlayerKey = isMlb
    ? (normalizeCsPlayerId(player) || (mlbSourceIdFromValue(player.source_player_id) ? `mlb:${mlbSourceIdFromValue(player.source_player_id)}` : null))
    : (player.cs_player_id || normalizeCsPlayerId(player));
  if (!normalizedPayload && weeklyPlayerKey) {
    try {
      const weeklyData = await fetchPlayerWeeklySignals(weeklyPlayerKey);
      weeklySnap = resolveWeeklySnapshot(player, weeklyData?.items || []);
    } catch (_) {
      weeklySnap = null;
    }
  }

  if (!normalizedPayload && !weeklySnap && !hasStoredPipelineReportData(player) && !hasStoredPipelineReportData(entry)) {
    throw new Error("Stored intelligence is unavailable for this player.");
  }

  const reportPlayer = hasStoredPipelineReportData(player) ? player : entry;
  const intel = buildPlayerIntel(reportPlayer, weeklySnap, normalizedPayload);
  return {
    player: reportPlayer,
    intel,
    weeklySnap,
    normalizedPayload,
    intelligenceLookupId: playerKey || null,
  };
}

function isNbaEntry(entry = {}) {
  const league = String(entry.league || entry.sport || '').toUpperCase();
  const csId = String(entry.cs_player_id || '');
  return league === 'NBA' || league === 'BASKETBALL' || csId.startsWith('CS-NBA-P-');
}

function isNflEntry(entry = {}) {
  const league = String(entry.league || entry.sport || '').toUpperCase();
  const csId = String(entry.cs_player_id || '');
  return league === 'NFL' || league === 'FOOTBALL' || csId.startsWith('CS-NFL-P-');
}

function resolveWeeklySnapshot(entry = {}, weeklyHistory = []) {
  const csId = normalizeCsPlayerId(entry);
  if (!weeklyHistory.length) return null;
  if (csId) {
    const match = [...weeklyHistory].reverse().find((snap) => snap.cs_player_id === csId);
    if (match) return match;
  }
  return weeklyHistory[weeklyHistory.length - 1] || null;
}

function deriveEvidenceTier(weeklySnap, entry = {}, normalizedPayload = null) {
  if (normalizedPayload?.evidence) return formatEvidenceTier(normalizedPayload.evidence);
  const stored = weeklySnap?.conviction || entry.conviction;
  if (!stored) return "INSUFFICIENT";
  return formatEvidenceTier(stored);
}

function resolvePlayerLeague(entry = {}, weeklySnap = null, normalizedPayload = null) {
  if (normalizedPayload?.league) return String(normalizedPayload.league).toUpperCase();
  if (weeklySnap?.league) return String(weeklySnap.league).toUpperCase();
  if (isNflEntry(entry)) return "NFL";
  if (isNbaEntry(entry)) return "NBA";
  return "MLB";
}

function resolveRecommendation(entry = {}, weeklySnap = null) {
  const rec = weeklySnap?.recommendation || entry.recommendation;
  if (rec) return String(rec).toUpperCase();
  return "WATCH";
}

function hasStoredRecommendation(entry = {}, weeklySnap = null) {
  return !!(weeklySnap?.recommendation || entry.recommendation);
}

function getReportStatus(entry = {}, weeklySnap = null) {
  const statusRaw = String(weeklySnap?.status || entry.status || "").toUpperCase();
  if (!statusRaw) {
    return { label: "Watch", emoji: "⚠", className: "sr-status--watch" };
  }
  if (statusRaw.includes("STABLE")) {
    return { label: "Stable", emoji: "➡", className: "sr-status--stable" };
  }
  if (statusRaw.includes("COOL")) {
    return { label: "Cooling", emoji: "📉", className: "sr-status--cooling" };
  }
  if (statusRaw.includes("HOT")) {
    return { label: "HOT", emoji: "🔥", className: "sr-status--hot" };
  }
  if (statusRaw.includes("RISING")) {
    return { label: "Rising", emoji: "📈", className: "sr-status--rising" };
  }
  if (statusRaw.includes("WATCH")) {
    return { label: "Watch", emoji: "⚠", className: "sr-status--watch" };
  }
  return { label: "Watch", emoji: "⚠", className: "sr-status--watch" };
}

function deriveEvidenceQuality(score, missingKeys = [], requiredKey = null) {
  if (requiredKey && missingKeys.includes(requiredKey)) return "INSUFFICIENT";
  if (csIntelSafeToNumber(score) === null) return "INSUFFICIENT";
  return null;
}

function getCardIdentityFields(card = {}) {
  const source = card.identity || card.registry || card;
  return {
    year: source.card_year ?? source.year ?? null,
    brand: source.brand ?? null,
    set: source.set ?? null,
    parallel: source.parallel ?? null,
    card_number: source.card_number ?? null,
    grade: source.grade ?? null,
    grading_company: source.grading_company ?? null,
  };
}

function hasCardRegistryIdentity(card = {}) {
  const fields = getCardIdentityFields(card);
  return !!(fields.year || fields.brand || fields.set);
}

function formatCardIdentityHtml(card = {}) {
  const fields = getCardIdentityFields(card);
  if (!hasCardRegistryIdentity(card)) return null;

  const titleParts = [fields.year, fields.brand, fields.set].filter((part) => part != null && part !== "");
  const lines = [];

  if (titleParts.length) {
    lines.push(`<p class="sr-card-title">${titleParts.join(" ")}</p>`);
  }
  if (fields.parallel) {
    lines.push(`<p class="sr-card-meta">${fields.parallel}</p>`);
  }
  if (fields.card_number) {
    lines.push(`<p class="sr-card-number">#${fields.card_number}</p>`);
  }
  if (fields.grade) {
    const gradeLine = [fields.grading_company, fields.grade].filter(Boolean).join(" ");
    lines.push(`<p class="sr-card-grade">${gradeLine}</p>`);
  } else if (fields.grading_company) {
    lines.push(`<p class="sr-card-grade">${fields.grading_company}</p>`);
  }

  return lines.length ? lines.join("") : null;
}

function parseStoredContributorDirection(value, fallback = "up") {
  const n = csIntelSafeToNumber(value);
  if (n === null) return fallback;
  return n >= 0 ? "up" : "down";
}

function buildStoredPlayerIntel(entry = {}, weeklySnap = null, normalizedPayload = null) {
  const payload = normalizedPayload || entry.intelligence || weeklySnap?.intelligence || null;
  if (payload) {
    return SRIntel.srIntelFromNormalized(payload, entry);
  }

  const hotness = entry.hotness || {};
  const missing = weeklySnap?.missing_inputs || [];
  const snapEvidence = weeklySnap?.evidence || {};
  const capabilities = weeklySnap?.capabilities || snapEvidence.capabilities || {};
  const isNfl = isNflEntry(entry) || weeklySnap?.league === 'NFL' || weeklySnap?.sport === 'FOOTBALL';
  const isNba = isNbaEntry(entry) || weeklySnap?.league === 'NBA' || weeklySnap?.sport === 'BASKETBALL';
  const nflReport = isNfl ? SRNfl.srNflMapScoutingReport(entry, weeklySnap) : null;
  const nbaReport = isNba ? SRNba.srNbaMapScoutingReport(entry, weeklySnap) : null;

  return {
    normalizedPayload: null,
    score: csIntelSafeToNumber(weeklySnap?.card_signal_score ?? hotness.total_score),
    performance: csIntelSafeToNumber(weeklySnap?.performance_score ?? hotness.performance_score),
    market: csIntelSafeToNumber(weeklySnap?.market_score ?? hotness.market_score),
    collector: csIntelSafeToNumber(weeklySnap?.collector_score ?? hotness.collector_score),
    momentum: csIntelSafeToNumber(weeklySnap?.momentum_score ?? hotness.momentum_score),
    scarcity: csIntelSafeToNumber(weeklySnap?.scarcity_score),
    evidenceTier: deriveEvidenceTier(weeklySnap, entry),
    recommendation: resolveRecommendation(entry, weeklySnap),
    hasStoredRecommendation: hasStoredRecommendation(entry, weeklySnap),
    weeklyChange: csIntelSafeToNumber(weeklySnap?.weekly_change ?? entry.weekly_change),
    evidence: snapEvidence,
    missingInputs: missing,
    capabilities,
    signalDrivers: weeklySnap?.signal_drivers || snapEvidence.signal_drivers || snapEvidence.nfl_signal_drivers || [],
    mappedDrivers: SRIntel.srMapNormalizedDrivers(weeklySnap?.signal_drivers || snapEvidence.signal_drivers || snapEvidence.nfl_signal_drivers || []),
    algorithmVersion: weeklySnap?.algorithm_version || weeklyIntelligence?.run?.algorithm_version || SCOUTING_REPORT_ALGO,
    capturedAt: weeklySnap?.captured_at || entry.generated_at || weeklyIntelligence?.run?.completed_at,
    stats7d: nbaReport?.recentStats || nflReport?.recentStats || entry.stats_7d || snapEvidence.nba_recent_stats || snapEvidence.nfl_recent_stats || null,
    stats30d: nbaReport?.seasonStats || nflReport?.seasonStats || entry.stats_30d || snapEvidence.nba_season_stats || snapEvidence.nfl_season_stats || null,
    marketSnapshots: entry.market_snapshots || snapEvidence.market_snapshots || {},
    isNfl,
    isNba,
    isMlb: !isNfl && !isNba,
    nfl: nflReport,
    nba: nbaReport,
    nflSeasonPhase: weeklySnap?.season_phase || nflReport?.nflSeasonPhase || snapEvidence.nfl_season_phase || null,
    nbaSeasonPhase: nbaReport?.nbaSeasonPhase || null,
    recentWindowLabel: weeklySnap?.recent_window_label || snapEvidence.recent_window_label || null,
    seasonPhase: weeklySnap?.season_phase || snapEvidence.season_phase || null,
  };
}

function hasPerformanceStats(stats) {
  return stats && Number(stats.games) > 0;
}

function srMetricFormatters() {
  return {
    money: (value) => csIntelFormatMoney(value),
    percent: (value) => csIntelFormatPercent(value),
    score: (value) => formatScore(value),
  };
}

function renderSnapshotStat(label, value, { title = "" } = {}) {
  const titleAttr = title ? ` title="${title}"` : "";
  return `
    <div class="sr-snapshot-stat">
      <span class="sr-snapshot-stat-value"${titleAttr}>${value}</span>
      <span class="sr-snapshot-stat-label">${label}</span>
    </div>`;
}

function renderPlayerSnapshot(intel, entry = {}) {
  const stats7d = intel.stats7d;
  const stats30d = intel.stats30d;
  const previousSeason = intel.previousSeasonStats;
  const isOffseason = intel.seasonPhase === "OFFSEASON" || intel.nflSeasonPhase === "OFFSEASON" || intel.nba?.nbaSeasonPhase === "OFFSEASON";
  const has7d = hasPerformanceStats(stats7d) || (stats7d && Object.keys(stats7d).length > 1);
  const hasSeason = hasPerformanceStats(stats30d) || (stats30d && Object.keys(stats30d).length > 1);
  const hasPreviousSeason = previousSeason && Object.keys(previousSeason).length > 0;
  const formatters = srMetricFormatters();
  const position = entry.position || piModalEntry?.position || '';
  const nflSpecs = intel.isNfl ? SRMetrics.srGetNflStatSpecs(position) : null;
  const nbaSpecs = intel.isNba ? SRMetrics.srGetNbaStatSpecs() : null;
  const nfl = intel.nfl;
  const nba = intel.nba;

  let recentTitle = 'Last 7 Days';
  let seasonTitle = 'Season Performance';
  let recentMeta = '';
  let seasonMeta = '';
  const helperText = intel.previousSeasonHelperText || null;
  if (intel.isNfl && nfl) {
    recentTitle = nfl.recentWindowLabel;
    seasonTitle = isOffseason ? (intel.previousSeasonLabel || nfl.previousSeasonLabel || nfl.seasonWindowLabel) : nfl.seasonWindowLabel;
    recentMeta = `<p class="sr-section-lead">${nfl.performancePeriodNote}: ${nfl.recentDateRange}${nfl.gamesInWindow != null ? ` · ${nfl.gamesInWindow} games` : ""}</p>`;
    seasonMeta = isOffseason && (helperText || nfl.previousSeasonHelperText)
      ? `<p class="sr-section-lead">${helperText || nfl.previousSeasonHelperText}</p>`
      : `<p class="sr-section-lead">${nfl.performancePeriodNote}: ${nfl.seasonDateRange}</p>`;
  } else if (intel.isNba && nba) {
    recentTitle = nba.recentWindowLabel;
    seasonTitle = isOffseason ? (intel.previousSeasonLabel || nba.previousSeasonLabel || nba.seasonWindowLabel) : nba.seasonWindowLabel;
    recentMeta = `<p class="sr-section-lead">${nba.performancePeriodNote}: ${nba.recentDateRange}${nba.gamesInWindow != null ? ` · ${nba.gamesInWindow} games` : ""}</p>`;
    seasonMeta = isOffseason && (helperText || nba.previousSeasonHelperText)
      ? `<p class="sr-section-lead">${helperText || nba.previousSeasonHelperText}</p>`
      : `<p class="sr-section-lead">${nba.performancePeriodNote}: ${nba.seasonDateRange}</p>`;
  } else if (isOffseason && intel.previousSeasonLabel) {
    seasonTitle = intel.previousSeasonLabel;
    if (helperText) {
      seasonMeta = `<p class="sr-section-lead">${helperText}</p>`;
    }
  } else if (intel.seasonLabel || intel.season) {
    const label = intel.seasonLabel || intel.season;
    seasonTitle = `${label} Season Performance`;
  }

  const seasonStatsSource = isOffseason && hasPreviousSeason ? previousSeason : stats30d;
  const hasSeasonPanel = isOffseason ? (hasPreviousSeason || !!intel.previousSeasonLabel) : hasSeason;
  const offseasonUnavailable = isOffseason && !hasPreviousSeason;

  const last7Body = has7d
    ? `
      <div class="sr-snapshot-grid">
        ${(nbaSpecs ? nbaSpecs.recent : nflSpecs ? nflSpecs.recent : SRMetrics.SR_PLAYER_STAT_SPECS.last7d).map((spec) => {
    const stat = SRMetrics.srFormatPlayerStat(spec, stats7d, formatters);
    return renderSnapshotStat(stat.label, stat.display, { title: stat.title });
  }).join("")}
      </div>`
    : `<p class="sr-pending">Performance data pending.</p>`;

  const seasonBody = offseasonUnavailable
    ? `<p class="sr-pending">Previous season performance unavailable</p>`
    : hasSeasonPanel
    ? `
      <div class="sr-snapshot-grid">
        ${(nbaSpecs ? nbaSpecs.season : nflSpecs ? nflSpecs.season : SRMetrics.SR_PLAYER_STAT_SPECS.season).map((spec) => {
    const stat = SRMetrics.srFormatPlayerStat(spec, seasonStatsSource, formatters);
    return renderSnapshotStat(stat.label, stat.display, { title: stat.title });
  }).join("")}
      </div>`
    : `<p class="sr-pending">Performance data pending.</p>`;

  const showRecent = (!intel.isNfl && !intel.isNba && !isOffseason) || (nfl && nfl.showRecentPanel) || (nba && nba.showRecentPanel) || (intel.showRecentPanel && !isOffseason);

  return `
    <section class="sr-section sr-snapshot">
      <h3 class="sr-section-title">Player Snapshot</h3>
      <div class="sr-snapshot-panels">
        ${showRecent ? `<article class="sr-panel">
          <h4 class="sr-panel-title">${recentTitle}</h4>
          ${recentMeta}
          ${last7Body}
        </article>` : ''}
        <article class="sr-panel">
          <h4 class="sr-panel-title">${seasonTitle}</h4>
          ${seasonMeta}
          ${seasonBody}
        </article>
      </div>
    </section>`;
}

function renderMlbSignalDrivers(intel) {
  if (!intel?.isMlb) return "";
  const drivers = intel.mappedDrivers || SRIntel.srMapNormalizedDrivers(intel.signalDrivers || []);
  const body = drivers.length
    ? `
      <div class="sr-mlb-drivers">
        ${drivers.map((driver) => `
          <article class="sr-mlb-driver">
            <div class="sr-mlb-driver-head">
              <strong>${driver.title}</strong>
              <span class="sr-mlb-driver-source">${driver.sourceType}</span>
            </div>
            <p class="sr-mlb-driver-summary">${driver.summary}</p>
            <div class="sr-mlb-driver-meta">
              <span>Occurred: ${driver.occurredAt}</span>
            </div>
          </article>`).join("")}
      </div>`
    : `<p class="sr-pending">No verified MLB Signal Drivers are available yet.</p>`;

  return `
    <section class="sr-section sr-mlb-drivers-section">
      <h3 class="sr-section-title">MLB Signal Drivers</h3>
      <p class="sr-section-lead">Verified baseball developments from stored performance evidence only.</p>
      ${body}
    </section>`;
}

function renderNflSignalDrivers(intel) {
  if (!intel?.isNfl || !intel?.nfl) return "";
  const driverTitle = (intel.showOffseasonDrivers || intel.nfl?.showOffseasonDrivers) ? (intel.offseasonDriverLabel || intel.nfl?.offseasonDriverLabel || "Offseason Signal Drivers") : "NFL Signal Drivers";
  const drivers = intel.mappedDrivers?.length ? intel.mappedDrivers.map((d) => ({
    title: d.title,
    summary: d.summary,
    sourceType: d.sourceType,
    impact: d.impact,
    evidenceQuality: d.evidenceQuality,
    occurredAt: d.occurredAt,
  })) : (intel.nfl.signalDrivers || []);
  const body = drivers.length
    ? `
      <div class="sr-nfl-drivers">
        ${drivers.map((driver) => `
          <article class="sr-nfl-driver">
            <div class="sr-nfl-driver-head">
              <strong>${driver.title}</strong>
              <span class="sr-nfl-driver-source">${driver.sourceType}</span>
            </div>
            <p class="sr-nfl-driver-summary">${driver.summary}</p>
            <div class="sr-nfl-driver-meta">
              <span>Impact: ${driver.impact}</span>
              <span>Evidence: ${driver.evidenceQuality}</span>
              <span>Occurred: ${driver.occurredAt}</span>
            </div>
          </article>`).join("")}
      </div>`
    : `<p class="sr-pending">${SRNfl.SR_NFL_NO_DRIVERS}</p>`;

  return `
    <section class="sr-section sr-nfl-drivers-section">
      <h3 class="sr-section-title">${driverTitle}</h3>
      <p class="sr-section-lead">Verified football developments from stored evidence only.</p>
      ${body}
    </section>`;
}

function renderNbaSignalDrivers(intel) {
  if (!intel?.isNba || !intel?.nba) return "";
  const driverTitle = (intel.showOffseasonDrivers || intel.nba?.showOffseasonDrivers) ? (intel.offseasonDriverLabel || intel.nba?.offseasonDriverLabel || "Offseason Signal Drivers") : "NBA Signal Drivers";
  const drivers = intel.mappedDrivers?.length ? intel.mappedDrivers.map((d) => ({
    title: d.title,
    summary: d.summary,
    sourceType: d.sourceType,
    impact: d.impact,
    evidenceQuality: d.evidenceQuality,
    occurredAt: d.occurredAt,
  })) : (intel.nba.signalDrivers || []);
  const body = drivers.length
    ? `
      <div class="sr-nba-drivers">
        ${drivers.map((driver) => `
          <article class="sr-nba-driver">
            <div class="sr-nba-driver-head">
              <strong>${driver.title}</strong>
              <span class="sr-nba-driver-source">${driver.sourceType}</span>
            </div>
            <p class="sr-nba-driver-summary">${driver.summary}</p>
            <div class="sr-nba-driver-meta">
              <span>Impact: ${driver.impact}</span>
              <span>Evidence: ${driver.evidenceQuality}</span>
              <span>Occurred: ${driver.occurredAt}</span>
            </div>
          </article>`).join("")}
      </div>`
    : `<p class="sr-pending">${SRNba.SR_NBA_NO_DRIVERS}</p>`;

  return `
    <section class="sr-section sr-nba-drivers-section">
      <h3 class="sr-section-title">${driverTitle}</h3>
      ${body}
    </section>`;
}

function buildSignalContributors(entry, intel, weeklySnap = null) {
  const contributors = [];
  if (intel.isNfl || intel.isNba) {
    return contributors;
  }
  const stats7d = intel.stats7d;
  const stats30d = intel.stats30d;
  const evidence = intel.evidence || {};

  if (hasPerformanceStats(stats7d)) {
    const avg = csIntelSafeToNumber(stats7d.avg);
    if (avg !== null) {
      contributors.push({
        label: "Last 7 Day AVG",
        direction: hasPerformanceStats(stats30d) ? (avg >= stats30d.avg ? "up" : "down") : "up",
        detail: avg.toFixed(3),
      });
    }

    const homeRuns = csIntelSafeToNumber(stats7d.home_runs);
    if (homeRuns !== null && homeRuns > 0) {
      contributors.push({
        label: "Home Runs",
        direction: "up",
        detail: `${Math.round(homeRuns)} in the last 7 days`,
      });
    }

    const ops = csIntelSafeToNumber(stats7d.ops);
    if (ops !== null && ops > 0) {
      contributors.push({
        label: "OPS",
        direction: hasPerformanceStats(stats30d) ? (ops >= stats30d.ops ? "up" : "down") : "up",
        detail: ops.toFixed(3),
      });
    }

    const rbi = csIntelSafeToNumber(stats7d.rbi);
    if (rbi !== null && rbi > 0) {
      contributors.push({
        label: "RBI",
        direction: "up",
        detail: `${Math.round(rbi)} in the last 7 days`,
      });
    }
  }

  (evidence.performance_reasons || []).forEach((reason) => {
    contributors.push({ label: "Performance", direction: "up", detail: reason });
  });

  (evidence.momentum_evidence || []).forEach((line) => {
    const text = String(line);
    const opsDelta = text.match(/ops_delta=([+-]?\d+(?:\.\d+)?)/);
    if (opsDelta) {
      const delta = Number(opsDelta[1]);
      if (Number.isFinite(delta)) {
        contributors.push({
          label: "OPS Movement",
          direction: parseStoredContributorDirection(delta),
          detail: `${delta >= 0 ? "+" : ""}${delta.toFixed(3)} vs 30-day baseline`,
        });
        return;
      }
    }
    contributors.push({ label: "Momentum", direction: "up", detail: text });
  });

  const weeklyChange = csIntelSafeToNumber(weeklySnap?.weekly_change ?? intel.weeklyChange);
  if (weeklyChange !== null && weeklyChange !== 0) {
    contributors.push({
      label: "CardSignal Score",
      direction: parseStoredContributorDirection(weeklyChange),
      detail: `${weeklyChange > 0 ? "+" : ""}${weeklyChange.toFixed(1)} weekly change`,
    });
  }

  (evidence.collector_evidence || []).forEach((line) => {
    contributors.push({ label: "Collector Demand", direction: "up", detail: String(line) });
  });

  (evidence.scarcity_evidence || []).forEach((line) => {
    contributors.push({ label: "Scarcity", direction: "up", detail: String(line) });
  });

  return contributors;
}

function renderWhyThisSignal(entry, intel, weeklySnap = null) {
  const contributors = buildSignalContributors(entry, intel, weeklySnap);
  const mlbDriversSection = intel.isMlb ? renderMlbSignalDrivers(intel) : "";
  const nflDriversSection = intel.isNfl ? renderNflSignalDrivers(intel) : "";
  const nbaDriversSection = intel.isNba ? renderNbaSignalDrivers(intel) : "";
  const body = contributors.length
    ? `
      <div class="sr-contributors">
        <p class="sr-contributors-label">Signal Contributors</p>
        ${contributors.map((c) => `
          <div class="sr-contributor">
            <span class="sr-contributor-arrow sr-contributor-arrow--${c.direction}">${c.direction === "up" ? "⬆" : "⬇"}</span>
            <div class="sr-contributor-copy">
              <strong>${c.label}</strong>
              <span>${c.detail}</span>
            </div>
          </div>`).join("")}
      </div>`
    : `<p class="sr-pending">Signal contributor data pending.</p>`;

  return `
    <section class="sr-section">
      <h3 class="sr-section-title">Why This Signal</h3>
      <p class="sr-section-lead">How recent performance and market activity shaped this week's CardSignal Score.</p>
      ${body}
      ${mlbDriversSection}
      ${nflDriversSection}
      ${nbaDriversSection}
    </section>`;
}

function collectPlayerCards(entry) {
  const csId = normalizeCsPlayerId(entry);
  const cardIntel = weeklyIntelligence?.card_intelligence || {};
  const sections = ["trending_cards", "biggest_movers", "buy_low_watch", "most_chased"];
  const seen = new Set();
  const cards = [];

  sections.forEach((key) => {
    (cardIntel[key] || []).forEach((row) => {
      if (csId && row.cs_player_id !== csId) return;
      if (!row.cs_card_id || seen.has(row.cs_card_id)) return;
      seen.add(row.cs_card_id);
      cards.push(row);
    });
  });

  return cards;
}

async function enrichPlayerCards(cards = []) {
  const enriched = [];
  for (const card of cards) {
    if (!card.cs_card_id) continue;
    try {
      const data = await fetchCardWeeklyIntelligence(card.cs_card_id);
      const items = data?.items || [];
      const latest = items.length ? items[items.length - 1] : null;
      enriched.push(latest ? { ...card, ...latest } : card);
    } catch (_) {
      enriched.push(card);
    }
  }
  return enriched;
}

function resolveStoredCardRecommendation(card = {}) {
  return card.recommendation ? String(card.recommendation).toUpperCase() : "WATCH";
}

function renderReportCardPanel(card) {
  const evidence = card.evidence || {};
  const tags = evidence.tags || {};
  const psaPop = tags.psa10_count != null ? formatStatCount(tags.psa10_count, "PSA population pending.") : "PSA population pending.";
  const identityHtml = formatCardIdentityHtml(card);
  const rec = resolveStoredCardRecommendation(card);
  const recClass = csIntelRecommendationClass(rec.toLowerCase());
  const metrics = SRMetrics.srBuildCardMetrics(card, srMetricFormatters());

  const metricRow = (metric) => `
    <div class="sr-card-metric">
      <span class="sr-card-metric-label">${metric.label}</span>
      <span class="sr-card-metric-value${metric.pending ? " sr-pending--inline" : ""}">${metric.display}</span>
    </div>`;

  return `
    <article class="sr-card-panel" data-cs-card-id="${card.cs_card_id || ""}">
      <div class="sr-card-identity">
        ${identityHtml || `<p class="sr-pending">Card registry data is still being linked.</p>`}
      </div>
      <div class="sr-card-metrics">
        ${metricRow(metrics.medianActivePrice)}
        ${metricRow(metrics.averageActivePrice)}
        ${metricRow(metrics.priceMovement7d)}
        ${!metrics.momentumScore.pending ? metricRow(metrics.momentumScore) : ""}
        ${metricRow(metrics.activeListings)}
        <div class="sr-card-metric">
          <span class="sr-card-metric-label">PSA Population</span>
          <span class="sr-card-metric-value">${psaPop}</span>
        </div>
        <div class="sr-card-metric">
          <span class="sr-card-metric-label">CardSignal Score</span>
          <span class="sr-card-metric-value">${card.card_signal_score != null ? formatScore(card.card_signal_score) : card.score != null ? formatScore(card.score) : "Pending"}</span>
        </div>
        <div class="sr-card-metric">
          <span class="sr-card-metric-label">Recommendation</span>
          <span class="cs-recommendation-badge ${recClass} sr-card-rec">${rec}</span>
        </div>
      </div>
      <p class="sr-card-evidence">
        <span class="sr-evidence-label">Evidence</span>
        ${evidence.listings_count
    ? `Based on ${evidence.listings_count} active listing${evidence.listings_count === 1 ? "" : "s"} in stored market snapshots.`
    : "Market history still building."}
      </p>
    </article>`;
}

function renderReportCards(cards = []) {
  const body = cards.length
    ? `<div class="sr-cards-list">${cards.map((c) => renderReportCardPanel(c)).join("")}</div>`
    : `<p class="sr-pending">Card intelligence pending for this player.</p>`;

  return `
    <section class="sr-section">
      <h3 class="sr-section-title">Cards</h3>
      <p class="sr-section-lead">Tracked cards linked to this player through stored weekly intelligence.</p>
      ${body}
    </section>`;
}

function renderReportMarket(entry, intel, weeklySnap = null) {
  const metrics = SRMetrics.srBuildMarketMetrics(intel, weeklySnap, srMetricFormatters());
  const missing = intel.missingInputs || [];
  const dataQuality = missing.length === 0 ? "Complete" : missing.length <= 2 ? "Partial" : "Building";
  const hasAnyMarketField = Object.values(metrics).some((metric) => !metric.pending);
  const summary = SRMetrics.srBuildMarketSummary(metrics);

  if (!hasAnyMarketField) {
    return `
      <section class="sr-section">
        <h3 class="sr-section-title">Market</h3>
        <p class="sr-pending">Market history still building.</p>
      </section>`;
  }

  const marketItem = (metric) => `
    <div class="sr-market-item">
      <span class="sr-market-label">${metric.label}</span>
      <span class="sr-market-value${metric.pending ? " sr-pending--inline" : ""}">${metric.display}</span>
    </div>`;

  return `
    <section class="sr-section">
      <h3 class="sr-section-title">Market</h3>
      <p class="sr-section-lead">${summary}</p>
      <div class="sr-market-grid">
        ${marketItem(metrics.medianActivePrice)}
        ${marketItem(metrics.averageActivePrice)}
        ${marketItem(metrics.activeListings)}
        ${marketItem(metrics.auctionCount)}
        ${marketItem(metrics.listingsWithBids)}
        ${marketItem(metrics.marketDepth)}
        <div class="sr-market-item">
          <span class="sr-market-label">Data Quality</span>
          <span class="sr-market-value">${dataQuality}</span>
        </div>
        <div class="sr-market-item">
          <span class="sr-market-label">Captured</span>
          <span class="sr-market-value">${intel.capturedAt ? formatTimestamp(intel.capturedAt) : "Pending"}</span>
        </div>
      </div>
    </section>`;
}

function renderSignalCategory(label, score, explanation, quality) {
  const v = csIntelSafeToNumber(score);
  const evidenceHtml = quality
    ? `<p class="sr-signal-category-evidence">
        <span class="sr-evidence-label">Evidence</span>
        <span class="cs-evidence-badge ${csIntelEvidenceClass(quality)}">${quality}</span>
      </p>`
    : "";

  return `
    <article class="sr-signal-category">
      <div class="sr-signal-category-head">
        <h4 class="sr-signal-category-title">${label}</h4>
        <span class="sr-signal-category-score">${v != null ? formatScore(v) : "—"}</span>
      </div>
      <p class="sr-signal-category-copy">${explanation}</p>
      ${evidenceHtml}
    </article>`;
}

function renderSignalAnalysis(entry, intel) {
  const payload = intel.normalizedPayload || {
    capabilities: intel.capabilities || {},
    missing_inputs: intel.missingInputs || [],
  };
  const missing = payload.missing_inputs || intel.missingInputs || [];
  const evidence = intel.evidence || {};
  const categories = [
    {
      label: "Performance",
      capability: "recent_form",
      score: intel.performance,
      explanation: (evidence.performance_reasons || [])[0]
        || capabilityStatusCopy(payload, "recent_form", intel.performance != null
          ? "Performance score captured from stored weekly intelligence."
          : "Performance inputs are still being collected for this player."),
    },
    {
      label: "Market",
      capability: "market_snapshots",
      score: intel.market,
      explanation: (evidence.market_reasons || evidence.collector_evidence || [])[0]
        || capabilityStatusCopy(payload, "market_snapshots", intel.market != null
          ? "Market score captured from stored weekly intelligence."
          : "Market snapshots are not yet available for this reporting period."),
    },
    {
      label: "Momentum",
      capability: "momentum",
      score: intel.momentum,
      explanation: (evidence.momentum_evidence || [])[0]
        || capabilityStatusCopy(payload, "momentum", intel.momentum != null
          ? "Momentum score (0–100) from stored weekly intelligence — not a percentage."
          : "Momentum history still building."),
    },
    {
      label: "Scarcity",
      capability: "card_intelligence",
      score: intel.scarcity,
      explanation: (evidence.scarcity_evidence || [])[0]
        || capabilityStatusCopy(payload, "card_intelligence", intel.scarcity != null
          ? "Scarcity score captured from stored weekly intelligence."
          : "PSA population pending."),
    },
    {
      label: "Collector Demand",
      capability: "card_intelligence",
      score: intel.collector,
      explanation: (evidence.collector_evidence || [])[0]
        || capabilityStatusCopy(payload, "card_intelligence", intel.collector != null
          ? "Collector demand score captured from stored weekly intelligence."
          : "Collector demand signals are pending."),
    },
  ];

  return `
    <section class="sr-section">
      <h3 class="sr-section-title">Signal Analysis</h3>
      <p class="sr-section-lead">How performance, market, momentum, scarcity, and collector demand combine into the CardSignal Score.</p>
      <div class="sr-signal-grid">
        ${categories.map((c) => renderSignalCategory(
          c.label,
          c.score,
          c.explanation,
          deriveSupportedEvidenceQuality(payload, c.capability, c.score, missing),
        )).join("")}
      </div>
    </section>`;
}

function buildOutlookSummary(entry, intel) {
  const name = entry.player_name || "This player";

  if (!intel.hasStoredRecommendation || intel.recommendation === "WATCH") {
    return "More evidence is required before CardSignal can issue a recommendation.";
  }

  const rec = intel.recommendation;
  if (rec === "BUY") {
    return `Recent production and market activity currently support a BUY outlook for ${name}, though outcomes are never guaranteed.`;
  }
  if (rec === "SELL") {
    return `Stored signal inputs currently support a SELL outlook for ${name}; near-term headwinds remain possible.`;
  }
  return `Stored signal inputs currently support a HOLD outlook for ${name} over the next reporting window.`;
}

function resolveStoredRisk(weeklySnap = null) {
  const risk = weeklySnap?.risk;
  if (!risk) return null;
  return String(risk).toUpperCase();
}

function renderOutlook(entry, intel, weeklySnap = null) {
  const recommendation = intel.recommendation;
  const recommendationClass = csIntelRecommendationClass(recommendation.toLowerCase());
  const evidenceClass = csIntelEvidenceClass(intel.evidenceTier);
  const risk = resolveStoredRisk(weeklySnap);
  const riskClass = risk === "LOW" ? "pi-risk--low" : risk === "HIGH" ? "pi-risk--high" : risk === "MEDIUM" ? "pi-risk--medium" : "";
  const summary = buildOutlookSummary(entry, intel);

  return `
    <section class="sr-section sr-outlook">
      <h3 class="sr-section-title">CardSignal Outlook</h3>
      <div class="sr-outlook-grid">
        <div class="sr-outlook-item">
          <span class="cs-recommendation-badge ${recommendationClass} sr-outlook-rec">${recommendation}</span>
          <span class="sr-outlook-label">Recommendation</span>
        </div>
        <div class="sr-outlook-item">
          <span class="cs-evidence-badge ${evidenceClass}">${intel.evidenceTier}</span>
          <span class="sr-outlook-label">Evidence</span>
        </div>
        <div class="sr-outlook-item">
          <span class="pi-risk-badge ${riskClass || "sr-pending-pill"}">${risk || "Pending"}</span>
          <span class="sr-outlook-label">Risk</span>
        </div>
        <div class="sr-outlook-item">
          <span class="sr-outlook-horizon">${weeklySnap?.time_horizon || "Pending"}</span>
          <span class="sr-outlook-label">Time Horizon</span>
        </div>
      </div>
      <div class="sr-outlook-summary">
        <p class="sr-outlook-summary-label">Summary</p>
        <p class="sr-outlook-summary-copy">${summary}</p>
      </div>
      <p class="sr-outlook-disclaimer">Outlook reflects stored signal inputs and may change as new data arrives. It does not guarantee returns.</p>
    </section>`;
}

function renderScoutingReportHeader(entry, intel) {
  const team = getTeamAbbrev(entry);
  const position = entry.position || "—";
  const recommendation = intel.recommendation;
  const recommendationClass = csIntelRecommendationClass(recommendation.toLowerCase());
  const status = getReportStatus(entry, piModalWeeklySnap);
  const updatedLabel = intel.capturedAt ? formatTimestamp(intel.capturedAt) : "Pending";

  return `
    <div class="pi-modal-header-main sr-header">
      <div class="pi-modal-identity">
        <div class="pi-modal-headshot">${renderPlayerHeadshot(entry)}</div>
        <div class="pi-modal-identity-copy">
          <p class="eyebrow pi-modal-kicker">Scouting Report</p>
          <h2 class="pi-modal-title" id="pi-modal-title">${entry.player_name}</h2>
          <div class="pi-modal-meta">
            <span class="pi-modal-meta-chip">
              <span class="team-logo-placeholder">${renderTeamLogoMarkup(entry)}</span>
              ${team}
            </span>
            <span class="pi-modal-meta-chip pi-modal-meta-chip--muted">${position}</span>
          </div>
          <p class="sr-header-tagline">Where performance meets the market.</p>
        </div>
      </div>

      <div class="pi-modal-header-stats sr-header-stats">
        <div class="pi-modal-stat">
          <span class="pi-modal-stat-value">${intel.score != null ? formatScore(intel.score) : "—"}</span>
          <span class="pi-modal-stat-label">CardSignal Score</span>
        </div>
        <div class="pi-modal-stat">
          <span class="pi-modal-stat-value cs-recommendation-badge ${recommendationClass} pi-modal-rec-badge">${recommendation}</span>
          <span class="pi-modal-stat-label">Recommendation</span>
        </div>
        <div class="pi-modal-stat">
          <span class="pi-modal-stat-value sr-status-pill ${status.className}">${status.emoji} ${status.label}</span>
          <span class="pi-modal-stat-label">Status</span>
        </div>
      </div>

      <div class="sr-header-meta">
        <span>Updated ${updatedLabel}</span>
        <span class="sr-header-meta-sep" aria-hidden="true">·</span>
        <span>${intel.algorithmVersion}</span>
      </div>

      ${!intel.hasStoredRecommendation
    ? `<p class="sr-recommendation-note">More evidence is required before CardSignal can issue a recommendation.</p>`
    : ""}

      <div class="pi-modal-header-actions">
        <button type="button" id="watchlist-toggle-btn" class="player-save-btn pi-modal-save-btn">
          ${currentUser ? "Save to watchlist" : "Sign in to save"}
        </button>
        <button type="button" class="pi-modal-close" data-pi-close aria-label="Close scouting report">✕</button>
      </div>
    </div>`;
}

function renderScoutingReport(entry, intel, cards = [], weeklySnap = null) {
  return `
    <div class="sr-report">
      ${renderPlayerSnapshot(intel, entry)}
      ${renderWhyThisSignal(entry, intel, weeklySnap)}
      ${renderReportCards(cards)}
      ${renderReportMarket(entry, intel, weeklySnap)}
      ${renderSignalAnalysis(entry, intel)}
      ${renderOutlook(entry, intel, weeklySnap)}
    </div>`;
}

function buildPlayerIntel(entry, weeklySnap = null, normalizedPayload = null) {
  return buildStoredPlayerIntel(entry, weeklySnap, normalizedPayload);
}

function isPlayerIntelligenceModalOpen() {
  const modal = document.getElementById("player-intelligence-modal");
  return modal && !modal.classList.contains("hidden");
}

function lockBodyScrollForModal() {
  document.body.classList.add("pi-modal-open");
}

function unlockBodyScrollForModal() {
  document.body.classList.remove("pi-modal-open");
}

function bindPiModalKeydown() {
  if (piModalKeydownHandler) return;
  piModalKeydownHandler = (event) => {
    if (event.key === "Escape" && isPlayerIntelligenceModalOpen()) {
      event.preventDefault();
      closePlayerIntelligenceModal();
    }
  };
  document.addEventListener("keydown", piModalKeydownHandler);
}

function setupPlayerIntelligenceModal() {
  const modal = document.getElementById("player-intelligence-modal");
  if (!modal || modal.dataset.piBound === "1") return;
  modal.dataset.piBound = "1";

  modal.addEventListener("click", (event) => {
    const closeTarget = event.target.closest("[data-pi-close]");
    if (closeTarget) {
      event.preventDefault();
      closePlayerIntelligenceModal();
    }
  });

  bindPiModalKeydown();
}

function closePlayerIntelligenceModal() {
  const modal = document.getElementById("player-intelligence-modal");
  if (!modal) return;

  modal.classList.add("hidden");
  modal.setAttribute("aria-hidden", "true");
  unlockBodyScrollForModal();
  piModalEntry = null;
  piModalIntel = null;
  piModalWeeklySnap = null;
  piModalCards = [];
}

async function openPlayerIntelligenceModal(entry) {
  const modal = document.getElementById("player-intelligence-modal");
  const header = document.getElementById("pi-modal-header");
  const body = document.getElementById("pi-modal-body");
  if (!modal || !header || !body) return;

  selectedPlayer = entry;

  try {
    const model = await loadScoutingReportModel(entry);
    const player = model.player;
    const intel = model.intel;
    const weeklySnap = model.weeklySnap;
    selectedPlayer = player;

    const cardRows = collectPlayerCards(player);
    const cards = await enrichPlayerCards(cardRows);

    piModalEntry = player;
    piModalIntel = intel;
    piModalWeeklySnap = weeklySnap;
    piModalCards = cards;

    header.innerHTML = renderScoutingReportHeader(player, intel);
    body.innerHTML = renderScoutingReport(player, intel, cards, weeklySnap);

    wirePlayerActions();

    modal.classList.remove("hidden");
    modal.setAttribute("aria-hidden", "false");
    lockBodyScrollForModal();

    requestAnimationFrame(() => {
      modal.querySelector(".pi-modal-close")?.focus();
    });
  } catch (error) {
    body.innerHTML = `<div class="pi-tab-placeholder"><p class="pi-tab-placeholder-copy">${error.message}</p></div>`;
    modal.classList.remove("hidden");
    modal.setAttribute("aria-hidden", "false");
    lockBodyScrollForModal();
  }
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

function getIsoWeek(date) {
  const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  d.setUTCDate(d.getUTCDate() + 4 - (d.getUTCDay() || 7));
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  return Math.ceil((((d - yearStart) / 86400000) + 1) / 7);
}

async function renderScoreHistory(playerId) {
  const canvas = document.getElementById("score-history-chart");
  if (!canvas || !playerId) return;

  try {
    let items = [];
    try {
      const weeklyPayload = await fetchPlayerWeeklySignals(playerId);
      items = (weeklyPayload.items || []).map((item) => ({
        created_at: item.captured_at || item.period_start,
        total_score: item.card_signal_score,
        performance_score: item.performance_score,
        market_score: item.market_score,
        week_label: item.period_start,
      }));
    } catch (_) {
      items = [];
    }

    if (items.length < 2) {
      const payload = await fetchPlayerHistory(playerId);
      items = payload.items || [];
    }

    destroyChart(scoreChart);

    if (items.length < 2) {
      showChartPlaceholder("score-history-chart", "score-history-placeholder", true);
      return;
    }

    showChartPlaceholder("score-history-chart", "score-history-placeholder", false);

    scoreChart = new Chart(canvas, {
      type: "line",
      data: {
        labels: items.map(item => {
          const d = new Date(item.week_label || item.created_at);
          return `W${getIsoWeek(d)} · ${d.toLocaleDateString(undefined, { month: "short", day: "numeric" })}`;
        }),
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
      options: getChartOptions("Selected Player Signal Timeline"),
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
      options: getChartOptions("Market Activity"),
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
  await openPlayerIntelligenceModal(entry);
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

function openSignalOfWeekReport(entry) {
  selectPlayer(entry);
}

function renderSignalOfTheWeek(entries = [], storedSignal = null) {
  const card = document.querySelector(".signal-of-week-card");
  if (!card) return;

  const officialSignal = signalOfWeekToEntry(storedSignal || weeklyIntelligence?.signal_of_the_week);
  const fallbackEntry = getSignalOfWeekTopEntry(entries);
  const hasOfficialSelection = !!officialSignal;
  const entry = officialSignal || fallbackEntry;

  if (!entry) {
    card.classList.remove("featured-signal-banner");
    card.removeAttribute("role");
    card.removeAttribute("tabindex");
    card.removeAttribute("aria-label");
    const message = weeklyIntelligence?.run
      ? "No player qualified this week — insufficient evidence across the Top 100 universe."
      : "Weekly intelligence pending — Signal of the Week will publish after the next official refresh.";
    card.innerHTML = `
      <div class="signal-week-banner signal-week-banner--empty">
        <div class="signal-week-content">
          <div class="signal-week-label">Signal of the Week</div>
          <p class="signal-week-reason">${message}</p>
        </div>
      </div>`;
    card.onclick = null;
    card.onkeydown = null;
    return;
  }

  const presentation = WeeklyMovement.resolveFeaturedSignalPresentation({
    hasOfficialSelection,
    entry,
  });
  const score = Number(entry?.hotness?.total_score ?? 0);
  const aiReasonSentence = entry?.signal_of_week_reason
    ? clampToOneSentence(entry.signal_of_week_reason)
    : (hasOfficialSelection ? "Weekly signal rationale pending." : "Current leaderboard signal based on stored CardSignal scores.");
  const aiAction = entry?.recommendation ? String(entry.recommendation).toUpperCase() : "WATCH";
  const team = getTeamAbbrev(entry);
  const position = entry.position || "—";
  const movement = presentation.movement;
  const moveClass = movement ? WeeklyMovement.weeklyMovementClass(movement) : "";

  card.classList.add("featured-signal-banner");
  card.removeAttribute("role");
  card.removeAttribute("tabindex");
  card.removeAttribute("aria-label");

  card.innerHTML = `
    <div class="signal-week-banner">
      <div class="signal-week-media">
        ${renderSignalWeekPlayerImage(entry)}
      </div>

      <div class="signal-week-content">
        <div class="signal-week-label">${presentation.label}</div>
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
            ${presentation.showWeeklyMovement ? `
            <div class="signal-week-stat">
              <span class="signal-week-stat-value ${moveClass}">${WeeklyMovement.renderWeeklyMovementLabel(movement)}</span>
              <span class="signal-week-stat-label">Weekly Movement</span>
            </div>` : ""}
          </div>
        </div>

        <div class="signal-week-insight">
          <div class="signal-week-ai-row">
            <span class="signal-week-ai-pill signal-week-ai-pill--${aiAction.toLowerCase()}">${aiAction}</span>
          </div>
          <p class="signal-week-reason">${aiReasonSentence}</p>
        </div>
      </div>

      <div class="signal-week-action">
        <button type="button" class="signal-week-cta" id="signal-week-view-report">
          View Report
          <span class="signal-week-cta-arrow" aria-hidden="true">→</span>
        </button>
      </div>
    </div>
  `;

  const cta = card.querySelector("#signal-week-view-report");
  if (cta) {
    cta.addEventListener("click", (event) => {
      event.stopPropagation();
      openSignalOfWeekReport(entry);
    });
  }

  card.onclick = null;
  card.onkeydown = null;
}

/* Signal Center — main dashboard render pipeline */
function renderSignalCenter(entries) {
  renderSignalOfTheWeek(entries, weeklyIntelligence?.signal_of_the_week);
  renderCardSection(entries, weeklyIntelligence?.card_intelligence);
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
  if (isNflEntry(entry)) {
    const label = isTop20 ? 'NFL Top' : 'NFL Search';
    return `<span class="player-search-result-badge player-search-result-badge--nfl">${label}</span>`;
  }
  if (isNbaEntry(entry)) {
    const label = isTop20 ? 'NBA Top' : 'NBA Search';
    return `<span class="player-search-result-badge player-search-result-badge--nba">${label}</span>`;
  }
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
        data-player-id="${SRNba.srNbaResolvePlayerId(entry) || SRNfl.srNflResolvePlayerId(entry) || entry.player_id || ""}"
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
}

async function handleBackendOnlyPlayerSelect(entry) {
  closePlayerSearch();
  selectedPlayer = entry;

  const leaderboardRoot = document.getElementById("leaderboard-table");
  leaderboardRoot?.querySelectorAll(".leader-table-row.active").forEach((row) => row.classList.remove("active"));

  await openPlayerIntelligenceModal(entry);
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
      if (isPlayerIntelligenceModalOpen()) return;
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
    const entry = resolveSearchEntryByPlayerId(currentSearchMatches, playerId);
    if (!entry) return;

    await handleSearchResultPick(entry);
  });

  document.addEventListener("click", (event) => {
    if (!event.target.closest("#player-search-module")) closePlayerSearch();
  });
}

function setupSportTabs() {
  const tabs = [...document.querySelectorAll(".sport-tab[data-sport-filter]")];
  const mlbContent = document.getElementById("sport-content-mlb");
  const nbaSoon = document.getElementById("sport-coming-soon-nba");
  const nflSoon = document.getElementById("sport-coming-soon-nfl");
  if (!tabs.length) return;

  const applySportFilter = async (filter) => {
    const normalized = String(filter || "all").toLowerCase();
    activeSportFilter = normalized;
    const showMlb = normalized === "all" || normalized === "mlb";
    const showNba = normalized === "nba";
    const showNbaSoon = showNba && !nbaDataAvailable;
    const showNflOnly = normalized === "nfl";
    const showNflSoon = showNflOnly && !nflDataAvailable;

    if (mlbContent) mlbContent.classList.toggle("hidden", !showMlb && !showNflOnly && !(showNba && nbaDataAvailable));
    if (nbaSoon) nbaSoon.classList.toggle("hidden", !showNbaSoon);
    if (nflSoon) nflSoon.classList.toggle("hidden", !showNflSoon);

    if (showNba && nbaDataAvailable) {
      const nbaPayload = await fetchWeeklyLatest('NBA').catch(() => null);
      if (nbaPayload?.todays_leaders?.length) {
        nbaWeeklyIntelligence = nbaPayload;
        latestEntries = nbaPayload.todays_leaders.map(weeklyLeaderToEntry);
        renderSignalCenter(latestEntries);
        const leaderboardRoot = document.getElementById('leaderboard-table');
        if (leaderboardRoot) leaderboardRoot.innerHTML = buildLeaderboard(latestEntries);
      }
    } else if (showNflOnly && nflDataAvailable) {
      const nflPayload = await fetchWeeklyLatest('NFL').catch(() => null);
      if (nflPayload?.todays_leaders?.length) {
        nflWeeklyIntelligence = nflPayload;
        latestEntries = nflPayload.todays_leaders.map(weeklyLeaderToEntry);
        renderSignalCenter(latestEntries);
        const leaderboardRoot = document.getElementById('leaderboard-table');
        if (leaderboardRoot) leaderboardRoot.innerHTML = buildLeaderboard(latestEntries);
      }
    } else if (showMlb || normalized === 'all') {
      const source = normalized === 'all'
        ? mergeAllSportLeaders(
          weeklyIntelligence?.todays_leaders || [],
          nflDataAvailable ? (nflWeeklyIntelligence?.todays_leaders || []) : [],
          nbaDataAvailable ? (nbaWeeklyIntelligence?.todays_leaders || []) : [],
        )
        : (weeklyIntelligence?.todays_leaders || []).map(weeklyLeaderToEntry);
      if (source.length) {
        latestEntries = source;
        renderSignalCenter(latestEntries);
        const leaderboardRoot = document.getElementById('leaderboard-table');
        if (leaderboardRoot) leaderboardRoot.innerHTML = buildLeaderboard(latestEntries);
      }
    }

    tabs.forEach((tab) => {
      const tabFilter = tab.dataset.sportFilter;
      tab.classList.remove("active", "active-sport");

      if (normalized === "all" && tabFilter === "all") {
        tab.classList.add("active");
      } else if (normalized === "mlb" && tabFilter === "mlb") {
        tab.classList.add("active", "active-sport");
      } else if (tabFilter === normalized && (tabFilter === "nba" || tabFilter === "nfl")) {
        tab.classList.add("active");
      }
    });
  };

  tabs.forEach((tab) => {
    if (tab.disabled) return;
    tab.addEventListener("click", () => {
      applySportFilter(tab.dataset.sportFilter);
    });
  });

  applySportFilter("all");
}

function mergeAllSportLeaders(mlbLeaders = [], nflLeaders = [], nbaLeaders = []) {
  const combined = [
    ...mlbLeaders.map((e) => ({ ...weeklyLeaderToEntry(e), sport: 'MLB', league: 'MLB' })),
    ...nflLeaders.map((e) => ({ ...weeklyLeaderToEntry(e), sport: 'FOOTBALL', league: 'NFL' })),
    ...nbaLeaders.map((e) => ({ ...weeklyLeaderToEntry(e), sport: 'BASKETBALL', league: 'NBA' })),
  ];
  return combined
    .filter((e) => e.card_signal_score != null || e.hotness?.total_score != null)
    .sort((a, b) => {
      const aScore = a.card_signal_score ?? a.hotness?.total_score ?? -1;
      const bScore = b.card_signal_score ?? b.hotness?.total_score ?? -1;
      return bScore - aScore;
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
    const nflStatus = await fetchNflStatus();
    nflDataAvailable = !!nflStatus.available;
    const nbaStatus = await fetchNbaStatus();
    nbaDataAvailable = !!nbaStatus.available;

    const weeklyRequests = [fetchWeeklyLatest('MLB').catch(() => null)];
    if (nflDataAvailable) weeklyRequests.push(fetchWeeklyLatest('NFL').catch(() => null));
    if (nbaDataAvailable) weeklyRequests.push(fetchWeeklyLatest('NBA').catch(() => null));

    const [payload, ...weeklyResults] = await Promise.all([
      fetch(SOURCE_URL).then(res => {
        if (!res.ok) throw new Error(`Could not load ${SOURCE_URL}.`);
        return res.json();
      }),
      ...weeklyRequests,
    ]);

    weeklyIntelligence = weeklyResults[0] || null;
    let weeklyIdx = 1;
    nflWeeklyIntelligence = nflDataAvailable ? (weeklyResults[weeklyIdx++] || null) : null;
    nbaWeeklyIntelligence = nbaDataAvailable ? (weeklyResults[weeklyIdx++] || null) : null;
    let entries = payload.items || [];

    if (weeklyIntelligence?.todays_leaders?.length) {
      entries = weeklyIntelligence.todays_leaders.map(weeklyLeaderToEntry);
    }
    if (activeSportFilter === 'all') {
      const merged = mergeAllSportLeaders(
        weeklyIntelligence?.todays_leaders || [],
        nflDataAvailable ? (nflWeeklyIntelligence?.todays_leaders || []) : [],
        nbaDataAvailable ? (nbaWeeklyIntelligence?.todays_leaders || []) : [],
      );
      if (merged.length) entries = merged;
    }

    latestEntries = entries;
    setupPlayerSearch();
    setupPlayerIntelligenceModal();
    setupSportTabs();

    status.textContent = 'Rendering Signal Center...';
    renderWeeklyRefreshNote();
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
    } else {
      leaderboardRoot.innerHTML = `<div class="detail-empty">Leaderboard unavailable.</div>`;
    }

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

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    renderScoutingReport,
    buildPlayerIntel,
    loadScoutingReportModel,
    hasStoredPipelineReportData,
    resolveMlbSourcePlayerId,
    mlbSourceIdFromValue,
    looksLikeUuid,
  };
} else {
  init();
}
