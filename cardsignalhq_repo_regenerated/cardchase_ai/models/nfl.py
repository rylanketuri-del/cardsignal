"""NFL performance and intelligence models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

NFL_PERFORMANCE_V1 = "NFL_PERFORMANCE_V1"
NFL_PLAYER_SIGNAL_V1 = "NFL_PLAYER_SIGNAL_V1"

NFLSourceMethod = Literal["OFFICIAL_API", "LICENSED_API", "APPROVED_IMPORT", "MANUAL_VERIFIED", "UNAVAILABLE"]
NFLDataQuality = Literal["HIGH", "MEDIUM", "LOW", "INSUFFICIENT"]
NFLPeriodType = Literal["RECENT_3_GAMES", "REGULAR_SEASON", "POSTSEASON", "PRESEASON", "PREVIOUS_SEASON"]
NFLPositionGroup = Literal["QB", "RB", "WR", "TE", "K", "DEFENSIVE_PLAYER", "UNKNOWN"]
NFLSeasonPhase = Literal["REGULAR_SEASON", "POSTSEASON", "PRESEASON", "OFFSEASON", "INACTIVE", "UNKNOWN"]

OFFENSIVE_POSITIONS = frozenset({"QB", "RB", "WR", "TE"})
OPTIONAL_POSITIONS = frozenset({"K", "DEFENSIVE_PLAYER"})

POSITION_MAP: dict[str, NFLPositionGroup] = {
    "QB": "QB",
    "RB": "RB",
    "FB": "RB",
    "WR": "WR",
    "TE": "TE",
    "K": "K",
    "PK": "K",
    "DE": "DEFENSIVE_PLAYER",
    "DT": "DEFENSIVE_PLAYER",
    "NT": "DEFENSIVE_PLAYER",
    "LB": "DEFENSIVE_PLAYER",
    "CB": "DEFENSIVE_PLAYER",
    "S": "DEFENSIVE_PLAYER",
    "SS": "DEFENSIVE_PLAYER",
    "FS": "DEFENSIVE_PLAYER",
    "DB": "DEFENSIVE_PLAYER",
    "DL": "DEFENSIVE_PLAYER",
    "OL": "DEFENSIVE_PLAYER",
    "OT": "DEFENSIVE_PLAYER",
    "OG": "DEFENSIVE_PLAYER",
    "C": "DEFENSIVE_PLAYER",
}


def map_nfl_position(position: str | None) -> NFLPositionGroup:
    if not position:
        return "UNKNOWN"
    normalized = position.strip().upper()
    return POSITION_MAP.get(normalized, "UNKNOWN")


class NFLPlayerIdentity(BaseModel):
    cs_player_id: str
    source_player_id: str
    sport: str = "FOOTBALL"
    league: str = "NFL"
    player_name: str
    team: str | None = None
    team_id: str | None = None
    position: str | None = None
    position_group: NFLPositionGroup = "UNKNOWN"
    jersey_number: int | None = None
    active_status: str = "ACTIVE"
    headshot_url: str | None = None
    team_logo_url: str | None = None
    season: int | None = None
    source_method: NFLSourceMethod = "UNAVAILABLE"
    last_updated: datetime | None = None


class NFLGameLogRow(BaseModel):
    game_id: str
    game_date: str
    season: int
    week: int | None = None
    team: str | None = None
    opponent: str | None = None
    home_away: str | None = None
    participated: bool = True
    is_bye_week: bool = False
    is_preseason: bool = False
    is_postseason: bool = False
    position_group: NFLPositionGroup = "UNKNOWN"
    stats: dict[str, Any] = Field(default_factory=dict)


class NFLPerformanceWindow(BaseModel):
    games_in_window: int = 0
    window_start: str | None = None
    window_end: str | None = None
    source_method: NFLSourceMethod = "UNAVAILABLE"
    captured_at: datetime | None = None
    data_quality: NFLDataQuality = "INSUFFICIENT"


class NFLPerformanceSnapshot(BaseModel):
    cs_player_id: str
    source_player_id: str
    league: str = "NFL"
    sport: str = "FOOTBALL"
    season: int
    position: str | None = None
    position_group: NFLPositionGroup = "UNKNOWN"
    period_type: NFLPeriodType
    period_start: str | None = None
    period_end: str | None = None
    games_played: int = 0
    stats: dict[str, Any] = Field(default_factory=dict)
    normalized_metrics: dict[str, float] = Field(default_factory=dict)
    performance_score: float | None = None
    data_quality: NFLDataQuality = "INSUFFICIENT"
    missing_inputs: list[str] = Field(default_factory=list)
    source_method: NFLSourceMethod = "UNAVAILABLE"
    algorithm_version: str = NFL_PERFORMANCE_V1
    captured_at: datetime | None = None
    explanation: str | None = None


class NFLSignalDriver(BaseModel):
    driver_type: str
    label: str
    description: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    source_method: NFLSourceMethod = "UNAVAILABLE"
    captured_at: datetime | None = None
    season_phase: NFLSeasonPhase | None = None


class NFLPlayerSearchResult(BaseModel):
    player_id: str
    cs_player_id: str
    source_player_id: str
    player_name: str
    team: str = "NFL"
    team_id: str | None = None
    position: str | None = None
    position_group: NFLPositionGroup = "UNKNOWN"
    sport: str = "FOOTBALL"
    league: str = "NFL"
    headshot_url: str = ""
    team_logo_url: str = ""
    active_status: str = "ACTIVE"
