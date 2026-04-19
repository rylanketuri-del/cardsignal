from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class PlayerLookup(BaseModel):
    player_id: int
    full_name: str


class HitterGameLogRow(BaseModel):
    date: str
    at_bats: int = 0
    hits: int = 0
    home_runs: int = 0
    rbi: int = 0
    stolen_bases: int = 0
    walks: int = 0
    strikeouts: int = 0
    avg: Optional[float] = None
    obp: Optional[float] = None
    slg: Optional[float] = None
    ops: Optional[float] = None


class ListingTagSummary(BaseModel):
    psa10_count: int = 0
    auto_count: int = 0
    bowman_1st_count: int = 0
    chrome_count: int = 0
    rookie_count: int = 0
    numbered_count: int = 0
    premium_count: int = 0


class ListingSummary(BaseModel):
    item_id: str
    title: str
    price: Optional[float] = None
    currency: Optional[str] = None
    condition: Optional[str] = None
    created_at: Optional[str] = None
    item_web_url: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class MarketSnapshot(BaseModel):
    query_name: str
    listings_count: int = 0
    avg_price: Optional[float] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    tags: ListingTagSummary = Field(default_factory=ListingTagSummary)
    listings: List[ListingSummary] = Field(default_factory=list)


class RollingHitterStats(BaseModel):
    games: int = 0
    at_bats: int = 0
    hits: int = 0
    home_runs: int = 0
    rbi: int = 0
    stolen_bases: int = 0
    walks: int = 0
    strikeouts: int = 0
    avg: float = 0.0
    obp: float = 0.0
    slg: float = 0.0
    ops: float = 0.0


class HitterHotnessBreakdown(BaseModel):
    player_name: str
    performance_score: float
    market_score: float
    total_score: float
    confidence_multiplier: float
    tag: str
    reasons: List[str]
