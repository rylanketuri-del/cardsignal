"""Canonical card identity model for the Card Registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CardIdentity(BaseModel):
    """Collector-facing card identity — only populated fields are serialized."""

    cs_card_id: str
    sport: str | None = None
    player_id: str | None = None
    player_name: str | None = None
    year: int | None = None
    brand: str | None = None
    set: str | None = None
    subset: str | None = None
    parallel: str | None = None
    variation: str | None = None
    card_number: str | None = None
    rookie_flag: bool | None = None
    autograph_flag: bool | None = None
    relic_flag: bool | None = None
    serial_number: str | None = None
    grading_company: str | None = None
    grade: str | None = None
    population: int | None = None
    image_url: str | None = None
    active_listings: int | None = None
    median_price: float | None = None
    average_price: float | None = None
    last_updated: datetime | None = None

    def to_api_dict(self) -> dict[str, Any]:
        """Return only fields with real values for API payloads."""
        data = self.model_dump(mode="json", exclude_none=True)
        if self.last_updated is not None:
            data["last_updated"] = self.last_updated.isoformat()
        return data

    def has_collector_identity(self) -> bool:
        return bool(self.year or self.brand or self.set)

    def title_line(self) -> str | None:
        parts = [self.year, self.brand, self.set]
        line = " ".join(str(part) for part in parts if part is not None and part != "")
        return line or None

    def grade_line(self) -> str | None:
        if self.grading_company and self.grade is not None:
            return f"{self.grading_company} {self.grade}".strip()
        if self.grading_company:
            return self.grading_company
        if self.grade is not None:
            return str(self.grade)
        if self.has_collector_identity():
            return "Raw"
        return None

    model_config = {"extra": "ignore"}
