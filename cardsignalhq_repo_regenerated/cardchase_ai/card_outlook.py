"""Centralized Card Outlook builder — stored evidence only, no heuristic fact generation."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from cardchase_ai.models.weekly import WEEKLY_INTELLIGENCE_V1

SUPPORTED_EVIDENCE_TYPES = {
    "market",
    "scarcity",
    "demand",
    "supply",
    "population",
    "listing",
    "outlook",
    "general",
    "momentum",
    "activity",
}

NO_EVIDENCE_SUMMARY = (
    "More verified card-level evidence is required before CardSignal can issue a full outlook."
)
NO_SUPPORT_SUMMARY = "Supporting evidence is not available in the current snapshot."
STORED_EVIDENCE_SUMMARY = "Outlook based on stored card-level evidence in the current snapshot."

HEURISTIC_EVIDENCE_PHRASES = {
    "improving demand",
    "tight listing supply",
    "positive price momentum",
    "premium listing activity",
}


def format_evidence_tier(conviction: str | None) -> str:
    if not conviction:
        return "INSUFFICIENT"
    normalized = str(conviction).strip()
    mapping = {"High": "HIGH", "Medium": "MEDIUM", "Low": "LOW"}
    return mapping.get(normalized, normalized.upper())


class CardOutlook(BaseModel):
    recommendation: str
    evidence: str
    risk: str | None = None
    time_horizon: str | None = None
    summary: str
    supporting_evidence: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    algorithm_version: str = WEEKLY_INTELLIGENCE_V1


def _is_valid_structured_evidence(item: dict[str, Any]) -> bool:
    if not item:
        return False

    item_type = item.get("type")
    if item_type and str(item_type).lower() not in SUPPORTED_EVIDENCE_TYPES:
        return False

    label_or_value = item.get("label") or item.get("value")
    if not label_or_value:
        return False

    if item_type and not (item.get("source_reference") or item.get("captured_at")):
        return False

    return True


def _extract_stored_evidence_items(evidence_data: dict[str, Any]) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()

    def add(text: str) -> None:
        normalized = text.strip()
        if not normalized:
            return
        key = normalized.lower()
        if key in seen:
            return
        seen.add(key)
        items.append(normalized)

    for raw in evidence_data.get("evidence_items") or evidence_data.get("outlook_evidence") or []:
        if isinstance(raw, str):
            add(raw)
            continue
        if isinstance(raw, dict):
            if not _is_valid_structured_evidence(raw):
                continue
            text = raw.get("label") or raw.get("value")
            if text:
                add(str(text))

    for reason in evidence_data.get("outlook_reasons") or []:
        if reason:
            add(str(reason))

    return items


def build_card_outlook(
    *,
    stored_recommendation: str | None,
    stored_evidence_tier: str | None,
    evidence_data: dict[str, Any] | None,
    stored_risk: str | None,
    stored_time_horizon: str | None,
    missing_inputs: list[str] | None,
    algorithm_version: str,
) -> CardOutlook:
    """Build card outlook from stored intelligence only — never from score heuristics."""
    evidence_data = evidence_data or {}
    missing = list(missing_inputs or [])
    supporting = _extract_stored_evidence_items(evidence_data)
    has_support = len(supporting) > 0

    stored_rec = str(stored_recommendation).upper() if stored_recommendation else None
    stored_summary = evidence_data.get("outlook_summary")

    if not has_support:
        if stored_rec and stored_rec != "WATCH":
            recommendation = stored_rec
            evidence_tier = "INSUFFICIENT"
            summary = NO_SUPPORT_SUMMARY
        else:
            recommendation = "WATCH"
            evidence_tier = "INSUFFICIENT"
            summary = NO_EVIDENCE_SUMMARY
    else:
        recommendation = stored_rec or "WATCH"
        evidence_tier = format_evidence_tier(stored_evidence_tier)
        summary = stored_summary or STORED_EVIDENCE_SUMMARY

    return CardOutlook(
        recommendation=recommendation,
        evidence=evidence_tier,
        risk=stored_risk,
        time_horizon=stored_time_horizon,
        summary=summary,
        supporting_evidence=supporting,
        missing_inputs=missing,
        algorithm_version=algorithm_version,
    )
