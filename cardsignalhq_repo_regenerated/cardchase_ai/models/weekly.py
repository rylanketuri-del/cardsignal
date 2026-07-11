"""Weekly intelligence data models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

WEEKLY_INTELLIGENCE_V1 = "WEEKLY_INTELLIGENCE_V1"

WeeklyRunStatus = Literal["PENDING", "RUNNING", "COMPLETED", "PARTIAL", "FAILED", "SKIPPED"]
WeeklyTriggeredBy = Literal["scheduler", "manual", "admin", "test"]


class WeeklyIntelligenceRun(BaseModel):
    run_id: str
    league: str
    sport: str
    season: int
    year: int
    week_number: int
    period_start: datetime
    period_end: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    status: WeeklyRunStatus = "PENDING"
    triggered_by: WeeklyTriggeredBy = "manual"
    force: bool = False
    algorithm_version: str = WEEKLY_INTELLIGENCE_V1
    player_limit: int = 100
    players_processed: int = 0
    cards_processed: int = 0
    market_snapshots_created: int = 0
    population_snapshots_created: int = 0
    intelligence_records_created: int = 0
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    stage_outcomes: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime | None = None


class PlayerWeeklySignalSnapshot(BaseModel):
    snapshot_id: str
    run_id: str
    cs_player_id: str
    source_player_id: str
    league: str
    sport: str
    season: int
    year: int
    week_number: int
    period_start: datetime
    period_end: datetime
    card_signal_score: float | None = None
    performance_score: float | None = None
    market_score: float | None = None
    collector_score: float | None = None
    momentum_score: float | None = None
    scarcity_score: float | None = None
    news_score: float | None = None
    recommendation: str | None = None
    conviction: str | None = None
    status: str | None = None
    weekly_change: float | None = None
    rank: int | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    missing_inputs: list[str] = Field(default_factory=list)
    supporting_driver_ids: list[str] = Field(default_factory=list)
    driver_evidence_used: list[str] = Field(default_factory=list)
    driver_missing_evidence: list[str] = Field(default_factory=list)
    algorithm_version: str = WEEKLY_INTELLIGENCE_V1
    captured_at: datetime | None = None
    player_name: str | None = None
    team: str | None = None
    position: str | None = None
    headshot_url: str | None = None
    team_logo_url: str | None = None


class CardWeeklyIntelligenceSnapshot(BaseModel):
    snapshot_id: str
    run_id: str
    cs_card_id: str
    cs_player_id: str
    league: str
    year: int
    week_number: int
    period_start: datetime
    period_end: datetime
    card_signal_score: float | None = None
    recommendation: str | None = None
    conviction: str | None = None
    risk: str | None = None
    time_horizon: str | None = None
    market_activity_score: float | None = None
    demand_score: float | None = None
    momentum_score: float | None = None
    scarcity_score: float | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    missing_inputs: list[str] = Field(default_factory=list)
    algorithm_version: str = WEEKLY_INTELLIGENCE_V1
    captured_at: datetime | None = None
    card_label: str | None = None
    player_name: str | None = None


class SignalOfTheWeek(BaseModel):
    run_id: str
    cs_player_id: str
    player_name: str
    rank: int | None = None
    score: float | None = None
    weekly_change: float | None = None
    recommendation: str | None = None
    conviction: str | None = None
    status: str | None = None
    reason: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    algorithm_version: str = WEEKLY_INTELLIGENCE_V1
    selected_at: datetime | None = None
    headshot_url: str | None = None
    team: str | None = None
    position: str | None = None
    team_logo_url: str | None = None
    source_player_id: str | None = None


class TodaysLeaderEntry(BaseModel):
    rank: int
    cs_player_id: str
    source_player_id: str
    player_name: str
    score: float | None = None
    performance: float | None = None
    market: float | None = None
    collector: float | None = None
    momentum: float | None = None
    recommendation: str | None = None
    weekly_change: float | None = None
    status: str | None = None
    team: str | None = None
    position: str | None = None
    headshot_url: str | None = None
    team_logo_url: str | None = None


class WeeklyHomepageIntelligence(BaseModel):
    run: WeeklyIntelligenceRun
    signal_of_the_week: SignalOfTheWeek | None = None
    todays_leaders: list[TodaysLeaderEntry] = Field(default_factory=list)
    trending_cards: list[dict[str, Any]] = Field(default_factory=list)
    biggest_movers: list[dict[str, Any]] = Field(default_factory=list)
    buy_low_watch: list[dict[str, Any]] = Field(default_factory=list)
    most_chased: list[dict[str, Any]] = Field(default_factory=list)
    next_refresh: datetime | None = None
    data_quality_summary: dict[str, Any] = Field(default_factory=dict)


class WeeklyRunSummary(BaseModel):
    run: WeeklyIntelligenceRun
    stages: list[dict[str, Any]] = Field(default_factory=list)
    homepage: WeeklyHomepageIntelligence | None = None
    skipped_reason: str | None = None
