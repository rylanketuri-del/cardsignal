/**
 * CardSignal Identity — Sprint 8.2
 *
 * Deterministic ID helpers shared across frontend registry and intelligence layers.
 * Mirrors cardchase_ai/identity.py so IDs remain stable across Python and JS.
 */
(function initCardSignalIdentity(global) {
  "use strict";

  const SUPPORTED_LEAGUES = new Set([
    "MLB",
    "NFL",
    "NBA",
    "NHL",
    "SOCCER",
    "F1",
    "UFC",
    "POKEMON",
    "TCG",
  ]);

  const SPORT_TO_LEAGUE = {
    MLB: "MLB",
    NFL: "NFL",
    NBA: "NBA",
    NHL: "NHL",
    SOCCER: "SOCCER",
    F1: "F1",
    UFC: "UFC",
    POKEMON: "POKEMON",
    TCG: "TCG",
  };

  const MIN_YEAR = 1900;
  const MAX_YEAR = 2100;
  const MIN_WEEK = 1;
  const MAX_WEEK = 53;
  const IDENTITY_SOURCE_PLACEHOLDER_REGISTRY = "placeholder_registry";

  function normalizeLeague(league) {
    const normalized = String(league || "").trim().toUpperCase();
    if (!SUPPORTED_LEAGUES.has(normalized)) {
      throw new Error(`Unsupported league namespace: ${league}`);
    }
    return normalized;
  }

  function normalizeSourceId(sourceId) {
    const value = String(sourceId || "").trim();
    if (!value) throw new Error("source_player_id is required");
    if (!/^[A-Za-z0-9_-]+$/.test(value)) {
      throw new Error(`Invalid source_player_id: ${sourceId}`);
    }
    return value;
  }

  function validateYear(year) {
    const value = Number(year);
    if (!Number.isFinite(value) || value < MIN_YEAR || value > MAX_YEAR) {
      throw new Error(`Invalid year: ${year}`);
    }
    return value;
  }

  function validateWeek(week) {
    const value = Number(week);
    if (!Number.isFinite(value) || value < MIN_WEEK || value > MAX_WEEK) {
      throw new Error(`Invalid week number: ${week}`);
    }
    return value;
  }

  function stableHash(parts) {
    const normalized = parts.map((part) => String(part || "").trim().toLowerCase()).join("|");
    let hash = 2166136261;
    for (let i = 0; i < normalized.length; i += 1) {
      hash ^= normalized.charCodeAt(i);
      hash = Math.imul(hash, 16777619);
    }
    const hex = (hash >>> 0).toString(16).padStart(8, "0");
    let hash2 = Math.imul(hash, 2246822519) >>> 0;
    hash2 = Math.imul(hash2 ^ (hash2 >>> 13), 3266489917) >>> 0;
    return `${hex}${hash2.toString(16).padStart(8, "0")}`.slice(0, 12);
  }

  function sportToLeague(sport) {
    const key = String(sport || "MLB").trim().toUpperCase();
    return SPORT_TO_LEAGUE[key] || (SUPPORTED_LEAGUES.has(key) ? key : "MLB");
  }

  function createPlayerCsId(league, sourcePlayerId) {
    const leagueCode = normalizeLeague(league);
    const stableId = normalizeSourceId(sourcePlayerId);
    return `CS-${leagueCode}-P-${stableId}`;
  }

  function createPlayerCsIdFromName(league, playerName) {
    const leagueCode = normalizeLeague(league);
    const name = String(playerName || "").trim().toLowerCase();
    if (!name) throw new Error("player_name is required when source_player_id is missing");
    const stableId = stableHash([leagueCode, "player-name", name]);
    return `CS-${leagueCode}-P-${stableId}`;
  }

  function parseSetIdentity(setValue) {
    const raw = String(setValue || "").trim();
    const yearMatch = raw.match(/^(\d{4})\s+(.+)$/);
    const year = yearMatch ? yearMatch[1] : "";
    const remainder = yearMatch ? yearMatch[2] : raw;
    const parts = remainder.split(/\s+/);
    const manufacturer = parts[0] || "";
    const setName = remainder || raw;
    return { year, manufacturer, setName };
  }

  function normalizeGradingFields(grade, gradingCompany) {
    const gradeValue = String(grade || "Raw").trim() || "Raw";
    if (gradeValue.toLowerCase() === "raw") {
      return { grade: "Raw", gradingCompany: null };
    }

    if (gradingCompany) {
      return { grade: gradeValue, gradingCompany: String(gradingCompany).trim() || null };
    }

    const psaMatch = gradeValue.match(/^PSA\s*(\d+(?:\.\d+)?)$/i);
    if (psaMatch) return { grade: psaMatch[1], gradingCompany: "PSA" };

    const bgsMatch = gradeValue.match(/^BGS\s*(\d+(?:\.\d+)?)$/i);
    if (bgsMatch) return { grade: bgsMatch[1], gradingCompany: "BGS" };

    const sgcMatch = gradeValue.match(/^SGC\s*(\d+(?:\.\d+)?)$/i);
    if (sgcMatch) return { grade: sgcMatch[1], gradingCompany: "SGC" };

    return { grade: gradeValue, gradingCompany: gradingCompany || null };
  }

  function createCardStableId(
    league,
    sourcePlayerId,
    { year, manufacturer, setName, cardName, parallel, grade = "Raw", gradingCompany = null } = {}
  ) {
    const leagueCode = normalizeLeague(league);
    const playerId = normalizeSourceId(sourcePlayerId);
    const grading = normalizeGradingFields(grade, gradingCompany);

    return stableHash([
      leagueCode,
      playerId,
      String(year || ""),
      manufacturer,
      setName,
      cardName,
      parallel,
      grading.grade,
      grading.gradingCompany || "",
    ]);
  }

  function createCardCsId(league, cardIdentity) {
    const leagueCode = normalizeLeague(league);
    let sourcePlayerId = cardIdentity.source_player_id;
    if (!sourcePlayerId && cardIdentity.cs_player_id) {
      sourcePlayerId = String(cardIdentity.cs_player_id).split("-").pop();
    }
    if (!sourcePlayerId && cardIdentity.player_name) {
      sourcePlayerId = stableHash(["player-name", cardIdentity.player_name]);
    }

    const stableCardId = createCardStableId(leagueCode, sourcePlayerId, {
      year: cardIdentity.year || "",
      manufacturer: cardIdentity.manufacturer || "",
      setName: cardIdentity.set_name || cardIdentity.set || "",
      cardName: cardIdentity.card_name || cardIdentity.card || "",
      parallel: cardIdentity.parallel || "",
      grade: cardIdentity.grade || "Raw",
      gradingCompany: cardIdentity.grading_company,
    });

    return `CS-${leagueCode}-C-${stableCardId}`;
  }

  function createSignalCsId(league, year, week, sourcePlayerId) {
    const leagueCode = normalizeLeague(league);
    const yearValue = validateYear(year);
    const weekValue = validateWeek(week);
    const stableId = normalizeSourceId(sourcePlayerId);
    return `CS-${leagueCode}-S-${yearValue}W${weekValue}-${stableId}`;
  }

  function createForecastCsId(league, year, week, sourcePlayerId) {
    const leagueCode = normalizeLeague(league);
    const yearValue = validateYear(year);
    const weekValue = validateWeek(week);
    const stableId = normalizeSourceId(sourcePlayerId);
    return `CS-${leagueCode}-F-${yearValue}W${weekValue}-${stableId}`;
  }

  function currentIsoWeekYear(referenceDate) {
    const moment = referenceDate instanceof Date ? referenceDate : new Date();
    const thursday = new Date(Date.UTC(moment.getUTCFullYear(), moment.getUTCMonth(), moment.getUTCDate()));
    thursday.setUTCDate(thursday.getUTCDate() + 4 - (thursday.getUTCDay() || 7));
    const yearStart = new Date(Date.UTC(thursday.getUTCFullYear(), 0, 1));
    const week = Math.ceil((((thursday - yearStart) / 86400000) + 1) / 7);
    return { year: thursday.getUTCFullYear(), week };
  }

  function resolveSourcePlayerId(entry) {
    for (const key of ["source_player_id", "player_id"]) {
      const value = entry?.[key];
      if (value !== null && value !== undefined && String(value).trim()) {
        return String(value).trim();
      }
    }
    return null;
  }

  function buildPlayerIdentity(entry) {
    const sport = String(entry?.sport || "MLB").trim().toUpperCase();
    const league = String(entry?.league || sportToLeague(sport)).trim().toUpperCase();
    const playerName = entry?.player_name || entry?.full_name || "";
    const sourcePlayerId = resolveSourcePlayerId(entry);

    let csPlayerId;
    if (sourcePlayerId) {
      csPlayerId = createPlayerCsId(league, sourcePlayerId);
    } else {
      csPlayerId = createPlayerCsIdFromName(league, playerName);
    }

    const { year, week } = currentIsoWeekYear();
    const signalSource = sourcePlayerId || csPlayerId.split("-").pop();

    return {
      cs_player_id: csPlayerId,
      source_player_id: sourcePlayerId,
      league,
      sport,
      player_name: playerName,
      cs_signal_id: createSignalCsId(league, year, week, signalSource),
      cs_forecast_id: createForecastCsId(league, year, week, signalSource),
      signal_year: year,
      signal_week: week,
    };
  }

  function enrichPlayerEntry(entry) {
    return { ...entry, ...buildPlayerIdentity(entry) };
  }

  function enrichCardRegistryEntry(card, { league, sourcePlayerId, csPlayerId, playerName = "" } = {}) {
    const setValue = card.set || "";
    const parsed = parseSetIdentity(setValue);
    const year = String(card.year || parsed.year || "");
    const manufacturer = card.manufacturer || parsed.manufacturer;
    const setName = card.set_name || parsed.setName;
    const cardName = card.card_name || card.card || "";
    const parallel = card.parallel || "";
    const grading = normalizeGradingFields(card.grade, card.grading_company);

    const identityFields = {
      year,
      manufacturer,
      set_name: setName,
      card_name: cardName,
      parallel,
      grade: grading.grade,
      grading_company: grading.gradingCompany,
      league: normalizeLeague(league),
      source_player_id: sourcePlayerId !== null && sourcePlayerId !== undefined ? String(sourcePlayerId) : null,
      cs_player_id: csPlayerId,
      player_name: playerName,
      source: card.source || IDENTITY_SOURCE_PLACEHOLDER_REGISTRY,
    };

    identityFields.cs_card_id = createCardCsId(league, {
      ...identityFields,
      set: setValue,
      card: cardName,
    });

    return { ...card, ...identityFields };
  }

  global.CardSignalIdentity = {
    SUPPORTED_LEAGUES,
    SPORT_TO_LEAGUE,
    IDENTITY_SOURCE_PLACEHOLDER_REGISTRY,
    normalizeLeague,
    normalizeSourceId,
    validateYear,
    validateWeek,
    sportToLeague,
    createPlayerCsId,
    createPlayerCsIdFromName,
    createCardStableId,
    createCardCsId,
    createSignalCsId,
    createForecastCsId,
    currentIsoWeekYear,
    parseSetIdentity,
    normalizeGradingFields,
    buildPlayerIdentity,
    enrichPlayerEntry,
    enrichCardRegistryEntry,
  };
})(typeof window !== "undefined" ? window : globalThis);
