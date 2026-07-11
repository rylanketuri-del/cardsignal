"""Provider-neutral development ingestion interface."""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from cardchase_ai.models.signal_driver import (
    SIGNAL_DRIVERS_V1,
    DriverCategory,
    DriverType,
    EvidenceQuality,
    Impact,
    SignalDriver,
    SourceType,
)

SUPPORTED_DEVELOPMENT_TYPES: set[DriverType] = {
    "CALL_UP",
    "DEMOTION",
    "DEBUT",
    "RETIREMENT",
    "HALL_OF_FAME",
    "MILESTONE",
    "AWARD",
    "ALL_STAR_SELECTION",
    "TRADE",
    "FREE_AGENT_SIGNING",
    "CONTRACT_EXTENSION",
    "DEPTH_CHART_CHANGE",
    "ROLE_CHANGE",
    "INJURY",
    "INJURY_RETURN",
    "SUSPENSION",
    "INACTIVE_STATUS",
    "VERIFIED_DEVELOPMENT",
}

UNSUPPORTED_RUMOR_MARKERS = (
    "rumor",
    "rumour",
    "speculation",
    "reportedly",
    "sources say",
    "unconfirmed",
    "hearing",
    "linked to",
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _driver_id_from_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]


def _category_for_type(driver_type: DriverType) -> DriverCategory:
    if driver_type in {"RECENT_FORM", "SEASON_PERFORMANCE", "PLAYOFF_PERFORMANCE", "PRESEASON_PERFORMANCE"}:
        return "PERFORMANCE"
    if driver_type in {"CALL_UP", "DEMOTION", "DEBUT", "RETIREMENT", "HALL_OF_FAME", "MILESTONE", "AWARD", "ALL_STAR_SELECTION"}:
        return "CAREER"
    if driver_type in {"TRADE", "FREE_AGENT_SIGNING", "CONTRACT_EXTENSION", "DEPTH_CHART_CHANGE", "ROLE_CHANGE"}:
        return "TEAM"
    if driver_type in {"INJURY", "INJURY_RETURN", "SUSPENSION", "INACTIVE_STATUS"}:
        return "AVAILABILITY"
    if driver_type in {"PRICE_MOVEMENT", "LISTING_SUPPLY", "BID_ACTIVITY", "SALES_ACTIVITY", "POPULATION_MOVEMENT", "SCARCITY_CHANGE"}:
        return "MARKET"
    return "OTHER"


class PlayerDevelopmentProvider(ABC):
    """Provider-neutral interface for verified player developments."""

    @abstractmethod
    def fetch_player_developments(
        self,
        cs_player_id: str,
        source_player_id: str,
        league: str,
        *,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Return raw development records from stored sources only."""

    def normalize_development(
        self,
        raw: dict[str, Any],
        *,
        cs_player_id: str,
        source_player_id: str,
        league: str,
        sport: str | None = None,
    ) -> SignalDriver | None:
        """Normalize a raw development into a SignalDriver."""
        driver_type = str(raw.get("driver_type", "")).upper()
        if driver_type not in SUPPORTED_DEVELOPMENT_TYPES:
            return None

        title = str(raw.get("title", "")).strip()
        summary = str(raw.get("summary", "")).strip()
        if not title or not summary:
            return None

        source_type = str(raw.get("source_type", "MANUAL_VERIFIED")).upper()
        if source_type not in {"OFFICIAL_API", "APPROVED_IMPORT", "MANUAL_VERIFIED"}:
            source_type = "MANUAL_VERIFIED"

        occurred_raw = raw.get("occurred_at")
        if not occurred_raw:
            return None

        occurred_at = datetime.fromisoformat(str(occurred_raw).replace("Z", "+00:00"))
        captured_at = _utcnow()

        impact = str(raw.get("impact", "UNKNOWN")).upper()
        if impact not in {"POSITIVE", "NEUTRAL", "NEGATIVE", "UNKNOWN"}:
            impact = "UNKNOWN"

        evidence = str(raw.get("evidence_quality", "INSUFFICIENT")).upper()
        if evidence not in {"HIGH", "MEDIUM", "LOW", "INSUFFICIENT"}:
            evidence = "INSUFFICIENT"

        source_reference = str(raw.get("source_reference", "")).strip()
        if not source_reference:
            evidence = "INSUFFICIENT"

        driver = SignalDriver(
            driver_id="",
            cs_player_id=cs_player_id,
            source_player_id=str(source_player_id),
            league=league.upper(),
            sport=(sport or league).upper(),
            driver_type=driver_type,  # type: ignore[arg-type]
            category=_category_for_type(driver_type),  # type: ignore[arg-type]
            title=title,
            summary=summary,
            metric_name=raw.get("metric_name"),
            metric_value=raw.get("metric_value"),
            comparison_value=raw.get("comparison_value"),
            impact=impact,  # type: ignore[arg-type]
            evidence_quality=evidence,  # type: ignore[arg-type]
            source_type=source_type,  # type: ignore[arg-type]
            source_reference=source_reference,
            occurred_at=occurred_at,
            captured_at=captured_at,
            expires_at=None,
            algorithm_version=SIGNAL_DRIVERS_V1,
            metadata=dict(raw.get("metadata") or {}),
        )
        driver.driver_id = _driver_id_from_key(driver.identity_key())
        return driver

    def validate_development(self, raw: dict[str, Any]) -> tuple[bool, str]:
        """Reject unsupported rumors and incomplete records."""
        text = f"{raw.get('title', '')} {raw.get('summary', '')}".lower()
        for marker in UNSUPPORTED_RUMOR_MARKERS:
            if marker in text:
                return False, f"unsupported_rumor:{marker}"

        if raw.get("is_rumor") is True or raw.get("verified") is False:
            return False, "unsupported_rumor_flag"

        driver_type = str(raw.get("driver_type", "")).upper()
        if driver_type not in SUPPORTED_DEVELOPMENT_TYPES:
            return False, "unsupported_driver_type"

        if not raw.get("title") or not raw.get("summary"):
            return False, "missing_title_or_summary"

        if not raw.get("occurred_at"):
            return False, "missing_occurred_at"

        source_type = str(raw.get("source_type", "")).upper()
        if source_type not in {"OFFICIAL_API", "APPROVED_IMPORT", "MANUAL_VERIFIED"}:
            return False, "invalid_source_type"

        if not str(raw.get("source_reference", "")).strip():
            return False, "missing_source_reference"

        return True, "ok"


class StoredDevelopmentProvider(PlayerDevelopmentProvider):
    """Reads verified developments from append-only local/Supabase storage."""

    def __init__(self, developments: list[dict[str, Any]] | None = None):
        self._developments = developments or []

    def fetch_player_developments(
        self,
        cs_player_id: str,
        source_player_id: str,
        league: str,
        *,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        matches = [
            d
            for d in self._developments
            if d.get("cs_player_id") == cs_player_id or str(d.get("source_player_id")) == str(source_player_id)
        ]
        return matches[:limit]


class ManualVerifiedDevelopmentProvider(StoredDevelopmentProvider):
    """Admin/manual verified seed provider."""

    pass
