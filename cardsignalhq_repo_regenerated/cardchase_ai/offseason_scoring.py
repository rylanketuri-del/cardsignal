"""Offseason scoring and evidence rules — prior season is context, not current momentum."""

from __future__ import annotations


def is_offseason_phase(season_phase: str | None) -> bool:
    return str(season_phase or "").upper() == "OFFSEASON"


def offseason_critical_evidence_requirements(league: str) -> frozenset[str]:
    """During offseason, recent games are not required when previous-season data exists."""
    from cardchase_ai.league_evidence import critical_evidence_requirements

    base = critical_evidence_requirements(league)
    return base - frozenset({"stats_recent", "stats_7d"})


def has_offseason_sufficient_evidence(
    league: str,
    performance: float | None,
    market: float | None,
    missing_inputs: list[str],
    *,
    has_previous_season: bool,
    season_phase: str | None,
) -> bool:
    """Evidence gate for offseason — previous season alone cannot satisfy recent-form requirements."""
    from cardchase_ai.league_evidence import has_sufficient_evidence

    if not is_offseason_phase(season_phase):
        return has_sufficient_evidence(league, performance, market, missing_inputs)

    if performance is None or market is None:
        return False

    if not has_previous_season:
        return False

    critical = offseason_critical_evidence_requirements(league)
    if critical.intersection(set(missing_inputs)):
        return False
    return True


def derive_offseason_recommendation(
    *,
    card_signal_score: float | None,
    has_recent_form: bool,
    has_market: bool,
    has_drivers: bool,
) -> str | None:
    """Previous-season stats alone cannot trigger a confident BUY."""
    if card_signal_score is None:
        return None
    if not has_market:
        return "WATCH"

    if not has_recent_form:
        if card_signal_score >= 80 and has_drivers:
            return "HOLD"
        return "WATCH"

    if card_signal_score >= 75:
        return "HOLD"
    if card_signal_score < 45:
        return "WATCH"
    return "WATCH"


def previous_season_label(league: str, season: int | None, *, stored_label: str | None = None) -> str:
    """Delegate to the centralized season-context helper (Season Performance labels)."""
    from cardchase_ai.season_context import format_season_performance_label

    return format_season_performance_label(league, season, stored_label=stored_label)


def offseason_driver_section_label() -> str:
    return "Offseason Signal Drivers"
