"""Lightweight CardSignal identity relationship models.

Relationship graph (future snapshots attach to cards; not implemented in Sprint 8.2):

    Player → many Cards
    Player → many Weekly Signals
    Player → many Forecasts
    Card → many Market Snapshots
    Card → many Population Snapshots
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class CardSignalPlayerIdentity(BaseModel):
    cs_player_id: str
    source_player_id: Optional[str] = None
    league: str
    sport: str = "MLB"
    player_name: str


class CardSignalCardIdentity(BaseModel):
    cs_card_id: str
    cs_player_id: str
    league: str
    year: str = ""
    manufacturer: str = ""
    set_name: str = ""
    card_name: str = ""
    parallel: str = ""
    grade: str = "Raw"
    grading_company: Optional[str] = None
    source: str = "placeholder_registry"


class CardSignalWeeklySignalIdentity(BaseModel):
    cs_signal_id: str
    cs_player_id: str
    league: str
    year: int
    week: int
    source_player_id: Optional[str] = None


class CardSignalForecastIdentity(BaseModel):
    cs_forecast_id: str
    cs_player_id: str
    league: str
    year: int
    week: int
    source_player_id: Optional[str] = None


class CardSignalMarketSnapshotRef(BaseModel):
    """Future market snapshot attachment point for a card identity."""

    cs_card_id: str
    snapshot_id: Optional[str] = None


class CardSignalPopulationSnapshotRef(BaseModel):
    """Future PSA/population snapshot attachment point for a card identity."""

    cs_card_id: str
    snapshot_id: Optional[str] = None


class CardSignalPlayerRelationships(BaseModel):
    """Documents one-to-many links without persisting snapshot rows yet."""

    player: CardSignalPlayerIdentity
    cards: List[CardSignalCardIdentity] = Field(default_factory=list)
    weekly_signals: List[CardSignalWeeklySignalIdentity] = Field(default_factory=list)
    forecasts: List[CardSignalForecastIdentity] = Field(default_factory=list)
    market_snapshots: List[CardSignalMarketSnapshotRef] = Field(default_factory=list)
    population_snapshots: List[CardSignalPopulationSnapshotRef] = Field(default_factory=list)
