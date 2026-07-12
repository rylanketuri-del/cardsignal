"""Reusable sport and league metadata for the adapter framework.

Canonical configuration for league behavior lives on LeagueMetadata in each
registered LeagueAdapter (see cardchase_ai/adapters/registry.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

RecentWindowKind = Literal["days", "games"]
LiveStatus = Literal["live", "coming_soon", "unsupported"]


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
    """Static metadata describing a registered league — single source of truth."""

    sport: str
    league: str
    display_name: str
    timezone: str
    recent_window: RecentWindow
    baseline_window_days: int
    season_phases: SeasonPhaseRules
    supported_positions: tuple[str, ...]
    supported_metrics: tuple[str, ...]
    card_support: bool
    search_enabled: bool
    live_status: LiveStatus
    scoring_algorithm_version: str
    period_start_weekday: int
    period_end_weekday: int
    refresh_day: int = 1
    refresh_hour: int = 6
    season_settings_key: str | None = None
    card_search_templates: dict[str, str] = field(default_factory=dict)
    card_query_labels: dict[str, str] = field(default_factory=dict)

    @property
    def search_support(self) -> bool:
        """Backward-compatible alias."""
        return self.search_enabled


@dataclass(frozen=True)
class SportMetadata:
    """Metadata for a sport grouping one or more leagues."""

    sport: str
    leagues: tuple[str, ...]
    card_support: bool
    search_support: bool
