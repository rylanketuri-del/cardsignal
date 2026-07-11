"""Card Report data models — individual collectible research destination."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from cardchase_ai.models.weekly import WEEKLY_INTELLIGENCE_V1

EvidenceTier = Literal["HIGH", "MEDIUM", "LOW", "INSUFFICIENT"]


class CardIdentity(BaseModel):
    year: str | int | None = None
    brand: str | None = None
    set: str | None = None
    parallel: str | None = None
    card_number: str | None = None
    grade: str | None = None
    grading_company: str | None = None
    serial_number: str | None = None


class CardReportDriver(BaseModel):
    label: str
    detail: str
    direction: str | None = None


class CardReportMarket(BaseModel):
    median_price: float | None = None
    average_price: float | None = None
    active_listings: int | None = None
    auction_count: int | None = None
    listings_with_bids: int | None = None
    market_depth: str | None = None
    data_quality: str | None = None
    sales_activity: str | None = None


class CardReportPopulation(BaseModel):
    psa_population: int | None = None
    population_grade: str | None = None
    serial_number: str | None = None
    parallel: str | None = None
    print_run: str | None = None
    scarcity_score: float | None = None


class PriceHistoryPoint(BaseModel):
    period_label: str
    captured_at: datetime | None = None
    median_price: float | None = None
    average_price: float | None = None
    card_signal_score: float | None = None


class PriceHistorySeries(BaseModel):
    """Time series foundation for future chart adapter."""

    series: list[PriceHistoryPoint] = Field(default_factory=list)
    period_labels: list[str] = Field(default_factory=list)
    chart_adapter: str = "pending"
    status: str = "coming_soon"


class CardReportExtensions(BaseModel):
    """Architecture hooks for future premium features — not implemented in Sprint 9.5."""

    comments: dict[str, Any] = Field(default_factory=lambda: {"enabled": False})
    watchlists: dict[str, Any] = Field(default_factory=lambda: {"enabled": False})
    sharing: dict[str, Any] = Field(default_factory=lambda: {"enabled": False})
    price_charts: dict[str, Any] = Field(default_factory=lambda: {"enabled": False, "adapter": "pending"})
    alerts: dict[str, Any] = Field(default_factory=lambda: {"enabled": False})
    signal_vault: dict[str, Any] = Field(default_factory=lambda: {"enabled": False})


class CardReport(BaseModel):
    cs_card_id: str
    player_id: str
    sport: str
    league: str
    player_name: str | None = None
    card_label: str | None = None
    card_identity: CardIdentity | None = None
    card_score: float | None = None
    recommendation: str | None = None
    evidence: EvidenceTier | None = None
    status: str | None = None
    market: CardReportMarket = Field(default_factory=CardReportMarket)
    population: CardReportPopulation = Field(default_factory=CardReportPopulation)
    price_history: PriceHistorySeries = Field(default_factory=PriceHistorySeries)
    signal_drivers: list[CardReportDriver] = Field(default_factory=list)
    market_drivers: list[CardReportDriver] = Field(default_factory=list)
    scarcity_drivers: list[CardReportDriver] = Field(default_factory=list)
    outlook_summary: str | None = None
    outlook_evidence: list[str] = Field(default_factory=list)
    risk: str | None = None
    time_horizon: str | None = None
    market_activity_score: float | None = None
    demand_score: float | None = None
    momentum_score: float | None = None
    scarcity_score: float | None = None
    missing_inputs: list[str] = Field(default_factory=list)
    updated_at: datetime | None = None
    algorithm_version: str = WEEKLY_INTELLIGENCE_V1
    extensions: CardReportExtensions = Field(default_factory=CardReportExtensions)
