"""League-specific critical evidence requirements for normalized gating."""

from __future__ import annotations


def is_offseason_phase(season_phase: str | None) -> bool:
    return str(season_phase or "").upper() == "OFFSEASON"


def critical_evidence_requirements(league: str) -> frozenset[str]:
    """Return league-owned missing-input keys that block sufficient evidence."""
    league_upper = league.upper()
    if league_upper == "MLB":
        return frozenset({"stats_7d", "market_snapshots", "listing_volume"})
    if league_upper == "NFL":
        return frozenset({"stats_recent", "market_snapshots", "listing_volume"})
    if league_upper == "NBA":
        return frozenset({"stats_recent", "market_snapshots", "listing_volume"})
    return frozenset({"market_snapshots", "listing_volume"})


def has_sufficient_evidence(
    league: str,
    performance: float | None,
    market: float | None,
    missing_inputs: list[str],
    *,
    season_phase: str | None = None,
    has_previous_season: bool = False,
) -> bool:
    """Normalized evidence gate with league-specific critical requirements."""
    if performance is None or market is None:
        return False

    if is_offseason_phase(season_phase) and has_previous_season:
        from cardchase_ai.offseason_scoring import offseason_critical_evidence_requirements
        critical = offseason_critical_evidence_requirements(league)
    else:
        critical = critical_evidence_requirements(league)

    if critical.intersection(set(missing_inputs)):
        return False
    return True


def insufficient_recommendation_fallback(league: str) -> tuple[str, str]:
    """Safe fallback when recent performance evidence is required but missing."""
    return "WATCH", "INSUFFICIENT"
