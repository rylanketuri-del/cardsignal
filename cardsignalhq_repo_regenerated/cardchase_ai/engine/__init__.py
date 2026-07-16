"""Sport-agnostic CardSignal engine package."""

from cardchase_ai.engine.cardsignal_engine import (
    CardSignalConfig,
    CardSignalEngineInput,
    CardSignalEngineResult,
    compute_cardsignal,
)
from cardchase_ai.engine.season_phase import (
    EngineSeasonPhase,
    PerformanceWindow,
    in_season_tuesday_window,
    resolve_engine_season_phase,
    season_phase_for_league,
)

__all__ = [
    "CardSignalConfig",
    "CardSignalEngineInput",
    "CardSignalEngineResult",
    "compute_cardsignal",
    "EngineSeasonPhase",
    "PerformanceWindow",
    "in_season_tuesday_window",
    "resolve_engine_season_phase",
    "season_phase_for_league",
]
