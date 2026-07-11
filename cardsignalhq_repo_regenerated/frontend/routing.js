/**
 * Hash-based client routing for Scouting Report and Card Report deep links.
 * Routes:
 *   #/                     — Signal Center
 *   #/player/:playerId     — Scouting Report
 *   #/player/:playerId/card/:cardId — Card Report (nested in scouting flow)
 */
(function initCardSignalRouting(global) {
  const listeners = new Set();
  let suppressNextPopstate = false;

  function normalizeHash(hash) {
    const raw = String(hash || "").replace(/^#/, "").trim();
    if (!raw || raw === "/") return { type: "home" };
    const parts = raw.split("/").filter(Boolean);
    if (parts[0] === "player" && parts[1] && parts[2] === "card" && parts[3]) {
      return { type: "card", playerId: decodeURIComponent(parts[1]), cardId: decodeURIComponent(parts[3]) };
    }
    if (parts[0] === "player" && parts[1]) {
      return { type: "player", playerId: decodeURIComponent(parts[1]) };
    }
    return { type: "invalid", raw };
  }

  function getCurrentRoute() {
    return normalizeHash(global.location.hash);
  }

  function buildHash(route) {
    if (!route || route.type === "home") return "#/";
    if (route.type === "player" && route.playerId) {
      return `#/player/${encodeURIComponent(route.playerId)}`;
    }
    if (route.type === "card" && route.playerId && route.cardId) {
      return `#/player/${encodeURIComponent(route.playerId)}/card/${encodeURIComponent(route.cardId)}`;
    }
    return "#/";
  }

  function navigateTo(route, options = {}) {
    const hash = buildHash(route);
    if (options.replace) {
      global.history.replaceState({ cardSignalRoute: route }, "", hash);
    } else {
      global.history.pushState({ cardSignalRoute: route }, "", hash);
    }
    notify(route);
  }

  function notify(route) {
    listeners.forEach((listener) => {
      try {
        listener(route || getCurrentRoute());
      } catch (_) {
        /* listener errors should not break routing */
      }
    });
  }

  function onRouteChange(listener) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  }

  function handlePopstate() {
    if (suppressNextPopstate) {
      suppressNextPopstate = false;
      return;
    }
    notify(getCurrentRoute());
  }

  function back() {
    global.history.back();
  }

  function setSuppressNextPopstate(value) {
    suppressNextPopstate = Boolean(value);
  }

  global.addEventListener("popstate", handlePopstate);

  global.CardSignalRouting = {
    normalizeHash,
    getCurrentRoute,
    buildHash,
    navigateTo,
    onRouteChange,
    back,
    setSuppressNextPopstate,
  };
})(window);
