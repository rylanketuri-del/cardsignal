"""Data Confidence Layer models — evidence quality independent of recommendations."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

DATA_CONFIDENCE_V1 = "DATA_CONFIDENCE_V1"
MLB_PLAYER_SIGNAL_V1 = "MLB_PLAYER_SIGNAL_V1"

ConfidenceLevel = Literal["VERY_HIGH", "HIGH", "MEDIUM", "LOW", "INSUFFICIENT"]
FreshnessBucket = Literal["LIVE", "RECENT", "CURRENT", "STALE", "UNKNOWN"]
EntityType = Literal["player", "card"]
ExplainabilityStatus = Literal["available", "missing", "pending"]


class ExplainabilityCategory(BaseModel):
    """Structured explainability for a report dimension."""

    category: str
    status: ExplainabilityStatus
    detail: str | None = None


class EvidenceSummary(BaseModel):
    """Counts derived from stored signals only."""

    player_snapshots: int = 0
    market_snapshots: int = 0
    signal_drivers: int = 0
    auction_observations: int = 0
    registry_linked: bool = False
    population_available: bool = False
    source_count: int = 0


class FreshnessInfo(BaseModel):
    bucket: FreshnessBucket = "UNKNOWN"
    freshness_minutes: int | None = None
    latest_snapshot_at: datetime | None = None
    oldest_snapshot_at: datetime | None = None


class DataConfidence(BaseModel):
    """Reusable data-confidence record for players and cards."""

    model_config = {"protected_namespaces": ()}

    confidence_id: str
    entity_type: EntityType
    entity_id: str
    model_version: str = DATA_CONFIDENCE_V1
    confidence_level: ConfidenceLevel = "INSUFFICIENT"
    confidence_score: float = 0.0
    evidence_count: int = 0
    source_count: int = 0
    snapshot_count: int = 0
    latest_snapshot_at: datetime | None = None
    oldest_snapshot_at: datetime | None = None
    freshness_minutes: int | None = None
    freshness_bucket: FreshnessBucket = "UNKNOWN"
    missing_inputs: list[str] = Field(default_factory=list)
    stale_inputs: list[str] = Field(default_factory=list)
    algorithm_version: str = MLB_PLAYER_SIGNAL_V1
    generated_at: datetime | None = None
    evidence_summary: EvidenceSummary = Field(default_factory=EvidenceSummary)
    explainability: list[ExplainabilityCategory] = Field(default_factory=list)


class ConfidenceApiResponse(BaseModel):
    """Public read-only confidence payload — no internal formulas or weights."""

    model_config = {"protected_namespaces": ()}

    entity_type: EntityType
    entity_id: str
    confidence: DataConfidence
    freshness: FreshnessInfo
    evidence_summary: EvidenceSummary
    missing_inputs: list[str] = Field(default_factory=list)
    explainability: list[ExplainabilityCategory] = Field(default_factory=list)
    trust_summary: dict[str, Any] = Field(default_factory=dict)
    model_version: str = DATA_CONFIDENCE_V1
