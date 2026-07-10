"""Backend player card registry — mirrors frontend Sprint 8.1 definitions."""

from __future__ import annotations

from typing import Any

from cardchase_ai.identity import enrich_card_registry_entry, normalize_league

CURRENT_CARD_YEAR = 2025

CardRegistryEntry = dict[str, str]

PLAYER_CARD_REGISTRIES: dict[str, dict[str, Any]] = {
    "elly de la cruz": {
        "profile": "rookie",
        "cards": [
            {"set": "2023 Topps Chrome", "card": "Base Rookie", "parallel": "Base", "grade": "Raw"},
            {"set": "2023 Topps Chrome", "card": "Refractor", "parallel": "Refractor", "grade": "Raw"},
            {"set": "2024 Topps Chrome", "card": "Auto", "parallel": "Blue", "grade": "Raw"},
            {"set": "2024 Bowman Chrome", "card": "Refractor", "parallel": "Refractor", "grade": "Raw"},
            {"set": "2025 Topps Chrome", "card": "Base", "parallel": "Base", "grade": "Raw"},
            {"set": "2024 Topps Chrome", "card": "Sapphire", "parallel": "Sapphire", "grade": "Raw"},
        ],
    },
    "bobby witt jr.": {
        "profile": "veteran",
        "cards": [
            {"set": "2022 Topps Chrome", "card": "Base Rookie", "parallel": "Base", "grade": "Raw"},
            {"set": "2024 Topps Chrome", "card": "Auto", "parallel": "Blue", "grade": "Raw"},
            {"set": "2024 Topps Chrome", "card": "Refractor", "parallel": "Refractor", "grade": "Raw"},
            {"set": "2023 Bowman Chrome", "card": "Refractor", "parallel": "Refractor", "grade": "Raw"},
            {"set": "2025 Topps Chrome", "card": "Base", "parallel": "Base", "grade": "Raw"},
            {"set": "2024 Topps Chrome", "card": "Sapphire", "parallel": "Sapphire", "grade": "Raw"},
        ],
    },
    "gunnar henderson": {
        "profile": "rookie",
        "cards": [
            {"set": "2023 Topps Chrome", "card": "Base Rookie", "parallel": "Base", "grade": "Raw"},
            {"set": "2023 Bowman Chrome", "card": "1st Bowman", "parallel": "Base", "grade": "Raw"},
            {"set": "2024 Topps Chrome", "card": "Auto", "parallel": "Blue", "grade": "Raw"},
            {"set": "2024 Topps Chrome", "card": "Refractor", "parallel": "Refractor", "grade": "Raw"},
            {"set": "2025 Topps Chrome", "card": "Base", "parallel": "Base", "grade": "Raw"},
            {"set": "2024 Topps Chrome", "card": "Sapphire", "parallel": "Sapphire", "grade": "Raw"},
        ],
    },
    "jackson chourio": {
        "profile": "rookie",
        "cards": [
            {"set": "2024 Topps Chrome", "card": "Base Rookie", "parallel": "Base", "grade": "Raw"},
            {"set": "2024 Bowman Chrome", "card": "1st Bowman", "parallel": "Base", "grade": "Raw"},
            {"set": "2025 Topps Chrome", "card": "Base Rookie", "parallel": "Base", "grade": "Raw"},
            {"set": "2025 Bowman Chrome", "card": "Auto", "parallel": "Blue", "grade": "Raw"},
            {"set": "2025 Topps Chrome", "card": "Refractor", "parallel": "Refractor", "grade": "Raw"},
            {"set": "2024 Topps Chrome", "card": "Sapphire", "parallel": "Sapphire", "grade": "Raw"},
        ],
    },
    "juan soto": {
        "profile": "veteran",
        "cards": [
            {"set": "2019 Topps Chrome", "card": "Base Rookie", "parallel": "Base", "grade": "Raw"},
            {"set": "2025 Topps Chrome", "card": "Auto", "parallel": "Blue", "grade": "Raw"},
            {"set": "2025 Topps Chrome", "card": "Refractor", "parallel": "Refractor", "grade": "Raw"},
            {"set": "2024 Topps Stadium Club", "card": "Auto", "parallel": "Base", "grade": "Raw"},
            {"set": "2025 Topps Heritage", "card": "Base", "parallel": "Base", "grade": "Raw"},
            {"set": "2024 Topps Chrome", "card": "Sapphire", "parallel": "Sapphire", "grade": "Raw"},
        ],
    },
    "aaron judge": {
        "profile": "veteran",
        "cards": [
            {"set": "2017 Topps Chrome", "card": "Base Rookie", "parallel": "Base", "grade": "Raw"},
            {"set": "2025 Topps Chrome", "card": "Auto", "parallel": "Blue", "grade": "Raw"},
            {"set": "2025 Topps Chrome", "card": "Refractor", "parallel": "Refractor", "grade": "Raw"},
            {"set": "2024 Topps Stadium Club", "card": "Auto", "parallel": "Base", "grade": "Raw"},
            {"set": "2025 Topps Heritage", "card": "Base", "parallel": "Base", "grade": "Raw"},
            {"set": "2024 Topps Chrome", "card": "Sapphire", "parallel": "Sapphire", "grade": "Raw"},
        ],
    },
    "shohei ohtani": {
        "profile": "veteran",
        "cards": [
            {"set": "2018 Topps Chrome", "card": "Base Rookie", "parallel": "Base", "grade": "Raw"},
            {"set": "2025 Topps Chrome", "card": "Auto", "parallel": "Blue", "grade": "Raw"},
            {"set": "2025 Topps Chrome", "card": "Refractor", "parallel": "Refractor", "grade": "Raw"},
            {"set": "2024 Topps Stadium Club", "card": "Auto", "parallel": "Base", "grade": "Raw"},
            {"set": "2025 Topps Heritage", "card": "Base", "parallel": "Base", "grade": "Raw"},
            {"set": "2024 Topps Chrome", "card": "Sapphire", "parallel": "Sapphire", "grade": "Raw"},
        ],
    },
    "mookie betts": {
        "profile": "veteran",
        "cards": [
            {"set": "2014 Topps Chrome", "card": "Base Rookie", "parallel": "Base", "grade": "Raw"},
            {"set": "2025 Topps Chrome", "card": "Auto", "parallel": "Blue", "grade": "Raw"},
            {"set": "2025 Topps Chrome", "card": "Refractor", "parallel": "Refractor", "grade": "Raw"},
            {"set": "2024 Topps Stadium Club", "card": "Auto", "parallel": "Base", "grade": "Raw"},
            {"set": "2025 Topps Heritage", "card": "Base", "parallel": "Base", "grade": "Raw"},
            {"set": "2024 Topps Chrome", "card": "Sapphire", "parallel": "Sapphire", "grade": "Raw"},
        ],
    },
    "ronald acuna jr.": {
        "profile": "veteran",
        "cards": [
            {"set": "2018 Topps Chrome", "card": "Base Rookie", "parallel": "Base", "grade": "Raw"},
            {"set": "2025 Topps Chrome", "card": "Auto", "parallel": "Blue", "grade": "Raw"},
            {"set": "2025 Topps Chrome", "card": "Refractor", "parallel": "Refractor", "grade": "Raw"},
            {"set": "2024 Topps Stadium Club", "card": "Auto", "parallel": "Base", "grade": "Raw"},
            {"set": "2025 Topps Heritage", "card": "Base", "parallel": "Base", "grade": "Raw"},
            {"set": "2024 Topps Chrome", "card": "Sapphire", "parallel": "Sapphire", "grade": "Raw"},
        ],
    },
    "julio rodriguez": {
        "profile": "rookie",
        "cards": [
            {"set": "2022 Topps Chrome", "card": "Base Rookie", "parallel": "Base", "grade": "Raw"},
            {"set": "2023 Bowman Chrome", "card": "Refractor", "parallel": "Refractor", "grade": "Raw"},
            {"set": "2024 Topps Chrome", "card": "Auto", "parallel": "Blue", "grade": "Raw"},
            {"set": "2025 Topps Chrome", "card": "Base", "parallel": "Base", "grade": "Raw"},
            {"set": "2025 Topps Chrome", "card": "Refractor", "parallel": "Refractor", "grade": "Raw"},
            {"set": "2024 Topps Chrome", "card": "Sapphire", "parallel": "Sapphire", "grade": "Raw"},
        ],
    },
    "corbin carroll": {
        "profile": "rookie",
        "cards": [
            {"set": "2023 Topps Chrome", "card": "Base Rookie", "parallel": "Base", "grade": "Raw"},
            {"set": "2023 Bowman Chrome", "card": "1st Bowman", "parallel": "Base", "grade": "Raw"},
            {"set": "2024 Topps Chrome", "card": "Auto", "parallel": "Blue", "grade": "Raw"},
            {"set": "2025 Topps Chrome", "card": "Refractor", "parallel": "Refractor", "grade": "Raw"},
            {"set": "2025 Topps Chrome", "card": "Base", "parallel": "Base", "grade": "Raw"},
            {"set": "2024 Topps Chrome", "card": "Sapphire", "parallel": "Sapphire", "grade": "Raw"},
        ],
    },
    "paul skenes": {
        "profile": "prospect",
        "cards": [
            {"set": "2024 Bowman Chrome", "card": "1st Bowman", "parallel": "Base", "grade": "Raw"},
            {"set": "2024 Topps Chrome", "card": "Base Rookie", "parallel": "Base", "grade": "Raw"},
            {"set": "2025 Bowman Chrome", "card": "Auto", "parallel": "Blue", "grade": "Raw"},
            {"set": "2025 Topps Chrome", "card": "Refractor", "parallel": "Refractor", "grade": "Raw"},
            {"set": "2025 Topps Chrome", "card": "Base Rookie", "parallel": "Base", "grade": "Raw"},
            {"set": "2024 Topps Chrome", "card": "Sapphire", "parallel": "Sapphire", "grade": "Raw"},
        ],
    },
    "junior caminero": {
        "profile": "prospect",
        "cards": [
            {"set": "2024 Bowman Chrome", "card": "1st Bowman", "parallel": "Base", "grade": "Raw"},
            {"set": "2025 Bowman Chrome", "card": "Auto", "parallel": "Blue", "grade": "Raw"},
            {"set": "2025 Topps Chrome", "card": "Base Rookie", "parallel": "Base", "grade": "Raw"},
            {"set": "2025 Topps Chrome", "card": "Refractor", "parallel": "Refractor", "grade": "Raw"},
            {"set": "2024 Topps Chrome", "card": "Base Rookie", "parallel": "Base", "grade": "Raw"},
            {"set": "2024 Topps Chrome", "card": "Sapphire", "parallel": "Sapphire", "grade": "Raw"},
        ],
    },
    "roman anthony": {
        "profile": "prospect",
        "cards": [
            {"set": "2024 Bowman Chrome", "card": "1st Bowman", "parallel": "Base", "grade": "Raw"},
            {"set": "2025 Bowman Chrome", "card": "Auto", "parallel": "Blue", "grade": "Raw"},
            {"set": "2025 Topps Chrome", "card": "Base Rookie", "parallel": "Base", "grade": "Raw"},
            {"set": "2025 Topps Chrome", "card": "Refractor", "parallel": "Refractor", "grade": "Raw"},
            {"set": "2024 Bowman Chrome", "card": "Refractor", "parallel": "Refractor", "grade": "Raw"},
            {"set": "2024 Topps Chrome", "card": "Sapphire", "parallel": "Sapphire", "grade": "Raw"},
        ],
    },
    "wyatt langford": {
        "profile": "rookie",
        "cards": [
            {"set": "2024 Topps Chrome", "card": "Base Rookie", "parallel": "Base", "grade": "Raw"},
            {"set": "2024 Bowman Chrome", "card": "1st Bowman", "parallel": "Base", "grade": "Raw"},
            {"set": "2025 Topps Chrome", "card": "Base Rookie", "parallel": "Base", "grade": "Raw"},
            {"set": "2025 Bowman Chrome", "card": "Auto", "parallel": "Blue", "grade": "Raw"},
            {"set": "2025 Topps Chrome", "card": "Refractor", "parallel": "Refractor", "grade": "Raw"},
            {"set": "2024 Topps Chrome", "card": "Sapphire", "parallel": "Sapphire", "grade": "Raw"},
        ],
    },
    "sal frelick": {
        "profile": "rookie",
        "cards": [
            {"set": "2024 Topps Chrome", "card": "Base Rookie", "parallel": "Base", "grade": "Raw"},
            {"set": "2024 Bowman Chrome", "card": "1st Bowman", "parallel": "Base", "grade": "Raw"},
            {"set": "2025 Topps Chrome", "card": "Refractor", "parallel": "Refractor", "grade": "Raw"},
            {"set": "2025 Topps Chrome", "card": "Base", "parallel": "Base", "grade": "Raw"},
            {"set": "2025 Bowman Chrome", "card": "Auto", "parallel": "Blue", "grade": "Raw"},
            {"set": "2024 Topps Chrome", "card": "Sapphire", "parallel": "Sapphire", "grade": "Raw"},
        ],
    },
}

PROFILE_CARD_TEMPLATES: dict[str, list[CardRegistryEntry]] = {
    "prospect": [
        {"set": f"{CURRENT_CARD_YEAR} Bowman Chrome", "card": "1st Bowman", "parallel": "Base", "grade": "Raw"},
        {"set": f"{CURRENT_CARD_YEAR} Bowman Chrome", "card": "Auto", "parallel": "Blue", "grade": "Raw"},
        {"set": f"{CURRENT_CARD_YEAR} Topps Chrome", "card": "Base Rookie", "parallel": "Base", "grade": "Raw"},
        {"set": f"{CURRENT_CARD_YEAR} Topps Chrome", "card": "Refractor", "parallel": "Refractor", "grade": "Raw"},
    ],
    "rookie": [
        {"set": f"{CURRENT_CARD_YEAR - 1} Topps Chrome", "card": "Base Rookie", "parallel": "Base", "grade": "Raw"},
        {"set": f"{CURRENT_CARD_YEAR} Topps Chrome", "card": "Base Rookie", "parallel": "Base", "grade": "Raw"},
        {"set": f"{CURRENT_CARD_YEAR} Topps Chrome", "card": "Refractor", "parallel": "Refractor", "grade": "Raw"},
        {"set": f"{CURRENT_CARD_YEAR} Bowman Chrome", "card": "Auto", "parallel": "Blue", "grade": "Raw"},
    ],
    "veteran": [
        {"set": f"{CURRENT_CARD_YEAR} Topps Chrome", "card": "Auto", "parallel": "Blue", "grade": "Raw"},
        {"set": f"{CURRENT_CARD_YEAR} Topps Chrome", "card": "Refractor", "parallel": "Refractor", "grade": "Raw"},
        {"set": f"{CURRENT_CARD_YEAR} Topps Stadium Club", "card": "Auto", "parallel": "Base", "grade": "Raw"},
        {"set": f"{CURRENT_CARD_YEAR} Topps Heritage", "card": "Base", "parallel": "Base", "grade": "Raw"},
    ],
}


def normalize_player_name(name: str) -> str:
    return str(name or "").strip().lower()


def detect_player_profile(player_name: str) -> str:
    key = normalize_player_name(player_name)
    registry = PLAYER_CARD_REGISTRIES.get(key)
    if registry:
        return str(registry.get("profile") or "rookie")
    return "rookie"


def get_player_card_registry(player_name: str) -> list[CardRegistryEntry]:
    key = normalize_player_name(player_name)
    registry = PLAYER_CARD_REGISTRIES.get(key)
    if registry:
        return [dict(card) for card in registry["cards"]]
    profile = detect_player_profile(player_name)
    return [dict(card) for card in PROFILE_CARD_TEMPLATES.get(profile, PROFILE_CARD_TEMPLATES["rookie"])]


def get_enriched_player_cards(
    player_entry: dict[str, Any],
    *,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    player_name = player_entry.get("player_name") or player_entry.get("full_name") or ""
    league = normalize_league(player_entry.get("league") or player_entry.get("sport") or "MLB")
    source_player_id = player_entry.get("source_player_id") or player_entry.get("player_id")
    cs_player_id = player_entry.get("cs_player_id")

    if not cs_player_id:
        from cardchase_ai.identity import build_player_identity

        identity = build_player_identity(player_entry)
        cs_player_id = identity["cs_player_id"]
        source_player_id = identity.get("source_player_id") or source_player_id

    cards = get_player_card_registry(player_name)
    if limit is not None:
        cards = cards[: max(0, limit)]

    enriched: list[dict[str, Any]] = []
    for card in cards:
        enriched.append(
            enrich_card_registry_entry(
                card,
                league=league,
                source_player_id=source_player_id,
                cs_player_id=cs_player_id,
                player_name=player_name,
            )
        )
    return enriched
