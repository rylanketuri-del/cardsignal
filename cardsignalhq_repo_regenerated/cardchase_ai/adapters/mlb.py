"""MLB league adapter — production implementation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from cardchase_ai.adapters.metadata import LeagueMetadata, RecentWindow, SeasonPhaseRules, SportMetadata
from cardchase_ai.clients.mlb import MLBClient
from cardchase_ai.config import Settings
from cardchase_ai.models.schemas import MarketSnapshot
from cardchase_ai.models.weekly import MLB_PLAYER_SIGNAL_V1
from cardchase_ai.signals.drivers import (
    MLB_CORE_DRIVERS,
    MLB_NARRATIVE_DRIVERS,
    build_hotness_from_drivers,
    run_signal_drivers,
)
from cardchase_ai.utils.normalize import summarize_market
from cardchase_ai.utils.reporting_period import ReportingPeriod, _build_reporting_period_direct
from cardchase_ai.utils.rolling import filter_last_n_days, summarize_hitter_window
from cardchase_ai.weekly_scoring import derive_momentum_score

from cardchase_ai.adapters.league_constants import (
    MLB_CARD_QUERY_LABELS,
    MLB_SEARCH_TEMPLATES,
    MLB_SUPPORTED_METRICS,
    MLB_SUPPORTED_POSITIONS,
)


DYNAMIC_CANDIDATE_LIMIT = 80
MARKET_SCAN_LIMIT = 45


class MlbSeasonAdapter:
    def resolve_season(self, settings: Settings, period_start: datetime) -> int:
        return settings.mlb_season

    def build_reporting_period(
        self,
        *,
        anchor: datetime | None = None,
        timezone_name: str,
        season: int | None = None,
    ) -> ReportingPeriod:
        return _build_reporting_period_direct(
            league="MLB",
            sport="MLB",
            anchor=anchor,
            timezone_name=timezone_name,
            season=season,
        )


class MlbPerformanceAdapter:
    def fetch_performance_windows(
        self,
        player_id: int,
        season: int,
        settings: Settings,
    ) -> tuple[Any, Any]:
        client = MLBClient()
        gamelog = client.get_hitter_gamelog(player_id, season)
        recent_days = 7
        stats_recent = summarize_hitter_window(filter_last_n_days(gamelog, recent_days))
        stats_baseline = summarize_hitter_window(filter_last_n_days(gamelog, 30))
        return stats_recent, stats_baseline

    def build_hotness_breakdown(
        self,
        player_name: str,
        stats_recent: Any,
        stats_baseline: Any,
        market_snapshots: dict[str, MarketSnapshot],
    ):
        return build_hotness_from_drivers(
            player_name=player_name,
            stats_7d=stats_recent,
            stats_30d=stats_baseline,
            market_snapshots=market_snapshots,
        )

    def derive_momentum(self, stats_recent: Any, stats_baseline: Any):
        return derive_momentum_score(stats_recent, stats_baseline)

    def recent_games_missing_key(self) -> str:
        return "stats_7d"


class MlbCardSignalAdapter:
    def search_templates(self) -> dict[str, str]:
        return dict(MLB_SEARCH_TEMPLATES)

    def query_labels(self) -> dict[str, str]:
        return dict(MLB_CARD_QUERY_LABELS)


class MlbPlayerSnapshotAdapter:
    def stat_specs(self) -> dict[str, Any]:
        return {
            "recent_label": "Last 7 Days",
            "baseline_label": "Season Snapshot",
            "metrics": list(MLB_SUPPORTED_METRICS),
        }

    def snapshot_labels(self) -> dict[str, str]:
        return {
            "recent": "Last 7 Days",
            "baseline": "Season Snapshot",
        }


class MlbCardReportAdapter:
    def card_metric_specs(self) -> dict[str, Any]:
        return {"labels": dict(MLB_CARD_QUERY_LABELS)}


class MlbNarrativeDriverAdapter:
    """Wraps narrative signal drivers for the LeagueAdapter contract."""

    def __init__(self, driver) -> None:
        self._driver = driver

    @property
    def driver_id(self) -> str:
        return self._driver.driver_id

    def generate(self, context: dict[str, Any]) -> list[str]:
        result = self._driver.compute(context)
        return result.reasons


class MlbLeagueAdapter:
    def __init__(self) -> None:
        self._season = MlbSeasonAdapter()
        self._performance = MlbPerformanceAdapter()
        self._card_signal = MlbCardSignalAdapter()
        self._player_snapshot = MlbPlayerSnapshotAdapter()
        self._card_report = MlbCardReportAdapter()
        self._mlb_client: MLBClient | None = None

    @property
    def league_code(self) -> str:
        return "MLB"

    @property
    def metadata(self) -> LeagueMetadata:
        return LeagueMetadata(
            sport="BASEBALL",
            league="MLB",
            timezone="America/New_York",
            recent_window=RecentWindow(kind="days", value=7),
            season_phases=SeasonPhaseRules(preseason=True, regular_season=True, postseason=True, offseason=True),
            supported_positions=MLB_SUPPORTED_POSITIONS,
            supported_metrics=MLB_SUPPORTED_METRICS,
            card_support=True,
            search_support=True,
            player_signal_algorithm_version=MLB_PLAYER_SIGNAL_V1,
            period_start_weekday=0,
            period_end_weekday=6,
            card_search_templates=MLB_SEARCH_TEMPLATES,
            card_query_labels=MLB_CARD_QUERY_LABELS,
        )

    @property
    def season(self) -> MlbSeasonAdapter:
        return self._season

    @property
    def performance(self) -> MlbPerformanceAdapter:
        return self._performance

    @property
    def card_signal(self) -> MlbCardSignalAdapter:
        return self._card_signal

    @property
    def player_snapshot(self) -> MlbPlayerSnapshotAdapter:
        return self._player_snapshot

    @property
    def card_report(self) -> MlbCardReportAdapter:
        return self._card_report

    @property
    def signal_drivers(self) -> tuple[MlbNarrativeDriverAdapter, ...]:
        return tuple(MlbNarrativeDriverAdapter(d) for d in MLB_NARRATIVE_DRIVERS)

    @property
    def pipeline_enabled(self) -> bool:
        return True

    def _client(self) -> MLBClient:
        if self._mlb_client is None:
            self._mlb_client = MLBClient()
        return self._mlb_client

    def build_market_universe(self, settings: Settings, *, scan_limit: int | None = None) -> list[dict[str, Any]]:
        mlb_client = self._client()
        candidate_limit = scan_limit or getattr(settings, "weekly_player_limit", None) or DYNAMIC_CANDIDATE_LIMIT
        market_limit = scan_limit or getattr(settings, "weekly_player_limit", None) or MARKET_SCAN_LIMIT
        universe: dict[int, dict] = {}

        try:
            dynamic_candidates = mlb_client.get_dynamic_hitter_candidates(
                season=settings.mlb_season,
                days=self.metadata.recent_window.value,
                limit=max(candidate_limit, DYNAMIC_CANDIDATE_LIMIT),
            )
            for candidate in dynamic_candidates:
                universe[int(candidate["player_id"])] = {
                    "player_id": int(candidate["player_id"]),
                    "player_name": candidate["player_name"],
                    "team": candidate.get("team") or "MLB",
                    "team_id": candidate.get("team_id"),
                    "position": candidate.get("position"),
                    "headshot_url": candidate.get("headshot_url"),
                    "team_logo_url": candidate.get("team_logo_url"),
                    "candidate_source": "dynamic",
                    "breakout_score": candidate.get("breakout_score", 0),
                }
        except Exception as error:
            print(f"Dynamic MLB candidate scan failed: {error}")

        for player_name in settings.tracked_players:
            try:
                player = mlb_client.search_player(player_name)
                existing = universe.get(int(player.player_id), {})
                universe[int(player.player_id)] = {
                    "player_id": int(player.player_id),
                    "player_name": player.full_name,
                    "team": existing.get("team") or "MLB",
                    "team_id": existing.get("team_id"),
                    "position": existing.get("position"),
                    "headshot_url": existing.get("headshot_url"),
                    "team_logo_url": existing.get("team_logo_url"),
                    "candidate_source": "manual",
                    "breakout_score": existing.get("breakout_score", 0),
                }
            except Exception as error:
                print(f"Manual tracked player lookup failed for {player_name}: {error}")

        candidates = list(universe.values())
        candidates.sort(
            key=lambda item: (
                item.get("breakout_score", 0),
                1 if item.get("candidate_source") == "manual" else 0,
            ),
            reverse=True,
        )
        return candidates[:market_limit]

    def search_players(self, query: str, *, limit: int = 10) -> list[dict[str, Any]]:
        return self._client().search_players(query, limit=limit)

    def process_player(
        self,
        candidate: dict[str, Any],
        ebay_client: Any | None,
        settings: Settings,
        *,
        market_enabled: bool,
    ) -> tuple[Any, list[MarketSnapshot], str | None]:
        from cardchase_ai.pipeline import PlayerPipelineOutput

        player_name = candidate["player_name"]
        player_id = int(candidate["player_id"])
        try:
            stats_7d, stats_30d = self._performance.fetch_performance_windows(
                player_id,
                settings.mlb_season,
                settings,
            )

            market_snapshots: dict[str, MarketSnapshot] = {}
            if market_enabled and ebay_client:
                for query_name, template in self._card_signal.search_templates().items():
                    payload = ebay_client.search_items(
                        template.format(player=player_name),
                        include_auctions=True,
                    )
                    listings = ebay_client.parse_listings(payload)
                    market_snapshots[query_name] = summarize_market(query_name, listings)

            driver_context = {
                "stats_7d": stats_7d,
                "stats_30d": stats_30d,
                "market_snapshots": market_snapshots,
                "candidate": candidate,
            }
            run_signal_drivers(MLB_CORE_DRIVERS, driver_context)

            hotness = self._performance.build_hotness_breakdown(
                player_name=player_name,
                stats_recent=stats_7d,
                stats_baseline=stats_30d,
                market_snapshots=market_snapshots,
            )

            output = PlayerPipelineOutput(
                player_name=player_name,
                player_id=player_id,
                stats_7d=stats_7d,
                stats_30d=stats_30d,
                market_snapshots=market_snapshots,
                hotness=hotness,
                team=candidate.get("team") or "MLB",
                team_id=candidate.get("team_id"),
                position=candidate.get("position"),
                headshot_url=candidate.get("headshot_url"),
                team_logo_url=candidate.get("team_logo_url"),
                sport="MLB",
                candidate_source=candidate.get("candidate_source", "dynamic"),
            )
            return output, list(market_snapshots.values()), None
        except Exception as error:
            return None, [], f"{player_name}: {error}"


class MlbSportAdapter:
    @property
    def sport_code(self) -> str:
        return "BASEBALL"

    @property
    def metadata(self) -> SportMetadata:
        return SportMetadata(
            sport="BASEBALL",
            leagues=("MLB",),
            card_support=True,
            search_support=True,
        )

    def leagues(self) -> tuple[str, ...]:
        return ("MLB",)
