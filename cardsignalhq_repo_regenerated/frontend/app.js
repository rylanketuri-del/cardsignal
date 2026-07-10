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
let piActiveTab = "overview";
let piModalEntry = null;
let piModalIntel = null;
let piModalKeydownHandler = null;
let weeklyIntelligence = null;
let activeSportFilter = 'ALL';
const LEADERBOARD_LIMIT = 30;
const QUICK_INTEL_LIMIT = 10;
const SPORT_KEYS = ['MLB', 'NBA', 'NFL'];
let sportDatasets = {
  MLB: { entries: [], weekly: null, signal: null },
  NBA: { entries: [], weekly: null, signal: null },
  NFL: { entries: [], weekly: null, signal: null },
};
const PI_TABS = [
  { id: "overview", label: "Overview" },
  { id: "cards", label: "Cards" },
  { id: "market", label: "Market" },
  { id: "signals", label: "Signals" },
  { id: "forecast", label: "Forecast" },
];

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

function weeklyLeaderToEntry(leader = {}) {
  return {
    player_id: leader.source_player_id || leader.cs_player_id,
    player_name: leader.player_name,
    rank: leader.rank,
    team: leader.team,
    position: leader.position,
    sport: leader.sport || 'MLB',
    headshot_url: leader.headshot_url,
    team_logo_url: leader.team_logo_url,
    weekly_change: leader.weekly_change,
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
    sport: signal.sport || 'MLB',
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
  return {
    name: `${player} · ${label}`,
    price: row.evidence?.avg_price ?? null,
    movement: row.demand_score != null ? `${row.demand_score > 0 ? '+' : ''}${Number(row.demand_score).toFixed(1)}%` : '—',
    score: row.score != null ? Number(row.score).toFixed(1) : '—',
  };
}

const DEMO_SPORT_ROSTERS = {
  NBA: [
    { player_name: 'Giannis Antetokounmpo', team: 'MIL', position: 'PF' },
    { player_name: 'Luka Dončić', team: 'DAL', position: 'PG' },
    { player_name: 'Jayson Tatum', team: 'BOS', position: 'SF' },
    { player_name: 'Anthony Edwards', team: 'MIN', position: 'SG' },
    { player_name: 'Nikola Jokić', team: 'DEN', position: 'C' },
    { player_name: 'Shai Gilgeous-Alexander', team: 'OKC', position: 'PG' },
    { player_name: 'Victor Wembanyama', team: 'SAS', position: 'C' },
    { player_name: 'Devin Booker', team: 'PHX', position: 'SG' },
    { player_name: 'Donovan Mitchell', team: 'CLE', position: 'SG' },
    { player_name: 'Ja Morant', team: 'MEM', position: 'PG' },
    { player_name: 'Tyrese Haliburton', team: 'IND', position: 'PG' },
    { player_name: 'Kevin Durant', team: 'PHX', position: 'SF' },
    { player_name: 'Stephen Curry', team: 'GSW', position: 'PG' },
    { player_name: 'LeBron James', team: 'LAL', position: 'SF' },
    { player_name: 'Joel Embiid', team: 'PHI', position: 'C' },
    { player_name: 'Anthony Davis', team: 'LAL', position: 'PF' },
    { player_name: 'Paolo Banchero', team: 'ORL', position: 'PF' },
    { player_name: 'Cade Cunningham', team: 'DET', position: 'PG' },
    { player_name: 'Trae Young', team: 'ATL', position: 'PG' },
    { player_name: 'Kawhi Leonard', team: 'LAC', position: 'SF' },
    { player_name: 'Damian Lillard', team: 'MIL', position: 'PG' },
    { player_name: 'Bam Adebayo', team: 'MIA', position: 'C' },
    { player_name: 'De\'Aaron Fox', team: 'SAC', position: 'PG' },
    { player_name: 'Jaylen Brown', team: 'BOS', position: 'SG' },
    { player_name: 'Zion Williamson', team: 'NOP', position: 'PF' },
    { player_name: 'LaMelo Ball', team: 'CHA', position: 'PG' },
    { player_name: 'Jalen Brunson', team: 'NYK', position: 'PG' },
    { player_name: 'Domantas Sabonis', team: 'SAC', position: 'C' },
    { player_name: 'Evan Mobley', team: 'CLE', position: 'PF' },
    { player_name: 'Chet Holmgren', team: 'OKC', position: 'C' },
  ],
  NFL: [
    { player_name: 'Patrick Mahomes', team: 'KC', position: 'QB' },
    { player_name: 'Justin Jefferson', team: 'MIN', position: 'WR' },
    { player_name: 'Ja\'Marr Chase', team: 'CIN', position: 'WR' },
    { player_name: 'Josh Allen', team: 'BUF', position: 'QB' },
    { player_name: 'CeeDee Lamb', team: 'DAL', position: 'WR' },
    { player_name: 'Lamar Jackson', team: 'BAL', position: 'QB' },
    { player_name: 'Tyreek Hill', team: 'MIA', position: 'WR' },
    { player_name: 'Joe Burrow', team: 'CIN', position: 'QB' },
    { player_name: 'Christian McCaffrey', team: 'SF', position: 'RB' },
    { player_name: 'Amon-Ra St. Brown', team: 'DET', position: 'WR' },
    { player_name: 'Brock Purdy', team: 'SF', position: 'QB' },
    { player_name: 'Trevor Lawrence', team: 'JAX', position: 'QB' },
    { player_name: 'Nico Collins', team: 'HOU', position: 'WR' },
    { player_name: 'Bijan Robinson', team: 'ATL', position: 'RB' },
    { player_name: 'Jalen Hurts', team: 'PHI', position: 'QB' },
    { player_name: 'Puka Nacua', team: 'LAR', position: 'WR' },
    { player_name: 'Saquon Barkley', team: 'PHI', position: 'RB' },
    { player_name: 'Derrick Henry', team: 'BAL', position: 'RB' },
    { player_name: 'Garrett Wilson', team: 'NYJ', position: 'WR' },
    { player_name: 'Jayden Daniels', team: 'WAS', position: 'QB' },
    { player_name: 'Caleb Williams', team: 'CHI', position: 'QB' },
    { player_name: 'Drake London', team: 'ATL', position: 'WR' },
    { player_name: 'Tua Tagovailoa', team: 'MIA', position: 'QB' },
    { player_name: 'DK Metcalf', team: 'SEA', position: 'WR' },
    { player_name: 'Travis Kelce', team: 'KC', position: 'TE' },
    { player_name: 'George Kittle', team: 'SF', position: 'TE' },
    { player_name: 'Jonathan Taylor', team: 'IND', position: 'RB' },
    { player_name: 'DeVonta Smith', team: 'PHI', position: 'WR' },
    { player_name: 'Stefon Diggs', team: 'HOU', position: 'WR' },
    { player_name: 'Micah Parsons', team: 'DAL', position: 'LB' },
  ],
};

function buildDemoSportEntry(player, sport, rank) {
  const key = `${sport}:${player.player_name}`;
  const seed = csIntelHashToUint32(key);
  const rng = csIntelMulberry32(seed);
  const score = csIntelClamp(55 + rng() * 42, 52, 97);
  const performance = csIntelClamp(score - 8 + rng() * 16, 40, 95);
  const market = csIntelClamp(score - 6 + rng() * 14, 42, 96);
  const momentum = csIntelClamp(45 + rng() * 40, 35, 92);
  const weeklyChange = csIntelClamp((momentum - 50) / 2.5 + (rng() - 0.5) * 3, -12, 14);
  const convictionTier = csIntelPickConvictionTier(rng());
  const recommendation = csIntelRecommendationFromTier(convictionTier);

  return {
    player_id: `${sport.toLowerCase()}:demo:${rank}`,
    player_name: player.player_name,
    rank,
    team: player.team,
    position: player.position,
    sport,
    headshot_url: null,
    team_logo_url: null,
    weekly_change: Number(weeklyChange.toFixed(1)),
    hotness: {
      total_score: Number(score.toFixed(1)),
      performance_score: Number(performance.toFixed(1)),
      market_score: Number(market.toFixed(1)),
      momentum_score: Number(momentum.toFixed(1)),
      collector_score: Number((market * 0.9).toFixed(1)),
      confidence_multiplier: 1,
      tag: recommendation === 'BUY' ? 'RISING' : recommendation,
      reasons: [],
    },
    recommendation,
    conviction: convictionTier,
  };
}

function buildDemoSportEntries(sport) {
  const roster = DEMO_SPORT_ROSTERS[sport] || [];
  return roster.map((player, index) => buildDemoSportEntry(player, sport, index + 1));
}

function getSportSignalEntry(sport) {
  const dataset = sportDatasets[sport];
  if (!dataset) return null;
  if (dataset.signal) return dataset.signal;
  const entries = dataset.entries || [];
  return getSignalOfWeekTopEntry(entries) || entries[0] || null;
}

function getCombinedLeaderEntries(limit = LEADERBOARD_LIMIT) {
  const combined = [];
  for (const sport of SPORT_KEYS) {
    for (const entry of sportDatasets[sport].entries || []) {
      combined.push({ ...entry, sport: entry.sport || sport });
    }
  }
  return combined
    .sort((a, b) => (b.hotness?.total_score || 0) - (a.hotness?.total_score || 0))
    .slice(0, limit)
    .map((entry, index) => ({ ...entry, rank: index + 1 }));
}

function getFilteredLeaderEntries() {
  if (activeSportFilter === 'ALL') return getCombinedLeaderEntries();
  return (sportDatasets[activeSportFilter]?.entries || [])
    .slice(0, LEADERBOARD_LIMIT)
    .map((entry, index) => ({ ...entry, rank: index + 1, sport: entry.sport || activeSportFilter }));
}

function getFilteredCardIntelEntries() {
  if (activeSportFilter === 'ALL') return getCombinedLeaderEntries(QUICK_INTEL_LIMIT);
  return getFilteredLeaderEntries().slice(0, QUICK_INTEL_LIMIT);
}

function getEntryRecommendation(entry = {}) {
  if (entry.recommendation) return entry.recommendation;
  const intel = csIntelGetPlaceholders(entry);
  return csIntelRecommendationFromTier(intel.convictionTier || intel.confidenceTier || 'MEDIUM');
}

function populateSportDatasets(mlbEntries, mlbWeekly) {
  const mlbTagged = (mlbEntries || []).map((entry) => ({ ...entry, sport: entry.sport || 'MLB' }));
  sportDatasets.MLB = {
    entries: mlbTagged.slice(0, LEADERBOARD_LIMIT),
    weekly: mlbWeekly,
    signal: signalOfWeekToEntry(mlbWeekly?.signal_of_the_week) || getSignalOfWeekTopEntry(mlbTagged),
  };

  for (const sport of ['NBA', 'NFL']) {
    const entries = buildDemoSportEntries(sport);
    sportDatasets[sport] = {
      entries,
      weekly: null,
      signal: getSignalOfWeekTopEntry(entries),
    };
  }

  weeklyIntelligence = mlbWeekly;
  latestEntries = getCombinedLeaderEntries(100);
}

function setupSportTabs() {
  const tabs = document.getElementById('sport-tabs');
  if (!tabs) return;

  tabs.addEventListener('click', (event) => {
    const button = event.target.closest('.sport-tab');
    if (!button || button.classList.contains('disabled')) return;

    const sport = button.dataset.sport || 'ALL';
    activeSportFilter = sport;

    tabs.querySelectorAll('.sport-tab').forEach((tab) => {
      tab.classList.toggle('active', tab.dataset.sport === sport);
      tab.classList.remove('active-sport');
    });

    refreshHomepage();
  });
}

function refreshHomepage() {
  const entries = getFilteredLeaderEntries();
  renderSignalCenter(entries);
  renderLeaderboardTable(entries);
}

function renderWeeklyRefreshNote() {
  const section = document.getElementById('this-weeks-signals-section');
  if (!section) return;
  let note = document.getElementById('weekly-refresh-note');
  if (!note) {
    note = document.createElement('p');
    note.id = 'weekly-refresh-note';
    note.className = 'weekly-refresh-note section-desc';
    section.querySelector('.section-header')?.appendChild(note);
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
  const filterLabel = activeSportFilter === 'ALL' ? 'Top 30 Overall' : `Top ${Math.min(entries.length, LEADERBOARD_LIMIT)} ${activeSportFilter}`;
  const sportClass = activeSportFilter === 'ALL' ? 'all-sports' : activeSportFilter.toLowerCase();

  return `
    <section class="market-leaders-module sport-section sport-section--${sportClass}" data-sport="${sportClass}">
      <div class="market-leaders-header">
        <div>
          <h2 class="leaders-section-title">Today's Leaders</h2>
          <p class="section-desc">${filterLabel} · ${SECTION_DESCRIPTIONS.leaders}</p>
        </div>
      </div>

      <div class="market-leaders-scroll">
        <div class="market-leaders-table market-leaders-table--v10">
          <div class="leaders-table-head">
            <span>Sport</span>
            <span>Player</span>
            <span>Team</span>
            <span>Signal</span>
            <span>Change</span>
            <span>Rec</span>
            <span>Report</span>
          </div>

          ${entries.map((entry, index) => {
            const score = entry.hotness?.total_score || 0;
            const movement = entry.weekly_change != null && Number.isFinite(Number(entry.weekly_change))
              ? (() => {
                const delta = Number(entry.weekly_change);
                const arrow = delta > 0.01 ? "↑" : delta < -0.01 ? "↓" : "→";
                const signed = delta > 0 ? `+${delta.toFixed(1)}` : delta < 0 ? `${delta.toFixed(1)}` : `+0.0`;
                return { arrow, signed };
              })()
              : computeSignalOfWeekMovement(entry);
            const moveClass = movement.signed.startsWith("+") ? "metric-up" : movement.signed.startsWith("-") ? "metric-down" : "metric-flat";
            const team = getTeamAbbrev(entry);
            const recommendation = getEntryRecommendation(entry);
            const recClass = recommendation.toLowerCase();

            return `
              <button class="leader-table-row" type="button" data-player-index="${index}">
                <span class="leader-sport-icon" aria-label="${entry.sport || 'MLB'}">${getSportIcon(entry)}</span>
                <span class="leader-player-cell">
                  <span class="leader-photo-cell">${renderLeaderHeadshot(entry)}</span>
                  <span class="leader-player-copy">
                    <span class="leader-player-name">${entry.player_name}</span>
                  </span>
                </span>
                <span class="leader-team-cell">${team}</span>
                <span class="leader-number">${formatScore(score)}</span>
                <span class="leader-trend ${moveClass}">${movement.arrow} ${movement.signed}</span>
                <span class="leader-rec-pill leader-rec-pill--${recClass}">${recommendation}</span>
                <span class="leader-report-pill">View Report</span>
              </button>
            `;
          }).join("")}
        </div>
      </div>
    </section>
  `;
}

function renderLeaderboardTable(entries) {
  const leaderboardRoot = document.getElementById('leaderboard-table');
  if (!leaderboardRoot) return;

  if (!entries.length) {
    leaderboardRoot.innerHTML = `<div class="detail-empty">No leaders available for this sport.</div>`;
    return;
  }

  leaderboardRoot.innerHTML = buildLeaderboard(entries);
  const leaderRows = [...leaderboardRoot.querySelectorAll('.leader-table-row')];
  leaderRows.forEach((row, index) => {
    row.addEventListener('click', async () => {
      leaderRows.forEach((r) => r.classList.remove('active'));
      row.classList.add('active');
      await selectPlayer(entries[index]);
    });
  });
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
  leaders: "Top 30 overall — the strongest CardSignal profiles across tracked players this week.",
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

function renderCardIntelBox({ title, modifier, description, items, maxItems = QUICK_INTEL_LIMIT }) {
  return `
    <article class="qi-card qi-card--${modifier}">
      <h3 class="qi-card-title">${title}</h3>
      <p class="qi-card-desc">${description}</p>
      <div class="qi-card-list">
        ${items.slice(0, maxItems).map((item) => renderCardIntelRow(item)).join("")}
      </div>
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

  const sportWeekly = activeSportFilter === 'ALL'
    ? null
    : sportDatasets[activeSportFilter]?.weekly;
  const stored = cardIntel
    || sportWeekly?.card_intelligence
    || (activeSportFilter === 'MLB' ? weeklyIntelligence?.card_intelligence : null);

  if (stored && (stored.trending_cards?.length || stored.biggest_movers?.length)) {
    root.innerHTML = `
      ${renderCardIntelBox({
        title: "Trending Cards",
        modifier: "trending",
        description: SECTION_DESCRIPTIONS.trending,
        items: (stored.trending_cards || []).map(weeklyCardRowToIntelItem),
      })}
      ${renderCardIntelBox({
        title: "Biggest Movers",
        modifier: "movers",
        description: SECTION_DESCRIPTIONS.movers,
        items: (stored.biggest_movers || []).map(weeklyCardRowToIntelItem),
      })}
      ${renderCardIntelBox({
        title: "Buy Low Watch",
        modifier: "buy-low",
        description: SECTION_DESCRIPTIONS.buyLow,
        items: (stored.buy_low_watch || []).map(weeklyCardRowToIntelItem),
      })}
      ${renderCardIntelBox({
        title: "Most Chased",
        modifier: "chased",
        description: SECTION_DESCRIPTIONS.chased,
        items: (stored.most_chased || []).map(weeklyCardRowToIntelItem),
      })}
    `;
    return;
  }

  const cardEntries = entries.length ? entries : getFilteredCardIntelEntries();
  const entry = getCardSectionEntry(cardEntries);
  const intel = csIntelGetPlaceholders(entry);

  root.innerHTML = `
    ${renderCardIntelBox({
      title: "Trending Cards",
      modifier: "trending",
      description: SECTION_DESCRIPTIONS.trending,
      items: intel.trendingCards,
    })}
    ${renderCardIntelBox({
      title: "Biggest Movers",
      modifier: "movers",
      description: SECTION_DESCRIPTIONS.movers,
      items: intel.biggestMovers,
    })}
    ${renderCardIntelBox({
      title: "Buy Low Watch",
      modifier: "buy-low",
      description: SECTION_DESCRIPTIONS.buyLow,
      items: intel.buyLowOpportunities,
    })}
    ${renderCardIntelBox({
      title: "Most Chased",
      modifier: "chased",
      description: SECTION_DESCRIPTIONS.chased,
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

  function pickItems(pool, count = 3, { bias = 0, priceMin = 8, priceMax = 230, moveMin = 4, moveMax = 30 } = {}) {
    const used = new Set();
    const out = [];
    while (out.length < count && used.size < pool.length) {
      const idx = Math.floor(rng() * pool.length);
      if (used.has(idx)) continue;
      used.add(idx);
      const price = priceMin + rng() * (priceMax - priceMin);
      const magnitude = moveMin + rng() * (moveMax - moveMin);
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

  const trendingCards = pickItems(trendingNamePool, QUICK_INTEL_LIMIT, {
    bias: (market - 50) / 8 + (momentum - 50) / 10,
    priceMin: 12,
    priceMax: 260,
    moveMin: 8,
    moveMax: 28,
  });

  const biggestMovers = pickItems(moverNamePool, QUICK_INTEL_LIMIT, {
    bias: (performance - 50) / 10,
    priceMin: 15,
    priceMax: 310,
    moveMin: 10,
    moveMax: 38,
  });

  const buyLowOpportunities = pickItems(buyLowNamePool, QUICK_INTEL_LIMIT, {
    bias: -6 + (market < 50 ? 3 : -2),
    priceMin: 9,
    priceMax: 170,
    moveMin: 4,
    moveMax: 22,
  });

  const mostChased = pickItems(chasedNamePool, QUICK_INTEL_LIMIT, {
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

function buildPlayerIntel(entry) {
  const hotness = entry.hotness || {};
  const placeholders = csIntelGetPlaceholders(entry);

  return {
    ...placeholders,
    performance: csIntelSafeToNumber(hotness.performance_score) ?? placeholders.performance,
    market: csIntelSafeToNumber(hotness.market_score) ?? placeholders.market,
    collector: csIntelSafeToNumber(hotness.collector_score) ?? placeholders.collector,
    momentum: csIntelSafeToNumber(hotness.momentum_score) ?? placeholders.momentum,
    score: csIntelSafeToNumber(hotness.total_score) ?? placeholders.score,
    convictionTier: placeholders.convictionTier || placeholders.confidenceTier,
  };
}

function renderProgressRow(label, value, colorClass) {
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
}

function renderPiCardRow(item) {
  const moveClass = movementClass(item.movement);
  const signalLabel = getCardSignalLabel(item.score);
  const signalClass = getCardSignalLabelClass(item.score);

  return `
    <div class="pi-card-row">
      <div class="pi-card-row-thumb" aria-hidden="true"></div>
      <div class="pi-card-row-copy">
        <div class="pi-card-row-name">${item.name}</div>
        <div class="pi-card-row-meta">
          <span class="pi-card-row-price">${csIntelFormatMoney(item.price)}</span>
          <span class="pi-card-row-move ${moveClass}">${item.movement}</span>
        </div>
      </div>
      <span class="pi-signal-label ${signalClass}">${signalLabel}</span>
    </div>
  `;
}

function renderPiPlayerSection(playerName, title, items) {
  return `
    <section class="cs-premium-card pi-intel-section">
      <div class="cs-premium-head">
        <h3 class="cs-premium-title">${playerName} ${title}</h3>
      </div>
      <div class="cs-premium-card-list cs-premium-card-list--unified">
        ${items.slice(0, 3).map((item) => renderPiCardRow(item)).join("")}
      </div>
    </section>
  `;
}

function renderPiOverviewTab(entry, intel) {
  const convictionTier = intel.convictionTier;
  const recommendation = csIntelRecommendationFromTier(convictionTier);
  const recommendationClass = csIntelRecommendationClass(recommendation);
  const convictionClass = csIntelConvictionClass(convictionTier);
  const convictionLabel = formatConvictionTier(convictionTier);
  const movement = computeSignalOfWeekMovement(entry);
  const moveClass = movement.signed.startsWith("+") ? "metric-up" : movement.signed.startsWith("-") ? "metric-down" : "metric-flat";
  const status = getSignalOfWeekStatus(entry);
  const whyMatters = buildWhySignalMatters(entry, intel);

  return `
    <div class="pi-tab-panel pi-tab-panel--overview" data-tab-panel="overview">
      <section class="cs-intel-score-card">
        <div class="cs-section-head">
          <div>
            <p class="eyebrow">CardSignal Score</p>
          </div>
          <div class="cs-section-head-right">
            <div class="cs-recommendation-wrap">
              <div class="cs-recommendation-badge ${recommendationClass}">${recommendation}</div>
              <small class="cs-recommendation-label">Recommendation</small>
            </div>
            <div class="cs-conviction-wrap">
              <div class="cs-conviction-badge ${convictionClass}">${convictionLabel}</div>
              <small class="cs-conviction-label">Conviction</small>
            </div>
          </div>
        </div>
        <div class="cs-score-large">
          <span>${formatScore(intel.score)}</span>
        </div>
      </section>

      <div class="pi-overview-stats">
        <div class="pi-overview-stat">
          <span class="pi-overview-stat-value ${moveClass}">${movement.arrow} ${movement.signed}</span>
          <span class="pi-overview-stat-label">Weekly Movement</span>
        </div>
        <div class="pi-overview-stat">
          <span class="pi-overview-stat-value pi-status-pill ${status.className} pi-status-pill--inline">${status.label}</span>
          <span class="pi-overview-stat-label">Status</span>
        </div>
      </div>

      <section class="cs-intel-breakdown">
        <div class="cs-section-head">
          <h3 class="cs-section-title">Signal Breakdown</h3>
        </div>
        <div class="cs-progress-list">
          ${renderProgressRow("Performance", intel.performance, "cs-progress-fill--performance")}
          ${renderProgressRow("Market", intel.market, "cs-progress-fill--market")}
          ${renderProgressRow("Collector Demand", intel.collector, "cs-progress-fill--collector")}
          ${renderProgressRow("Momentum", intel.momentum, "cs-progress-fill--momentum")}
        </div>
      </section>

      <section class="cs-premium-card pi-why-matters">
        <div class="cs-premium-head">
          <h3 class="cs-premium-title">Why This Signal Matters</h3>
        </div>
        <p class="pi-why-matters-copy">${whyMatters}</p>
      </section>
    </div>
  `;
}

function renderPiCardsTab(entry, intel) {
  const playerName = entry.player_name || "Player";

  return `
    <div class="pi-tab-panel pi-tab-panel--cards" data-tab-panel="cards">
      <div class="pi-cards-grid">
        ${renderPiPlayerSection(playerName, "Trending Cards", intel.trendingCards)}
        ${renderPiPlayerSection(playerName, "Biggest Movers", intel.biggestMovers)}
        ${renderPiPlayerSection(playerName, "Buy Low Watch", intel.buyLowOpportunities)}
        ${renderPiPlayerSection(playerName, "Most Chased", intel.mostChased)}
      </div>
    </div>
  `;
}

function renderPiMarketTab(entry, intel) {
  const market = buildMarketPlaceholders(entry, intel);
  const moveClass = market.priceMove > 0.01 ? "metric-up" : market.priceMove < -0.01 ? "metric-down" : "metric-flat";
  const priceMoveFormatted = csIntelFormatPercent(market.priceMove);

  return `
    <div class="pi-tab-panel pi-tab-panel--market" data-tab-panel="market">
      <div class="pi-market-grid">
        <div class="pi-market-stat">
          <span class="pi-market-stat-value">${csIntelFormatMoney(market.avgSale)}</span>
          <span class="pi-market-stat-label">Avg Sale</span>
        </div>
        <div class="pi-market-stat">
          <span class="pi-market-stat-value">${market.salesVolume}</span>
          <span class="pi-market-stat-label">Sales Volume</span>
        </div>
        <div class="pi-market-stat">
          <span class="pi-market-stat-value">${market.activeListings}</span>
          <span class="pi-market-stat-label">Active Listings</span>
        </div>
        <div class="pi-market-stat">
          <span class="pi-market-stat-value ${moveClass}">${priceMoveFormatted}</span>
          <span class="pi-market-stat-label">7-Day Price Move</span>
        </div>
      </div>

      <div class="pi-market-liquidity">
        <span class="pi-market-liquidity-label">Liquidity</span>
        <span class="pi-market-liquidity-value">${market.liquidity}</span>
      </div>

      <section class="cs-premium-card pi-market-summary">
        <div class="cs-premium-head">
          <h3 class="cs-premium-title">Market Summary</h3>
        </div>
        <p class="pi-market-summary-copy">${market.summary}</p>
      </section>

      <div class="pi-market-placeholder-note">
        Live card-market data will populate after pricing snapshots.
      </div>
    </div>
  `;
}

function renderPiSignalDetailRow(label, score, explanation, colorClass) {
  const v = csIntelClamp(Number(score) || 0, 0, 100);
  return `
    <section class="cs-premium-card pi-signal-detail">
      <div class="cs-premium-head">
        <h3 class="cs-premium-title">${label}</h3>
        <span class="pi-signal-detail-score">${formatScore(v)}</span>
      </div>
      <div class="cs-progress-track pi-signal-detail-bar" aria-hidden="true">
        <span class="cs-progress-fill ${colorClass}" style="width:${v}%"></span>
      </div>
      <p class="pi-signal-detail-copy">${explanation}</p>
    </section>
  `;
}

function renderPiSignalsTab(entry, intel) {
  return `
    <div class="pi-tab-panel pi-tab-panel--signals" data-tab-panel="signals">
      <div class="pi-signals-intro">
        <p class="eyebrow">Signal Analysis</p>
        <h3 class="pi-signals-heading">Why does this player have this CardSignal Score?</h3>
      </div>
      <div class="pi-signals-list">
        ${renderPiSignalDetailRow(
          "Performance Signal",
          intel.performance,
          getSignalExplanation("performance", intel.performance, entry),
          "cs-progress-fill--performance"
        )}
        ${renderPiSignalDetailRow(
          "Market Signal",
          intel.market,
          getSignalExplanation("market", intel.market, entry),
          "cs-progress-fill--market"
        )}
        ${renderPiSignalDetailRow(
          "Collector Demand Signal",
          intel.collector,
          getSignalExplanation("collector", intel.collector, entry),
          "cs-progress-fill--collector"
        )}
        ${renderPiSignalDetailRow(
          "Momentum Signal",
          intel.momentum,
          getSignalExplanation("momentum", intel.momentum, entry),
          "cs-progress-fill--momentum"
        )}
      </div>
    </div>
  `;
}

function renderPiForecastTab(entry, intel) {
  const convictionTier = intel.convictionTier;
  const recommendation = csIntelRecommendationFromTier(convictionTier);
  const recommendationClass = csIntelRecommendationClass(recommendation);
  const convictionClass = csIntelConvictionClass(convictionTier);
  const convictionLabel = formatConvictionTier(convictionTier);
  const risk = getRiskLevel(intel);
  const riskClass = risk === "Low" ? "pi-risk--low" : risk === "High" ? "pi-risk--high" : "pi-risk--medium";
  const summary = buildForecastSummary(entry, intel);
  const reasons = buildForecastReasons(entry, intel);

  return `
    <div class="pi-tab-panel pi-tab-panel--forecast" data-tab-panel="forecast">
      <section class="cs-premium-card pi-forecast-hero">
        <div class="pi-forecast-top">
          <div class="pi-forecast-rec">
            <span class="cs-recommendation-badge ${recommendationClass} pi-forecast-rec-badge">${recommendation}</span>
            <small class="cs-recommendation-label">Recommendation</small>
          </div>
          <div class="pi-forecast-conviction">
            <span class="cs-conviction-badge ${convictionClass}">${convictionLabel}</span>
            <small class="cs-conviction-label">Conviction</small>
          </div>
          <div class="pi-forecast-horizon">
            <span class="pi-forecast-horizon-value">2–4 weeks</span>
            <small class="pi-forecast-horizon-label">Time Horizon</small>
          </div>
          <div class="pi-forecast-risk">
            <span class="pi-risk-badge ${riskClass}">${risk}</span>
            <small class="pi-forecast-risk-label">Risk</small>
          </div>
        </div>
      </section>

      <section class="cs-premium-card pi-forecast-summary">
        <div class="cs-premium-head">
          <h3 class="cs-premium-title">Forecast Summary</h3>
        </div>
        <p class="pi-forecast-summary-copy">${summary}</p>
      </section>

      <section class="cs-premium-card pi-forecast-reasons">
        <div class="cs-premium-head">
          <h3 class="cs-premium-title">Key Factors</h3>
        </div>
        <ul class="pi-forecast-reasons-list">
          ${reasons.map((reason) => `<li>${reason}</li>`).join("")}
        </ul>
        <p class="pi-forecast-disclaimer">Forecasts reflect current signal inputs and may change as new data arrives. They do not guarantee returns.</p>
      </section>
    </div>
  `;
}

function renderPiModalTabs(activeTab) {
  return PI_TABS.map((tab) => `
    <button
      type="button"
      class="pi-modal-tab${tab.id === activeTab ? " pi-modal-tab--active" : ""}"
      data-pi-tab="${tab.id}"
      role="tab"
      aria-selected="${tab.id === activeTab ? "true" : "false"}"
      aria-controls="pi-tab-panel-${tab.id}"
    >${tab.label}</button>
  `).join("");
}

function renderPiModalHeader(entry, intel) {
  const team = getTeamAbbrev(entry);
  const position = entry.position || "—";
  const recommendation = csIntelRecommendationFromTier(intel.convictionTier);
  const recommendationClass = csIntelRecommendationClass(recommendation);
  const status = getSignalOfWeekStatus(entry);

  return `
    <div class="pi-modal-header-main">
      <div class="pi-modal-identity">
        <div class="pi-modal-headshot">${renderPlayerHeadshot(entry)}</div>
        <div class="pi-modal-identity-copy">
          <p class="eyebrow pi-modal-kicker">Player Intelligence</p>
          <h2 class="pi-modal-title" id="pi-modal-title">${entry.player_name}</h2>
          <div class="pi-modal-meta">
            <span class="pi-modal-meta-chip">
              <span class="team-logo-placeholder">${renderTeamLogoMarkup(entry)}</span>
              ${team}
            </span>
            <span class="pi-modal-meta-chip pi-modal-meta-chip--muted">${position}</span>
          </div>
        </div>
      </div>

      <div class="pi-modal-header-stats">
        <div class="pi-modal-stat">
          <span class="pi-modal-stat-value">${formatScore(intel.score)}</span>
          <span class="pi-modal-stat-label">CardSignal Score</span>
        </div>
        <div class="pi-modal-stat">
          <span class="pi-modal-stat-value cs-recommendation-badge ${recommendationClass} pi-modal-rec-badge">${recommendation}</span>
          <span class="pi-modal-stat-label">Recommendation</span>
        </div>
        <div class="pi-modal-stat">
          <span class="pi-modal-stat-value pi-status-pill ${status.className}">${status.label}</span>
          <span class="pi-modal-stat-label">Status</span>
        </div>
      </div>

      <div class="pi-modal-header-actions">
        <button type="button" id="watchlist-toggle-btn" class="player-save-btn pi-modal-save-btn">
          ${currentUser ? "Save to watchlist" : "Sign in to save"}
        </button>
        <button type="button" class="pi-modal-close" data-pi-close aria-label="Close player intelligence report">✕</button>
      </div>
    </div>
  `;
}

function renderPiModalBody(entry, intel, activeTab) {
  switch (activeTab) {
    case "cards":
      return renderPiCardsTab(entry, intel);
    case "market":
      return renderPiMarketTab(entry, intel);
    case "signals":
      return renderPiSignalsTab(entry, intel);
    case "forecast":
      return renderPiForecastTab(entry, intel);
    case "overview":
    default:
      return renderPiOverviewTab(entry, intel);
  }
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

function updatePiModalTabState() {
  const tabsRoot = document.getElementById("pi-modal-tabs");
  if (!tabsRoot) return;

  tabsRoot.querySelectorAll("[data-pi-tab]").forEach((button) => {
    const isActive = button.dataset.piTab === piActiveTab;
    button.classList.toggle("pi-modal-tab--active", isActive);
    button.setAttribute("aria-selected", isActive ? "true" : "false");
  });
}

function setupPiTabNavigation() {
  const tabsRoot = document.getElementById("pi-modal-tabs");
  if (!tabsRoot || tabsRoot.dataset.piTabsBound === "1") return;
  tabsRoot.dataset.piTabsBound = "1";

  tabsRoot.addEventListener("click", (event) => {
    const button = event.target.closest("[data-pi-tab]");
    if (!button || !piModalEntry || !piModalIntel) return;

    const tabId = button.dataset.piTab;
    if (!tabId || tabId === piActiveTab) return;

    piActiveTab = tabId;
    updatePiModalTabState();

    const body = document.getElementById("pi-modal-body");
    if (body) body.innerHTML = renderPiModalBody(piModalEntry, piModalIntel, piActiveTab);
  });
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

  setupPiTabNavigation();
  bindPiModalKeydown();
}

function closePlayerIntelligenceModal() {
  const modal = document.getElementById("player-intelligence-modal");
  if (!modal) return;

  modal.classList.add("hidden");
  modal.setAttribute("aria-hidden", "true");
  unlockBodyScrollForModal();
  piActiveTab = "overview";
  piModalEntry = null;
  piModalIntel = null;
}

async function openPlayerIntelligenceModal(entry) {
  const modal = document.getElementById("player-intelligence-modal");
  const header = document.getElementById("pi-modal-header");
  const tabs = document.getElementById("pi-modal-tabs");
  const body = document.getElementById("pi-modal-body");
  if (!modal || !header || !tabs || !body) return;

  selectedPlayer = entry;

  try {
    const player = entry.player_id ? await fetchPlayer(entry.player_id) : entry;
    selectedPlayer = player;
    const intel = buildPlayerIntel(player);

    piModalEntry = player;
    piModalIntel = intel;
    piActiveTab = "overview";

    header.innerHTML = renderPiModalHeader(player, intel);
    tabs.innerHTML = renderPiModalTabs(piActiveTab);
    body.innerHTML = renderPiModalBody(player, intel, piActiveTab);

    wirePlayerActions();
    updatePiModalTabState();

    modal.classList.remove("hidden");
    modal.setAttribute("aria-hidden", "false");
    lockBodyScrollForModal();

    requestAnimationFrame(() => {
      modal.querySelector(".pi-modal-close")?.focus();
    });

    if (player.player_id) {
      await renderScoreHistory(player.player_id);
    } else {
      destroyChart(scoreChart);
      showChartPlaceholder("score-history-chart", "score-history-placeholder", true);
    }
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
  if (!canvas) return;
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

function computeSignalOfWeekMovement(entry = {}) {
  if (entry.weekly_change != null && Number.isFinite(Number(entry.weekly_change))) {
    const delta = Number(entry.weekly_change);
    const arrow = delta > 0.01 ? "↑" : delta < -0.01 ? "↓" : "→";
    const signed = delta > 0 ? `+${delta.toFixed(1)}` : delta < 0 ? `${delta.toFixed(1)}` : `+0.0`;
    return { arrow, signed };
  }

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

function openSignalOfWeekReport(entry) {
  selectPlayer(entry);
}

function renderSportSignalCard(sport) {
  const entry = getSportSignalEntry(sport);
  const noSelection = !entry && sport === 'MLB' && weeklyIntelligence?.run;

  if (noSelection) {
    return `
      <article class="sport-signal-card sport-signal-card--empty" data-sport="${sport}">
        <div class="sport-signal-card-header">
          <span class="sport-signal-sport-icon">${getSportIcon({ sport })}</span>
          <span class="sport-signal-sport-label">${sport} Signal</span>
        </div>
        <p class="sport-signal-empty-copy">No player qualified this week — insufficient evidence.</p>
      </article>`;
  }

  if (!entry) {
    return `
      <article class="sport-signal-card sport-signal-card--empty" data-sport="${sport}">
        <div class="sport-signal-card-header">
          <span class="sport-signal-sport-icon">${getSportIcon({ sport })}</span>
          <span class="sport-signal-sport-label">${sport} Signal</span>
        </div>
        <p class="sport-signal-empty-copy">Signal data unavailable.</p>
      </article>`;
  }

  const score = Number(entry?.hotness?.total_score ?? 0);
  const movement = computeSignalOfWeekMovement(entry);
  const moveClass = movement.signed.startsWith("+") ? "metric-up" : movement.signed.startsWith("-") ? "metric-down" : "metric-flat";
  const recommendation = getEntryRecommendation(entry);
  const recClass = recommendation.toLowerCase();
  const team = getTeamAbbrev(entry);
  const initials = getPlayerInitials(entry.player_name);
  const photo = entry.headshot_url
    ? `<img src="${entry.headshot_url}" alt="" loading="lazy" class="player-headshot-image" onerror="this.remove();this.parentElement.insertAdjacentHTML('beforeend','<span>${initials}</span>')" />`
    : `<span>${initials}</span>`;

  return `
    <article class="sport-signal-card" data-sport="${sport}">
      <div class="sport-signal-card-header">
        <span class="sport-signal-sport-icon">${getSportIcon(entry)}</span>
        <span class="sport-signal-sport-label">${sport} Signal</span>
      </div>
      <div class="sport-signal-player">
        <div class="sport-signal-photo">${photo}</div>
        <div class="sport-signal-identity">
          <div class="sport-signal-name">${entry.player_name || "—"}</div>
          <div class="sport-signal-team">${team}</div>
        </div>
      </div>
      <div class="sport-signal-metrics">
        <div class="sport-signal-metric">
          <span class="sport-signal-metric-value">${formatScore(score)}</span>
          <span class="sport-signal-metric-label">CardSignal Score</span>
        </div>
        <div class="sport-signal-metric">
          <span class="sport-signal-rec-pill sport-signal-rec-pill--${recClass}">${recommendation}</span>
          <span class="sport-signal-metric-label">Recommendation</span>
        </div>
        <div class="sport-signal-metric">
          <span class="sport-signal-metric-value ${moveClass}">${movement.arrow} ${movement.signed}</span>
          <span class="sport-signal-metric-label">Weekly Movement</span>
        </div>
      </div>
      <button type="button" class="sport-signal-cta" data-sport-signal="${sport}">
        View Report
        <span class="sport-signal-cta-arrow" aria-hidden="true">→</span>
      </button>
    </article>`;
}

function wireSportSignalCards() {
  const root = document.getElementById('this-weeks-signals-grid');
  if (!root) return;

  root.querySelectorAll('[data-sport-signal]').forEach((button) => {
    button.addEventListener('click', (event) => {
      event.stopPropagation();
      const sport = button.dataset.sportSignal;
      const entry = getSportSignalEntry(sport);
      if (entry) openSignalOfWeekReport(entry);
    });
  });
}

function renderThisWeeksSignals() {
  const root = document.getElementById('this-weeks-signals-grid');
  if (!root) return;

  const sportsToShow = activeSportFilter === 'ALL' ? SPORT_KEYS : [activeSportFilter];
  root.innerHTML = sportsToShow.map((sport) => renderSportSignalCard(sport)).join('');
  wireSportSignalCards();
}

/** @deprecated Use renderThisWeeksSignals — kept for compatibility */
function renderSignalOfTheWeek(entries = [], storedSignal = null) {
  renderThisWeeksSignals();
}

/* Signal Center — main dashboard render pipeline */
function renderSignalCenter(entries) {
  renderThisWeeksSignals();
  renderCardSection(entries, activeSportFilter === 'MLB' ? weeklyIntelligence?.card_intelligence : null);
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
    const [payload, weeklyPayload] = await Promise.all([
      fetch(SOURCE_URL).then(res => {
        if (!res.ok) throw new Error(`Could not load ${SOURCE_URL}.`);
        return res.json();
      }),
      fetchWeeklyLatest('MLB').catch(() => null),
    ]);

    weeklyIntelligence = weeklyPayload;
    let entries = payload.items || [];

    if (weeklyPayload?.todays_leaders?.length) {
      entries = weeklyPayload.todays_leaders.map(weeklyLeaderToEntry);
    }

    populateSportDatasets(entries, weeklyPayload);
    setupPlayerSearch();
    setupPlayerIntelligenceModal();
    setupSportTabs();

    status.textContent = 'Rendering Signal Center...';
    renderWeeklyRefreshNote();
    refreshHomepage();

    status.textContent = `Loaded ${getCombinedLeaderEntries().length} players from ${payload.data_source || 'api'}`;

    if (currentUser) {
      await Promise.all([loadRules(), loadWatchlist(), loadAlerts(), loadNotifications()]);
    }

    if (adminToken) await loadAdmin();

  } catch (error) {
    console.error("CardSignal load error:", error);

    status.textContent = `Load failed: ${error.message}`;
    status.style.color = '#9A6656';

    // Graceful fallback: still show Signal Center sections.
    try {
      populateSportDatasets([], null);
      setupSportTabs();
      refreshHomepage();
    } catch (_) {}
  }
}

init();
