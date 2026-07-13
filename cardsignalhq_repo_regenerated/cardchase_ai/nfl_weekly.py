"""NFL weekly intelligence processing."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid

from cardchase_ai.clients.ebay import EbayClient
from cardchase_ai.clients.nfl_import import NFLPerformanceProvider
from cardchase_ai.config import Settings
from cardchase_ai.identity import cs_nfl_player_id
from cardchase_ai.models.nfl import NFL_PLAYER_SIGNAL_V1, map_nfl_position
from cardchase_ai.models.schemas import HitterHotnessBreakdown, MarketSnapshot, RollingHitterStats
from cardchase_ai.models.weekly import PlayerWeeklySignalSnapshot, WeeklyIntelligenceRun
from cardchase_ai.nfl_score import build_nfl_performance_snapshot
from cardchase_ai.nfl_scouting_mapper import build_nfl_scouting_evidence, resolve_nfl_season_phase
from cardchase_ai.nfl_season import nfl_season_phase
from cardchase_ai.nfl_signal_drivers import generate_nfl_signal_drivers
from cardchase_ai.nfl_storage import NFLStorage
from cardchase_ai.pipeline import PlayerPipelineOutput
from cardchase_ai.score import score_market
from cardchase_ai.utils.normalize import summarize_market
from cardchase_ai.utils.reporting_period import ReportingPeriod
from cardchase_ai.utils.nfl_rolling import aggregate_position_stats, select_recent_games
from cardchase_ai.weekly_scoring import (
    compute_weekly_change,
    derive_collector_score,
    derive_conviction,
    derive_momentum_from_prior_snapshots,
    derive_nfl_status,
    derive_recommendation,
    derive_scarcity_score,
    has_sufficient_evidence,
)
from cardchase_ai.weekly_storage import WeeklyStorage
from cardchase_ai.capabilities import declare_nfl_capabilities
from cardchase_ai.offseason_scoring import (
    derive_offseason_recommendation,
    has_offseason_sufficient_evidence,
    is_offseason_phase,
)
from cardchase_ai.season_context import (
    active_season_performance_label,
    resolve_offseason_season_context,
)
from cardchase_ai.performance_evidence import (
    build_nfl_performance_evidence,
    build_nfl_previous_season_evidence,
)
from cardchase_ai.performance_storage import PerformanceStorage, build_performance_storage
from cardchase_ai.nfl_season import recent_window_label as nfl_recent_label, should_show_recent_window

NFL_SEARCH_TEMPLATES = {
    "broad": '{player} football card',
    "rookie": '{player} rookie card football',
    "auto": '{player} autograph football card',
    "psa10": '{player} PSA 10 football card',
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _nfl_player_id_int(source_id: str) -> int:
    if source_id.isdigit():
        return int(source_id)
    return abs(hash(source_id)) % (10**9)


def _rolling_from_nfl(stats: dict[str, Any]) -> RollingHitterStats:
    return RollingHitterStats(games=int(stats.get("games_played", 0)))


def build_nfl_market_universe(
    provider: NFLPerformanceProvider,
    limit: int,
    *,
    performance_storage: PerformanceStorage | None = None,
) -> list[dict[str, Any]]:
    identities = provider.fetch_player_universe(limit=limit)
    candidates = []
    seen: set[str] = set()
    for identity in identities:
        seen.add(identity.source_player_id)
        candidates.append({
            "player_id": identity.source_player_id,
            "cs_player_id": identity.cs_player_id,
            "player_name": identity.player_name,
            "team": identity.team or "NFL",
            "team_id": identity.team_id,
            "position": identity.position,
            "position_group": identity.position_group,
            "headshot_url": identity.headshot_url,
            "team_logo_url": identity.team_logo_url,
            "candidate_source": "nfl_universe",
        })
    if performance_storage and len(candidates) < limit:
        for snap in performance_storage.list_league_snapshots("NFL")[:limit]:
            if snap.source_player_id in seen:
                continue
            seen.add(snap.source_player_id)
            candidates.append({
                "player_id": snap.source_player_id,
                "cs_player_id": snap.cs_player_id,
                "player_name": snap.player_name or f"NFL Player {snap.source_player_id}",
                "team": snap.team or "NFL",
                "team_id": None,
                "position": snap.position,
                "position_group": map_nfl_position(snap.position),
                "headshot_url": snap.headshot_url,
                "team_logo_url": snap.team_logo_url,
                "candidate_source": "previous_season_import",
            })
            if len(candidates) >= limit:
                break
    return candidates


def build_nfl_player_snapshot(
    output: PlayerPipelineOutput,
    run: WeeklyIntelligenceRun,
    period: ReportingPeriod,
    rank: int,
    storage: WeeklyStorage,
    nfl_storage: NFLStorage,
    *,
    performance_storage: PerformanceStorage | None = None,
) -> PlayerWeeklySignalSnapshot:
    source_id = output.source_player_id or str(output.player_id)
    csp_id = cs_nfl_player_id(source_id)
    hotness = output.hotness
    perf_store = performance_storage or build_performance_storage()

    collector, collector_evidence, collector_missing = derive_collector_score(output.market_snapshots)
    scarcity, scarcity_evidence, scarcity_missing = derive_scarcity_score(output.market_snapshots)

    recent_snap = nfl_storage.fetch_latest_snapshot_by_period(csp_id, "RECENT_3_GAMES")
    season_snap = nfl_storage.fetch_latest_snapshot_by_period(csp_id, "REGULAR_SEASON")
    stored_phase = output.nfl_season_phase or "UNKNOWN"
    offseason = is_offseason_phase(stored_phase)
    season_ctx = resolve_offseason_season_context(
        "NFL",
        csp_id,
        perf_store,
        preferred_season=period.season - 1 if offseason else None,
    )
    prev_season_snap = None
    if season_ctx.season is not None:
        prev_season_snap = perf_store.get_previous_season("NFL", csp_id, season_ctx.season)
    if prev_season_snap is None:
        prev_season_snap = perf_store.get_previous_season("NFL", csp_id, None)
        season_ctx = resolve_offseason_season_context("NFL", csp_id, perf_store)
    drivers = nfl_storage.fetch_signal_drivers(csp_id)

    missing_inputs = list(dict.fromkeys(collector_missing + scarcity_missing))
    if recent_snap and recent_snap.missing_inputs:
        missing_inputs.extend(recent_snap.missing_inputs)
    if output.stats_7d.games == 0:
        missing_inputs.append("stats_recent")
    if not output.market_snapshots and run.market_snapshots_created == 0:
        missing_inputs.append("market_snapshots")

    has_prev = prev_season_snap is not None
    if offseason and has_prev and "stats_recent" in missing_inputs:
        missing_inputs = [m for m in missing_inputs if m != "stats_recent"]

    performance = recent_snap.performance_score if recent_snap and not offseason else None
    if performance is None and has_prev and offseason:
        performance = hotness.performance_score
    market = hotness.market_score if output.market_snapshots else None

    card_signal = None
    if performance is not None and has_offseason_sufficient_evidence(
        run.league,
        performance,
        market,
        missing_inputs,
        has_previous_season=has_prev,
        season_phase=stored_phase,
    ):
        card_signal = round(0.55 * performance + 0.45 * (market or 0), 2)

    prior = storage.fetch_prior_official_player_snapshot(csp_id, run.league, period.year, period.week_number)
    prior_score = prior.card_signal_score if prior else None
    weekly_change = compute_weekly_change(card_signal, prior_score)

    momentum = None
    if prior is not None and not offseason:
        momentum = derive_momentum_from_prior_snapshots(
            performance,
            prior.performance_score,
        )

    conviction = derive_conviction(hotness.confidence_multiplier, len(missing_inputs))
    if offseason:
        recommendation = derive_offseason_recommendation(
            card_signal_score=card_signal,
            has_recent_form=bool(recent_snap and recent_snap.games_played > 0),
            has_market=bool(output.market_snapshots),
            has_drivers=bool(drivers),
        )
    else:
        recommendation = derive_recommendation(hotness, collector) if card_signal is not None else None
    status = derive_nfl_status(
        performance_score=performance,
        weekly_change=weekly_change,
        card_signal_score=card_signal,
        recommendation=recommendation,
    )

    recent_evidence = [] if offseason else build_nfl_performance_evidence(recent_snap)
    season_evidence = build_nfl_performance_evidence(season_snap)
    prev_evidence = build_nfl_previous_season_evidence(prev_season_snap)
    driver_payloads = [d.model_dump(mode="json") for d in drivers]
    perf_quality = prev_season_snap.data_quality if offseason and has_prev else (
        recent_snap.data_quality if recent_snap else "INSUFFICIENT"
    )
    driver_quality = "HIGH" if len(drivers) >= 2 else "MEDIUM" if drivers else "INSUFFICIENT"
    capabilities = declare_nfl_capabilities(
        has_prior_weekly_snapshot=prior is not None,
        has_market_history=False,
        has_import_data=bool(recent_snap or season_snap or has_prev),
        has_previous_season=has_prev,
        season_phase=stored_phase,
    )

    period_start_str = period.period_start.isoformat() if period.period_start else None
    period_end_str = period.period_end.isoformat() if period.period_end else None
    if offseason:
        window_label = season_ctx.display_label if has_prev else "Previous Season Performance"
        represented_season = season_ctx.season if season_ctx.season is not None else period.season
        helper_text = season_ctx.helper_text if has_prev else None
        source_snap_id = season_ctx.source_snapshot_id
        prev_label = season_ctx.display_label if has_prev else "Previous Season Performance"
        season_label_value = season_ctx.season_label
        season_perf_label = prev_label
    else:
        window_label = nfl_recent_label(stored_phase) if isinstance(stored_phase, str) else "Recent 3 Games"
        represented_season = period.season
        helper_text = None
        source_snap_id = season_ctx.source_snapshot_id if has_prev else None
        prev_label = season_ctx.display_label if has_prev else None
        season_label_value = str(represented_season)
        season_perf_label = active_season_performance_label("NFL", period.season)

    evidence = build_nfl_scouting_evidence(
        nfl_season_phase=stored_phase,
        season=represented_season,
        recent_snap=recent_snap if should_show_recent_window(stored_phase) else None,
        season_snap=season_snap,
        drivers=drivers,
        performance_reasons=hotness.reasons,
        collector_evidence=collector_evidence,
        scarcity_evidence=scarcity_evidence,
        confidence_multiplier=hotness.confidence_multiplier,
        tag=status,
    )
    evidence["nfl_algorithm_version"] = NFL_PLAYER_SIGNAL_V1
    evidence["recent_performance"] = [e.model_dump(mode="json") for e in recent_evidence]
    evidence["season_performance"] = [e.model_dump(mode="json") for e in season_evidence]
    evidence["previous_season_performance"] = [e.model_dump(mode="json") for e in prev_evidence]
    evidence["previous_season_label"] = prev_label
    evidence["previous_season_helper_text"] = helper_text
    evidence["previous_season_source_snapshot_id"] = source_snap_id
    evidence["season_label"] = season_label_value
    evidence["season_performance_label"] = season_perf_label
    evidence["signal_drivers"] = driver_payloads
    evidence["performance_data_quality"] = perf_quality
    evidence["previous_season_data_quality"] = prev_season_snap.data_quality if prev_season_snap else "INSUFFICIENT"
    evidence["driver_data_quality"] = driver_quality
    evidence["season_phase"] = stored_phase
    evidence["recent_window_label"] = window_label
    evidence["period_type"] = "PREVIOUS_SEASON" if offseason else "RECENT_3_GAMES"
    evidence["performance_algorithm_version"] = NFL_PLAYER_SIGNAL_V1
    evidence["market_snapshots"] = {
        k: v.model_dump(mode="json") if hasattr(v, "model_dump") else v
        for k, v in output.market_snapshots.items()
    }

    market_missing = [m for m in missing_inputs if m in {"market_snapshots", "listing_volume"}]
    performance_missing = [m for m in missing_inputs if m.startswith("stats")]

    return PlayerWeeklySignalSnapshot(
        snapshot_id=str(uuid.uuid4()),
        run_id=run.run_id,
        cs_player_id=csp_id,
        source_player_id=source_id,
        league=run.league,
        sport="FOOTBALL",
        season=represented_season,
        year=period.year,
        week_number=period.week_number,
        period_start=period.period_start,
        period_end=period.period_end,
        card_signal_score=card_signal,
        performance_score=performance,
        market_score=market,
        collector_score=collector,
        momentum_score=momentum,
        scarcity_score=scarcity,
        news_score=None,
        recommendation=recommendation,
        conviction=conviction,
        status=status,
        weekly_change=weekly_change,
        rank=rank,
        evidence=evidence,
        missing_inputs=list(dict.fromkeys(missing_inputs)),
        algorithm_version=NFL_PLAYER_SIGNAL_V1,
        captured_at=_utcnow(),
        player_name=output.player_name,
        team=output.team,
        position=output.position,
        headshot_url=output.headshot_url,
        team_logo_url=output.team_logo_url,
        season_phase=stored_phase,
        period_type="PREVIOUS_SEASON" if offseason else "RECENT_3_GAMES",
        recent_window_label=window_label,
        signal_drivers=driver_payloads,
        recent_performance=[e.model_dump(mode="json") for e in recent_evidence],
        season_performance=[e.model_dump(mode="json") for e in season_evidence],
        previous_season_performance=[e.model_dump(mode="json") for e in prev_evidence],
        performance_data_quality=perf_quality,
        performance_missing_inputs=performance_missing,
        market_data_quality="MEDIUM" if output.market_snapshots else "INSUFFICIENT",
        market_missing_inputs=market_missing,
        driver_data_quality=driver_quality,
        capabilities=capabilities,
        weekly_algorithm_version=NFL_PLAYER_SIGNAL_V1,
        scoring_algorithm_version=NFL_PLAYER_SIGNAL_V1,
        performance_algorithm_version=NFL_PLAYER_SIGNAL_V1,
        card_algorithm_version=NFL_PLAYER_SIGNAL_V1,
        prior_score=prior_score,
        official_weekly_snapshot=True,
        data_confidence="INSUFFICIENT" if offseason and not has_prev else perf_quality,
        evidence_summary=f"{len(drivers)} NFL signal drivers from stored evidence",
        freshness_summary=period_end_str,
    )


def process_player_for_nfl_weekly(
    candidate: dict[str, Any],
    provider: NFLPerformanceProvider,
    ebay_client: EbayClient | None,
    settings: Settings,
    *,
    market_enabled: bool,
    nfl_storage: NFLStorage,
) -> tuple[PlayerPipelineOutput | None, list[MarketSnapshot], str | None]:
    player_name = candidate["player_name"]
    source_id = str(candidate["player_id"])
    position_group = map_nfl_position(candidate.get("position"))
    season = settings.nfl_season

    try:
        all_games = provider.fetch_recent_games(source_id, limit=20)
        season_stats = provider.fetch_season_stats(source_id, season)
        recent_games = select_recent_games(all_games, limit=3)
        recent_stats = aggregate_position_stats(position_group, recent_games)
        season_phase = resolve_nfl_season_phase(
            active_status=candidate.get("active_status"),
            computed_phase=nfl_season_phase(has_active_season_games=bool(recent_games)),
        )

        cs_id = cs_nfl_player_id(source_id)
        recent_snapshot = build_nfl_performance_snapshot(
            cs_player_id=cs_id,
            source_player_id=source_id,
            season=season,
            position=candidate.get("position"),
            position_group=position_group,
            period_type="RECENT_3_GAMES",
            games=all_games,
            season_stats=season_stats,
            source_method=provider.source_method,
        )
        season_snapshot = build_nfl_performance_snapshot(
            cs_player_id=cs_id,
            source_player_id=source_id,
            season=season,
            position=candidate.get("position"),
            position_group=position_group,
            period_type="REGULAR_SEASON",
            games=all_games,
            season_stats=season_stats,
            source_method=provider.source_method,
        )
        nfl_storage.append_snapshot(recent_snapshot)
        nfl_storage.append_snapshot(season_snapshot)

        developments = []
        data = getattr(provider, "_load", lambda: None)()
        if data:
            dev_map = data.get("developments") or {}
            developments = dev_map.get(source_id) or []

        drivers = generate_nfl_signal_drivers(
            recent_stats=recent_stats,
            season_stats=season_stats,
            position_group=position_group,
            developments=developments,
            season_phase=season_phase,
            source_method=provider.source_method,
        )
        if drivers:
            nfl_storage.save_signal_drivers(cs_id, drivers)
        else:
            # Preserve verified stored offseason drivers when generation yields none
            stored_drivers = nfl_storage.fetch_signal_drivers(cs_id)
            if stored_drivers:
                drivers = stored_drivers
            else:
                nfl_storage.save_signal_drivers(cs_id, drivers)

        market_snapshots: dict[str, MarketSnapshot] = {}
        if market_enabled and ebay_client:
            for query_name, template in NFL_SEARCH_TEMPLATES.items():
                payload = ebay_client.search_items(
                    template.format(player=player_name),
                    include_auctions=True,
                )
                listings = ebay_client.parse_listings(payload)
                market_snapshots[query_name] = summarize_market(query_name, listings)

        stats_recent = _rolling_from_nfl(recent_stats)
        stats_season = _rolling_from_nfl(season_stats or recent_stats)

        perf_score = recent_snapshot.performance_score or 0.0
        market_score, market_reasons = score_market(market_snapshots)

        hotness = HitterHotnessBreakdown(
            player_name=player_name,
            performance_score=perf_score,
            market_score=market_score,
            total_score=round(0.55 * perf_score + 0.45 * market_score, 2) if perf_score else round(market_score * 0.45, 2),
            confidence_multiplier=0.9 if recent_snapshot.data_quality == "LOW" else 1.0,
            tag="WATCH",
            reasons=(list(recent_snapshot.normalized_metrics.keys()) if recent_snapshot.normalized_metrics else []) + market_reasons,
        )

        output = PlayerPipelineOutput(
            player_name=player_name,
            player_id=_nfl_player_id_int(source_id),
            source_player_id=source_id,
            nfl_season_phase=season_phase,
            stats_7d=stats_recent,
            stats_30d=stats_season,
            market_snapshots=market_snapshots,
            hotness=hotness,
            team=candidate.get("team") or "NFL",
            team_id=int(candidate["team_id"]) if candidate.get("team_id") and str(candidate["team_id"]).isdigit() else None,
            position=candidate.get("position"),
            headshot_url=candidate.get("headshot_url"),
            team_logo_url=candidate.get("team_logo_url"),
            sport="FOOTBALL",
            candidate_source=candidate.get("candidate_source", "nfl_universe"),
        )

        return output, list(market_snapshots.values()), None
    except Exception as error:
        return None, [], f"{player_name}: {error}"
