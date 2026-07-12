"""Shared adapter contracts for the CardSignal sport framework."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from cardchase_ai.adapters.metadata import LeagueMetadata, SportMetadata
from typing import TYPE_CHECKING

from cardchase_ai.config import Settings
from cardchase_ai.models.schemas import HitterHotnessBreakdown, MarketSnapshot
from cardchase_ai.utils.reporting_period import ReportingPeriod

if TYPE_CHECKING:
    from cardchase_ai.pipeline import PlayerPipelineOutput


@runtime_checkable
class SeasonAdapter(Protocol):
    """Season calendar and reporting period rules."""

    def resolve_season(self, settings: Settings, period_start: datetime) -> int: ...

    def build_reporting_period(
        self,
        *,
        anchor: datetime | None = None,
        timezone_name: str,
        season: int | None = None,
        settings: Any | None = None,
    ) -> ReportingPeriod: ...


@runtime_checkable
class PerformanceAdapter(Protocol):
    """Sport-specific performance metrics, normalization, and scoring."""

    def fetch_performance_windows(
        self,
        player_id: int,
        season: int,
        settings: Settings,
    ) -> tuple[Any, Any]: ...

    def build_hotness_breakdown(
        self,
        player_name: str,
        stats_recent: Any,
        stats_baseline: Any,
        market_snapshots: dict[str, MarketSnapshot],
    ) -> HitterHotnessBreakdown: ...

    def derive_momentum(
        self,
        stats_recent: Any,
        stats_baseline: Any,
    ) -> tuple[float | None, list[str], list[str]]: ...

    def recent_games_missing_key(self) -> str: ...


@runtime_checkable
class SignalDriverAdapter(Protocol):
    """League-specific signal driver generation."""

    @property
    def driver_id(self) -> str: ...

    def generate(self, context: dict[str, Any]) -> list[str]: ...


@runtime_checkable
class PlayerSnapshotAdapter(Protocol):
    """Snapshot content and labels for player reports."""

    def stat_specs(self) -> dict[str, Any]: ...

    def snapshot_labels(self) -> dict[str, str]: ...


@runtime_checkable
class CardSignalAdapter(Protocol):
    """Card search templates and card intelligence labels."""

    def search_templates(self) -> dict[str, str]: ...

    def query_labels(self) -> dict[str, str]: ...


@runtime_checkable
class CardReportAdapter(Protocol):
    """Card report metric specs and labels."""

    def card_metric_specs(self) -> dict[str, Any]: ...


@runtime_checkable
class LeagueAdapter(Protocol):
    """League-level routing: roster, schedule, standings, and pipeline wiring."""

    @property
    def league_code(self) -> str: ...

    @property
    def metadata(self) -> LeagueMetadata: ...

    @property
    def season(self) -> SeasonAdapter: ...

    @property
    def performance(self) -> PerformanceAdapter: ...

    @property
    def card_signal(self) -> CardSignalAdapter: ...

    @property
    def player_snapshot(self) -> PlayerSnapshotAdapter: ...

    @property
    def card_report(self) -> CardReportAdapter: ...

    @property
    def signal_drivers(self) -> tuple[SignalDriverAdapter, ...]: ...

    @property
    def pipeline_enabled(self) -> bool: ...

    def build_market_universe(self, settings: Settings, *, scan_limit: int | None = None) -> list[dict[str, Any]]: ...

    def search_players(self, query: str, *, limit: int = 10) -> list[dict[str, Any]]: ...

    def process_player(
        self,
        candidate: dict[str, Any],
        ebay_client: Any | None,
        settings: Settings,
        *,
        market_enabled: bool,
    ) -> tuple["PlayerPipelineOutput | None", list[MarketSnapshot], str | None]: ...


@runtime_checkable
class SportAdapter(Protocol):
    """Sport-level grouping and registry integration."""

    @property
    def sport_code(self) -> str: ...

    @property
    def metadata(self) -> SportMetadata: ...

    def leagues(self) -> tuple[str, ...]: ...
