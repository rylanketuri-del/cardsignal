const API_BASE_URL =
  (window.APP_CONFIG && window.APP_CONFIG.API_BASE_URL) ||
  "https://cardsignal-api.onrender.com";

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

function buildLeaderboard(entries) {
  return `
    <table class="table">
      <thead><tr><th>Rank</th><th>Player</th><th>Total</th><th>Performance</th><th>Market</th><th>Tag</th></tr></thead>
      <tbody>
        ${entries.map((entry, index) => `
          <tr data-index="${index}" data-player-id="${entry.player_id || ''}">
            <td>#${entry.rank || index + 1}</td>
            <td>${entry.player_name}</td>
            <td class="score">${formatScore(entry.hotness.total_score)}</td>
            <td>${formatScore(entry.hotness.performance_score)}</td>
            <td>${formatScore(entry.hotness.market_score)}</td>
            <td><span class="${tagClass(entry.hotness.tag)}">${entry.hotness.tag}</span></td>
          </tr>`).join('')}
      </tbody>
    </table>`;
}

function renderPlayerDetail(entry) {
  selectedPlayer = entry;
  const reasons = entry.hotness.reasons?.length
    ? entry.hotness.reasons.map(reason => `<span class="reason">${reason}</span>`).join('')
    : '<span class="reason">No key reasons generated yet</span>';
  const marketRows = Object.entries(entry.market_snapshots || {}).map(([name, snapshot]) => `
      <tr><td>${name}</td><td>${snapshot.listings_count ?? 0}</td><td>${snapshot.avg_price ? `$${snapshot.avg_price.toFixed(2)}` : '—'}</td></tr>`).join('');
  return `
    <div class="detail-card">
      <div class="detail-top">
        <div><div class="detail-name">${entry.player_name}</div><div class="hero-sub"><span class="${tagClass(entry.hotness.tag)}">${entry.hotness.tag}</span></div></div>
        <button id="watchlist-toggle-btn" class="primary">${currentUser ? 'Save to watchlist' : 'Sign in to save'}</button>
      </div>
      <div class="stat-grid">
        <div class="stat-box"><div class="k">Total score</div><div class="v">${formatScore(entry.hotness.total_score)}</div></div>
        <div class="stat-box"><div class="k">7D OPS</div><div class="v">${formatScore(entry.stats_7d.ops)}</div></div>
        <div class="stat-box"><div class="k">7D HR</div><div class="v">${entry.stats_7d.home_runs ?? 0}</div></div>
        <div class="stat-box"><div class="k">7D SB</div><div class="v">${entry.stats_7d.stolen_bases ?? 0}</div></div>
        <div class="stat-box"><div class="k">Market score</div><div class="v">${formatScore(entry.hotness.market_score)}</div></div>
        <div class="stat-box"><div class="k">Confidence</div><div class="v">${formatScore(entry.hotness.confidence_multiplier)}</div></div>
      </div>
      <div><div class="label">Why this player is here</div><div class="reasons">${reasons}</div></div>
      <div><div class="label">Market snapshots</div><table class="mini-table"><thead><tr><td><strong>Query</strong></td><td><strong>Listings</strong></td><td><strong>Avg price</strong></td></tr></thead><tbody>${marketRows}</tbody></table></div>
    </div>`;
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

function destroyChart(instance) { if (instance) instance.destroy(); }

async function renderScoreHistory(playerId) {
  const canvas = document.getElementById('score-history-chart');
  if (!canvas || !playerId) return;
  try {
    const payload = await fetchPlayerHistory(playerId);
    const items = payload.items || [];
    destroyChart(scoreChart);
    scoreChart = new Chart(canvas, {
      type: 'line',
      data: {
        labels: items.map(item => new Date(item.created_at).toLocaleDateString()),
        datasets: [
          { label: 'Total', data: items.map(i => i.total_score), tension: 0.3 },
          { label: 'Performance', data: items.map(i => i.performance_score), tension: 0.3 },
          { label: 'Market', data: items.map(i => i.market_score), tension: 0.3 },
        ],
      },
      options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true, max: 100 } } },
    });
  } catch (_) {}
}

async function renderLeaderboardHistory() {
  const canvas = document.getElementById('leaderboard-history-chart');
  if (!canvas) return;
  try {
    const payload = await fetchLeaderboardHistory();
    const items = payload.items || [];
    destroyChart(leaderboardHistoryChart);
    leaderboardHistoryChart = new Chart(canvas, {
      type: 'bar',
      data: {
        labels: items.map(item => new Date(item.created_at).toLocaleDateString()),
        datasets: [{ label: 'Top total score', data: items.map(item => Number(item.leaders?.[0]?.total_score || 0)) }],
      },
      options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true, max: 100 } } },
    });
  } catch (_) {}
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

async function init() {
  const status = document.getElementById('load-status');
  document.getElementById('api-hint').textContent = `API: ${API_BASE_URL}`;
  document.getElementById('admin-token').value = adminToken;
  try {
    await bootstrapSupabase();
    bindAuthActions();
    bindAdminActions();

    const payload = await fetch(SOURCE_URL).then(res => { if (!res.ok) throw new Error(`Could not load ${SOURCE_URL}.`); return res.json(); });
    const entries = payload.items || [];
    latestEntries = entries;
    if (!entries.length) throw new Error('Leaderboard response is empty.');

    const hot = entries[0];
    const chased = [...entries].sort((a, b) => b.hotness.market_score - a.hotness.market_score)[0];
    const buyLow = entries.find(item => item.hotness.tag === 'BUY LOW') || entries[0];
    document.getElementById('hero-player').textContent = hot.player_name;
    document.getElementById('hero-tag').textContent = `${hot.hotness.tag} • ${formatScore(hot.hotness.total_score)}`;
    document.getElementById('most-chased').textContent = `${chased.player_name} • ${formatScore(chased.hotness.market_score)}`;
    document.getElementById('buy-low').textContent = `${buyLow.player_name} • ${buyLow.hotness.tag}`;

    const leaderboardRoot = document.getElementById('leaderboard-table');
    leaderboardRoot.innerHTML = buildLeaderboard(entries);
    const rows = [...leaderboardRoot.querySelectorAll('tbody tr')];
    rows.forEach((row, index) => row.addEventListener('click', async () => {
      rows.forEach(r => r.classList.remove('active'));
      row.classList.add('active');
      await selectPlayer(entries[index]);
    }));
    if (rows[0]) rows[0].classList.add('active');
    await selectPlayer(entries[0]);
    await renderLeaderboardHistory();
    status.textContent = `Loaded ${entries.length} players from ${payload.data_source || 'api'}`;

    if (currentUser) await Promise.all([loadRules(), loadWatchlist(), loadAlerts(), loadNotifications()]);
    if (adminToken) await loadAdmin();
  } catch (error) {
    status.textContent = 'Load failed';
    status.style.color = '#ff9c9c';
    document.getElementById('leaderboard-table').innerHTML = `<div class="detail-empty">${error.message}</div>`;
  }
}

init();
