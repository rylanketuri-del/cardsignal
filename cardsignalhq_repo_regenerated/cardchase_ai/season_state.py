"""Reusable sport-season state model with league adapters."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from cardchase_ai.models.signal_driver import (
    LeagueSeasonMetadata,
    SeasonState,
    SourceType,
    SportSeasonState,
)

SIGNAL_DRIVERS_V1 = "SIGNAL_DRIVERS_V1"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class SeasonStateAdapter(Protocol):
    league: str
    sport: str

    def resolve(
        self,
        *,
        anchor: datetime,
        season: int,
        metadata: LeagueSeasonMetadata | None,
        player_games_recent: int | None = None,
    ) -> SportSeasonState: ...


def _state_from_metadata(
    league: str,
    sport: str,
    season: int,
    anchor: datetime,
    metadata: LeagueSeasonMetadata | None,
    source_reference: str,
) -> SeasonState:
    """Resolve season state from stored metadata only — never calendar guessing."""
    if metadata is None:
        return "UNKNOWN"

    anchor = _ensure_aware(anchor)

    def in_range(start: datetime | None, end: datetime | None) -> bool:
        if start is None or end is None:
            return False
        start = _ensure_aware(start)
        end = _ensure_aware(end)
        return start <= anchor <= end

    if in_range(metadata.postseason_start, metadata.postseason_end):
        return "POSTSEASON"
    if in_range(metadata.regular_season_start, metadata.regular_season_end):
        return "REGULAR_SEASON"
    if in_range(metadata.preseason_start, metadata.preseason_end):
        return "PRESEASON"
    if in_range(metadata.offseason_start, metadata.offseason_end):
        return "OFFSEASON"

    return "UNKNOWN"


def _apply_player_inactivity(
    base_state: SeasonState,
    player_games_recent: int | None,
) -> SeasonState:
    """Player-level INACTIVE during active league periods when no recent games."""
    if player_games_recent is None:
        return base_state
    if base_state in {"REGULAR_SEASON", "POSTSEASON", "PRESEASON"} and player_games_recent == 0:
        return "INACTIVE"
    return base_state


class MLBSeasonStateAdapter:
    league = "MLB"
    sport = "MLB"

    def resolve(
        self,
        *,
        anchor: datetime,
        season: int,
        metadata: LeagueSeasonMetadata | None,
        player_games_recent: int | None = None,
    ) -> SportSeasonState:
        base = _state_from_metadata(
            self.league,
            self.sport,
            season,
            anchor,
            metadata,
            source_reference="league_season_metadata",
        )
        state = _apply_player_inactivity(base, player_games_recent)
        return SportSeasonState(
            league=self.league,
            sport=self.sport,
            season=season,
            state=state,
            determined_at=_utcnow(),
            source_type=metadata.source_type if metadata else "PERFORMANCE_SNAPSHOT",
            source_reference=metadata.source_reference if metadata else "no_stored_metadata",
            metadata={
                "adapter": "MLBSeasonStateAdapter",
                "has_stored_metadata": metadata is not None,
            },
        )


class NBASeasonStateAdapter:
    """Prepared adapter — returns UNKNOWN without stored NBA metadata."""

    league = "NBA"
    sport = "NBA"

    def resolve(
        self,
        *,
        anchor: datetime,
        season: int,
        metadata: LeagueSeasonMetadata | None,
        player_games_recent: int | None = None,
    ) -> SportSeasonState:
        base = _state_from_metadata(
            self.league,
            self.sport,
            season,
            anchor,
            metadata,
            source_reference="nba_season_metadata",
        )
        state = _apply_player_inactivity(base, player_games_recent)
        return SportSeasonState(
            league=self.league,
            sport=self.sport,
            season=season,
            state=state,
            determined_at=_utcnow(),
            source_type=metadata.source_type if metadata else "PERFORMANCE_SNAPSHOT",
            source_reference=metadata.source_reference if metadata else "nba_not_configured",
            metadata={"adapter": "NBASeasonStateAdapter", "configured": metadata is not None},
        )


class NFLSeasonStateAdapter:
    """Prepared adapter — returns UNKNOWN without stored NFL metadata."""

    league = "NFL"
    sport = "NFL"

    def resolve(
        self,
        *,
        anchor: datetime,
        season: int,
        metadata: LeagueSeasonMetadata | None,
        player_games_recent: int | None = None,
    ) -> SportSeasonState:
        base = _state_from_metadata(
            self.league,
            self.sport,
            season,
            anchor,
            metadata,
            source_reference="nfl_season_metadata",
        )
        state = _apply_player_inactivity(base, player_games_recent)
        return SportSeasonState(
            league=self.league,
            sport=self.sport,
            season=season,
            state=state,
            determined_at=_utcnow(),
            source_type=metadata.source_type if metadata else "PERFORMANCE_SNAPSHOT",
            source_reference=metadata.source_reference if metadata else "nfl_not_configured",
            metadata={"adapter": "NFLSeasonStateAdapter", "configured": metadata is not None},
        )


SPORT_SEASON_ADAPTERS: dict[str, SeasonStateAdapter] = {
    "MLB": MLBSeasonStateAdapter(),
    "NBA": NBASeasonStateAdapter(),
    "NFL": NFLSeasonStateAdapter(),
}


# Multi-sport performance window configuration (foundation only).
SPORT_DRIVER_CONFIG: dict[str, dict[str, int | str]] = {
    "MLB": {
        "recent_window_days": 7,
        "season_window_days": 30,
        "recent_label": "Last 7 Days",
        "season_label": "Season Snapshot",
    },
    "NBA": {
        "recent_window_games": 5,
        "season_label": "Season Averages",
        "status": "prepared_not_active",
    },
    "NFL": {
        "recent_window_games": 3,
        "season_label": "Season Totals",
        "status": "prepared_not_active",
    },
}


def get_season_adapter(league: str) -> SeasonStateAdapter:
    return SPORT_SEASON_ADAPTERS.get(league.upper(), MLBSeasonStateAdapter())


def resolve_season_state(
    league: str,
    *,
    season: int,
    anchor: datetime | None = None,
    metadata: LeagueSeasonMetadata | None = None,
    player_games_recent: int | None = None,
) -> SportSeasonState:
    adapter = get_season_adapter(league)
    return adapter.resolve(
        anchor=anchor or _utcnow(),
        season=season,
        metadata=metadata,
        player_games_recent=player_games_recent,
    )
