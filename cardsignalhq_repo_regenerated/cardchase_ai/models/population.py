"""PSA population, matching, and scarcity models — Sprint 8.6."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

MATCH_STATUSES = frozenset({"MATCHED", "POSSIBLE", "UNMATCHED", "AMBIGUOUS"})
MATCH_CONFIDENCES = frozenset({"HIGH", "MEDIUM", "LOW"})
DATA_QUALITIES = frozenset({"HIGH", "MEDIUM", "LOW", "INSUFFICIENT"})
SOURCE_METHODS = frozenset({"official_api", "approved_import", "manual_beta_seed"})


class PSACardMatch(BaseModel):
    cs_card_id: str
    cs_player_id: str
    league: str
    provider: str = "PSA"
    psa_subject_id: Optional[str] = None
    psa_set_id: Optional[str] = None
    psa_card_id: Optional[str] = None
    certification_number: Optional[str] = None
    year: str = ""
    manufacturer: str = ""
    set_name: str = ""
    card_number: str = ""
    card_name: str = ""
    parallel: str = ""
    variety: str = ""
    player_name: str = ""
    match_status: str = "UNMATCHED"
    match_confidence: str = "LOW"
    matched_at: Optional[datetime] = None
    source_method: str = "manual_beta_seed"
    notes: str = ""


class CardPopulationSnapshot(BaseModel):
    cs_card_id: str
    cs_player_id: str
    league: str
    provider: str = "PSA"
    source_method: str = "manual_beta_seed"
    captured_at: datetime
    psa_card_id: Optional[str] = None
    total_population: Optional[int] = None
    population_by_grade: Dict[str, Optional[int]] = Field(default_factory=dict)
    psa_10_population: Optional[int] = None
    psa_9_population: Optional[int] = None
    psa_8_population: Optional[int] = None
    higher_grade_population: Optional[int] = None
    lower_grade_population: Optional[int] = None
    grade_requested: Optional[str] = None
    requested_grade_population: Optional[int] = None
    gem_rate: Optional[float] = None
    top_grade_rate: Optional[float] = None
    data_quality: str = "INSUFFICIENT"
    match_confidence: str = "LOW"
    algorithm_version: str
    provider_updated_at: Optional[datetime] = None
    notes: str = ""


class CardScarcityMetrics(BaseModel):
    cs_card_id: str
    cs_player_id: str
    population_score: Optional[float] = None
    grade_scarcity_score: Optional[float] = None
    listing_scarcity_score: Optional[float] = None
    population_growth_score: Optional[float] = None
    overall_scarcity_score: Optional[float] = None
    confidence: str = "LOW"
    inputs_available: List[str] = Field(default_factory=list)
    algorithm_version: str
    calculated_at: datetime
    label: str = "PSA Population Scarcity"


class CardPopulationMovement(BaseModel):
    cs_card_id: str
    cs_player_id: str
    current_population: Optional[int] = None
    previous_population: Optional[int] = None
    population_change: Optional[int] = None
    population_change_pct: Optional[float] = None
    current_psa_10_population: Optional[int] = None
    previous_psa_10_population: Optional[int] = None
    psa_10_population_change: Optional[int] = None
    comparison_captured_at: Optional[datetime] = None
    movement_quality: str = "INSUFFICIENT"
    has_movement: bool = False
