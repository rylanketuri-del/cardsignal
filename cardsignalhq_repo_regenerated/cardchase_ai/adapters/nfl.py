"""NFL league adapter — metadata and period rules; pipeline stub for future sprint."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from cardchase_ai.adapters.league_constants import (
    NFL_CARD_QUERY_LABELS,
    NFL_SEARCH_TEMPLATES,
    NFL_SUPPORTED_METRICS,
    NFL_SUPPORTED_POSITIONS,
)
from cardchase_ai.adapters.metadata import LeagueMetadata, RecentWindow, SeasonPhaseRules, SportMetadata
from cardchase_ai.adapters.period_rules import build_reporting_period_from_metadata
from cardchase_ai.config import Settings
from cardchase_ai.models.schemas import MarketSnapshot
from cardchase_ai.models.weekly import NFL_PLAYER_SIGNAL_V1
from cardchase_ai.signals.drivers import NFL_NARRATIVE_DRIVERS
from cardchase_ai.utils.reporting_period import ReportingPeriod


class NflSeasonAdapter:
    def __init__(self, league: NflLeagueAdapter) -> None:
        self._league = league

    def resolve_season(self, settings: Settings, period_start: datetime, explicit_season: int | None = None) -> int:
        from cardchase_ai.adapters.period_rules import resolve_season_from_metadata

        return resolve_season_from_metadata(
            self._league.metadata,
            period_start,
            settings,
            explicit_season,
        )

    def build_reporting_period(
        self,
        *,
        anchor: datetime | None = None,
        timezone_name: str,
        season: int | None = None,
        settings: Settings | None = None,
    ) -> ReportingPeriod:
        return build_reporting_period_from_metadata(
            self._league.metadata,
            anchor=anchor,
            timezone_name=timezone_name,
            season=season,
            settings=settings,
        )


class NflPerformanceAdapter:
    """Stub — NFL performance formulas arrive in Sprint 11.1+."""

    def __init__(self, league: NflLeagueAdapter) -> None:
        self._league = league

    def fetch_performance_windows(self, player_id: int, season: int, settings: Settings):
        raise NotImplementedError("NFL performance adapter is not yet implemented")

    def build_hotness_breakdown(self, player_name: str, stats_recent, stats_baseline, market_snapshots):
        raise NotImplementedError("NFL performance adapter is not yet implemented")

    def derive_momentum(self, stats_recent, stats_baseline):
        raise NotImplementedError("NFL performance adapter is not yet implemented")

    def recent_games_missing_key(self) -> str:
        return "stats_recent_games"


class NflCardSignalAdapter:
    def search_templates(self) -> dict[str, str]:
        return dict(NFL_SEARCH_TEMPLATES)

    def query_labels(self) -> dict[str, str]:
        return dict(NFL_CARD_QUERY_LABELS)


class NflPlayerSnapshotAdapter:
    def stat_specs(self) -> dict[str, Any]:
        return {
            "recent_label": "Last 3 Games",
            "baseline_label": "Season Snapshot",
            "metrics": list(NFL_SUPPORTED_METRICS),
        }

    def snapshot_labels(self) -> dict[str, str]:
        return {
            "recent": "Last 3 Games",
            "baseline": "Season Snapshot",
        }


class NflCardReportAdapter:
    def card_metric_specs(self) -> dict[str, Any]:
        return {"labels": dict(NFL_CARD_QUERY_LABELS)}


class NflNarrativeDriverAdapter:
    def __init__(self, driver) -> None:
        self._driver = driver

    @property
    def driver_id(self) -> str:
        return self._driver.driver_id

    def generate(self, context: dict[str, Any]) -> list[str]:
        result = self._driver.compute(context)
        return result.reasons


class NflLeagueAdapter:
    def __init__(self) -> None:
        self._season = NflSeasonAdapter(self)
        self._performance = NflPerformanceAdapter(self)
        self._card_signal = NflCardSignalAdapter()
        self._player_snapshot = NflPlayerSnapshotAdapter()
        self._card_report = NflCardReportAdapter()

    @property
    def league_code(self) -> str:
        return "NFL"

    @property
    def metadata(self) -> LeagueMetadata:
        return LeagueMetadata(
            sport="FOOTBALL",
            league="NFL",
            display_name="National Football League",
            timezone="America/New_York",
            recent_window=RecentWindow(kind="games", value=3),
            baseline_window_days=30,
            season_phases=SeasonPhaseRules(preseason=True, regular_season=True, postseason=True, offseason=True),
            supported_positions=NFL_SUPPORTED_POSITIONS,
            supported_metrics=NFL_SUPPORTED_METRICS,
            card_support=True,
            search_enabled=True,
            live_status="coming_soon",
            scoring_algorithm_version=NFL_PLAYER_SIGNAL_V1,
            period_start_weekday=3,
            period_end_weekday=0,
            refresh_day=1,
            refresh_hour=6,
            card_search_templates=NFL_SEARCH_TEMPLATES,
            card_query_labels=NFL_CARD_QUERY_LABELS,
        )

    @property
    def season(self) -> NflSeasonAdapter:
        return self._season

    @property
    def performance(self) -> NflPerformanceAdapter:
        return self._performance

    @property
    def card_signal(self) -> NflCardSignalAdapter:
        return self._card_signal

    @property
    def player_snapshot(self) -> NflPlayerSnapshotAdapter:
        return self._player_snapshot

    @property
    def card_report(self) -> NflCardReportAdapter:
        return self._card_report

    @property
    def signal_drivers(self) -> tuple[NflNarrativeDriverAdapter, ...]:
        return tuple(NflNarrativeDriverAdapter(d) for d in NFL_NARRATIVE_DRIVERS)

    @property
    def pipeline_enabled(self) -> bool:
        return False

    def build_market_universe(self, settings: Settings, *, scan_limit: int | None = None) -> list[dict[str, Any]]:
        raise NotImplementedError("NFL weekly pipeline is not yet enabled")

    def search_players(self, query: str, *, limit: int = 10) -> list[dict[str, Any]]:
        return []

    def process_player(
        self,
        candidate: dict[str, Any],
        ebay_client: Any | None,
        settings: Settings,
        *,
        market_enabled: bool,
    ) -> tuple[Any, list[MarketSnapshot], str | None]:
        raise NotImplementedError("NFL player processing is not yet enabled")


class NflSportAdapter:
    @property
    def sport_code(self) -> str:
        return "FOOTBALL"

    @property
    def metadata(self) -> SportMetadata:
        return SportMetadata(
            sport="FOOTBALL",
            leagues=("NFL",),
            card_support=True,
            search_support=False,
        )

    def leagues(self) -> tuple[str, ...]:
        return ("NFL",)
