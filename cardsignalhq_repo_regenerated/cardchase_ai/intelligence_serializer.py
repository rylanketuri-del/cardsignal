"""Serialize stored weekly snapshots into normalized PlayerIntelligencePayload."""

from __future__ import annotations

from typing import Any

from cardchase_ai.capabilities import declare_mlb_capabilities, declare_nfl_capabilities, declare_nba_capabilities
from cardchase_ai.models.intelligence import (
    CardIntelligenceSummary,
    EvidenceQuality,
    MarketMovementPayload,
    MarketSnapshotPayload,
    NormalizedPerformanceEvidence,
    PlayerIntelligencePayload,
    SignalDriverPayload,
)
from cardchase_ai.models.nfl import NFLSignalDriver
from cardchase_ai.models.weekly import CardWeeklyIntelligenceSnapshot, PlayerWeeklySignalSnapshot
from cardchase_ai.offseason_scoring import previous_season_label
from cardchase_ai.weekly_scoring import CARD_QUERY_LABELS, conviction_to_evidence


def _parse_evidence_list(items: list[Any] | None) -> list[NormalizedPerformanceEvidence]:
    if not items:
        return []
    result: list[NormalizedPerformanceEvidence] = []
    for item in items:
        if isinstance(item, NormalizedPerformanceEvidence):
            result.append(item)
        elif isinstance(item, dict):
            try:
                result.append(NormalizedPerformanceEvidence.model_validate(item))
            except Exception:
                continue
    return result


def _parse_drivers(items: list[Any] | None) -> list[SignalDriverPayload]:
    if not items:
        return []
    result: list[SignalDriverPayload] = []
    for item in items:
        if isinstance(item, SignalDriverPayload):
            result.append(item)
        elif isinstance(item, dict):
            try:
                result.append(SignalDriverPayload.model_validate(item))
            except Exception:
                continue
    return result


def _nfl_drivers_from_evidence(evidence: dict[str, Any]) -> list[SignalDriverPayload]:
    raw = evidence.get("nfl_signal_drivers") or evidence.get("signal_drivers") or []
    drivers: list[SignalDriverPayload] = []
    for item in raw:
        if isinstance(item, dict):
            try:
                nfl_driver = NFLSignalDriver.model_validate(item)
                drivers.append(SignalDriverPayload(
                    driver_type=nfl_driver.driver_type,
                    label=nfl_driver.label,
                    description=nfl_driver.description,
                    evidence=nfl_driver.evidence,
                    source_method=nfl_driver.source_method,
                    season_phase=nfl_driver.season_phase,
                    captured_at=nfl_driver.captured_at.isoformat() if nfl_driver.captured_at else None,
                ))
            except Exception:
                drivers.append(SignalDriverPayload.model_validate(item))
    return drivers


def _derive_data_confidence(missing: list[str], conviction: str | None) -> EvidenceQuality:
    if len(missing) >= 3:
        return "INSUFFICIENT"
    tier = conviction_to_evidence(conviction)
    if tier in {"HIGH", "MEDIUM", "LOW", "INSUFFICIENT"}:
        return tier  # type: ignore[return-value]
    return "LOW"


def serialize_card_snapshots(
    cards: list[CardWeeklyIntelligenceSnapshot],
    *,
    cs_player_id: str,
) -> CardIntelligenceSummary:
    player_cards = [c for c in cards if c.cs_player_id == cs_player_id]
    ranked = sorted(
        player_cards,
        key=lambda c: (-(c.card_signal_score or -1), c.cs_card_id),
    )
    missing: list[str] = []
    for card in ranked:
        missing.extend(card.missing_inputs)
    quality: EvidenceQuality = "INSUFFICIENT"
    if ranked and all(c.card_signal_score is not None for c in ranked[:1]):
        quality = "MEDIUM"
    if ranked and len(ranked) >= 2:
        quality = "HIGH"

    return CardIntelligenceSummary(
        ranked_cards=[c.model_dump(mode="json") for c in ranked],
        card_data_quality=quality,
        card_missing_inputs=list(dict.fromkeys(missing)),
    )


def serialize_player_intelligence(
    snapshot: PlayerWeeklySignalSnapshot,
    *,
    card_snapshots: list[CardWeeklyIntelligenceSnapshot] | None = None,
    market_movements: list[dict[str, Any]] | None = None,
    has_prior_weekly: bool = False,
    has_market_history: bool = False,
) -> PlayerIntelligencePayload:
    """Map a stored weekly player snapshot to the normalized intelligence contract."""
    league = snapshot.league.upper()
    evidence = snapshot.evidence or {}

    recent_perf = _parse_evidence_list(
        snapshot.recent_performance or evidence.get("recent_performance")
    )
    season_perf = _parse_evidence_list(
        snapshot.season_performance or evidence.get("season_performance")
    )
    prev_perf = _parse_evidence_list(
        snapshot.previous_season_performance or evidence.get("previous_season_performance")
    )

    drivers = _parse_drivers(snapshot.signal_drivers or evidence.get("signal_drivers"))
    if not drivers and league == "NFL":
        drivers = _nfl_drivers_from_evidence(evidence)

    if league == "MLB":
        capabilities = declare_mlb_capabilities(
            has_market_history=has_market_history,
            has_weekly_history=True,
        )
    elif league == "NBA":
        capabilities = declare_nba_capabilities(
            has_prior_weekly_snapshot=has_prior_weekly,
            has_market_history=has_market_history,
            has_import_data=bool(recent_perf or season_perf or prev_perf or drivers),
            has_previous_season=bool(prev_perf),
            season_phase=snapshot.season_phase or evidence.get("season_phase"),
        )
    else:
        capabilities = declare_nfl_capabilities(
            has_prior_weekly_snapshot=has_prior_weekly,
            has_market_history=has_market_history,
            has_import_data=bool(recent_perf or season_perf or prev_perf or drivers),
            has_previous_season=bool(prev_perf),
            season_phase=snapshot.season_phase or evidence.get("nfl_season_phase") or evidence.get("season_phase"),
        )

    market_snapshots: list[MarketSnapshotPayload] = []
    for key, label in CARD_QUERY_LABELS.items():
        snap_data = evidence.get("market_snapshots", {}).get(key) if isinstance(evidence.get("market_snapshots"), dict) else None
        if snap_data and isinstance(snap_data, dict):
            market_snapshots.append(MarketSnapshotPayload(
                query_name=key,
                listings_count=int(snap_data.get("listings_count", 0)),
                avg_price=snap_data.get("avg_price"),
                min_price=snap_data.get("min_price"),
                max_price=snap_data.get("max_price"),
                card_label=label,
            ))

    if league == "NFL":
        for key, label in {"rookie": "Rookie Cards"}.items():
            snap_data = evidence.get("market_snapshots", {}).get(key) if isinstance(evidence.get("market_snapshots"), dict) else None
            if snap_data and isinstance(snap_data, dict):
                market_snapshots.append(MarketSnapshotPayload(
                    query_name=key,
                    listings_count=int(snap_data.get("listings_count", 0)),
                    avg_price=snap_data.get("avg_price"),
                    card_label=label,
                ))

    movements: list[MarketMovementPayload] = []
    for mv in market_movements or evidence.get("market_movements") or []:
        if isinstance(mv, dict):
            movements.append(MarketMovementPayload(
                status=mv.get("status", "pending"),
                price_change_pct=mv.get("price_change_pct"),
                listings_change=mv.get("listings_change"),
                label=mv.get("label", "Movement pending"),
                query_name=mv.get("query_name"),
            ))

    card_summary = serialize_card_snapshots(card_snapshots or [], cs_player_id=snapshot.cs_player_id)
    perf_quality = snapshot.performance_data_quality or evidence.get("performance_data_quality") or "INSUFFICIENT"
    driver_quality = snapshot.driver_data_quality or evidence.get("driver_data_quality") or (
        "HIGH" if len(drivers) >= 2 else "MEDIUM" if drivers else "INSUFFICIENT"
    )

    evidence_tier = conviction_to_evidence(snapshot.conviction)
    data_confidence = snapshot.data_confidence or _derive_data_confidence(snapshot.missing_inputs, snapshot.conviction)

    prev_label = evidence.get("previous_season_label") or (
        previous_season_label(league, snapshot.season - 1 if snapshot.season else None)
        if prev_perf else None
    )
    prev_quality = evidence.get("previous_season_data_quality") or (
        prev_perf[0].quality if prev_perf else "INSUFFICIENT"
    )

    return PlayerIntelligencePayload(
        player_id=snapshot.source_player_id,
        source_player_id=snapshot.source_player_id,
        cs_player_id=snapshot.cs_player_id,
        sport=snapshot.sport,
        league=snapshot.league,
        player_name=snapshot.player_name,
        team=snapshot.team,
        position=snapshot.position,
        headshot_url=snapshot.headshot_url,
        team_logo_url=snapshot.team_logo_url,
        season=snapshot.season,
        season_phase=snapshot.season_phase or evidence.get("nfl_season_phase") or evidence.get("season_phase"),
        period_type=snapshot.period_type or evidence.get("period_type"),
        period_start=snapshot.period_start,
        period_end=snapshot.period_end,
        recent_window_label=snapshot.recent_window_label or evidence.get("recent_window_label"),
        card_signal_score=snapshot.card_signal_score,
        performance_score=snapshot.performance_score,
        market_score=snapshot.market_score,
        collector_score=snapshot.collector_score,
        momentum_score=snapshot.momentum_score,
        scarcity_score=snapshot.scarcity_score,
        news_score=snapshot.news_score,
        recommendation=snapshot.recommendation,
        evidence=evidence_tier,
        freshness=snapshot.freshness_summary,
        risk=evidence.get("risk"),
        time_horizon=evidence.get("time_horizon"),
        status=snapshot.status,
        recent_performance=recent_perf,
        season_performance=season_perf,
        previous_season_performance=prev_perf,
        previous_season_label=prev_label,
        previous_season_data_quality=prev_quality,
        performance_data_quality=perf_quality,
        performance_missing_inputs=snapshot.performance_missing_inputs or [],
        signal_drivers=drivers,
        driver_count=len(drivers),
        driver_data_quality=driver_quality,
        market_snapshot=market_snapshots,
        market_movement=movements,
        market_data_quality=snapshot.market_data_quality or ("MEDIUM" if market_snapshots else "INSUFFICIENT"),
        market_missing_inputs=snapshot.market_missing_inputs or [],
        card_intelligence_summary=card_summary,
        rank=snapshot.rank,
        weekly_change=snapshot.weekly_change,
        prior_score=snapshot.prior_score,
        snapshot_week=snapshot.week_number,
        official_weekly_snapshot=snapshot.official_weekly_snapshot,
        data_confidence=data_confidence,
        evidence_summary=snapshot.evidence_summary,
        freshness_summary=snapshot.freshness_summary,
        missing_inputs=snapshot.missing_inputs,
        weekly_algorithm_version=snapshot.weekly_algorithm_version or snapshot.algorithm_version,
        scoring_algorithm_version=snapshot.scoring_algorithm_version or snapshot.algorithm_version,
        performance_algorithm_version=snapshot.performance_algorithm_version or evidence.get("performance_algorithm_version"),
        card_algorithm_version=snapshot.card_algorithm_version or snapshot.algorithm_version,
        capabilities=capabilities,
        captured_at=snapshot.captured_at,
        updated_at=snapshot.captured_at,
        conviction=snapshot.conviction,
        league_evidence={k: v for k, v in evidence.items() if not k.startswith("_")},
    )


def payload_top_level_keys() -> list[str]:
    """Stable key list for contract tests."""
    return list(PlayerIntelligencePayload.model_fields.keys())
