"""Weekly intelligence orchestration service."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from cardchase_ai.clients.ebay import EbayClient
from cardchase_ai.clients.mlb import MLBClient
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
    SEARCH_TEMPLATES,
    PlayerPipelineOutput,
    _build_market_universe,
    _process_alerts,
    _write_outputs,
)
from cardchase_ai.score import build_hotness_breakdown
from cardchase_ai.signal_of_week import select_signal_of_the_week
from cardchase_ai.storage import SupabaseStorage
from cardchase_ai.utils.normalize import summarize_market
from cardchase_ai.utils.reporting_period import (
    ReportingPeriod,
    build_reporting_period,
    next_scheduled_refresh,
)
from cardchase_ai.utils.rolling import filter_last_n_days, summarize_hitter_window
from cardchase_ai.weekly_scoring import (
    CARD_QUERY_LABELS,
    card_intelligence_from_snapshot,
    compute_weekly_change,
    cs_card_id,
    cs_player_id,
    derive_collector_score,
    derive_conviction,
    derive_momentum_score,
    derive_recommendation,
    derive_scarcity_score,
    derive_status,
    has_sufficient_evidence,
)
from cardchase_ai.weekly_storage import WeeklyJsonStorage, WeeklyStorage


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _stage_log(stages: list[dict[str, Any]], name: str, status: str, detail: str = "") -> None:
    stages.append({"stage": name, "status": status, "detail": detail, "at": _utcnow().isoformat()})


def build_weekly_storage(settings: Settings) -> WeeklyStorage:
    supabase = None
    if settings.supabase_url and settings.supabase_service_role_key:
        supabase = SupabaseStorage(settings.supabase_url, settings.supabase_service_role_key)
    json_store = WeeklyJsonStorage(settings.output_dir)
    return WeeklyStorage(supabase, json_store)


def process_player_for_weekly(
    candidate: dict[str, Any],
    mlb_client: MLBClient,
    ebay_client: EbayClient | None,
    settings: Settings,
    *,
    market_enabled: bool,
) -> tuple[PlayerPipelineOutput | None, list[MarketSnapshot], str | None]:
    player_name = candidate["player_name"]
    player_id = int(candidate["player_id"])
    try:
        gamelog = mlb_client.get_hitter_gamelog(player_id, settings.mlb_season)
        stats_7d = summarize_hitter_window(filter_last_n_days(gamelog, 7))
        stats_30d = summarize_hitter_window(filter_last_n_days(gamelog, 30))

        market_snapshots: dict[str, MarketSnapshot] = {}
        if market_enabled and ebay_client:
            for query_name, template in SEARCH_TEMPLATES.items():
                payload = ebay_client.search_items(
                    template.format(player=player_name),
                    include_auctions=True,
                )
                listings = ebay_client.parse_listings(payload)
                market_snapshots[query_name] = summarize_market(query_name, listings)

        hotness = build_hotness_breakdown(
            player_name=player_name,
            stats_7d=stats_7d,
            stats_30d=stats_30d,
            market_snapshots=market_snapshots,
        )

        output = PlayerPipelineOutput(
            player_name=player_name,
            player_id=player_id,
            stats_7d=stats_7d,
            stats_30d=stats_30d,
            market_snapshots=market_snapshots,
            hotness=hotness,
            team=candidate.get("team") or "MLB",
            team_id=candidate.get("team_id"),
            position=candidate.get("position"),
            headshot_url=candidate.get("headshot_url"),
            team_logo_url=candidate.get("team_logo_url"),
            sport="MLB",
            candidate_source=candidate.get("candidate_source", "dynamic"),
        )
        return output, list(market_snapshots.values()), None
    except Exception as error:
        return None, [], f"{player_name}: {error}"


def build_player_snapshot(
    output: PlayerPipelineOutput,
    run: WeeklyIntelligenceRun,
    period: ReportingPeriod,
    rank: int,
    storage: WeeklyStorage,
) -> PlayerWeeklySignalSnapshot:
    pid = str(output.player_id)
    csp_id = cs_player_id(pid, run.league)
    hotness = output.hotness

    collector, collector_evidence, collector_missing = derive_collector_score(output.market_snapshots)
    momentum, momentum_evidence, momentum_missing = derive_momentum_score(output.stats_7d, output.stats_30d)
    scarcity, scarcity_evidence, scarcity_missing = derive_scarcity_score(output.market_snapshots)

    missing_inputs = list(dict.fromkeys(collector_missing + momentum_missing + scarcity_missing))
    if output.stats_7d.games == 0:
        missing_inputs.append("stats_7d")
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
) -> list[CardWeeklyIntelligenceSnapshot]:
    snapshots: list[CardWeeklyIntelligenceSnapshot] = []
    pid = str(output.player_id)
    csp_id = cs_player_id(pid, run.league)

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
                captured_at=_utcnow(),
                card_label=CARD_QUERY_LABELS.get(query_name, query_name),
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

    player_limit = min(player_limit or settings.weekly_player_limit, settings.weekly_player_limit)
    market_enabled = settings.weekly_market_enabled if market_enabled is None else market_enabled
    population_enabled = settings.weekly_population_enabled if population_enabled is None else population_enabled

    period = build_reporting_period(
        league=league,
        timezone_name=settings.weekly_timezone,
        season=settings.mlb_season,
    )
    _stage_log(stages, "determine_period", "completed", f"week {period.week_number}")

    if not force and triggered_by != "test":
        existing = storage.find_official_completed_run(league, period.year, period.week_number)
        if existing:
            _stage_log(stages, "duplicate_guard", "skipped", "official run already exists")
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
    _stage_log(stages, "create_run", "completed", run.run_id)

    mlb_client = MLBClient()
    ebay_client = None
    if market_enabled and settings.ebay_token:
        ebay_client = EbayClient(
            token=settings.ebay_token,
            marketplace_id=settings.ebay_marketplace_id,
            client_id=settings.ebay_client_id,
            client_secret=settings.ebay_client_secret,
        )

    _stage_log(stages, "build_universe", "started")
    candidates = _build_market_universe(mlb_client, settings, scan_limit=player_limit)[:player_limit]
    _stage_log(stages, "build_universe", "completed", f"{len(candidates)} candidates")

    processor = player_processor or process_player_for_weekly
    outputs: list[PlayerPipelineOutput] = []
    player_errors: list[str] = []

    _stage_log(stages, "refresh_players", "started")
    for candidate in candidates:
        output, _, err = processor(
            candidate,
            mlb_client,
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
    _stage_log(stages, "refresh_players", "completed" if not player_errors else "partial", f"{len(outputs)} ok, {len(player_errors)} errors")

    _stage_log(stages, "score_players", "started")
    player_snapshots: list[PlayerWeeklySignalSnapshot] = []
    card_snapshots: list[CardWeeklyIntelligenceSnapshot] = []
    market_count = 0

    for rank, output in enumerate(outputs, start=1):
        try:
            snap = build_player_snapshot(output, run, period, rank, storage)
            player_snapshots.append(snap)
            cards = build_card_snapshots(
                output,
                run,
                period,
                card_limit=settings.weekly_card_limit_per_player,
            )
            card_snapshots.extend(cards)
            market_count += len(output.market_snapshots)
        except Exception as error:
            player_errors.append(f"{output.player_name}: {error}")

    run.cards_processed = len(card_snapshots)
    run.market_snapshots_created = market_count
    run.population_snapshots_created = 0 if not population_enabled else 0
    run.intelligence_records_created = len(player_snapshots) + len(card_snapshots)
    _stage_log(stages, "score_players", "completed", f"{len(player_snapshots)} snapshots")

    _stage_log(stages, "select_signal", "started")
    signal = select_signal_of_the_week(player_snapshots, run.run_id)
    if signal:
        signal.selected_at = _utcnow()
    _stage_log(stages, "select_signal", "completed", signal.player_name if signal else "none")

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

    _stage_log(stages, "persist", "started")
    legacy_entries = snapshots_to_legacy_leaderboard(player_snapshots)
    if legacy_entries:
        file_path = _write_outputs(legacy_entries, settings.output_dir)
        if storage.uses_supabase and storage.supabase:
            try:
                run_id = storage.supabase.persist_leaderboard(str(file_path), legacy_entries)
                _process_alerts(storage.supabase, run_id, legacy_entries)
            except Exception as error:
                run.warnings.append(f"legacy leaderboard persist: {error}")

    run.errors.extend(player_errors[:20])
    if player_errors:
        run.warnings.append(f"{len(player_errors)} player-level errors")
    run.status = "PARTIAL" if player_errors else "COMPLETED"
    run.completed_at = _utcnow()
    storage.persist_run_results(run, player_snapshots, card_snapshots, signal, homepage)
    storage.update_run(run)
    _stage_log(stages, "persist", "completed")

    return WeeklyRunSummary(run=run, stages=stages, homepage=homepage)


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
