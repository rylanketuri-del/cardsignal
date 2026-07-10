"""Historical market movement models."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

MovementStatus = Literal["calculated", "pending", "unavailable"]


class CardMarketMovement(BaseModel):
    cs_player_id: str
    cs_card_id: str
    query_name: str
    run_id: str
    league: str
    year: int
    week_number: int
    current_avg_price: float | None = None
    prior_avg_price: float | None = None
    price_change_pct: float | None = None
    current_listings_count: int = 0
    prior_listings_count: int | None = None
    listings_change: int | None = None
    currency: str | None = None
    prior_currency: str | None = None
    status: MovementStatus = "pending"
    label: str = "Movement pending"
    captured_at: datetime | None = None
    evidence: dict = Field(default_factory=dict)
