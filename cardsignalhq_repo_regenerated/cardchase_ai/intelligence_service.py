"""Canonical normalized intelligence read service — stored data only."""

from __future__ import annotations

from typing import Any

from cardchase_ai.identity import normalize_api_player_id
from cardchase_ai.intelligence_serializer import serialize_player_intelligence
from cardchase_ai.league_evidence import has_sufficient_evidence, insufficient_recommendation_fallback
from cardchase_ai.models.intelligence import PlayerIntelligencePayload
from cardchase_ai.models.weekly import PlayerWeeklySignalSnapshot, TodaysLeaderEntry
from cardchase_ai.repositories.adapters import RepositoryBundle


def resolve_cs_player_id(league: str, player_id: str) -> str:
    if player_id.startswith("CS-NFL-P-") or player_id.startswith("CS-NBA-P-") or ":" in player_id:
        return player_id
    return normalize_api_player_id(player_id, league.upper())


def _apply_legacy_compatibility(snapshot: PlayerWeeklySignalSnapshot) -> PlayerWeeklySignalSnapshot:
    """Map older stored records into normalized snapshot fields without rewriting history."""
    evidence = dict(snapshot.evidence or {})
    updates: dict[str, Any] = {}

    if not snapshot.recent_performance and evidence.get("recent_performance"):
        updates["recent_performance"] = evidence["recent_performance"]
    if not snapshot.season_performance and evidence.get("season_performance"):
        updates["season_performance"] = evidence["season_performance"]
    if not snapshot.signal_drivers:
        drivers = evidence.get("signal_drivers") or evidence.get("nfl_signal_drivers")
        if drivers:
            updates["signal_drivers"] = drivers
    if not snapshot.capabilities and evidence.get("capabilities"):
        updates["capabilities"] = evidence["capabilities"]
    if not snapshot.season_phase:
        phase = evidence.get("season_phase") or evidence.get("nfl_season_phase")
        if phase:
            updates["season_phase"] = phase
    if not snapshot.recent_window_label and evidence.get("recent_window_label"):
        updates["recent_window_label"] = evidence["recent_window_label"]

    if updates:
        return snapshot.model_copy(update=updates)
    return snapshot


def _finalize_payload(payload: PlayerIntelligencePayload, league: str) -> PlayerIntelligencePayload:
    """Apply league evidence rules to recommendation/evidence without changing scores."""
    if has_sufficient_evidence(
        league,
        payload.performance_score,
        payload.market_score,
        payload.missing_inputs,
    ):
        return payload

    watch, insufficient = insufficient_recommendation_fallback(league)
    return payload.model_copy(
        update={
            "recommendation": watch,
            "evidence": insufficient,
            "data_confidence": "INSUFFICIENT",
        }
    )


def build_normalized_leader_rows(
    league: str,
    snapshots: list[PlayerWeeklySignalSnapshot],
    repos: RepositoryBundle,
) -> list[dict[str, Any]]:
    """Batch-build homepage leader rows from normalized intelligence."""
    payloads = batch_get_player_intelligence(league, snapshots, repos)
    ranked = sorted(
        payloads,
        key=lambda p: (-(p.card_signal_score or -1), p.rank or 999, p.cs_player_id),
    )
    return [intelligence_to_leader_entry(payload, idx) for idx, payload in enumerate(ranked[:20], start=1)]


def get_player_intelligence(
    league: str,
    player_id: str,
    repos: RepositoryBundle,
) -> PlayerIntelligencePayload | None:
    """Read and assemble normalized player intelligence from generalized repositories."""
    league_upper = league.upper()
    cs_id = resolve_cs_player_id(league_upper, player_id)
    snapshot = repos.weekly.get_latest_player_snapshot(league_upper, cs_id)
    if not snapshot:
        return None

    snapshot = _apply_legacy_compatibility(snapshot)
    history = repos.weekly.get_player_weekly_history(league_upper, cs_id, limit=12)
    has_prior = len(history) >= 2
    cards = repos.weekly.get_card_snapshots_for_player(league_upper, cs_id)
    market = repos.market.get_latest_player_market(league_upper, cs_id)
    movements = (snapshot.evidence or {}).get("market_movements")
    has_market_history = bool(movements or repos.market.get_player_market_history(league_upper, cs_id, limit=2))

    payload = serialize_player_intelligence(
        snapshot,
        card_snapshots=cards,
        market_movements=movements,
        has_prior_weekly=has_prior,
        has_market_history=has_market_history,
    )
    return _finalize_payload(payload, league_upper)


def batch_get_player_intelligence(
    league: str,
    snapshots: list[PlayerWeeklySignalSnapshot],
    repos: RepositoryBundle,
) -> list[PlayerIntelligencePayload]:
    """Batch-normalize persisted weekly snapshots for homepage surfaces."""
    league_upper = league.upper()
    payloads: list[PlayerIntelligencePayload] = []
    for snapshot in snapshots:
        if snapshot.league.upper() != league_upper:
            continue
        compatible = _apply_legacy_compatibility(snapshot)
        cards = repos.weekly.get_card_snapshots_for_player(league_upper, snapshot.cs_player_id)
        movements = (compatible.evidence or {}).get("market_movements")
        history = repos.weekly.get_player_weekly_history(league_upper, snapshot.cs_player_id, limit=12)
        payload = serialize_player_intelligence(
            compatible,
            card_snapshots=cards,
            market_movements=movements,
            has_prior_weekly=len(history) >= 2,
            has_market_history=bool(movements),
        )
        payloads.append(_finalize_payload(payload, league_upper))
    return payloads


def intelligence_to_leader_entry(payload: PlayerIntelligencePayload, rank: int) -> dict[str, Any]:
    """Derive homepage leader presentation from normalized intelligence."""
    leader = TodaysLeaderEntry(
        rank=rank,
        cs_player_id=payload.cs_player_id,
        source_player_id=payload.source_player_id,
        player_name=payload.player_name or payload.cs_player_id,
        score=payload.card_signal_score,
        performance=payload.performance_score,
        market=payload.market_score,
        collector=payload.collector_score,
        momentum=payload.momentum_score,
        recommendation=payload.recommendation,
        weekly_change=payload.weekly_change,
        status=payload.status,
        team=payload.team,
        position=payload.position,
        headshot_url=payload.headshot_url,
        team_logo_url=payload.team_logo_url,
    )
    data = leader.model_dump(mode="json")
    data["league"] = payload.league
    data["sport"] = payload.sport
    data["capabilities"] = payload.capabilities
    data["intelligence"] = payload.model_dump(mode="json")
    return data


def get_player_intelligence_payload(
    league: str,
    player_id: str,
    repos: RepositoryBundle,
) -> dict[str, Any] | None:
    payload = get_player_intelligence(league, player_id, repos)
    if not payload:
        return None
    return payload.model_dump(mode="json")
