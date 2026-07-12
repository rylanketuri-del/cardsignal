"""NBA performance and intelligence models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

NBA_PERFORMANCE_V1 = "NBA_PERFORMANCE_V1"
NBA_PLAYER_SIGNAL_V1 = "NBA_PLAYER_SIGNAL_V1"

NBASourceMethod = Literal["OFFICIAL_API", "LICENSED_API", "APPROVED_IMPORT", "MANUAL_VERIFIED", "UNAVAILABLE"]
NBADataQuality = Literal["HIGH", "MEDIUM", "LOW", "INSUFFICIENT"]
NBAPeriodType = Literal["RECENT_5_GAMES", "REGULAR_SEASON", "POSTSEASON", "PRESEASON", "PREVIOUS_SEASON"]
NBAPosition = Literal["PG", "SG", "SF", "PF", "C", "UNKNOWN"]
NBASeasonPhase = Literal["REGULAR_SEASON", "POSTSEASON", "PRESEASON", "OFFSEASON", "INACTIVE", "UNKNOWN"]

SUPPORTED_POSITIONS = frozenset({"PG", "SG", "SF", "PF", "C"})

NBA_RECENT_WINDOW = {
    "recent_window_type": "COMPLETED_GAMES",
    "recent_window_value": 5,
}


def recent_window_value() -> int:
    return int(NBA_RECENT_WINDOW["recent_window_value"])


POSITION_MAP: dict[str, NBAPosition] = {
    "PG": "PG",
    "POINT GUARD": "PG",
    "G": "PG",
    "SG": "SG",
    "SHOOTING GUARD": "SG",
    "SF": "SF",
    "SMALL FORWARD": "SF",
    "F": "SF",
    "PF": "PF",
    "POWER FORWARD": "PF",
    "C": "C",
    "CENTER": "C",
}


def map_nba_position(position: str | None) -> NBAPosition:
    if not position:
        return "UNKNOWN"
    normalized = position.strip().upper()
    if normalized in SUPPORTED_POSITIONS:
        return normalized  # type: ignore[return-value]
    return POSITION_MAP.get(normalized, "UNKNOWN")


class NBAPlayerIdentity(BaseModel):
    cs_player_id: str
    source_player_id: str
    sport: str = "BASKETBALL"
    league: str = "NBA"
    player_name: str
    team: str | None = None
    team_id: str | None = None
    position: str | None = None
    position_group: NBAPosition = "UNKNOWN"
    jersey_number: int | None = None
    active_status: str = "ACTIVE"
    headshot_url: str | None = None
    team_logo_url: str | None = None
    season: int | None = None
    source_method: NBASourceMethod = "UNAVAILABLE"
    last_updated: datetime | None = None


class NBAGameLogRow(BaseModel):
    game_id: str
    game_date: str
    season: int
    team: str | None = None
    opponent: str | None = None
    home_away: str | None = None
    participated: bool = True
    is_preseason: bool = False
    is_postseason: bool = False
    position: NBAPosition = "UNKNOWN"
    stats: dict[str, Any] = Field(default_factory=dict)


class NBAPerformanceWindow(BaseModel):
    games_in_window: int = 0
    window_start: str | None = None
    window_end: str | None = None
    window_type: str = NBA_RECENT_WINDOW["recent_window_type"]
    window_value: int = NBA_RECENT_WINDOW["recent_window_value"]
    source_method: NBASourceMethod = "UNAVAILABLE"
    captured_at: datetime | None = None
    data_quality: NBADataQuality = "INSUFFICIENT"


class NBAPerformanceSnapshot(BaseModel):
    cs_player_id: str
    source_player_id: str
    league: str = "NBA"
    sport: str = "BASKETBALL"
    season: int
    position: str | None = None
    position_group: NBAPosition = "UNKNOWN"
    period_type: NBAPeriodType
    period_start: str | None = None
    period_end: str | None = None
    games_played: int = 0
    stats: dict[str, Any] = Field(default_factory=dict)
    normalized_metrics: dict[str, float] = Field(default_factory=dict)
    performance_score: float | None = None
    data_quality: NBADataQuality = "INSUFFICIENT"
    missing_inputs: list[str] = Field(default_factory=list)
    source_method: NBASourceMethod = "UNAVAILABLE"
    algorithm_version: str = NBA_PERFORMANCE_V1
    captured_at: datetime | None = None
    explanation: str | None = None


class NBASignalDriver(BaseModel):
    driver_type: str
    label: str
    description: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    source_method: NBASourceMethod = "UNAVAILABLE"
    captured_at: datetime | None = None
    season_phase: NBASeasonPhase | None = None


class NBAPlayerSearchResult(BaseModel):
    player_id: str
    cs_player_id: str
    source_player_id: str
    player_name: str
    team: str = "NBA"
    team_id: str | None = None
    position: str | None = None
    position_group: NBAPosition = "UNKNOWN"
    sport: str = "BASKETBALL"
    league: str = "NBA"
    headshot_url: str = ""
    team_logo_url: str = ""
    active_status: str = "ACTIVE"
