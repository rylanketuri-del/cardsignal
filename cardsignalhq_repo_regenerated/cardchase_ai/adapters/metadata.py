"""Reusable sport and league metadata for the adapter framework."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

RecentWindowKind = Literal["days", "games"]


@dataclass(frozen=True)
class RecentWindow:
    """Defines how a league measures the 'recent' performance window."""

    kind: RecentWindowKind
    value: int


@dataclass(frozen=True)
class SeasonPhaseRules:
    """League season phase configuration."""

    preseason: bool = False
    regular_season: bool = True
    postseason: bool = True
    offseason: bool = True


@dataclass(frozen=True)
class LeagueMetadata:
    """Static metadata describing a registered league."""

    sport: str
    league: str
    timezone: str
    recent_window: RecentWindow
    season_phases: SeasonPhaseRules
    supported_positions: tuple[str, ...]
    supported_metrics: tuple[str, ...]
    card_support: bool
    search_support: bool
    player_signal_algorithm_version: str
    period_start_weekday: int
    period_end_weekday: int
    card_search_templates: dict[str, str] = field(default_factory=dict)
    card_query_labels: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SportMetadata:
    """Metadata for a sport grouping one or more leagues."""

    sport: str
    leagues: tuple[str, ...]
    card_support: bool
    search_support: bool
