"""Normalized league intelligence contract shared across MLB and NFL."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

CapabilityStatus = Literal["SUPPORTED", "UNAVAILABLE", "PENDING", "DISABLED"]

LEAGUE_CAPABILITIES = (
    "live_performance",
    "imported_performance",
    "recent_form",
    "season_stats",
    "previous_season_stats",
    "signal_drivers",
    "momentum",
    "market_snapshots",
    "market_movement",
    "card_intelligence",
    "population",
    "alerts",
    "legacy_supabase",
    "weekly_history",
)

EvidenceQuality = Literal["HIGH", "MEDIUM", "LOW", "INSUFFICIENT"]
EvidenceImpact = Literal["positive", "negative", "neutral"]


class NormalizedPerformanceEvidence(BaseModel):
    """Shared performance evidence shape — league-specific metrics stay in metric/label."""

    type: Literal["PERFORMANCE"] = "PERFORMANCE"
    metric: str
    label: str
    value: float | int | str | None = None
    comparison_value: float | int | str | None = None
    period_type: str
    period_start: str | None = None
    period_end: str | None = None
    impact: EvidenceImpact | None = None
    quality: EvidenceQuality = "INSUFFICIENT"
    source_reference: str = ""


class SignalDriverPayload(BaseModel):
    """Normalized signal driver for cross-league serialization."""

    driver_type: str
    label: str
    description: str = ""
    evidence: dict[str, Any] = Field(default_factory=dict)
    source_method: str = "UNAVAILABLE"
    season_phase: str | None = None
    captured_at: str | None = None


class MarketSnapshotPayload(BaseModel):
    query_name: str
    listings_count: int = 0
    avg_price: float | None = None
    min_price: float | None = None
    max_price: float | None = None
    card_label: str | None = None


class MarketMovementPayload(BaseModel):
    status: Literal["calculated", "pending", "unavailable"] = "pending"
    price_change_pct: float | None = None
    listings_change: int | None = None
    label: str = "Movement pending"
    query_name: str | None = None


class CardIntelligenceSummary(BaseModel):
    ranked_cards: list[dict[str, Any]] = Field(default_factory=list)
    card_data_quality: EvidenceQuality = "INSUFFICIENT"
    card_missing_inputs: list[str] = Field(default_factory=list)


class PlayerIntelligencePayload(BaseModel):
    """Normalized player intelligence contract consumed by homepage and Scouting Report."""

    # Identity
    player_id: str
    source_player_id: str
    cs_player_id: str
    sport: str
    league: str
    player_name: str | None = None
    team: str | None = None
    team_id: str | int | None = None
    position: str | None = None
    headshot_url: str | None = None
    team_logo_url: str | None = None

    # Season context
    season: int | None = None
    season_label: str | None = None
    season_phase: str | None = None
    period_type: str | None = None
    period_start: datetime | str | None = None
    period_end: datetime | str | None = None
    recent_window_label: str | None = None

    # Scores
    card_signal_score: float | None = None
    performance_score: float | None = None
    market_score: float | None = None
    collector_score: float | None = None
    momentum_score: float | None = None
    scarcity_score: float | None = None
    news_score: float | None = None

    # Recommendation
    recommendation: str | None = None
    evidence: EvidenceQuality | str | None = None
    freshness: str | None = None
    risk: str | None = None
    time_horizon: str | None = None
    status: str | None = None

    # Performance
    recent_performance: list[NormalizedPerformanceEvidence] = Field(default_factory=list)
    season_performance: list[NormalizedPerformanceEvidence] = Field(default_factory=list)
    previous_season_performance: list[NormalizedPerformanceEvidence] = Field(default_factory=list)
    previous_season_label: str | None = None
    previous_season_helper_text: str | None = None
    previous_season_source_snapshot_id: str | None = None
    previous_season_data_quality: EvidenceQuality = "INSUFFICIENT"
    performance_data_quality: EvidenceQuality = "INSUFFICIENT"
    performance_missing_inputs: list[str] = Field(default_factory=list)

    # Signal drivers
    signal_drivers: list[SignalDriverPayload] = Field(default_factory=list)
    driver_count: int = 0
    driver_data_quality: EvidenceQuality = "INSUFFICIENT"

    # Market
    market_snapshot: list[MarketSnapshotPayload] = Field(default_factory=list)
    market_movement: list[MarketMovementPayload] = Field(default_factory=list)
    market_data_quality: EvidenceQuality = "INSUFFICIENT"
    market_missing_inputs: list[str] = Field(default_factory=list)

    # Cards
    card_intelligence_summary: CardIntelligenceSummary = Field(default_factory=CardIntelligenceSummary)

    # Weekly
    rank: int | None = None
    weekly_change: float | None = None
    prior_score: float | None = None
    snapshot_week: int | None = None
    official_weekly_snapshot: bool = True

    # Confidence
    data_confidence: EvidenceQuality = "INSUFFICIENT"
    evidence_summary: str | None = None
    freshness_summary: str | None = None
    missing_inputs: list[str] = Field(default_factory=list)

    # Versions
    weekly_algorithm_version: str | None = None
    scoring_algorithm_version: str | None = None
    performance_algorithm_version: str | None = None
    card_algorithm_version: str | None = None

    # Capabilities
    capabilities: dict[str, CapabilityStatus] = Field(default_factory=dict)

    # Timestamps
    captured_at: datetime | str | None = None
    updated_at: datetime | str | None = None

    # Legacy compatibility (conviction retained for downstream consumers)
    conviction: str | None = None

    # Internal league evidence blob (not raw provider payloads)
    league_evidence: dict[str, Any] = Field(default_factory=dict)
