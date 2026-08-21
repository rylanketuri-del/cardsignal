"""Weekly intelligence orchestration service."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from cardchase_ai.clients.ebay import EbayClient, has_usable_ebay_credentials
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
from cardchase_ai.models.nfl import NFL_PLAYER_SIGNAL_V1
from cardchase_ai.pipeline import (
    SEARCH_TEMPLATES,
    PlayerPipelineOutput,
    _build_market_universe,
)
from cardchase_ai.market_movement import MarketSnapshotHistory
from cardchase_ai.models.market_movement import CardMarketMovement
from cardchase_ai.population import StageOutcome, get_population_provider, run_population_stage
from cardchase_ai.score import build_hotness_breakdown
from cardchase_ai.signal_of_week import select_signal_of_the_week
from cardchase_ai.storage import SupabaseStorage
from cardchase_ai.utils.normalize import summarize_market
from cardchase_ai.utils.reporting_period import (
    ReportingPeriod,
    build_reporting_period,
    next_scheduled_refresh,
)
from cardchase_ai.utils.rolling import summarize_mlb_hitter_windows
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
from cardchase_ai.capabilities import declare_mlb_capabilities
from cardchase_ai.mlb_signal_drivers import driver_data_quality, generate_mlb_signal_drivers
from cardchase_ai.performance_evidence import build_mlb_recent_evidence, build_mlb_season_evidence
from cardchase_ai.season_context import active_season_performance_label
from cardchase_ai.weekly_storage import WeeklyJsonStorage, WeeklyStorage
from cardchase_ai.nfl_weekly import (
    build_nfl_market_universe,
    build_nfl_player_snapshot,
    process_player_for_nfl_weekly,
)
from cardchase_ai.nfl_storage import build_nfl_storage
from cardchase_ai.clients.nfl_import import get_nfl_provider
from cardchase_ai.nba_weekly import (
    build_nba_market_universe,
    build_nba_player_snapshot,
    process_player_for_nba_weekly,
)
from cardchase_ai.nba_storage import build_nba_storage
from cardchase_ai.clients.nba_import import get_nba_provider
from cardchase_ai.sports.registry import is_league_available, season_for_league
from cardchase_ai.performance_storage import build_performance_storage


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


def _weekly_ebay_client(
    settings: Settings,
    run: WeeklyIntelligenceRun,
    market_enabled: bool,
) -> tuple[EbayClient | None, bool]:
    """Build an EbayClient when weekly market is on and usable credentials exist.

    Usable credentials are a static token OR client-id + client-secret OAuth.
    Never log credential values.
    """
    if not market_enabled:
        return None, False
    if has_usable_ebay_credentials(
        token=settings.ebay_token,
        client_id=settings.ebay_client_id,
        client_secret=settings.ebay_client_secret,
    ):
        return (
            EbayClient(
                token=settings.ebay_token or None,
                marketplace_id=settings.ebay_marketplace_id,
                client_id=settings.ebay_client_id or None,
                client_secret=settings.ebay_client_secret or None,
            ),
            True,
        )
    run.warnings.append("Market enabled but eBay credentials missing; market snapshots skipped")
    return None, False


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
        stats_7d, stats_30d, stats_season = summarize_mlb_hitter_windows(gamelog)

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
            stats_season=stats_season,
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
    pid = str(output.source_player_id or output.player_id)
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
    card_signal = hotness.total_score if has_sufficient_evidence(performance, market, missing_inputs, league=run.league) else None

    prior = storage.fetch_prior_official_player_snapshot(csp_id, run.league, period.year, period.week_number)
    prior_score = prior.card_signal_score if prior else None
    weekly_change = compute_weekly_change(card_signal, prior_score)

    conviction = derive_conviction(hotness.confidence_multiplier, len(missing_inputs))
    recommendation = derive_recommendation(hotness, collector) if card_signal is not None else None
    status = derive_status(hotness, momentum)

    period_start_str = period.period_start.isoformat() if period.period_start else None
    period_end_str = period.period_end.isoformat() if period.period_end else None
    recent_evidence = build_mlb_recent_evidence(
        output.stats_7d,
        output.stats_30d,
        period_start=period_start_str,
        period_end=period_end_str,
    )
    season_evidence = build_mlb_season_evidence(
        output.stats_season,
        period_start=period_start_str,
        period_end=period_end_str,
    )
    drivers = generate_mlb_signal_drivers(
        stats_7d=output.stats_7d,
        stats_30d=output.stats_30d,
        season_phase="REGULAR_SEASON",
    )
    perf_quality = "HIGH" if output.stats_7d.games >= 5 else "MEDIUM" if output.stats_7d.games >= 3 else "LOW" if output.stats_7d.games > 0 else "INSUFFICIENT"
    driver_quality = driver_data_quality(drivers, output.stats_7d.games)
    capabilities = declare_mlb_capabilities(has_market_history=False, has_weekly_history=prior is not None)

    market_missing = [m for m in missing_inputs if m in {"market_snapshots", "listing_volume"}]
    performance_missing = [m for m in missing_inputs if m.startswith("stats")]

    evidence = {
        "performance_reasons": hotness.reasons,
        "market_reasons": hotness.reasons,
        "collector_evidence": collector_evidence,
        "momentum_evidence": momentum_evidence,
        "scarcity_evidence": scarcity_evidence,
        "confidence_multiplier": hotness.confidence_multiplier,
        "tag": hotness.tag,
        "recent_performance": [e.model_dump(mode="json") for e in recent_evidence],
        "season_performance": [e.model_dump(mode="json") for e in season_evidence],
        "stats_season": output.stats_season.model_dump(mode="json") if output.stats_season else {},
        "signal_drivers": [d.model_dump(mode="json") for d in drivers],
        "performance_data_quality": perf_quality,
        "driver_data_quality": driver_quality,
        "season_phase": "REGULAR_SEASON",
        "recent_window_label": "Last 7 Days",
        "season_label": str(period.season),
        "season_performance_label": active_season_performance_label("MLB", period.season),
        "period_type": "LAST_7_DAYS",
        "performance_algorithm_version": WEEKLY_INTELLIGENCE_V1,
        "market_snapshots": {
            k: v.model_dump(mode="json") if hasattr(v, "model_dump") else v
            for k, v in output.market_snapshots.items()
        },
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
        season_phase="REGULAR_SEASON",
        period_type="LAST_7_DAYS",
        recent_window_label="Last 7 Days",
        signal_drivers=[d.model_dump(mode="json") for d in drivers],
        recent_performance=[e.model_dump(mode="json") for e in recent_evidence],
        season_performance=[e.model_dump(mode="json") for e in season_evidence],
        performance_data_quality=perf_quality,
        performance_missing_inputs=performance_missing,
        market_data_quality="MEDIUM" if output.market_snapshots else "INSUFFICIENT",
        market_missing_inputs=market_missing,
        driver_data_quality=driver_quality,
        capabilities=capabilities,
        weekly_algorithm_version=WEEKLY_INTELLIGENCE_V1,
        scoring_algorithm_version=WEEKLY_INTELLIGENCE_V1,
        performance_algorithm_version=WEEKLY_INTELLIGENCE_V1,
        card_algorithm_version=WEEKLY_INTELLIGENCE_V1,
        prior_score=prior_score,
        official_weekly_snapshot=True,
        data_confidence=perf_quality if perf_quality != "INSUFFICIENT" else "LOW",
        evidence_summary=f"{len(drivers)} signal drivers from stored performance",
        freshness_summary=period_end_str,
    )


def build_card_snapshots(
    output: PlayerPipelineOutput,
    run: WeeklyIntelligenceRun,
    period: ReportingPeriod,
    *,
    card_limit: int,
) -> list[CardWeeklyIntelligenceSnapshot]:
    snapshots: list[CardWeeklyIntelligenceSnapshot] = []
    pid = str(output.source_player_id or output.player_id)
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


def empty_card_intelligence() -> dict[str, list[dict[str, Any]]]:
    return {
        "trending_cards": [],
        "biggest_movers": [],
        "buy_low_watch": [],
        "most_chased": [],
    }


def card_intelligence_from_homepage(homepage: Any) -> dict[str, list[dict[str, Any]]]:
    """Extract homepage card sections from a persisted homepage payload."""
    homepage_dict = _homepage_as_dict(homepage)
    if not homepage_dict:
        return empty_card_intelligence()
    return {
        "trending_cards": list(homepage_dict.get("trending_cards") or []),
        "biggest_movers": list(homepage_dict.get("biggest_movers") or []),
        "buy_low_watch": list(homepage_dict.get("buy_low_watch") or []),
        "most_chased": list(homepage_dict.get("most_chased") or []),
    }


def _homepage_as_dict(homepage: Any) -> dict[str, Any] | None:
    if homepage is None:
        return None
    if hasattr(homepage, "model_dump"):
        dumped = homepage.model_dump(mode="json")
        return dumped if isinstance(dumped, dict) else None
    if isinstance(homepage, dict):
        return homepage
    return None


def homepage_has_usable_leaders(homepage: Any) -> bool:
    """True when persisted homepage_payload can serve GET /api/weekly/latest."""
    homepage_dict = _homepage_as_dict(homepage)
    if not homepage_dict:
        return False
    leaders = homepage_dict.get("todays_leaders")
    return isinstance(leaders, list) and len(leaders) > 0


def _serialize_run(run_data: Any) -> dict[str, Any] | None:
    if hasattr(run_data, "model_dump"):
        dumped = run_data.model_dump(mode="json")
        return dumped if isinstance(dumped, dict) else None
    if isinstance(run_data, dict):
        return run_data
    return None


def _leaders_from_homepage(homepage: dict[str, Any], run_dict: dict[str, Any] | None) -> list[dict[str, Any]]:
    raw = homepage.get("todays_leaders") or []
    if not isinstance(raw, list):
        return []
    league = (run_dict or {}).get("league")
    sport = (run_dict or {}).get("sport")
    leaders: list[dict[str, Any]] = []
    for row in raw:
        if hasattr(row, "model_dump"):
            item = row.model_dump(mode="json")
        elif isinstance(row, dict):
            item = dict(row)
        else:
            continue
        if not isinstance(item, dict):
            continue
        if league and not item.get("league"):
            item["league"] = league
        if sport and not item.get("sport"):
            item["sport"] = sport
        leaders.append(item)
    return leaders


def _empty_latest_weekly_api_payload(next_refresh: datetime) -> dict[str, Any]:
    return {
        "run": None,
        "signal_of_the_week": None,
        "todays_leaders": [],
        "homepage": None,
        "next_refresh": next_refresh.isoformat(),
        "data_quality_summary": {},
        "card_intelligence": empty_card_intelligence(),
    }


def _latest_payload_from_homepage(
    run_dict: dict[str, Any] | None,
    homepage: Any,
    next_refresh: datetime,
) -> dict[str, Any]:
    homepage_dict = _homepage_as_dict(homepage) or {}
    return {
        "run": run_dict,
        "signal_of_the_week": homepage_dict.get("signal_of_the_week"),
        "todays_leaders": _leaders_from_homepage(homepage_dict, run_dict),
        "homepage": homepage_dict,
        "next_refresh": next_refresh.isoformat(),
        "data_quality_summary": homepage_dict.get("data_quality_summary") or {},
        "card_intelligence": card_intelligence_from_homepage(homepage_dict),
    }


def build_homepage_card_sections(
    card_snapshots: list[CardWeeklyIntelligenceSnapshot],
    market_movements: list | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Build homepage card modules from stored weekly card snapshots.

    Movement is only attached when a genuine calculated historical
    price_change_pct exists. Demand/momentum/avg_price are never copied
    into movement. Biggest Movers stays empty without that history.
    """
    scored = [c for c in card_snapshots if c.card_signal_score is not None]

    trending = sorted(scored, key=lambda c: (-(c.demand_score or 0), c.cs_card_id))[:5]
    buy_low = sorted(
        [c for c in scored if c.recommendation == "BUY"],
        key=lambda c: (c.card_signal_score or 0, c.cs_card_id),
    )[:5]
    chased = sorted(scored, key=lambda c: (-(c.demand_score or 0), c.cs_card_id))[:5]

    historical_by_card: dict[str, float] = {}
    for movement in market_movements or []:
        card_id, pct = _historical_price_change_pct(movement)
        if card_id and pct is not None:
            historical_by_card[card_id] = pct

    movers = sorted(
        [c for c in scored if c.cs_card_id in historical_by_card],
        key=lambda c: (-abs(historical_by_card[c.cs_card_id]), c.cs_card_id),
    )[:5]

    def row(c: CardWeeklyIntelligenceSnapshot) -> dict[str, Any]:
        pct = historical_by_card.get(c.cs_card_id)
        historical = pct is not None
        evidence = dict(c.evidence or {})
        evidence.pop("listings", None)
        return {
            "cs_card_id": c.cs_card_id,
            "cs_player_id": c.cs_player_id,
            "player_name": c.player_name,
            "card_label": c.card_label,
            "score": c.card_signal_score,
            "recommendation": c.recommendation,
            "demand_score": c.demand_score,
            "momentum_score": c.momentum_score,
            "market_activity_score": c.market_activity_score,
            "movement": round(pct, 2) if historical else None,
            "movement_status": "calculated" if historical else "pending",
            "movement_is_historical": historical,
            "movement_type": "price_change_pct" if historical else None,
            "evidence": evidence,
        }

    return {
        "trending_cards": [row(c) for c in trending],
        "biggest_movers": [row(c) for c in movers],
        "buy_low_watch": [row(c) for c in buy_low],
        "most_chased": [row(c) for c in chased],
    }


def _historical_price_change_pct(movement: Any) -> tuple[str | None, float | None]:
    """Return (cs_card_id, price_change_pct) only for calculated historical moves."""
    if movement is None:
        return None, None
    if hasattr(movement, "status"):
        status = movement.status
        pct = getattr(movement, "price_change_pct", None)
        card_id = getattr(movement, "cs_card_id", None)
    elif isinstance(movement, dict):
        status = movement.get("status")
        pct = movement.get("price_change_pct")
        card_id = movement.get("cs_card_id")
    else:
        return None, None
    if str(status or "").lower() != "calculated" or pct is None or not card_id:
        return None, None
    try:
        return str(card_id), float(pct)
    except (TypeError, ValueError):
        return None, None


def build_data_quality_summary(snapshots: list[PlayerWeeklySignalSnapshot]) -> dict[str, Any]:
    total = len(snapshots)
    if total == 0:
        return {"total_players": 0, "sufficient_evidence": 0, "partial_evidence": 0, "insufficient_evidence": 0}

    sufficient = sum(
        1 for s in snapshots
        if has_sufficient_evidence(s.performance_score, s.market_score, s.missing_inputs, league=s.league)
    )
    partial = sum(
        1 for s in snapshots
        if s.card_signal_score is not None and not has_sufficient_evidence(s.performance_score, s.market_score, s.missing_inputs, league=s.league)
    )
    insufficient = total - sufficient - partial
    return {
        "total_players": total,
        "sufficient_evidence": sufficient,
        "partial_evidence": partial,
        "insufficient_evidence": insufficient,
        "sufficient_pct": round((sufficient / total) * 100, 1),
    }


def snapshots_to_leaderboard_entries(
    snapshots: list[PlayerWeeklySignalSnapshot],
    repos=None,
    settings: Settings | None = None,
) -> list[TodaysLeaderEntry]:
    from cardchase_ai.intelligence_service import build_normalized_leader_rows
    from cardchase_ai.repositories.factory import build_repository_bundle

    if not snapshots:
        return []
    bundle = repos or build_repository_bundle(settings)
    rows = build_normalized_leader_rows(snapshots[0].league, snapshots, bundle)
    leader_fields = set(TodaysLeaderEntry.model_fields.keys())
    return [TodaysLeaderEntry.model_validate({k: v for k, v in row.items() if k in leader_fields}) for row in rows]


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
    league_upper = league.upper()

    if league_upper == "NFL" and not is_league_available("NFL", settings):
        _record_stage(stages, outcomes, "player_universe", "UNAVAILABLE", "NFL data not loaded")
        run.status = "SKIPPED"
        run.completed_at = _utcnow()
        run.warnings.append("NFL intelligence unavailable — import verified NFL data first")
        run.stage_outcomes = outcomes
        storage.update_run(run)
        return WeeklyRunSummary(run=run, stages=stages, homepage=None, skipped_reason="NFL data unavailable")

    if league_upper == "NBA" and not is_league_available("NBA", settings):
        _record_stage(stages, outcomes, "player_universe", "UNAVAILABLE", "NBA data not loaded")
        run.status = "SKIPPED"
        run.completed_at = _utcnow()
        run.warnings.append("NBA intelligence unavailable — import verified NBA data first")
        run.stage_outcomes = outcomes
        storage.update_run(run)
        return WeeklyRunSummary(run=run, stages=stages, homepage=None, skipped_reason="NBA data unavailable")

    if league_upper == "NFL":
        return _execute_nfl_weekly_pipeline(
            run=run,
            period=period,
            league=league,
            player_limit=player_limit,
            market_enabled=market_enabled,
            population_enabled=population_enabled,
            settings=settings,
            storage=storage,
            stages=stages,
            outcomes=outcomes,
        )

    if league_upper == "NBA":
        return _execute_nba_weekly_pipeline(
            run=run,
            period=period,
            league=league,
            player_limit=player_limit,
            market_enabled=market_enabled,
            population_enabled=population_enabled,
            settings=settings,
            storage=storage,
            stages=stages,
            outcomes=outcomes,
        )

    mlb_client = MLBClient()
    ebay_client, market_enabled = _weekly_ebay_client(settings, run, market_enabled)

    _record_stage(stages, outcomes, "player_universe", "COMPLETED", "building candidate universe")
    candidates = _build_market_universe(mlb_client, settings, scan_limit=player_limit)[:player_limit]
    outcomes[-1]["detail"] = f"{len(candidates)} candidates"
    stages[-1]["detail"] = f"{len(candidates)} candidates"

    outputs: list[PlayerPipelineOutput] = []
    player_errors: list[str] = []

    _record_stage(stages, outcomes, "performance_scoring", "COMPLETED", "refresh started")
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
            snap = build_player_snapshot(output, run, period, rank, storage)
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
    leaders = snapshots_to_leaderboard_entries(player_snapshots, settings=settings)
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
    # Weekly official snapshots persist via persist_run_results only.
    # Do not write weekly CardSignal/Market scores into daily leaderboard_entries.

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


def _execute_nfl_weekly_pipeline(
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
) -> WeeklyRunSummary:
    provider = get_nfl_provider(settings)
    nfl_storage = build_nfl_storage(settings)
    perf_storage = build_performance_storage(settings)
    ebay_client, market_enabled = _weekly_ebay_client(settings, run, market_enabled)

    _record_stage(stages, outcomes, "player_universe", "COMPLETED", "building NFL candidate universe")
    candidates = build_nfl_market_universe(
        provider,
        player_limit,
        performance_storage=build_performance_storage(settings),
    )[:player_limit]
    outcomes[-1]["detail"] = f"{len(candidates)} candidates"

    outputs: list[PlayerPipelineOutput] = []
    player_errors: list[str] = []

    _record_stage(stages, outcomes, "performance_scoring", "COMPLETED", "NFL refresh started")
    for candidate in candidates:
        output, _, err = process_player_for_nfl_weekly(
            candidate,
            provider,
            ebay_client,
            settings,
            market_enabled=market_enabled,
            nfl_storage=nfl_storage,
        )
        if output:
            outputs.append(output)
        elif err:
            player_errors.append(err)

    outputs.sort(key=lambda item: item.hotness.total_score, reverse=True)
    run.players_processed = len(outputs)
    perf_status: StageOutcome = "PARTIAL" if player_errors and outputs else ("FAILED" if player_errors and not outputs else "COMPLETED")
    _record_stage(stages, outcomes, "performance_scoring", perf_status, f"{len(outputs)} ok, {len(player_errors)} errors")

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

    _record_stage(stages, outcomes, "card_intelligence", "COMPLETED", "building NFL snapshots")
    for rank, output in enumerate(outputs, start=1):
        try:
            snap = build_nfl_player_snapshot(
                output, run, period, rank, storage, nfl_storage, performance_storage=perf_storage,
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
    _record_stage(stages, outcomes, "rankings", "COMPLETED", "ranking NFL leaders")

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
    leaders = snapshots_to_leaderboard_entries(player_snapshots, settings=settings)
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
    _record_stage(stages, outcomes, "homepage_payload", "COMPLETED", "NFL homepage assembled")

    registry = [
        profile
        for o in outputs
        if (profile := provider.fetch_player_profile(str(o.source_player_id or o.player_id)))
    ]
    if registry:
        nfl_storage.save_player_registry(registry)
    nfl_storage.save_leaderboard([l.model_dump(mode="json") if hasattr(l, "model_dump") else l for l in leaders])

    all_errors = player_errors + card_errors
    run.errors.extend(all_errors[:20])
    if all_errors:
        run.warnings.append(f"{len(all_errors)} player/card-level errors")
    run.status = "PARTIAL" if all_errors else "COMPLETED"
    run.completed_at = _utcnow()
    run.stage_outcomes = outcomes
    storage.persist_run_results(run, player_snapshots, card_snapshots, signal, homepage, market_movements=[])
    storage.update_run(run)
    _record_stage(stages, outcomes, "persist", "COMPLETED", "NFL persist finished")

    return WeeklyRunSummary(run=run, stages=stages, homepage=homepage)


def _execute_nba_weekly_pipeline(
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
) -> WeeklyRunSummary:
    provider = get_nba_provider(settings)
    nba_storage = build_nba_storage(settings)
    perf_storage = build_performance_storage(settings)
    ebay_client, market_enabled = _weekly_ebay_client(settings, run, market_enabled)

    _record_stage(stages, outcomes, "player_universe", "COMPLETED", "building NBA candidate universe")
    candidates = build_nba_market_universe(
        provider,
        player_limit,
        performance_storage=perf_storage,
    )[:player_limit]
    outcomes[-1]["detail"] = f"{len(candidates)} candidates"

    outputs: list[PlayerPipelineOutput] = []
    player_errors: list[str] = []

    _record_stage(stages, outcomes, "performance_scoring", "COMPLETED", "NBA refresh started")
    for candidate in candidates:
        output, _, err = process_player_for_nba_weekly(
            candidate,
            provider,
            ebay_client,
            settings,
            market_enabled=market_enabled,
            nba_storage=nba_storage,
        )
        if output:
            outputs.append(output)
        elif err:
            player_errors.append(err)

    outputs.sort(key=lambda item: item.hotness.total_score, reverse=True)
    run.players_processed = len(outputs)
    perf_status: StageOutcome = "PARTIAL" if player_errors and outputs else ("FAILED" if player_errors and not outputs else "COMPLETED")
    _record_stage(stages, outcomes, "performance_scoring", perf_status, f"{len(outputs)} ok, {len(player_errors)} errors")

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

    _record_stage(stages, outcomes, "card_intelligence", "COMPLETED", "building NBA snapshots")
    for rank, output in enumerate(outputs, start=1):
        try:
            snap = build_nba_player_snapshot(
                output, run, period, rank, storage, nba_storage, performance_storage=perf_storage,
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
    _record_stage(stages, outcomes, "rankings", "COMPLETED", "ranking NBA leaders")

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
    leaders = snapshots_to_leaderboard_entries(player_snapshots, settings=settings)
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
    _record_stage(stages, outcomes, "homepage_payload", "COMPLETED", "NBA homepage assembled")

    registry = [
        profile
        for o in outputs
        if (profile := provider.fetch_player_profile(str(o.source_player_id or o.player_id)))
    ]
    if registry:
        nba_storage.save_player_registry(registry)
    nba_storage.save_leaderboard([l.model_dump(mode="json") if hasattr(l, "model_dump") else l for l in leaders])

    all_errors = player_errors + card_errors
    run.errors.extend(all_errors[:20])
    if all_errors:
        run.warnings.append(f"{len(all_errors)} player/card-level errors")
    run.status = "PARTIAL" if all_errors else "COMPLETED"
    run.completed_at = _utcnow()
    run.stage_outcomes = outcomes
    storage.persist_run_results(run, player_snapshots, card_snapshots, signal, homepage, market_movements=[])
    storage.update_run(run)
    _record_stage(stages, outcomes, "persist", "COMPLETED", "NBA persist finished")

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

    period = build_reporting_period(
        league=league,
        timezone_name=settings.weekly_timezone,
        season=season_for_league(league, settings),
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

    processor = player_processor or process_player_for_weekly

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
    """Build GET /api/weekly/latest response from stored data only.

    Query count:
      Fast path (homepage_payload.todays_leaders non-empty): 1 storage read
        — weekly_intelligence_runs row only. No player snapshots, card
        snapshots, signal table, batch_get_player_intelligence, or per-player
        history. Shared for MLB/NFL/NBA.
      Before this fast path: 4 payload reads (run + 100 players + 400 cards +
        signal) then batch_get_player_intelligence reloaded the full weekly
        payload and player history for each of 100 players (~500+ GETs).
      Fallback (missing/empty/malformed homepage): unchanged reconstruction
        via fetch_latest_completed_payload + snapshot rebuild.
    """
    next_refresh = next_scheduled_refresh(
        league=league,
        timezone_name=settings.weekly_timezone,
        refresh_day=settings.weekly_refresh_day,
        refresh_hour=settings.weekly_refresh_hour,
    )

    run_row = storage.fetch_latest_official_run_row(league)
    if not run_row:
        return _empty_latest_weekly_api_payload(next_refresh)

    run_dict = _serialize_run(run_row)
    homepage = (run_dict or {}).get("homepage_payload")
    if homepage_has_usable_leaders(homepage):
        return _latest_payload_from_homepage(run_dict, homepage, next_refresh)

    from cardchase_ai.intelligence_service import build_normalized_leader_rows
    from cardchase_ai.repositories.factory import build_repository_bundle

    payload = storage.fetch_latest_completed_payload(league)
    if not payload:
        return _empty_latest_weekly_api_payload(next_refresh)

    run_data = payload.get("run")
    run_dict = _serialize_run(run_data) or run_dict
    homepage = payload.get("homepage")
    player_snaps = payload.get("player_snapshots", [])
    parsed_snaps = [PlayerWeeklySignalSnapshot.model_validate(p) for p in player_snaps] if player_snaps else []
    repos = build_repository_bundle(settings)

    if parsed_snaps:
        leaders = build_normalized_leader_rows(league, parsed_snaps, repos)
        card_snaps = payload.get("card_snapshots", [])
        if card_snaps:
            card_intel = build_homepage_card_sections(
                [CardWeeklyIntelligenceSnapshot.model_validate(c) for c in card_snaps]
            )
        else:
            # Prefer rebuilt sections when snapshots exist; otherwise keep persisted homepage sections.
            card_intel = card_intelligence_from_homepage(homepage)
        quality = build_data_quality_summary(parsed_snaps)
    elif homepage is not None:
        card_intel = card_intelligence_from_homepage(homepage)
        homepage_dict = _homepage_as_dict(homepage) or {}
        quality = homepage_dict.get("data_quality_summary") or {}
        leaders = homepage_dict.get("todays_leaders") or []
    else:
        card_intel = empty_card_intelligence()
        quality = {}
        leaders = []

    return {
        "run": run_dict,
        "signal_of_the_week": payload.get("signal_of_the_week"),
        "todays_leaders": leaders,
        "homepage": homepage,
        "next_refresh": next_refresh.isoformat(),
        "data_quality_summary": quality,
        "card_intelligence": card_intel,
    }
