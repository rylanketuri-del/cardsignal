"""Shared weekly intelligence pipeline for NFL and NBA.

Workflow:
  1. determine season phase (IN_SEASON / OFFSEASON / PRESEASON)
  2. if IN_SEASON → previous Tuesday → current Tuesday window
  3. if OFFSEASON → completed previous season performance baseline
  4. fetch market
  5. calculate CardSignal (shared engine)
  6. write official weekly snapshot
  7. persist to Supabase

Only the data provider changes between NFL and NBA.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Literal

from cardchase_ai.clients.ebay import EbayClient
from cardchase_ai.config import Settings, get_settings
from cardchase_ai.engine.season_phase import (
    in_season_tuesday_window,
    resolve_engine_season_phase,
    season_phase_for_league,
    uses_previous_season_baseline,
)
from cardchase_ai.models.weekly import (
    CardWeeklyIntelligenceSnapshot,
    PlayerWeeklySignalSnapshot,
    WeeklyHomepageIntelligence,
    WeeklyIntelligenceRun,
    WeeklyRunSummary,
    WeeklyTriggeredBy,
)
from cardchase_ai.population import StageOutcome, get_population_provider, run_population_stage
from cardchase_ai.pipeline import PlayerPipelineOutput
from cardchase_ai.signal_of_week import select_signal_of_the_week
from cardchase_ai.sports.registry import is_league_available, season_for_league
from cardchase_ai.utils.reporting_period import ReportingPeriod, build_reporting_period, next_scheduled_refresh
from cardchase_ai.weekly_storage import WeeklyStorage

WeeklyLeague = Literal["NFL", "NBA"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _record_stage(
    stages: list[dict[str, Any]],
    outcomes: list[dict[str, Any]],
    name: str,
    status: StageOutcome | str,
    detail: str = "",
) -> None:
    entry = {"stage": name, "status": status, "detail": detail, "at": _utcnow().isoformat()}
    stages.append(entry)
    outcomes.append(entry)


def _league_hooks(league: str) -> dict[str, Any]:
    """Provider/storage/process hooks — NFL and NBA share the same workflow shape."""
    league_upper = league.upper()
    if league_upper == "NFL":
        from cardchase_ai.clients.nfl_import import get_nfl_provider
        from cardchase_ai.nfl_storage import build_nfl_storage
        from cardchase_ai.nfl_weekly import (
            build_nfl_market_universe,
            build_nfl_player_snapshot,
            process_player_for_nfl_weekly,
        )

        return {
            "get_provider": get_nfl_provider,
            "build_storage": build_nfl_storage,
            "build_universe": build_nfl_market_universe,
            "process_player": process_player_for_nfl_weekly,
            "build_snapshot": build_nfl_player_snapshot,
            "storage_kwarg": "nfl_storage",
            "label": "NFL",
        }
    if league_upper == "NBA":
        from cardchase_ai.clients.nba_import import get_nba_provider
        from cardchase_ai.nba_storage import build_nba_storage
        from cardchase_ai.nba_weekly import (
            build_nba_market_universe,
            build_nba_player_snapshot,
            process_player_for_nba_weekly,
        )

        return {
            "get_provider": get_nba_provider,
            "build_storage": build_nba_storage,
            "build_universe": build_nba_market_universe,
            "process_player": process_player_for_nba_weekly,
            "build_snapshot": build_nba_player_snapshot,
            "storage_kwarg": "nba_storage",
            "label": "NBA",
        }
    raise ValueError(f"weekly_pipeline supports NFL/NBA only, got {league}")


def determine_weekly_season_context(
    league: str,
    *,
    settings: Settings | None = None,
    today=None,
) -> dict[str, Any]:
    """Step 1–3 of the weekly workflow: phase + performance window selection."""
    settings = settings or get_settings()
    engine_phase = season_phase_for_league(league, today=today)
    window = None
    baseline = "PREVIOUS_SEASON" if uses_previous_season_baseline(engine_phase) else "IN_SEASON_WINDOW"
    if engine_phase == "IN_SEASON":
        window = in_season_tuesday_window(timezone_name=settings.weekly_timezone)
    return {
        "league": league.upper(),
        "engine_season_phase": engine_phase,
        "performance_baseline": baseline,
        "performance_window": window,
        "completed_previous_season": settings.nfl_season if league.upper() == "NFL" else settings.nba_season,
    }


def execute_weekly_league_pipeline(
    *,
    run: WeeklyIntelligenceRun,
    period: ReportingPeriod,
    league: str,
    player_limit: int,
    market_enabled: bool,
    population_enabled: bool,
    settings: Settings,
    storage: WeeklyStorage,
    stages: list[dict[str, Any]],
    outcomes: list[dict[str, Any]],
    build_card_snapshots: Callable,
    build_homepage_card_sections: Callable,
    snapshots_to_leaderboard_entries: Callable,
    build_data_quality_summary: Callable,
) -> WeeklyRunSummary:
    """Unified NFL/NBA weekly execution — provider is the only league fork."""
    from cardchase_ai.performance_storage import build_performance_storage

    league_upper = league.upper()
    hooks = _league_hooks(league_upper)

    if not is_league_available(league_upper, settings):
        _record_stage(stages, outcomes, "player_universe", "UNAVAILABLE", f"{league_upper} data not loaded")
        run.status = "SKIPPED"
        run.completed_at = _utcnow()
        run.warnings.append(f"{league_upper} intelligence unavailable — import verified data first")
        run.stage_outcomes = outcomes
        storage.update_run(run)
        return WeeklyRunSummary(
            run=run,
            stages=stages,
            homepage=None,
            skipped_reason=f"{league_upper} data unavailable",
        )

    season_ctx = determine_weekly_season_context(league_upper, settings=settings)
    _record_stage(
        stages,
        outcomes,
        "season_phase",
        "COMPLETED",
        f"{season_ctx['engine_season_phase']} / {season_ctx['performance_baseline']}",
    )

    provider = hooks["get_provider"](settings)
    league_storage = hooks["build_storage"](settings)
    perf_storage = build_performance_storage(settings)

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

    label = hooks["label"]
    _record_stage(stages, outcomes, "player_universe", "COMPLETED", f"building {label} candidate universe")
    candidates = hooks["build_universe"](
        provider,
        player_limit,
        performance_storage=perf_storage,
    )[:player_limit]
    outcomes[-1]["detail"] = f"{len(candidates)} candidates"

    outputs: list[PlayerPipelineOutput] = []
    player_errors: list[str] = []

    _record_stage(stages, outcomes, "performance_scoring", "COMPLETED", f"{label} refresh started")
    process_kwargs = {hooks["storage_kwarg"]: league_storage}
    for candidate in candidates:
        output, _, err = hooks["process_player"](
            candidate,
            provider,
            ebay_client,
            settings,
            market_enabled=market_enabled,
            **process_kwargs,
        )
        if output:
            outputs.append(output)
        elif err:
            player_errors.append(err)

    outputs.sort(key=lambda item: item.hotness.total_score, reverse=True)
    run.players_processed = len(outputs)
    perf_status: StageOutcome = (
        "PARTIAL" if player_errors and outputs else ("FAILED" if player_errors and not outputs else "COMPLETED")
    )
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

    population_provider = get_population_provider(settings)
    population_result = run_population_stage(
        enabled=population_enabled,
        provider=population_provider,
        league=run.league,
        player_ids=[str(o.source_player_id or o.player_id) for o in outputs],
    )
    run.population_snapshots_created = population_result.snapshots_created
    run.warnings.extend(population_result.warnings)
    _record_stage(stages, outcomes, "population_snapshots", population_result.status, population_result.detail)

    player_snapshots: list[PlayerWeeklySignalSnapshot] = []
    card_snapshots: list[CardWeeklyIntelligenceSnapshot] = []
    card_errors: list[str] = []

    _record_stage(stages, outcomes, "card_intelligence", "COMPLETED", f"building {label} snapshots")
    for rank, output in enumerate(outputs, start=1):
        try:
            snap = hooks["build_snapshot"](
                output,
                run,
                period,
                rank,
                storage,
                league_storage,
                performance_storage=perf_storage,
            )
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
            )
            card_snapshots.extend(cards)
        except Exception as error:
            card_errors.append(f"{output.player_name} cards: {error}")

    run.cards_processed = len(card_snapshots)
    run.intelligence_records_created = len(player_snapshots) + len(card_snapshots)

    _record_stage(stages, outcomes, "weekly_player_snapshots", "COMPLETED", f"{len(player_snapshots)} player snapshots")
    _record_stage(stages, outcomes, "weekly_card_snapshots", "COMPLETED", f"{len(card_snapshots)} card snapshots")
    _record_stage(stages, outcomes, "rankings", "COMPLETED", f"ranking {label} leaders")

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
    _record_stage(stages, outcomes, "homepage_payload", "COMPLETED", f"{label} homepage assembled")

    registry = [
        profile
        for o in outputs
        if (profile := provider.fetch_player_profile(str(o.source_player_id or o.player_id)))
    ]
    if registry:
        league_storage.save_player_registry(registry)
    league_storage.save_leaderboard(
        [l.model_dump(mode="json") if hasattr(l, "model_dump") else l for l in leaders]
    )

    all_errors = player_errors + card_errors
    run.errors.extend(all_errors[:20])
    if all_errors:
        run.warnings.append(f"{len(all_errors)} player/card-level errors")
    run.status = "PARTIAL" if all_errors else "COMPLETED"
    run.completed_at = _utcnow()
    run.stage_outcomes = outcomes

    # Production path: persist official weekly snapshot to Supabase (JSON is debug fallback).
    storage.persist_run_results(run, player_snapshots, card_snapshots, signal, homepage, market_movements=[])
    storage.update_run(run)
    _record_stage(
        stages,
        outcomes,
        "persist",
        "COMPLETED",
        f"{label} persist finished (supabase={storage.uses_supabase})",
    )

    return WeeklyRunSummary(run=run, stages=stages, homepage=homepage)


def run_weekly_pipeline(
    league: WeeklyLeague | str,
    *,
    force: bool = False,
    triggered_by: WeeklyTriggeredBy = "manual",
    player_limit: int | None = None,
    market_enabled: bool | None = None,
    population_enabled: bool | None = None,
    settings: Settings | None = None,
    storage: WeeklyStorage | None = None,
) -> WeeklyRunSummary:
    """Public entry point: run weekly intelligence for NFL or NBA."""
    from cardchase_ai.weekly_intelligence import run_weekly_intelligence

    league_upper = str(league).upper()
    if league_upper not in {"NFL", "NBA"}:
        raise ValueError(f"run_weekly_pipeline expects NFL or NBA, got {league}")

    return run_weekly_intelligence(
        league=league_upper,
        force=force,
        triggered_by=triggered_by,
        player_limit=player_limit,
        market_enabled=market_enabled,
        population_enabled=population_enabled,
        settings=settings,
        storage=storage,
    )
