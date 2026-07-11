"""Centralized Card Registry — normalize stored intelligence into collector identity."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from cardchase_ai.models.card_identity import CardIdentity

# Fields implied directly by eBay search query templates in pipeline.SEARCH_TEMPLATES.
QUERY_REGISTRY_HINTS: dict[str, dict[str, Any]] = {
    "bowman_chrome": {
        "brand": "Bowman",
        "set": "Chrome",
        "rookie_flag": True,
    },
    "auto": {
        "autograph_flag": True,
    },
    "psa10": {
        "grading_company": "PSA",
        "grade": "10",
    },
}


def _query_name_from_cs_card_id(cs_card_id: str) -> str | None:
    if ":card:" not in cs_card_id:
        return None
    return cs_card_id.rsplit(":card:", 1)[-1] or None


def _player_id_from_cs_card_id(cs_card_id: str) -> str | None:
    parts = cs_card_id.split(":")
    if len(parts) >= 3 and parts[2] == "card":
        return parts[1]
    return None


def _coalesce(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _normalize_year(value: Any) -> int | None:
    if value is None:
        return None
    try:
        year = int(value)
    except (TypeError, ValueError):
        return None
    if 1900 <= year <= 2100:
        return year
    return None


def _normalize_card_number(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text.lstrip("#")


def _normalize_grade(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_grading_company(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().upper()
    if not text:
        return None
    return text


def _normalize_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None


def _normalize_price(value: Any) -> float | None:
    if value is None:
        return None
    try:
        price = float(value)
    except (TypeError, ValueError):
        return None
    if price < 0:
        return None
    return round(price, 2)


def _normalize_count(value: Any) -> int | None:
    if value is None:
        return None
    try:
        count = int(value)
    except (TypeError, ValueError):
        return None
    if count < 0:
        return None
    return count


def _parse_last_updated(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _merge_identity_sources(*sources: dict[str, Any] | None) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for source in sources:
        if not source:
            continue
        for key, value in source.items():
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            merged[key] = value
    return merged


def resolve_card_identity(
    *,
    cs_card_id: str,
    sport: str | None = None,
    player_id: str | None = None,
    player_name: str | None = None,
    evidence: dict[str, Any] | None = None,
    captured_at: datetime | str | None = None,
    identity: dict[str, Any] | None = None,
    registry: dict[str, Any] | None = None,
    **extra: Any,
) -> CardIdentity:
    """Map a stored card record to a normalized CardIdentity."""
    evidence = evidence or {}
    query_name = _coalesce(
        evidence.get("query_name"),
        extra.get("query_name"),
        _query_name_from_cs_card_id(cs_card_id),
    )
    hints = QUERY_REGISTRY_HINTS.get(str(query_name or ""), {})
    merged = _merge_identity_sources(hints, registry, identity, extra)

    resolved_player_id = _coalesce(
        merged.get("player_id"),
        player_id,
        _player_id_from_cs_card_id(cs_card_id),
    )

    return CardIdentity(
        cs_card_id=cs_card_id,
        sport=_coalesce(merged.get("sport"), sport),
        player_id=str(resolved_player_id) if resolved_player_id is not None else None,
        player_name=_coalesce(merged.get("player_name"), player_name),
        year=_normalize_year(_coalesce(merged.get("card_year"), merged.get("year"))),
        brand=_coalesce(merged.get("brand")),
        set=_coalesce(merged.get("set")),
        subset=_coalesce(merged.get("subset")),
        parallel=_coalesce(merged.get("parallel")),
        variation=_coalesce(merged.get("variation")),
        card_number=_normalize_card_number(merged.get("card_number")),
        rookie_flag=_normalize_bool(merged.get("rookie_flag")),
        autograph_flag=_normalize_bool(merged.get("autograph_flag")),
        relic_flag=_normalize_bool(merged.get("relic_flag")),
        serial_number=_coalesce(merged.get("serial_number")),
        grading_company=_normalize_grading_company(merged.get("grading_company")),
        grade=_normalize_grade(merged.get("grade")),
        population=_normalize_count(merged.get("population")),
        image_url=_coalesce(merged.get("image_url")),
        active_listings=_normalize_count(
            _coalesce(merged.get("active_listings"), evidence.get("listings_count"))
        ),
        median_price=_normalize_price(
            _coalesce(merged.get("median_price"), evidence.get("median_price"))
        ),
        average_price=_normalize_price(
            _coalesce(merged.get("average_price"), evidence.get("avg_price"))
        ),
        last_updated=_parse_last_updated(_coalesce(merged.get("last_updated"), captured_at)),
    )


def enrich_card_row(row: dict[str, Any]) -> dict[str, Any]:
    """Attach registry identity to a stored card row when missing."""
    if not row.get("cs_card_id"):
        return row
    enriched = dict(row)
    enriched["identity"] = card_identity_from_snapshot(enriched)
    return enriched


def card_identity_from_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Build API-ready identity payload from a stored card snapshot row."""
    identity = resolve_card_identity(
        cs_card_id=snapshot.get("cs_card_id", ""),
        sport=snapshot.get("league") or snapshot.get("sport"),
        player_id=snapshot.get("cs_player_id"),
        player_name=snapshot.get("player_name"),
        evidence=snapshot.get("evidence") or {},
        captured_at=snapshot.get("captured_at"),
        identity=snapshot.get("identity"),
        registry=snapshot.get("registry"),
    )
    return identity.to_api_dict()
