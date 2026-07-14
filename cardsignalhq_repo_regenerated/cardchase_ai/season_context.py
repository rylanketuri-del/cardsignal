"""Centralized season-context resolution for offseason and active-season labels.

Season years and split-year labels must come from stored snapshot data —
never from the calendar year alone, player age, rank, or frontend guesses.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

OFFSEASON_HELPER_TEXT = "Most recently completed season"
FALLBACK_DISPLAY_LABEL = "Previous Season Performance"
UNAVAILABLE_PREVIOUS_SEASON = "Previous season performance unavailable"
PRESEASON_PERFORMANCE_LABEL = "Preseason Performance"


class _PreviousSeasonLookup(Protocol):
    def get_previous_season(
        self,
        league: str,
        cs_player_id: str,
        season: int | None = None,
    ) -> Any:
        ...


@dataclass(frozen=True)
class SeasonContext:
    """Resolved season display context for intelligence surfaces."""

    season: int | None
    season_label: str | None
    display_label: str
    helper_text: str | None
    source_snapshot_id: str | None
    data_quality: str


def format_single_year_season_label(season: int) -> str:
    return str(season)


def format_nba_split_season_label(season: int) -> str:
    """League-aware split-year label from a stored starting season year."""
    return f"{season}–{str(season + 1)[-2:]}"


def canonical_season_label(
    league: str,
    season: int | None,
    *,
    stored_label: str | None = None,
) -> str | None:
    """Return the canonical season label for a league from stored data.

    Prefer an explicit stored label (especially NBA). Otherwise format from the
    stored season year using league-aware rules — never a hardcoded year.
    """
    if stored_label:
        return str(stored_label).strip() or None
    if season is None:
        return None
    if str(league or "").upper() == "NBA":
        return format_nba_split_season_label(int(season))
    return format_single_year_season_label(int(season))


def format_season_performance_label(
    league: str,
    season: int | None,
    *,
    stored_label: str | None = None,
) -> str:
    """Build `{season_label} Season Performance`, or the fallback when missing."""
    label = canonical_season_label(league, season, stored_label=stored_label)
    if not label:
        return FALLBACK_DISPLAY_LABEL
    return f"{label} Season Performance"


def empty_season_context(*, offseason: bool = True) -> SeasonContext:
    return SeasonContext(
        season=None,
        season_label=None,
        display_label=FALLBACK_DISPLAY_LABEL,
        helper_text=OFFSEASON_HELPER_TEXT if offseason else None,
        source_snapshot_id=None,
        data_quality="INSUFFICIENT",
    )


def context_from_previous_season_snapshot(
    snapshot: Any,
    *,
    offseason: bool = True,
) -> SeasonContext:
    """Build season context from a verified PREVIOUS_SEASON performance snapshot."""
    if snapshot is None:
        return empty_season_context(offseason=offseason)

    league = getattr(snapshot, "league", None) or ""
    season = getattr(snapshot, "season", None)
    stored_label = getattr(snapshot, "season_label", None)
    quality = getattr(snapshot, "data_quality", None) or "INSUFFICIENT"
    source_id = None
    if hasattr(snapshot, "snapshot_key"):
        try:
            source_id = snapshot.snapshot_key()
        except Exception:
            source_id = None
    if source_id is None:
        source_id = getattr(snapshot, "source_reference", None) or None

    season_label = canonical_season_label(league, season, stored_label=stored_label)
    return SeasonContext(
        season=int(season) if season is not None else None,
        season_label=season_label,
        display_label=format_season_performance_label(league, season, stored_label=stored_label),
        helper_text=OFFSEASON_HELPER_TEXT if offseason else None,
        source_snapshot_id=source_id,
        data_quality=str(quality),
    )


def context_from_stored_fields(
    league: str,
    *,
    season: int | None = None,
    season_label: str | None = None,
    source_snapshot_id: str | None = None,
    data_quality: str | None = None,
    offseason: bool = True,
) -> SeasonContext:
    """Build context from already-resolved stored season fields (no inference)."""
    if season is None and not season_label:
        return empty_season_context(offseason=offseason)
    return SeasonContext(
        season=int(season) if season is not None else None,
        season_label=canonical_season_label(league, season, stored_label=season_label),
        display_label=format_season_performance_label(league, season, stored_label=season_label),
        helper_text=OFFSEASON_HELPER_TEXT if offseason else None,
        source_snapshot_id=source_snapshot_id,
        data_quality=data_quality or "INSUFFICIENT",
    )


def resolve_offseason_season_context(
    league: str,
    cs_player_id: str,
    performance_store: _PreviousSeasonLookup | None,
    *,
    preferred_season: int | None = None,
) -> SeasonContext:
    """Resolve the most recently completed verified season for offseason surfaces.

    Priority:
      1. Latest verified stored PREVIOUS_SEASON snapshot for that player/league
         (optionally preferring a specific season when provided).
      2. Same generalized performance repository lookup without a season filter.
      3. No season available → fallback label.
    """
    if not performance_store or not cs_player_id:
        return empty_season_context(offseason=True)

    snap = None
    if preferred_season is not None:
        snap = performance_store.get_previous_season(league, cs_player_id, preferred_season)
    if snap is None:
        snap = performance_store.get_previous_season(league, cs_player_id, None)
    return context_from_previous_season_snapshot(snap, offseason=True)


def active_season_performance_label(
    league: str,
    season: int | None,
    *,
    stored_label: str | None = None,
) -> str:
    """Active-season display label from the current stored season."""
    return format_season_performance_label(league, season, stored_label=stored_label)


# Back-compat alias used by weekly pipelines / serializer
def previous_season_label(
    league: str,
    season: int | None,
    *,
    stored_label: str | None = None,
) -> str:
    return format_season_performance_label(league, season, stored_label=stored_label)


def previous_season_helper_text(*, has_season: bool) -> str | None:
    if has_season:
        return OFFSEASON_HELPER_TEXT
    return None
