"""Deterministic PSA card matching helpers — Sprint 8.6."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from cardchase_ai.models.population import PSACardMatch

_MATCH_TOKEN_RE = re.compile(r"[^a-z0-9]+")


def _tokenize(value: str) -> set[str]:
    raw = _MATCH_TOKEN_RE.sub(" ", str(value or "").strip().lower())
    return {part for part in raw.split() if part}


def _normalize_field(value: Any) -> str:
    return str(value or "").strip().lower()


def build_match_identity(card_identity: dict[str, Any]) -> dict[str, str]:
    return {
        "year": _normalize_field(card_identity.get("year")),
        "manufacturer": _normalize_field(card_identity.get("manufacturer")),
        "set_name": _normalize_field(card_identity.get("set_name") or card_identity.get("set")),
        "card_number": _normalize_field(card_identity.get("card_number")),
        "card_name": _normalize_field(card_identity.get("card_name") or card_identity.get("card")),
        "parallel": _normalize_field(card_identity.get("parallel")),
        "variety": _normalize_field(card_identity.get("variety")),
        "player_name": _normalize_field(card_identity.get("player_name")),
    }


def match_score(card_identity: dict[str, Any], candidate: dict[str, Any]) -> tuple[int, list[str]]:
    left = build_match_identity(card_identity)
    right = build_match_identity(candidate)
    score = 0
    reasons: list[str] = []

    weighted_fields = [
        ("year", 20, True),
        ("manufacturer", 10, False),
        ("set_name", 20, False),
        ("card_number", 25, False),
        ("card_name", 15, False),
        ("parallel", 15, False),
        ("variety", 10, False),
        ("player_name", 15, False),
    ]

    for field, weight, exact_only in weighted_fields:
        left_value = left[field]
        right_value = right[field]
        if not left_value or not right_value:
            continue
        if left_value == right_value:
            score += weight
            reasons.append(f"{field}:exact")
            continue
        if exact_only:
            continue
        left_tokens = _tokenize(left_value)
        right_tokens = _tokenize(right_value)
        if left_tokens and right_tokens and (left_tokens <= right_tokens or right_tokens <= left_tokens):
            score += max(1, weight // 2)
            reasons.append(f"{field}:partial")

    return score, reasons


def resolve_match_status(candidates: list[tuple[int, PSACardMatch]]) -> list[PSACardMatch]:
    if not candidates:
        return []

    ranked = sorted(candidates, key=lambda item: (-item[0], item[1].cs_card_id, item[1].psa_card_id or ""))
    top_score, top_match = ranked[0]

    if top_score < 35:
        top_match.match_status = "UNMATCHED"
        top_match.match_confidence = "LOW"
        return [top_match]

    if len(ranked) > 1 and ranked[1][0] == top_score:
        ambiguous = [match for score, match in ranked if score == top_score]
        for match in ambiguous:
            match.match_status = "AMBIGUOUS"
            match.match_confidence = "LOW"
            match.notes = "Multiple equally scored PSA candidates; review required."
        return ambiguous

    if top_score >= 75:
        top_match.match_status = "MATCHED"
        top_match.match_confidence = "HIGH"
    else:
        top_match.match_status = "POSSIBLE"
        top_match.match_confidence = "MEDIUM" if top_score >= 55 else "LOW"

    return [top_match]


def build_psa_card_match(
    card_identity: dict[str, Any],
    *,
    source_method: str,
    psa_card_id: str | None = None,
    psa_set_id: str | None = None,
    psa_subject_id: str | None = None,
    certification_number: str | None = None,
    variety: str = "",
    card_number: str = "",
    notes: str = "",
) -> PSACardMatch:
    now = datetime.now(timezone.utc)
    return PSACardMatch(
        cs_card_id=str(card_identity["cs_card_id"]),
        cs_player_id=str(card_identity["cs_player_id"]),
        league=str(card_identity.get("league") or "MLB"),
        psa_subject_id=psa_subject_id,
        psa_set_id=psa_set_id,
        psa_card_id=psa_card_id,
        certification_number=certification_number,
        year=str(card_identity.get("year") or ""),
        manufacturer=str(card_identity.get("manufacturer") or ""),
        set_name=str(card_identity.get("set_name") or card_identity.get("set") or ""),
        card_number=str(card_number or card_identity.get("card_number") or ""),
        card_name=str(card_identity.get("card_name") or card_identity.get("card") or ""),
        parallel=str(card_identity.get("parallel") or ""),
        variety=str(variety or card_identity.get("variety") or ""),
        player_name=str(card_identity.get("player_name") or ""),
        matched_at=now,
        source_method=source_method,
        notes=notes,
    )
