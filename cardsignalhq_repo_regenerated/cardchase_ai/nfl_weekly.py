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
from cardchase_ai.weekly_scoring import derive_collector_score, derive_scarcity_score
from cardchase_ai.weekly_storage import WeeklyStorage

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
) -> list[dict[str, Any]]:
    identities = provider.fetch_player_universe(limit=limit)
    candidates = []
    for identity in identities:
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
    return candidates


def build_nfl_player_snapshot(
    output: PlayerPipelineOutput,
    run: WeeklyIntelligenceRun,
    period: ReportingPeriod,
    rank: int,
    storage: WeeklyStorage,
    nfl_storage: NFLStorage,
) -> PlayerWeeklySignalSnapshot:
    source_id = output.source_player_id or str(output.player_id)
    csp_id = cs_nfl_player_id(source_id)
    hotness = output.hotness

    collector, collector_evidence, collector_missing = derive_collector_score(output.market_snapshots)
    scarcity, scarcity_evidence, scarcity_missing = derive_scarcity_score(output.market_snapshots)

    recent_snap = nfl_storage.fetch_latest_snapshot_by_period(csp_id, "RECENT_3_GAMES")
    season_snap = nfl_storage.fetch_latest_snapshot_by_period(csp_id, "REGULAR_SEASON")
    drivers = nfl_storage.fetch_signal_drivers(csp_id)
    stored_phase = output.nfl_season_phase or "UNKNOWN"

    missing_inputs = list(dict.fromkeys(collector_missing + scarcity_missing))
    if recent_snap and recent_snap.missing_inputs:
        missing_inputs.extend(recent_snap.missing_inputs)
    if output.stats_7d.games == 0:
        missing_inputs.append("stats_recent")
    if not output.market_snapshots and run.market_snapshots_created == 0:
        missing_inputs.append("market_snapshots")

    performance = recent_snap.performance_score if recent_snap else hotness.performance_score
    market = hotness.market_score if output.market_snapshots else None

    from cardchase_ai.weekly_scoring import (
        compute_weekly_change,
        derive_conviction,
        derive_recommendation,
        derive_status,
        has_sufficient_evidence,
    )

    card_signal = None
    if performance is not None and has_sufficient_evidence(performance, market, missing_inputs):
        card_signal = round(0.55 * performance + 0.45 * (market or 0), 2)

    prior = storage.fetch_prior_official_player_snapshot(csp_id, run.league, period.year, period.week_number)
    prior_score = prior.card_signal_score if prior else None
    weekly_change = compute_weekly_change(card_signal, prior_score)

    conviction = derive_conviction(hotness.confidence_multiplier, len(missing_inputs))
    recommendation = derive_recommendation(hotness, collector) if card_signal is not None else None
    status = derive_status(hotness, None)

    evidence = build_nfl_scouting_evidence(
        nfl_season_phase=stored_phase,
        season=period.season,
        recent_snap=recent_snap,
        season_snap=season_snap,
        drivers=drivers,
        performance_reasons=hotness.reasons,
        collector_evidence=collector_evidence,
        scarcity_evidence=scarcity_evidence,
        confidence_multiplier=hotness.confidence_multiplier,
        tag=hotness.tag,
    )
    evidence["nfl_algorithm_version"] = NFL_PLAYER_SIGNAL_V1

    return PlayerWeeklySignalSnapshot(
        snapshot_id=str(uuid.uuid4()),
        run_id=run.run_id,
        cs_player_id=csp_id,
        source_player_id=source_id,
        league=run.league,
        sport="FOOTBALL",
        season=period.season,
        year=period.year,
        week_number=period.week_number,
        period_start=period.period_start,
        period_end=period.period_end,
        card_signal_score=card_signal,
        performance_score=performance,
        market_score=market,
        collector_score=collector,
        momentum_score=None,
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
            tag="RISING" if perf_score >= 65 else "WATCH",
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
