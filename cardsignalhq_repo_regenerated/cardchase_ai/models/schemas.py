from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class PlayerLookup(BaseModel):
    player_id: int
    full_name: str


class PlayerSearchResult(BaseModel):
    player_id: int
    player_name: str
    team: str = "MLB"
    team_id: int | None = None
    position: str | None = None
    sport: str = "MLB"
    headshot_url: str
    team_logo_url: str = ""


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


class NormalizedActiveListing(BaseModel):
    """Normalized eBay active listing observation (asking price, not a sold comp)."""

    source_listing_id: str
    title: str
    price: float | None = None
    shipping: float | None = None
    total_price: float | None = None
    currency: str = "USD"
    condition: str | None = None
    listing_type: str = "unknown"
    bid_count: int = 0
    item_url: str | None = None
    image_url: str | None = None
    seller: str | None = None
    captured_at: str | None = None


class CardMarketSnapshot(BaseModel):
    """Historical active-listing market observation for one registry card."""

    cs_card_id: str
    cs_player_id: str
    league: str
    source: str = "ebay"
    query: str
    captured_at: datetime
    active_listing_count: int = 0
    auction_count: int = 0
    buy_it_now_count: int = 0
    listings_with_bids: int = 0
    total_bid_count: int = 0
    average_price: float | None = None
    median_price: float | None = None
    minimum_price: float | None = None
    maximum_price: float | None = None
    average_shipping: float | None = None
    total_market_value: float | None = None
    currency: str = "USD"
    sample_size: int = 0
    data_quality: str = "INSUFFICIENT"
    algorithm_version: str


class CardMarketMovement(BaseModel):
    """Historical active-listing movement between two stored snapshots."""

    cs_card_id: str
    cs_player_id: str
    current_captured_at: datetime
    comparison_captured_at: datetime | None = None
    comparison_window: str
    current_median_price: float | None = None
    previous_median_price: float | None = None
    median_price_change: float | None = None
    median_price_change_pct: float | None = None
    current_average_price: float | None = None
    previous_average_price: float | None = None
    average_price_change: float | None = None
    average_price_change_pct: float | None = None
    listing_count_change: int | None = None
    listing_count_change_pct: float | None = None
    bid_count_change: int | None = None
    bid_count_change_pct: float | None = None
    auction_count_change: int | None = None
    sample_size_current: int = 0
    sample_size_previous: int = 0
    current_data_quality: str = "INSUFFICIENT"
    previous_data_quality: str = "INSUFFICIENT"
    movement_quality: str = "INSUFFICIENT"
    algorithm_version: str
