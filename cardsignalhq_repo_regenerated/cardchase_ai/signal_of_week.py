"""Deterministic Signal of the Week selection."""

from __future__ import annotations

from cardchase_ai.models.weekly import PlayerWeeklySignalSnapshot, SignalOfTheWeek, WEEKLY_INTELLIGENCE_V1
from cardchase_ai.weekly_scoring import has_sufficient_evidence


def select_signal_of_the_week(
    snapshots: list[PlayerWeeklySignalSnapshot],
    run_id: str,
) -> SignalOfTheWeek | None:
    """Select Signal of the Week from player snapshots with sufficient evidence."""
    candidates: list[tuple[tuple, PlayerWeeklySignalSnapshot]] = []

    for snap in snapshots:
        if snap.card_signal_score is None:
            continue
        if not has_sufficient_evidence(
            snap.performance_score,
            snap.market_score,
            snap.missing_inputs,
            league=snap.league,
        ):
            continue
        if snap.recommendation is None:
            continue

        evidence_quality = len(snap.evidence) - len(snap.missing_inputs)
        weekly_move = snap.weekly_change if snap.weekly_change is not None else float("-inf")

        # Sort key: score desc, evidence quality desc, weekly_change desc, cs_player_id asc (deterministic tie-break)
        sort_key = (
            -snap.card_signal_score,
            -evidence_quality,
            -weekly_move if weekly_move != float("-inf") else float("-inf"),
            snap.cs_player_id,
        )
        candidates.append((sort_key, snap))

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0])
    _, winner = candidates[0]

    reason_parts = []
    if winner.card_signal_score is not None:
        reason_parts.append(f"CardSignal Score {winner.card_signal_score:.1f}")
    if winner.weekly_change is not None and winner.weekly_change > 0:
        reason_parts.append(f"weekly gain of +{winner.weekly_change:.1f}")
    if winner.status:
        reason_parts.append(f"status {winner.status}")
    if winner.evidence.get("performance_reasons"):
        reason_parts.append("strong performance evidence")
    if winner.evidence.get("market_reasons"):
        reason_parts.append("confirmed market activity")

    reason = "; ".join(reason_parts) if reason_parts else "Top qualified signal with complete evidence."

    return SignalOfTheWeek(
        run_id=run_id,
        cs_player_id=winner.cs_player_id,
        source_player_id=winner.source_player_id,
        player_name=winner.player_name or winner.cs_player_id,
        rank=winner.rank,
        score=winner.card_signal_score,
        weekly_change=winner.weekly_change,
        recommendation=winner.recommendation,
        conviction=winner.conviction,
        status=winner.status,
        reason=reason,
        evidence={
            "performance_score": winner.performance_score,
            "market_score": winner.market_score,
            "collector_score": winner.collector_score,
            "momentum_score": winner.momentum_score,
            "missing_inputs": winner.missing_inputs,
            "evidence_keys": list(winner.evidence.keys()),
        },
        algorithm_version=WEEKLY_INTELLIGENCE_V1,
        headshot_url=winner.headshot_url,
        team=winner.team,
        position=winner.position,
        team_logo_url=winner.team_logo_url,
    )
