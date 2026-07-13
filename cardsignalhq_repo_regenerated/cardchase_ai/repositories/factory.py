"""Build generalized repository adapters from application settings."""

from __future__ import annotations

from cardchase_ai.config import Settings, get_settings
from cardchase_ai.nfl_storage import build_nfl_storage
from cardchase_ai.nba_storage import build_nba_storage
from cardchase_ai.performance_storage import build_performance_storage
from cardchase_ai.repositories.adapters import (
    MarketSnapshotRepositoryAdapter,
    PerformanceSnapshotRepositoryAdapter,
    PlayerRegistryRepositoryAdapter,
    RepositoryBundle,
    SignalDriverRepositoryAdapter,
    WeeklySnapshotRepositoryAdapter,
)
from cardchase_ai.weekly_intelligence import build_weekly_storage


def build_repository_bundle(settings: Settings | None = None) -> RepositoryBundle:
    settings = settings or get_settings()
    weekly_storage = build_weekly_storage(settings)
    nfl_storage = build_nfl_storage(settings)
    nba_storage = build_nba_storage(settings)
    perf_storage = build_performance_storage(settings)
    weekly = WeeklySnapshotRepositoryAdapter(weekly_storage)
    return RepositoryBundle(
        weekly=weekly,
        performance=PerformanceSnapshotRepositoryAdapter(nfl_storage, nba_storage, perf_storage),
        drivers=SignalDriverRepositoryAdapter(nfl_storage),
        market=MarketSnapshotRepositoryAdapter(weekly_storage),
        registry=PlayerRegistryRepositoryAdapter(nfl_storage),
    )
