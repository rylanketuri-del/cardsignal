"""Centralized card identity helpers for CardSignal card intelligence."""

from __future__ import annotations

from typing import Any


def get_card_identity(
    *,
    card_label: str | None = None,
    evidence: dict[str, Any] | None = None,
    registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge registry-linked identity with stored card intelligence metadata."""
    evidence = evidence or {}
    registry = registry or evidence.get("registry") or evidence.get("identity") or {}
    tags = evidence.get("tags") or {}

    identity = {
        "year": registry.get("card_year") or registry.get("year"),
        "brand": registry.get("brand"),
        "set": registry.get("set"),
        "parallel": registry.get("parallel"),
        "card_number": registry.get("card_number"),
        "grade": registry.get("grade"),
        "grading_company": registry.get("grading_company"),
        "card_label": card_label or evidence.get("card_label"),
        "query_name": evidence.get("query_name"),
    }

    if tags.get("rookie_count"):
        identity["is_rookie"] = True
    if tags.get("auto_count"):
        identity["is_autograph"] = True
    if tags.get("psa10_count"):
        identity["is_psa10"] = True

    return identity


def has_registry_identity(identity: dict[str, Any]) -> bool:
    return bool(identity.get("year") or identity.get("brand") or identity.get("set"))


def card_report_path(cs_card_id: str) -> str:
    """Future card report URL path (navigation not wired yet)."""
    return f"/cards/{cs_card_id}"
