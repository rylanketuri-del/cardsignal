"""Previous-season and durable performance snapshot models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

PREVIOUS_SEASON_V1 = "PREVIOUS_SEASON_V1"

PerformancePeriodType = Literal[
    "RECENT_3_GAMES",
    "RECENT_5_GAMES",
    "REGULAR_SEASON",
    "POSTSEASON",
    "PRESEASON",
    "PREVIOUS_SEASON",
]
PerformanceSourceMethod = Literal[
    "OFFICIAL_API",
    "LICENSED_API",
    "APPROVED_IMPORT",
    "MANUAL_VERIFIED",
    "UNAVAILABLE",
]
PerformanceDataQuality = Literal["HIGH", "MEDIUM", "LOW", "INSUFFICIENT"]


class PreviousSeasonPerformanceSnapshot(BaseModel):
    """Normalized previous-season performance record — never masquerades as current form."""

    cs_player_id: str
    source_player_id: str
    league: str
    sport: str
    season: int
    season_label: str | None = None
    position: str | None = None
    team: str | None = None
    games_played: int = 0
    starts: int | None = None
    stats: dict[str, Any] = Field(default_factory=dict)
    data_quality: PerformanceDataQuality = "INSUFFICIENT"
    source_method: PerformanceSourceMethod = "APPROVED_IMPORT"
    source_reference: str = ""
    provider_updated_at: datetime | str | None = None
    captured_at: datetime | None = None
    algorithm_version: str = PREVIOUS_SEASON_V1
    period_type: Literal["PREVIOUS_SEASON"] = "PREVIOUS_SEASON"
    player_name: str | None = None
    headshot_url: str | None = None
    team_logo_url: str | None = None

    def snapshot_key(self) -> str:
        return f"{self.league.upper()}:{self.cs_player_id}:{self.season}:{self.period_type}"
