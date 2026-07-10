"""Optional PSA population stage interface for weekly orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol

StageOutcome = Literal["COMPLETED", "PARTIAL", "FAILED", "SKIPPED", "UNAVAILABLE"]


@dataclass
class PopulationStageResult:
    status: StageOutcome
    snapshots_created: int = 0
    warnings: list[str] = field(default_factory=list)
    detail: str = ""


class PopulationProvider(Protocol):
    """Interface for future PSA population integrations."""

    def is_configured(self) -> bool:
        ...

    def refresh_population_snapshots(self, *, league: str, player_ids: list[str]) -> int:
        ...


def run_population_stage(
    *,
    enabled: bool,
    provider: PopulationProvider | None,
    league: str,
    player_ids: list[str],
) -> PopulationStageResult:
    if not enabled:
        return PopulationStageResult(status="SKIPPED", detail="population_enabled=false")

    if provider is None or not provider.is_configured():
        return PopulationStageResult(
            status="UNAVAILABLE",
            detail="No PSA population provider configured",
            warnings=["PSA population provider is not configured; stage skipped"],
        )

    try:
        created = provider.refresh_population_snapshots(league=league, player_ids=player_ids)
        return PopulationStageResult(
            status="COMPLETED",
            snapshots_created=created,
            detail=f"{created} population snapshots created",
        )
    except Exception as error:
        return PopulationStageResult(
            status="PARTIAL",
            warnings=[f"population stage error: {error}"],
            detail="population provider failed",
        )


def get_population_provider(settings) -> PopulationProvider | None:
    """Return a configured provider when one exists; currently none in this branch."""
    _ = settings
    return None
