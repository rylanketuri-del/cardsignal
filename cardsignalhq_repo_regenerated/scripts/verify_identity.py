"""Verification checks for CardSignal identity foundation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cardchase_ai.identity import (  # noqa: E402
    IdentityValidationError,
    build_player_identity,
    create_card_cs_id,
    create_forecast_cs_id,
    create_player_cs_id,
    create_signal_cs_id,
    enrich_card_registry_entry,
    enrich_player_entry,
)


def main() -> int:
    errors: list[str] = []

    player_id = create_player_cs_id("MLB", 660271)
    if player_id != "CS-MLB-P-660271":
        errors.append(f"unexpected player id: {player_id}")

    repeat = create_player_cs_id("MLB", 660271)
    if repeat != player_id:
        errors.append("player id not deterministic")

    signal_id = create_signal_cs_id("MLB", 2026, 28, 660271)
    if signal_id != "CS-MLB-S-2026W28-660271":
        errors.append(f"unexpected signal id: {signal_id}")

    forecast_id = create_forecast_cs_id("MLB", 2026, 28, 660271)
    if forecast_id != "CS-MLB-F-2026W28-660271":
        errors.append(f"unexpected forecast id: {forecast_id}")

    try:
        create_player_cs_id("INVALID", 1)
        errors.append("expected league validation failure")
    except IdentityValidationError:
        pass

    try:
        create_signal_cs_id("MLB", 2026, 0, 660271)
        errors.append("expected week validation failure")
    except IdentityValidationError:
        pass

    entry = enrich_player_entry(
        {
            "player_id": 660271,
            "player_name": "Elly De La Cruz",
            "sport": "MLB",
        }
    )

    for field in ("cs_player_id", "source_player_id", "league", "sport", "player_name", "cs_signal_id", "cs_forecast_id"):
        if field not in entry:
            errors.append(f"missing player field: {field}")

    if entry["player_id"] != 660271:
        errors.append("legacy player_id changed")

    card = enrich_card_registry_entry(
        {
            "set": "2025 Topps Chrome",
            "card": "Base Rookie",
            "parallel": "Base",
            "grade": "Raw",
        },
        league="MLB",
        source_player_id=660271,
        cs_player_id=entry["cs_player_id"],
        player_name="Elly De La Cruz",
    )

    for field in (
        "cs_card_id",
        "cs_player_id",
        "league",
        "year",
        "manufacturer",
        "set_name",
        "card_name",
        "parallel",
        "grade",
        "source",
    ):
        if field not in card:
            errors.append(f"missing card field: {field}")

    if card["source"] != "placeholder_registry":
        errors.append("unexpected card source")

    card_repeat = enrich_card_registry_entry(
        {
            "set": "2025 Topps Chrome",
            "card": "Base Rookie",
            "parallel": "Base",
            "grade": "Raw",
        },
        league="MLB",
        source_player_id=660271,
        cs_player_id=entry["cs_player_id"],
        player_name="Elly De La Cruz",
    )

    if card["cs_card_id"] != card_repeat["cs_card_id"]:
        errors.append("card id not deterministic")

  # Price must not affect card id
    priced = dict(card)
    priced["price"] = 999.99
    priced["movement"] = "+25%"
    priced_id = create_card_cs_id(
        "MLB",
        {
            "source_player_id": 660271,
            "year": priced["year"],
            "manufacturer": priced["manufacturer"],
            "set_name": priced["set_name"],
            "card_name": priced["card_name"],
            "parallel": priced["parallel"],
            "grade": priced["grade"],
            "grading_company": priced.get("grading_company"),
        },
    )
    if priced_id != card["cs_card_id"]:
        errors.append("price/movement affected card id")

    tracked = [
        "Elly De La Cruz",
        "Bobby Witt Jr.",
        "Gunnar Henderson",
        "Jackson Chourio",
    ]
    for name in tracked:
        identity = build_player_identity({"player_name": name, "sport": "MLB"})
        if not identity["cs_player_id"].startswith("CS-MLB-P-"):
            errors.append(f"invalid cs_player_id for {name}")

    if errors:
        print("FAIL")
        for error in errors:
            print(error)
        return 1

    print("PASS")
    print(json.dumps({"player_id": player_id, "card_id": card["cs_card_id"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
