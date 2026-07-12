"""Weekly intelligence orchestration service."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from cardchase_ai.adapters import get_league_adapter
from cardchase_ai.clients.ebay import EbayClient
from cardchase_ai.config import Settings, get_settings
from cardchase_ai.models.schemas import MarketSnapshot
from cardchase_ai.models.weekly import (
    WEEKLY_INTELLIGENCE_V1,
    CardWeeklyIntelligenceSnapshot,
    PlayerWeeklySignalSnapshot,
    TodaysLeaderEntry,
    WeeklyHomepageIntelligence,
    WeeklyIntelligenceRun,
    WeeklyRunSummary,
    WeeklyTriggeredBy,
)
from cardchase_ai.pipeline import (
    PlayerPipelineOutput,
    _process_alerts,
    _write_outputs,
)
from cardchase_ai.market_movement import MarketSnapshotHistory
from cardchase_ai.models.market_movement import CardMarketMovement
from cardchase_ai.population import StageOutcome, get_population_provider, run_population_stage
from cardchase_ai.signal_of_week import select_signal_of_the_week
from cardchase_ai.storage import SupabaseStorage
from cardchase_ai.utils.reporting_period import (
    ReportingPeriod,
    next_scheduled_refresh,
)
from cardchase_ai.weekly_scoring import (
    card_intelligence_from_snapshot,
    compute_weekly_change,
    cs_card_id,
    cs_player_id,
    derive_collector_score,
    derive_conviction,
    derive_recommendation,
    derive_scarcity_score,
    derive_status,
    has_sufficient_evidence,
)
from cardchase_ai.weekly_storage import WeeklyJsonStorage, WeeklyStorage


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _sanitize_error(error: Exception, settings: Settings) -> str:
    message = f"{type(error).__name__}: {error}"
    for secret in (
        settings.ebay_token,
        settings.ebay_client_secret,
        settings.ebay_client_id,
        settings.supabase_service_role_key,
        settings.pipeline_trigger_token,
        settings.admin_api_token,
        settings.resend_api_key,
        settings.alert_webhook_bearer_token,
    ):
        if secret and secret in message:
            message = message.replace(secret, "[REDACTED]")
    return message[:500]


def _record_stage(
    stages: list[dict[str, Any]],
    outcomes: list[dict[str, Any]],
    name: str,
    status: StageOutcome,
    detail: str = "",
) -> None:
    entry = {"stage": name, "status": status, "detail": detail, "at": _utcnow().isoformat()}
    stages.append(entry)
    outcomes.append(entry)


def _stage_log(stages: list[dict[str, Any]], name: str, status: str, detail: str = "") -> None:
    stages.append({"stage": name, "status": status, "detail": detail, "at": _utcnow().isoformat()})


def build_weekly_storage(settings: Settings) -> WeeklyStorage:
    supabase = None
    if settings.supabase_url and settings.supabase_service_role_key:
        supabase = SupabaseStorage(settings.supabase_url, settings.supabase_service_role_key)
    json_store = WeeklyJsonStorage(settings.output_dir)
    return WeeklyStorage(supabase, json_store)


def _build_market_universe(mlb_client=None, settings=None, *, scan_limit: int | None = None, league: str = "MLB") -> list[dict[str, Any]]:
    """Backward-compatible shim — delegates to the registered league adapter."""
    settings = settings or get_settings()
    return get_league_adapter(league).build_market_universe(settings, scan_limit=scan_limit)


def process_player_for_weekly(
    candidate: dict[str, Any],
    mlb_client: Any,
    ebay_client: EbayClient | None,
    settings: Settings,
    *,
    market_enabled: bool,
    league: str = "MLB",
) -> tuple[PlayerPipelineOutput | None, list[MarketSnapshot], str | None]:
    """Process a player via the registered league adapter (mlb_client kept for test compatibility)."""
    adapter = get_league_adapter(league)
    return adapter.process_player(
        candidate,
        ebay_client,
        settings,
        market_enabled=market_enabled,
    )


def build_player_snapshot(
    output: PlayerPipelineOutput,
    run: WeeklyIntelligenceRun,
    period: ReportingPeriod,
    rank: int,
    storage: WeeklyStorage,
    league_adapter=None,
) -> PlayerWeeklySignalSnapshot:
    pid = str(output.player_id)
    csp_id = cs_player_id(pid, run.league)
    hotness = output.hotness
    adapter = league_adapter or get_league_adapter(run.league)

    collector, collector_evidence, collector_missing = derive_collector_score(output.market_snapshots)
    momentum, momentum_evidence, momentum_missing = adapter.performance.derive_momentum(
        output.stats_7d,
        output.stats_30d,
    )
    scarcity, scarcity_evidence, scarcity_missing = derive_scarcity_score(output.market_snapshots)

    driver_context = {
        "stats_7d": output.stats_7d,
        "stats_30d": output.stats_30d,
        "market_snapshots": output.market_snapshots,
        "candidate": {"player_name": output.player_name, "candidate_source": output.candidate_source},
    }
    narrative_signals: list[str] = []
    for narrative_driver in adapter.signal_drivers:
        narrative_signals.extend(narrative_driver.generate(driver_context))

    missing_inputs = list(dict.fromkeys(collector_missing + momentum_missing + scarcity_missing))
    if output.stats_7d.games == 0:
        missing_inputs.append(adapter.performance.recent_games_missing_key())
    if not output.market_snapshots and run.market_snapshots_created == 0:
        missing_inputs.append("market_snapshots")

    performance = hotness.performance_score
    market = hotness.market_score if output.market_snapshots else None
    card_signal = hotness.total_score if has_sufficient_evidence(performance, market, missing_inputs) else None

    prior = storage.fetch_prior_official_player_snapshot(csp_id, run.league, period.year, period.week_number)
    prior_score = prior.card_signal_score if prior else None
    weekly_change = compute_weekly_change(card_signal, prior_score)

    conviction = derive_conviction(hotness.confidence_multiplier, len(missing_inputs))
    recommendation = derive_recommendation(hotness, collector) if card_signal is not None else None
    status = derive_status(hotness, momentum)

    evidence = {
        "performance_reasons": hotness.reasons,
        "market_reasons": hotness.reasons,
        "collector_evidence": collector_evidence,
        "momentum_evidence": momentum_evidence,
        "scarcity_evidence": scarcity_evidence,
        "confidence_multiplier": hotness.confidence_multiplier,
        "tag": hotness.tag,
    }
    if narrative_signals:
        evidence["narrative_signals"] = narrative_signals

    return PlayerWeeklySignalSnapshot(
        snapshot_id=str(uuid.uuid4()),
        run_id=run.run_id,
        cs_player_id=csp_id,
        source_player_id=pid,
        league=run.league,
        sport=run.sport,
        season=period.season,
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
        missing_inputs=missing_inputs,
        algorithm_version=WEEKLY_INTELLIGENCE_V1,
        weekly_algorithm_version=WEEKLY_INTELLIGENCE_V1,
        scoring_algorithm_version=adapter.metadata.scoring_algorithm_version,
        captured_at=_utcnow(),
        player_name=output.player_name,
        team=output.team,
        position=output.position,
        headshot_url=output.headshot_url,
        team_logo_url=output.team_logo_url,
    )


def build_card_snapshots(
    output: PlayerPipelineOutput,
    run: WeeklyIntelligenceRun,
    period: ReportingPeriod,
    *,
    card_limit: int,
    league_adapter=None,
) -> list[CardWeeklyIntelligenceSnapshot]:
    snapshots: list[CardWeeklyIntelligenceSnapshot] = []
    pid = str(output.player_id)
    csp_id = cs_player_id(pid, run.league)
    adapter = league_adapter or get_league_adapter(run.league)
    query_labels = adapter.card_signal.query_labels()

    for query_name, snapshot in list(output.market_snapshots.items())[:card_limit]:
        intel = card_intelligence_from_snapshot(query_name, snapshot, output.player_name)
        snapshots.append(
            CardWeeklyIntelligenceSnapshot(
                snapshot_id=str(uuid.uuid4()),
                run_id=run.run_id,
                cs_card_id=cs_card_id(pid, query_name, run.league),
                cs_player_id=csp_id,
                league=run.league,
                year=period.year,
                week_number=period.week_number,
                period_start=period.period_start,
                period_end=period.period_end,
                card_signal_score=intel["card_signal_score"],
                recommendation=intel["recommendation"],
                conviction=intel["conviction"],
                risk=intel["risk"],
                time_horizon=intel["time_horizon"],
                market_activity_score=intel["market_activity_score"],
                demand_score=intel["demand_score"],
                momentum_score=intel["momentum_score"],
                scarcity_score=intel["scarcity_score"],
                evidence=intel["evidence"],
                missing_inputs=intel["missing_inputs"],
                algorithm_version=WEEKLY_INTELLIGENCE_V1,
                weekly_algorithm_version=WEEKLY_INTELLIGENCE_V1,
                scoring_algorithm_version=adapter.metadata.scoring_algorithm_version,
                captured_at=_utcnow(),
                card_label=query_labels.get(query_name, query_name),
                player_name=output.player_name,
            )
        )
    return snapshots


def build_homepage_card_sections(card_snapshots: list[CardWeeklyIntelligenceSnapshot]) -> dict[str, list[dict[str, Any]]]:
    scored = [c for c in card_snapshots if c.card_signal_score is not None]

    trending = sorted(scored, key=lambda c: (-(c.demand_score or 0), c.cs_card_id))[:5]
    movers = sorted(
        [c for c in scored if c.momentum_score is not None],
        key=lambda c: (-(c.momentum_score or 0), c.cs_card_id),
    )[:5]
    buy_low = sorted(
        [c for c in scored if c.recommendation == "BUY"],
        key=lambda c: (c.card_signal_score or 0, c.cs_card_id),
    )[:5]
    chased = sorted(scored, key=lambda c: (-(c.demand_score or 0), c.cs_card_id))[:5]

    def row(c: CardWeeklyIntelligenceSnapshot) -> dict[str, Any]:
        return {
            "cs_card_id": c.cs_card_id,
            "cs_player_id": c.cs_player_id,
            "player_name": c.player_name,
            "card_label": c.card_label,
            "score": c.card_signal_score,
            "recommendation": c.recommendation,
            "demand_score": c.demand_score,
            "market_activity_score": c.market_activity_score,
        }

    return {
        "trending_cards": [row(c) for c in trending],
        "biggest_movers": [row(c) for c in movers],
        "buy_low_watch": [row(c) for c in buy_low],
        "most_chased": [row(c) for c in chased],
    }


def build_data_quality_summary(snapshots: list[PlayerWeeklySignalSnapshot]) -> dict[str, Any]:
    total = len(snapshots)
    if total == 0:
        return {"total_players": 0, "sufficient_evidence": 0, "partial_evidence": 0, "insufficient_evidence": 0}

    sufficient = sum(
        1 for s in snapshots
        if has_sufficient_evidence(s.performance_score, s.market_score, s.missing_inputs)
    )
    partial = sum(
        1 for s in snapshots
        if s.card_signal_score is not None and not has_sufficient_evidence(s.performance_score, s.market_score, s.missing_inputs)
    )
    insufficient = total - sufficient - partial
    return {
        "total_players": total,
        "sufficient_evidence": sufficient,
        "partial_evidence": partial,
        "insufficient_evidence": insufficient,
        "sufficient_pct": round((sufficient / total) * 100, 1),
    }


def snapshots_to_leaderboard_entries(snapshots: list[PlayerWeeklySignalSnapshot]) -> list[TodaysLeaderEntry]:
    ranked = sorted(
        snapshots,
        key=lambda s: (-(s.card_signal_score or -1), s.rank or 999, s.cs_player_id),
    )
    leaders: list[TodaysLeaderEntry] = []
    for idx, snap in enumerate(ranked[:20], start=1):
        leaders.append(
            TodaysLeaderEntry(
                rank=idx,
                cs_player_id=snap.cs_player_id,
                source_player_id=snap.source_player_id,
                player_name=snap.player_name or snap.cs_player_id,
                score=snap.card_signal_score,
                performance=snap.performance_score,
                market=snap.market_score,
                collector=snap.collector_score,
                momentum=snap.momentum_score,
                recommendation=snap.recommendation,
                weekly_change=snap.weekly_change,
                status=snap.status,
                team=snap.team,
                position=snap.position,
                headshot_url=snap.headshot_url,
                team_logo_url=snap.team_logo_url,
            )
        )
    return leaders


def snapshots_to_legacy_leaderboard(snapshots: list[PlayerWeeklySignalSnapshot]) -> list[dict[str, Any]]:
    """Convert weekly snapshots to legacy leaderboard format for compatibility."""
    entries: list[dict[str, Any]] = []
    for snap in sorted(snapshots, key=lambda s: s.rank or 999)[:20]:
        entries.append(
            {
                "player_name": snap.player_name,
                "player_id": int(snap.source_player_id) if snap.source_player_id.isdigit() else snap.source_player_id,
                "rank": snap.rank,
                "team": snap.team,
                "position": snap.position,
                "headshot_url": snap.headshot_url,
                "team_logo_url": snap.team_logo_url,
                "hotness": {
                    "performance_score": snap.performance_score,
                    "market_score": snap.market_score,
                    "total_score": snap.card_signal_score,
                    "momentum_score": snap.momentum_score,
                    "collector_score": snap.collector_score,
                    "confidence_multiplier": 1.0,
                    "tag": snap.status or "WATCH",
                    "reasons": snap.evidence.get("performance_reasons", []),
                },
                "weekly_change": snap.weekly_change,
                "recommendation": snap.recommendation,
                "conviction": snap.conviction,
            }
        )
    return entries


def _finalize_failed_run(
    run: WeeklyIntelligenceRun,
    storage: WeeklyStorage,
    stages: list[dict[str, Any]],
    outcomes: list[dict[str, Any]],
    error: Exception,
    settings: Settings,
) -> WeeklyRunSummary:
    sanitized = _sanitize_error(error, settings)
    run.status = "FAILED"
    run.completed_at = _utcnow()
    run.errors.append(sanitized)
    run.stage_outcomes = outcomes
    _record_stage(stages, outcomes, "orchestration", "FAILED", sanitized)
    storage.update_run(run)
    return WeeklyRunSummary(run=run, stages=stages, homepage=None)


def _execute_weekly_pipeline(
    *,
    run: WeeklyIntelligenceRun,
    period: ReportingPeriod,
    league: str,
    player_limit: int,
    market_enabled: bool,
    population_enabled: bool,
    settings: Settings,
    storage: WeeklyStorage,
    processor: Callable,
    stages: list[dict[str, Any]],
    outcomes: list[dict[str, Any]],
) -> WeeklyRunSummary:
    league_adapter = get_league_adapter(league)
    if not league_adapter.pipeline_enabled:
        raise NotImplementedError(f"Weekly pipeline is not enabled for league {league}")

    ebay_client = None
    if market_enabled and settings.ebay_token:
        ebay_client = EbayClient(
            token=settings.ebay_token,
            marketplace_id=settings.ebay_marketplace_id,
            client_id=settings.ebay_client_id,
            client_secret=settings.ebay_client_secret,
        )
    elif market_enabled:
        run.warnings.append("Market enabled but eBay credentials missing; market snapshots skipped")
        market_enabled = False

    _record_stage(stages, outcomes, "player_universe", "COMPLETED", "building candidate universe")
    candidates = _build_market_universe(settings=settings, scan_limit=player_limit, league=league)[:player_limit]
    outcomes[-1]["detail"] = f"{len(candidates)} candidates"
    stages[-1]["detail"] = f"{len(candidates)} candidates"

    outputs: list[PlayerPipelineOutput] = []
    player_errors: list[str] = []

    _record_stage(stages, outcomes, "performance_scoring", "COMPLETED", "refresh started")
    for candidate in candidates:
        output, _, err = processor(
            candidate,
            None,
            ebay_client,
            settings,
            market_enabled=market_enabled,
        )
        if output:
            outputs.append(output)
        elif err:
            player_errors.append(err)
    outputs.sort(key=lambda item: item.hotness.total_score, reverse=True)
    run.players_processed = len(outputs)
    perf_status: StageOutcome = "PARTIAL" if player_errors and outputs else ("FAILED" if player_errors and not outputs else "COMPLETED")
    _record_stage(
        stages,
        outcomes,
        "performance_scoring",
        perf_status,
        f"{len(outputs)} ok, {len(player_errors)} errors",
    )

    market_count = sum(len(o.market_snapshots) for o in outputs)
    run.market_snapshots_created = market_count
    if not market_enabled:
        _record_stage(stages, outcomes, "market_snapshots", "SKIPPED", "market_enabled=false")
    elif market_count == 0:
        _record_stage(stages, outcomes, "market_snapshots", "UNAVAILABLE", "no market snapshots captured")
    else:
        _record_stage(stages, outcomes, "market_snapshots", "COMPLETED", f"{market_count} snapshots")

    market_history = MarketSnapshotHistory(settings.output_dir)
    market_movements: list[CardMarketMovement] = []
    captured_at = _utcnow()

    if not market_enabled or market_count == 0:
        _record_stage(stages, outcomes, "historical_movement", "SKIPPED", "no market snapshots to compare")
    else:
        movement_errors: list[str] = []
        for output in outputs:
            if not output.market_snapshots:
                continue
            try:
                movements = market_history.compute_movements_for_player(
                    run_id=run.run_id,
                    league=run.league,
                    year=period.year,
                    week_number=period.week_number,
                    source_player_id=str(output.player_id),
                    market_snapshots=output.market_snapshots,
                    captured_at=captured_at,
                )
                market_movements.extend(movements)
            except Exception as error:
                movement_errors.append(f"{output.player_name} movement: {error}")
        if movement_errors:
            run.warnings.extend(movement_errors[:10])
        if not market_movements:
            movement_status = "UNAVAILABLE"
        elif movement_errors:
            movement_status = "PARTIAL"
        else:
            movement_status = "COMPLETED"
        _record_stage(
            stages,
            outcomes,
            "historical_movement",
            movement_status,
            f"{len(market_movements)} movement records",
        )

    population_provider = get_population_provider(settings)
    population_result = run_population_stage(
        enabled=population_enabled,
        provider=population_provider,
        league=run.league,
        player_ids=[str(o.player_id) for o in outputs],
    )
    run.population_snapshots_created = population_result.snapshots_created
    run.warnings.extend(population_result.warnings)
    _record_stage(stages, outcomes, "population_snapshots", population_result.status, population_result.detail)

    player_snapshots: list[PlayerWeeklySignalSnapshot] = []
    card_snapshots: list[CardWeeklyIntelligenceSnapshot] = []
    card_errors: list[str] = []

    _record_stage(stages, outcomes, "card_intelligence", "COMPLETED", "building snapshots")
    for rank, output in enumerate(outputs, start=1):
        try:
            snap = build_player_snapshot(output, run, period, rank, storage, league_adapter=league_adapter)
            player_snapshots.append(snap)
        except Exception as error:
            player_errors.append(f"{output.player_name}: {error}")
            continue
        try:
            cards = build_card_snapshots(
                output,
                run,
                period,
                card_limit=settings.weekly_card_limit_per_player,
                league_adapter=league_adapter,
            )
            card_snapshots.extend(cards)
        except Exception as error:
            card_errors.append(f"{output.player_name} cards: {error}")

    run.cards_processed = len(card_snapshots)
    run.intelligence_records_created = len(player_snapshots) + len(card_snapshots)

    player_stage: StageOutcome = "PARTIAL" if player_errors and player_snapshots else ("FAILED" if player_errors and not player_snapshots else "COMPLETED")
    _record_stage(
        stages,
        outcomes,
        "weekly_player_snapshots",
        player_stage,
        f"{len(player_snapshots)} player snapshots",
    )
    card_stage: StageOutcome = "PARTIAL" if card_errors and card_snapshots else ("FAILED" if card_errors and not card_snapshots else "COMPLETED")
    _record_stage(
        stages,
        outcomes,
        "weekly_card_snapshots",
        card_stage,
        f"{len(card_snapshots)} card snapshots",
    )

    _record_stage(stages, outcomes, "rankings", "COMPLETED", "ranking today's leaders")
    signal = select_signal_of_the_week(player_snapshots, run.run_id)
    if signal:
        signal.selected_at = _utcnow()
    _record_stage(
        stages,
        outcomes,
        "signal_of_the_week",
        "COMPLETED" if signal else "UNAVAILABLE",
        signal.player_name if signal else "no qualifying player",
    )

    card_sections = build_homepage_card_sections(card_snapshots)
    leaders = snapshots_to_leaderboard_entries(player_snapshots)
    quality = build_data_quality_summary(player_snapshots)
    next_refresh = next_scheduled_refresh(
        league=league,
        timezone_name=settings.weekly_timezone,
        refresh_day=settings.weekly_refresh_day,
        refresh_hour=settings.weekly_refresh_hour,
    )

    homepage = WeeklyHomepageIntelligence(
        run=run,
        signal_of_the_week=signal,
        todays_leaders=leaders,
        trending_cards=card_sections["trending_cards"],
        biggest_movers=card_sections["biggest_movers"],
        buy_low_watch=card_sections["buy_low_watch"],
        most_chased=card_sections["most_chased"],
        next_refresh=next_refresh,
        data_quality_summary=quality,
    )
    _record_stage(stages, outcomes, "homepage_payload", "COMPLETED", "homepage assembled")

    _record_stage(stages, outcomes, "persist", "COMPLETED", "persist started")
    legacy_entries = snapshots_to_legacy_leaderboard(player_snapshots)
    if legacy_entries:
        file_path = _write_outputs(legacy_entries, settings.output_dir)
        if storage.uses_supabase and storage.supabase:
            try:
                run_id = storage.supabase.persist_leaderboard(str(file_path), legacy_entries)
                _process_alerts(storage.supabase, run_id, legacy_entries)
            except Exception as error:
                run.warnings.append(f"legacy leaderboard persist: {_sanitize_error(error, settings)}")

    all_errors = player_errors + card_errors
    run.errors.extend(all_errors[:20])
    if all_errors:
        run.warnings.append(f"{len(all_errors)} player/card-level errors")
    run.status = "PARTIAL" if all_errors else "COMPLETED"
    run.completed_at = _utcnow()
    run.stage_outcomes = outcomes
    storage.persist_run_results(
        run,
        player_snapshots,
        card_snapshots,
        signal,
        homepage,
        market_movements=market_movements,
    )
    storage.update_run(run)
    _record_stage(stages, outcomes, "persist", "COMPLETED", "persist finished")

    return WeeklyRunSummary(run=run, stages=stages, homepage=homepage)


def run_weekly_intelligence(
    *,
    league: str = "MLB",
    force: bool = False,
    triggered_by: WeeklyTriggeredBy = "manual",
    player_limit: int | None = None,
    market_enabled: bool | None = None,
    population_enabled: bool | None = None,
    settings: Settings | None = None,
    storage: WeeklyStorage | None = None,
    player_processor: Callable | None = None,
) -> WeeklyRunSummary:
    """Execute the full weekly intelligence pipeline."""
    settings = settings or get_settings()
    storage = storage or build_weekly_storage(settings)
    stages: list[dict[str, Any]] = []
    outcomes: list[dict[str, Any]] = []

    player_limit = min(player_limit or settings.weekly_player_limit, settings.weekly_player_limit)
    market_enabled = settings.weekly_market_enabled if market_enabled is None else market_enabled
    population_enabled = settings.weekly_population_enabled if population_enabled is None else population_enabled

    league_adapter = get_league_adapter(league)
    period = league_adapter.season.build_reporting_period(
        timezone_name=settings.weekly_timezone,
        settings=settings,
    )
    _record_stage(stages, outcomes, "determine_period", "COMPLETED", f"week {period.week_number}")

    if not force and triggered_by != "test":
        existing = storage.find_official_completed_run(league, period.year, period.week_number)
        if existing:
            _record_stage(stages, outcomes, "duplicate_guard", "SKIPPED", "official run already exists")
            skipped_run = WeeklyIntelligenceRun(
                run_id=existing.run_id,
                league=existing.league,
                sport=existing.sport,
                season=existing.season,
                year=existing.year,
                week_number=existing.week_number,
                period_start=existing.period_start,
                period_end=existing.period_end,
                status="SKIPPED",
                triggered_by=triggered_by,
                force=force,
                algorithm_version=WEEKLY_INTELLIGENCE_V1,
            )
            return WeeklyRunSummary(
                run=skipped_run,
                stages=stages,
                skipped_reason=f"Official weekly run already completed for {league} {period.year} W{period.week_number:02d}",
            )

    run = WeeklyIntelligenceRun(
        run_id=WeeklyStorage.new_run_id(),
        league=period.league,
        sport=period.sport,
        season=period.season,
        year=period.year,
        week_number=period.week_number,
        period_start=period.period_start,
        period_end=period.period_end,
        started_at=_utcnow(),
        status="RUNNING",
        triggered_by=triggered_by,
        force=force,
        algorithm_version=WEEKLY_INTELLIGENCE_V1,
        player_limit=player_limit,
        created_at=_utcnow(),
    )
    run = storage.create_run(run)
    _record_stage(stages, outcomes, "create_run", "COMPLETED", run.run_id)

    processor = player_processor
    if player_processor is None:
        def processor(candidate, _mlb, ebay, settings, *, market_enabled):  # type: ignore[no-redef]
            return process_player_for_weekly(
                candidate,
                _mlb,
                ebay,
                settings,
                market_enabled=market_enabled,
                league=league,
            )

    try:
        return _execute_weekly_pipeline(
            run=run,
            period=period,
            league=league,
            player_limit=player_limit,
            market_enabled=market_enabled,
            population_enabled=population_enabled,
            settings=settings,
            storage=storage,
            processor=processor,
            stages=stages,
            outcomes=outcomes,
        )
    except Exception as error:
        return _finalize_failed_run(run, storage, stages, outcomes, error, settings)


def build_latest_weekly_api_payload(league: str, storage: WeeklyStorage, settings: Settings) -> dict[str, Any]:
    """Build GET /api/weekly/latest response from stored data only."""
    payload = storage.fetch_latest_completed_payload(league)
    next_refresh = next_scheduled_refresh(
        league=league,
        timezone_name=settings.weekly_timezone,
        refresh_day=settings.weekly_refresh_day,
        refresh_hour=settings.weekly_refresh_hour,
    )

    if not payload:
        return {
            "run": None,
            "signal_of_the_week": None,
            "todays_leaders": [],
            "homepage": None,
            "next_refresh": next_refresh.isoformat(),
            "data_quality_summary": {},
            "card_intelligence": {
                "trending_cards": [],
                "biggest_movers": [],
                "buy_low_watch": [],
                "most_chased": [],
            },
        }

    run_data = payload.get("run")
    if hasattr(run_data, "model_dump"):
        run_dict = run_data.model_dump(mode="json")
    elif isinstance(run_data, dict):
        run_dict = run_data
    else:
        run_dict = None

    homepage = payload.get("homepage")
    if isinstance(homepage, dict):
        card_intel = {
            "trending_cards": homepage.get("trending_cards", []),
            "biggest_movers": homepage.get("biggest_movers", []),
            "buy_low_watch": homepage.get("buy_low_watch", []),
            "most_chased": homepage.get("most_chased", []),
        }
        quality = homepage.get("data_quality_summary", {})
        leaders = homepage.get("todays_leaders", [])
    else:
        player_snaps = payload.get("player_snapshots", [])
        card_snaps = payload.get("card_snapshots", [])
        sections = build_homepage_card_sections(
            [CardWeeklyIntelligenceSnapshot.model_validate(c) for c in card_snaps]
        ) if card_snaps else {"trending_cards": [], "biggest_movers": [], "buy_low_watch": [], "most_chased": []}
        card_intel = sections
        quality = build_data_quality_summary(
            [PlayerWeeklySignalSnapshot.model_validate(p) for p in player_snaps]
        ) if player_snaps else {}
        leaders = [
            TodaysLeaderEntry.model_validate(l).model_dump(mode="json")
            for l in snapshots_to_leaderboard_entries(
                [PlayerWeeklySignalSnapshot.model_validate(p) for p in player_snaps]
            )
        ] if player_snaps else []

    return {
        "run": run_dict,
        "signal_of_the_week": payload.get("signal_of_the_week"),
        "todays_leaders": leaders,
        "homepage": homepage,
        "next_refresh": next_refresh.isoformat(),
        "data_quality_summary": quality,
        "card_intelligence": card_intel,
    }
