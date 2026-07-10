/**
 * Player Card Registry — Sprint 8.1
 *
 * Canonical card-product definitions per player. Future pricing sources
 * (eBay, PSA, SportscardsPro, etc.) enrich entries via enrichCardWithPricing()
 * without replacing the registry structure.
 */
(function initCardRegistry(global) {
  "use strict";

  const CURRENT_CARD_YEAR = 2025;

  /** @typedef {{ set: string, card: string, parallel: string, grade: string }} CardRegistryEntry */

  /**
   * Player-specific card registries. Keys are normalized player names.
   * @type {Record<string, { profile: 'prospect'|'rookie'|'veteran', cards: CardRegistryEntry[] }>}
   */
  const PLAYER_CARD_REGISTRIES = {
    "elly de la cruz": {
      profile: "rookie",
      cards: [
        { set: "2023 Topps Chrome", card: "Base Rookie", parallel: "Base", grade: "Raw" },
        { set: "2023 Topps Chrome", card: "Refractor", parallel: "Refractor", grade: "Raw" },
        { set: "2024 Topps Chrome", card: "Auto", parallel: "Blue", grade: "Raw" },
        { set: "2024 Bowman Chrome", card: "Refractor", parallel: "Refractor", grade: "Raw" },
        { set: "2025 Topps Chrome", card: "Base", parallel: "Base", grade: "Raw" },
        { set: "2024 Topps Chrome", card: "Sapphire", parallel: "Sapphire", grade: "Raw" },
      ],
    },
    "bobby witt jr.": {
      profile: "veteran",
      cards: [
        { set: "2022 Topps Chrome", card: "Base Rookie", parallel: "Base", grade: "Raw" },
        { set: "2024 Topps Chrome", card: "Auto", parallel: "Blue", grade: "Raw" },
        { set: "2024 Topps Chrome", card: "Refractor", parallel: "Refractor", grade: "Raw" },
        { set: "2023 Bowman Chrome", card: "Refractor", parallel: "Refractor", grade: "Raw" },
        { set: "2025 Topps Chrome", card: "Base", parallel: "Base", grade: "Raw" },
        { set: "2024 Topps Chrome", card: "Sapphire", parallel: "Sapphire", grade: "Raw" },
      ],
    },
    "gunnar henderson": {
      profile: "rookie",
      cards: [
        { set: "2023 Topps Chrome", card: "Base Rookie", parallel: "Base", grade: "Raw" },
        { set: "2023 Bowman Chrome", card: "1st Bowman", parallel: "Base", grade: "Raw" },
        { set: "2024 Topps Chrome", card: "Auto", parallel: "Blue", grade: "Raw" },
        { set: "2024 Topps Chrome", card: "Refractor", parallel: "Refractor", grade: "Raw" },
        { set: "2025 Topps Chrome", card: "Base", parallel: "Base", grade: "Raw" },
        { set: "2024 Topps Chrome", card: "Sapphire", parallel: "Sapphire", grade: "Raw" },
      ],
    },
    "jackson chourio": {
      profile: "rookie",
      cards: [
        { set: "2024 Topps Chrome", card: "Base Rookie", parallel: "Base", grade: "Raw" },
        { set: "2024 Bowman Chrome", card: "1st Bowman", parallel: "Base", grade: "Raw" },
        { set: "2025 Topps Chrome", card: "Base Rookie", parallel: "Base", grade: "Raw" },
        { set: "2025 Bowman Chrome", card: "Auto", parallel: "Blue", grade: "Raw" },
        { set: "2025 Topps Chrome", card: "Refractor", parallel: "Refractor", grade: "Raw" },
        { set: "2024 Topps Chrome", card: "Sapphire", parallel: "Sapphire", grade: "Raw" },
      ],
    },
    "juan soto": {
      profile: "veteran",
      cards: [
        { set: "2019 Topps Chrome", card: "Base Rookie", parallel: "Base", grade: "Raw" },
        { set: "2025 Topps Chrome", card: "Auto", parallel: "Blue", grade: "Raw" },
        { set: "2025 Topps Chrome", card: "Refractor", parallel: "Refractor", grade: "Raw" },
        { set: "2024 Topps Stadium Club", card: "Auto", parallel: "Base", grade: "Raw" },
        { set: "2025 Topps Heritage", card: "Base", parallel: "Base", grade: "Raw" },
        { set: "2024 Topps Chrome", card: "Sapphire", parallel: "Sapphire", grade: "Raw" },
      ],
    },
    "aaron judge": {
      profile: "veteran",
      cards: [
        { set: "2017 Topps Chrome", card: "Base Rookie", parallel: "Base", grade: "Raw" },
        { set: "2025 Topps Chrome", card: "Auto", parallel: "Blue", grade: "Raw" },
        { set: "2025 Topps Chrome", card: "Refractor", parallel: "Refractor", grade: "Raw" },
        { set: "2024 Topps Stadium Club", card: "Auto", parallel: "Base", grade: "Raw" },
        { set: "2025 Topps Heritage", card: "Base", parallel: "Base", grade: "Raw" },
        { set: "2024 Topps Chrome", card: "Sapphire", parallel: "Sapphire", grade: "Raw" },
      ],
    },
    "shohei ohtani": {
      profile: "veteran",
      cards: [
        { set: "2018 Topps Chrome", card: "Base Rookie", parallel: "Base", grade: "Raw" },
        { set: "2025 Topps Chrome", card: "Auto", parallel: "Blue", grade: "Raw" },
        { set: "2025 Topps Chrome", card: "Refractor", parallel: "Refractor", grade: "Raw" },
        { set: "2024 Topps Stadium Club", card: "Auto", parallel: "Base", grade: "Raw" },
        { set: "2025 Topps Heritage", card: "Base", parallel: "Base", grade: "Raw" },
        { set: "2024 Topps Chrome", card: "Sapphire", parallel: "Sapphire", grade: "Raw" },
      ],
    },
    "mookie betts": {
      profile: "veteran",
      cards: [
        { set: "2014 Topps Chrome", card: "Base Rookie", parallel: "Base", grade: "Raw" },
        { set: "2025 Topps Chrome", card: "Auto", parallel: "Blue", grade: "Raw" },
        { set: "2025 Topps Chrome", card: "Refractor", parallel: "Refractor", grade: "Raw" },
        { set: "2024 Topps Stadium Club", card: "Auto", parallel: "Base", grade: "Raw" },
        { set: "2025 Topps Heritage", card: "Base", parallel: "Base", grade: "Raw" },
        { set: "2024 Topps Chrome", card: "Sapphire", parallel: "Sapphire", grade: "Raw" },
      ],
    },
    "ronald acuna jr.": {
      profile: "veteran",
      cards: [
        { set: "2018 Topps Chrome", card: "Base Rookie", parallel: "Base", grade: "Raw" },
        { set: "2025 Topps Chrome", card: "Auto", parallel: "Blue", grade: "Raw" },
        { set: "2025 Topps Chrome", card: "Refractor", parallel: "Refractor", grade: "Raw" },
        { set: "2024 Topps Stadium Club", card: "Auto", parallel: "Base", grade: "Raw" },
        { set: "2025 Topps Heritage", card: "Base", parallel: "Base", grade: "Raw" },
        { set: "2024 Topps Chrome", card: "Sapphire", parallel: "Sapphire", grade: "Raw" },
      ],
    },
    "julio rodriguez": {
      profile: "rookie",
      cards: [
        { set: "2022 Topps Chrome", card: "Base Rookie", parallel: "Base", grade: "Raw" },
        { set: "2023 Bowman Chrome", card: "Refractor", parallel: "Refractor", grade: "Raw" },
        { set: "2024 Topps Chrome", card: "Auto", parallel: "Blue", grade: "Raw" },
        { set: "2025 Topps Chrome", card: "Base", parallel: "Base", grade: "Raw" },
        { set: "2025 Topps Chrome", card: "Refractor", parallel: "Refractor", grade: "Raw" },
        { set: "2024 Topps Chrome", card: "Sapphire", parallel: "Sapphire", grade: "Raw" },
      ],
    },
    "corbin carroll": {
      profile: "rookie",
      cards: [
        { set: "2023 Topps Chrome", card: "Base Rookie", parallel: "Base", grade: "Raw" },
        { set: "2023 Bowman Chrome", card: "1st Bowman", parallel: "Base", grade: "Raw" },
        { set: "2024 Topps Chrome", card: "Auto", parallel: "Blue", grade: "Raw" },
        { set: "2025 Topps Chrome", card: "Refractor", parallel: "Refractor", grade: "Raw" },
        { set: "2025 Topps Chrome", card: "Base", parallel: "Base", grade: "Raw" },
        { set: "2024 Topps Chrome", card: "Sapphire", parallel: "Sapphire", grade: "Raw" },
      ],
    },
    "paul skenes": {
      profile: "prospect",
      cards: [
        { set: "2024 Bowman Chrome", card: "1st Bowman", parallel: "Base", grade: "Raw" },
        { set: "2024 Topps Chrome", card: "Base Rookie", parallel: "Base", grade: "Raw" },
        { set: "2025 Bowman Chrome", card: "Auto", parallel: "Blue", grade: "Raw" },
        { set: "2025 Topps Chrome", card: "Refractor", parallel: "Refractor", grade: "Raw" },
        { set: "2025 Topps Chrome", card: "Base Rookie", parallel: "Base", grade: "Raw" },
        { set: "2024 Topps Chrome", card: "Sapphire", parallel: "Sapphire", grade: "Raw" },
      ],
    },
    "junior caminero": {
      profile: "prospect",
      cards: [
        { set: "2024 Bowman Chrome", card: "1st Bowman", parallel: "Base", grade: "Raw" },
        { set: "2025 Bowman Chrome", card: "Auto", parallel: "Blue", grade: "Raw" },
        { set: "2025 Topps Chrome", card: "Base Rookie", parallel: "Base", grade: "Raw" },
        { set: "2025 Topps Chrome", card: "Refractor", parallel: "Refractor", grade: "Raw" },
        { set: "2024 Topps Chrome", card: "Base Rookie", parallel: "Base", grade: "Raw" },
        { set: "2024 Topps Chrome", card: "Sapphire", parallel: "Sapphire", grade: "Raw" },
      ],
    },
    "roman anthony": {
      profile: "prospect",
      cards: [
        { set: "2024 Bowman Chrome", card: "1st Bowman", parallel: "Base", grade: "Raw" },
        { set: "2025 Bowman Chrome", card: "Auto", parallel: "Blue", grade: "Raw" },
        { set: "2025 Topps Chrome", card: "Base Rookie", parallel: "Base", grade: "Raw" },
        { set: "2025 Topps Chrome", card: "Refractor", parallel: "Refractor", grade: "Raw" },
        { set: "2024 Bowman Chrome", card: "Refractor", parallel: "Refractor", grade: "Raw" },
        { set: "2024 Topps Chrome", card: "Sapphire", parallel: "Sapphire", grade: "Raw" },
      ],
    },
    "wyatt langford": {
      profile: "rookie",
      cards: [
        { set: "2024 Topps Chrome", card: "Base Rookie", parallel: "Base", grade: "Raw" },
        { set: "2024 Bowman Chrome", card: "1st Bowman", parallel: "Base", grade: "Raw" },
        { set: "2025 Topps Chrome", card: "Base Rookie", parallel: "Base", grade: "Raw" },
        { set: "2025 Bowman Chrome", card: "Auto", parallel: "Blue", grade: "Raw" },
        { set: "2025 Topps Chrome", card: "Refractor", parallel: "Refractor", grade: "Raw" },
        { set: "2024 Topps Chrome", card: "Sapphire", parallel: "Sapphire", grade: "Raw" },
      ],
    },
    "sal frelick": {
      profile: "rookie",
      cards: [
        { set: "2024 Topps Chrome", card: "Base Rookie", parallel: "Base", grade: "Raw" },
        { set: "2024 Bowman Chrome", card: "1st Bowman", parallel: "Base", grade: "Raw" },
        { set: "2025 Topps Chrome", card: "Refractor", parallel: "Refractor", grade: "Raw" },
        { set: "2025 Topps Chrome", card: "Base", parallel: "Base", grade: "Raw" },
        { set: "2025 Bowman Chrome", card: "Auto", parallel: "Blue", grade: "Raw" },
        { set: "2024 Topps Chrome", card: "Sapphire", parallel: "Sapphire", grade: "Raw" },
      ],
    },
  };

  /** @type {Record<'prospect'|'rookie'|'veteran', CardRegistryEntry[]>} */
  const PROFILE_CARD_TEMPLATES = {
    prospect: [
      { set: `${CURRENT_CARD_YEAR} Bowman Chrome`, card: "1st Bowman", parallel: "Base", grade: "Raw" },
      { set: `${CURRENT_CARD_YEAR} Bowman Chrome`, card: "Auto", parallel: "Blue", grade: "Raw" },
      { set: `${CURRENT_CARD_YEAR} Topps Chrome`, card: "Base Rookie", parallel: "Base", grade: "Raw" },
      { set: `${CURRENT_CARD_YEAR} Topps Chrome`, card: "Refractor", parallel: "Refractor", grade: "Raw" },
      { set: `${CURRENT_CARD_YEAR - 1} Topps Chrome`, card: "Sapphire", parallel: "Sapphire", grade: "Raw" },
      { set: `${CURRENT_CARD_YEAR} Bowman Draft`, card: "Chrome Auto", parallel: "Gold", grade: "Raw" },
    ],
    rookie: [
      { set: `${CURRENT_CARD_YEAR} Topps Chrome`, card: "Base Rookie", parallel: "Base", grade: "Raw" },
      { set: `${CURRENT_CARD_YEAR} Topps Chrome`, card: "Refractor", parallel: "Refractor", grade: "Raw" },
      { set: `${CURRENT_CARD_YEAR} Bowman Chrome`, card: "1st Bowman", parallel: "Base", grade: "Raw" },
      { set: `${CURRENT_CARD_YEAR} Bowman Chrome`, card: "Auto", parallel: "Blue", grade: "Raw" },
      { set: `${CURRENT_CARD_YEAR - 1} Topps Chrome`, card: "Sapphire", parallel: "Sapphire", grade: "Raw" },
      { set: `${CURRENT_CARD_YEAR} Topps Update`, card: "Base Rookie", parallel: "Base", grade: "Raw" },
    ],
    veteran: [
      { set: `${CURRENT_CARD_YEAR} Topps Chrome`, card: "Base", parallel: "Base", grade: "Raw" },
      { set: `${CURRENT_CARD_YEAR} Topps Chrome`, card: "Refractor", parallel: "Refractor", grade: "Raw" },
      { set: `${CURRENT_CARD_YEAR} Topps Chrome`, card: "Auto", parallel: "Blue", grade: "Raw" },
      { set: `${CURRENT_CARD_YEAR - 1} Topps Stadium Club`, card: "Auto", parallel: "Base", grade: "Raw" },
      { set: `${CURRENT_CARD_YEAR} Topps Heritage`, card: "Base", parallel: "Base", grade: "Raw" },
      { set: `${CURRENT_CARD_YEAR - 1} Topps Chrome`, card: "Sapphire", parallel: "Sapphire", grade: "Raw" },
    ],
  };

  /** Section filters — which card types surface in each intelligence bucket. */
  const SECTION_CARD_FILTERS = {
    trending: (card) =>
      /refractor|sapphire|chrome/i.test(card.set + card.card + card.parallel),
    movers: (card) =>
      /auto|gold|blue|sapphire|refractor/i.test(card.card + card.parallel),
    buyLow: (card) =>
      /base|heritage|update/i.test(card.card + card.parallel + card.set) && !/auto/i.test(card.card),
    chased: (card) =>
      /auto|1st bowman|sapphire|bowman/i.test(card.card + card.set + card.parallel),
  };

  function normalizePlayerName(name = "") {
    return String(name || "").trim().toLowerCase().replace(/\s+/g, " ");
  }

  function extractCardYear(set = "") {
    const match = String(set).match(/\b(19|20)\d{2}\b/);
    return match ? match[0] : "";
  }

  function extractSetName(set = "") {
    return String(set).replace(/^\s*\d{4}\s+/, "").trim();
  }

  function formatCardLabel(entry) {
    if (entry.parallel === "Sapphire" || /sapphire/i.test(entry.card)) return "Sapphire";
    if (/^base/i.test(entry.card)) return "Base";
    if (/refractor/i.test(entry.card) || entry.parallel === "Refractor") return "Refractor";
    if (/auto/i.test(entry.card)) return "Auto";
    if (/1st bowman/i.test(entry.card)) return "1st Bowman";
    return entry.card;
  }

  function formatCardDisplayName(entry) {
    const year = extractCardYear(entry.set);
    const setName = extractSetName(entry.set);
    const label = formatCardLabel(entry);
    return year ? `${year} ${setName} ${label}` : `${setName} ${label}`;
  }

  function detectPlayerProfile(entry = {}) {
    const name = normalizePlayerName(entry.player_name);
    if (PLAYER_CARD_REGISTRIES[name]) {
      return PLAYER_CARD_REGISTRIES[name].profile;
    }

    const tag = String(entry.hotness?.tag || "").toUpperCase();
    if (tag.includes("BUY LOW") || tag.includes("MOST CHASED")) {
      return "prospect";
    }

    const position = String(entry.position || "").toUpperCase();
    if (position && !["OF", "SS", "2B", "3B", "1B", "C", "DH", "INF", "UTIL"].some((p) => position.includes(p))) {
      return "veteran";
    }

    return "rookie";
  }

  function getPlayerCardRegistry(entry = {}) {
    const identityApi = global.CardSignalIdentity;
    const playerIdentity = identityApi
      ? identityApi.buildPlayerIdentity(entry)
      : null;

    const name = normalizePlayerName(entry.player_name);
    const known = PLAYER_CARD_REGISTRIES[name];
    let cards;

    if (known && known.cards.length) {
      cards = known.cards.map((card) => ({ ...card }));
    } else {
      const profile = detectPlayerProfile(entry);
      cards = PROFILE_CARD_TEMPLATES[profile].map((card) => ({ ...card }));
    }

    if (!playerIdentity || !identityApi) {
      return cards;
    }

    return cards.map((card) => identityApi.enrichCardRegistryEntry(card, {
      league: playerIdentity.league,
      sourcePlayerId: playerIdentity.source_player_id,
      csPlayerId: playerIdentity.cs_player_id,
      playerName: playerIdentity.player_name,
    }));
  }

  function pickRegistryCards(registry, section, count, rng) {
    const filter = SECTION_CARD_FILTERS[section] || (() => true);
    const pool = registry.filter(filter);
    const source = pool.length >= count ? pool : registry;
    const used = new Set();
    const out = [];

    let attempts = 0;
    const maxAttempts = Math.max(source.length * 4, count * 8);

    while (out.length < count && used.size < source.length && attempts < maxAttempts) {
      attempts += 1;
      const idx = Math.floor(rng() * source.length);
      if (used.has(idx)) continue;
      used.add(idx);
      out.push({ ...source[idx] });
    }

    for (let i = 0; out.length < count && i < source.length; i += 1) {
      if (used.has(i)) continue;
      used.add(i);
      out.push({ ...source[i] });
    }

    return out;
  }

  /**
   * Attach placeholder or live pricing fields to a registry entry.
   * Future eBay/PSA sources call this instead of replacing registry rows.
   */
  function enrichCardWithPricing(card, pricing = {}) {
    return {
      ...card,
      price: pricing.price ?? card.price ?? null,
      movement: pricing.movement ?? card.movement ?? null,
      sales: pricing.sales ?? card.sales ?? null,
      listingCount: pricing.listingCount ?? card.listingCount ?? null,
      score: pricing.score ?? card.score ?? null,
    };
  }

  function buildCardDisplayItem(card, { price, movement, score } = {}) {
    const year = card.year || extractCardYear(card.set);
    const setName = card.set_name || extractSetName(card.set);
    const name = formatCardDisplayName(card);

    return {
      ...card,
      name,
      year,
      setName,
      parallel: card.parallel,
      grade: card.grade,
      price: price ?? card.price ?? null,
      movement: movement ?? card.movement ?? null,
      sales: card.sales ?? null,
      listingCount: card.listingCount ?? null,
      score: score ?? card.score ?? null,
    };
  }

  function buildSectionCards(registry, section, rng, options = {}) {
    const {
      count = 3,
      priceMin = 8,
      priceMax = 230,
      moveMin = 4,
      moveMax = 30,
      bias = 0,
      formatPercent,
    } = options;

    const picks = pickRegistryCards(registry, section, count, rng);

    return picks.map((card) => {
      const price = priceMin + rng() * (priceMax - priceMin);
      const magnitude = moveMin + rng() * (moveMax - moveMin);
      const direction = rng() > 0.5 ? 1 : -1;
      const move = (direction * magnitude) + bias + (rng() - 0.5) * 5;
      const movement = typeof formatPercent === "function"
        ? formatPercent(move)
        : `${move >= 0 ? "+" : ""}${move.toFixed(1)}%`;

      return buildCardDisplayItem(card, {
        price,
        movement,
        score: Math.round(40 + rng() * 55),
      });
    });
  }

  /**
   * Batch-enrich registry cards with live market snapshots.
   * Match on set + card + parallel; unmatched cards keep placeholders.
   */
  function applyMarketPricing(cards, marketSnapshots = []) {
    if (!Array.isArray(marketSnapshots) || !marketSnapshots.length) {
      return cards.map((card) => enrichCardWithPricing(card));
    }

    return cards.map((card) => {
      const key = `${card.set}|${card.card}|${card.parallel}`.toLowerCase();
      const match = marketSnapshots.find((snap) => {
        const snapKey = `${snap.set || ""}|${snap.card || ""}|${snap.parallel || ""}`.toLowerCase();
        return snapKey === key;
      });

      if (!match) return enrichCardWithPricing(card);

      return enrichCardWithPricing(card, {
        price: match.price ?? match.avg_price,
        movement: match.movement ?? match.price_movement,
        sales: match.sales ?? match.sales_volume,
        listingCount: match.listing_count ?? match.listings_count,
        score: match.score,
      });
    });
  }

  global.CardRegistry = {
    CURRENT_CARD_YEAR,
    PLAYER_CARD_REGISTRIES,
    PROFILE_CARD_TEMPLATES,
    normalizePlayerName,
    extractCardYear,
    extractSetName,
    formatCardDisplayName,
    formatCardLabel,
    detectPlayerProfile,
    getPlayerCardRegistry,
    pickRegistryCards,
    enrichCardWithPricing,
    buildCardDisplayItem,
    buildSectionCards,
    applyMarketPricing,
  };
})(typeof window !== "undefined" ? window : globalThis);
