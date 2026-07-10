"""Card Intelligence synthesis models — Sprint 8.7."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

RECOMMENDATIONS = frozenset({"BUY", "HOLD", "SELL", "WATCH"})
CONVICTIONS = frozenset({"HIGH", "MEDIUM", "LOW", "INSUFFICIENT"})
RISKS = frozenset({"LOW", "MEDIUM", "HIGH", "UNKNOWN"})
EVIDENCE_IMPACTS = frozenset({"POSITIVE", "NEUTRAL", "NEGATIVE", "UNKNOWN"})
EVIDENCE_TYPES = frozenset({"MARKET", "MOMENTUM", "SCARCITY", "DEMAND", "POPULATION"})


class IntelligenceEvidenceItem(BaseModel):
    type: str
    label: str
    value: str
    impact: str = "UNKNOWN"
    quality: str = "INSUFFICIENT"


class CardIntelligence(BaseModel):
    """Synthesized card-level intelligence from stored market and population inputs."""

    # Identity
    cs_card_id: str
    cs_player_id: str
    league: str
    player_name: str = ""
    year: Optional[str] = None
    manufacturer: Optional[str] = None
    set_name: Optional[str] = None
    card_name: Optional[str] = None
    card_number: Optional[str] = None
    parallel: Optional[str] = None
    variety: Optional[str] = None
    grade: Optional[str] = None
    grading_company: Optional[str] = None

    # Market
    latest_market_snapshot: Optional[Dict[str, Any]] = None
    market_movement_7d: Optional[Dict[str, Any]] = None
    market_movement_30d: Optional[Dict[str, Any]] = None
    active_listing_count: Optional[int] = None
    auction_count: Optional[int] = None
    buy_it_now_count: Optional[int] = None
    listings_with_bids: Optional[int] = None
    total_bid_count: Optional[int] = None
    median_active_price: Optional[float] = None
    average_active_price: Optional[float] = None
    market_depth: Optional[str] = None
    market_data_quality: Optional[str] = None

    # Population
    psa_match_status: Optional[str] = None
    total_psa_population: Optional[int] = None
    psa_10_population: Optional[int] = None
    psa_9_population: Optional[int] = None
    gem_rate: Optional[float] = None
    population_change: Optional[int] = None
    population_data_quality: Optional[str] = None
    population_source_method: Optional[str] = None

    # Scarcity (from population synthesis)
    scarcity_metrics: Optional[Dict[str, Any]] = None

    # Derived intelligence
    market_activity_score: Optional[float] = None
    demand_score: Optional[float] = None
    scarcity_score: Optional[float] = None
    momentum_score: Optional[float] = None
    card_signal_score: Optional[float] = None
    recommendation: str = "WATCH"
    conviction: str = "INSUFFICIENT"
    risk: str = "UNKNOWN"
    time_horizon: str = "Not available"
    evidence: List[IntelligenceEvidenceItem] = Field(default_factory=list)
    missing_inputs: List[str] = Field(default_factory=list)
    calculated_at: datetime
    algorithm_version: str


class PlayerCardIntelligenceSummary(BaseModel):
    highest_card_signal: Optional[float] = None
    highest_card_signal_card_id: Optional[str] = None
    strongest_market_activity: Optional[float] = None
    strongest_market_activity_card_id: Optional[str] = None
    strongest_scarcity: Optional[float] = None
    strongest_scarcity_card_id: Optional[str] = None
    most_bid_activity: Optional[int] = None
    most_bid_activity_card_id: Optional[str] = None
    cards_with_sufficient_evidence: int = 0
    cards_pending_evidence: int = 0
    total_cards: int = 0
