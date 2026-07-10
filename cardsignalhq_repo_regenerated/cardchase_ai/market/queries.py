"""Deterministic eBay search query builder for registry cards."""

from __future__ import annotations

import re
from typing import Any


def _normalize_token(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _dedupe_words(parts: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []

    for part in parts:
        token = _normalize_token(part)
        if not token:
            continue
        key = token.lower()
        if key in seen:
            continue
        seen.add(key)
        output.append(token)

    return output


def _build_set_phrase(year: str, manufacturer: str, set_name: str) -> str:
    year_value = _normalize_token(str(year or ""))
    manufacturer_value = _normalize_token(manufacturer)
    set_value = _normalize_token(set_name)

    if set_value:
        if year_value and not set_value.startswith(year_value):
            return f"{year_value} {set_value}"
        return set_value

    return " ".join(_dedupe_words([year_value, manufacturer_value]))


def build_card_search_query(card: dict[str, Any]) -> str:
    """Build a reproducible active-listing search query from card identity fields."""

    player_name = _normalize_token(card.get("player_name") or "")
    year = _normalize_token(str(card.get("year") or ""))
    manufacturer = _normalize_token(card.get("manufacturer") or "")
    set_name = _normalize_token(card.get("set_name") or card.get("set") or "")
    card_name = _normalize_token(card.get("card_name") or card.get("card") or "")
    parallel = _normalize_token(card.get("parallel") or "")
    grade = _normalize_token(card.get("grade") or "")
    grading_company = _normalize_token(card.get("grading_company") or "")

    parts: list[str] = []
    if player_name:
        parts.append(player_name)

    set_phrase = _build_set_phrase(year, manufacturer, set_name)
    if set_phrase:
        parts.append(set_phrase)

    card_tokens = _dedupe_words([card_name, parallel])
    existing = {part.lower() for part in parts}
    for token in card_tokens:
        if token.lower() not in existing:
            parts.append(token)
            existing.add(token.lower())

    if grade and grade.lower() != "raw":
        if grading_company:
            grade_label = f"{grading_company} {grade}".strip()
        else:
            grade_label = grade
        parts.append(grade_label)

    return " ".join(_dedupe_words(parts))
