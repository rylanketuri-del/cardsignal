"""Signal Driver data models for Sprint 9.3."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

SIGNAL_DRIVERS_V1 = "SIGNAL_DRIVERS_V1"

SeasonState = Literal[
    "REGULAR_SEASON",
    "POSTSEASON",
    "PRESEASON",
    "OFFSEASON",
    "INACTIVE",
    "UNKNOWN",
]

DriverCategory = Literal[
    "PERFORMANCE",
    "CAREER",
    "TEAM",
    "AVAILABILITY",
    "MARKET",
    "OTHER",
]

DriverType = Literal[
    # PERFORMANCE
    "RECENT_FORM",
    "SEASON_PERFORMANCE",
    "PLAYOFF_PERFORMANCE",
    "PRESEASON_PERFORMANCE",
    # CAREER
    "CALL_UP",
    "DEMOTION",
    "DEBUT",
    "RETIREMENT",
    "HALL_OF_FAME",
    "MILESTONE",
    "AWARD",
    "ALL_STAR_SELECTION",
    # TEAM
    "TRADE",
    "FREE_AGENT_SIGNING",
    "CONTRACT_EXTENSION",
    "DEPTH_CHART_CHANGE",
    "ROLE_CHANGE",
    # AVAILABILITY
    "INJURY",
    "INJURY_RETURN",
    "SUSPENSION",
    "INACTIVE_STATUS",
    # MARKET
    "PRICE_MOVEMENT",
    "LISTING_SUPPLY",
    "BID_ACTIVITY",
    "SALES_ACTIVITY",
    "POPULATION_MOVEMENT",
    "SCARCITY_CHANGE",
    # OTHER
    "VERIFIED_DEVELOPMENT",
]

Impact = Literal["POSITIVE", "NEUTRAL", "NEGATIVE", "UNKNOWN"]
EvidenceQuality = Literal["HIGH", "MEDIUM", "LOW", "INSUFFICIENT"]
SourceType = Literal[
    "OFFICIAL_API",
    "APPROVED_IMPORT",
    "MANUAL_VERIFIED",
    "MARKET_SNAPSHOT",
    "PERFORMANCE_SNAPSHOT",
]


class SignalDriver(BaseModel):
    driver_id: str
    cs_player_id: str
    source_player_id: str
    league: str
    sport: str
    driver_type: DriverType
    category: DriverCategory
    title: str
    summary: str
    metric_name: str | None = None
    metric_value: float | str | None = None
    comparison_value: float | str | None = None
    impact: Impact = "UNKNOWN"
    evidence_quality: EvidenceQuality = "INSUFFICIENT"
    source_type: SourceType
    source_reference: str
    occurred_at: datetime
    captured_at: datetime
    expires_at: datetime | None = None
    algorithm_version: str = SIGNAL_DRIVERS_V1
    metadata: dict[str, Any] = Field(default_factory=dict)

    def identity_key(self) -> str:
        """Deterministic identity for duplicate prevention."""
        occurred = self.occurred_at.date().isoformat()
        metric = self.metric_name or ""
        return f"{self.cs_player_id}:{self.driver_type}:{metric}:{occurred}:{self.source_reference}"


class LeagueSeasonMetadata(BaseModel):
    """Stored league schedule/season metadata — never guessed at read time."""

    league: str
    sport: str
    season: int
    regular_season_start: datetime | None = None
    regular_season_end: datetime | None = None
    postseason_start: datetime | None = None
    postseason_end: datetime | None = None
    preseason_start: datetime | None = None
    preseason_end: datetime | None = None
    offseason_start: datetime | None = None
    offseason_end: datetime | None = None
    source_type: SourceType = "OFFICIAL_API"
    source_reference: str = ""
    captured_at: datetime | None = None
    algorithm_version: str = SIGNAL_DRIVERS_V1


class SportSeasonState(BaseModel):
    league: str
    sport: str
    season: int
    state: SeasonState
    determined_at: datetime
    source_type: SourceType
    source_reference: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class SignalDriverDataQuality(BaseModel):
    total_drivers: int = 0
    current_drivers: int = 0
    high_evidence: int = 0
    medium_evidence: int = 0
    low_evidence: int = 0
    insufficient_evidence: int = 0


class SignalDriversResponse(BaseModel):
    cs_player_id: str
    source_player_id: str
    player_name: str | None = None
    league: str
    sport: str
    season_state: SportSeasonState
    current_drivers: list[SignalDriver] = Field(default_factory=list)
    previous_season_context: dict[str, Any] = Field(default_factory=dict)
    data_quality: SignalDriverDataQuality = Field(default_factory=SignalDriverDataQuality)
    algorithm_version: str = SIGNAL_DRIVERS_V1


class ScoreDriverRelationship(BaseModel):
    """Future-compatible link between scores and supporting drivers."""

    supporting_driver_ids: list[str] = Field(default_factory=list)
    evidence_used: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
