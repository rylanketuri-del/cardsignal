"""Build Card Report payloads from stored weekly intelligence — read-only, no provider calls."""

from __future__ import annotations

from typing import Any

from cardchase_ai.card_outlook import CardOutlook, build_card_outlook
from cardchase_ai.models.card_report import (
    CardIdentity,
    CardReport,
    CardReportDriver,
    CardReportMarket,
    CardReportPopulation,
    PriceHistoryPoint,
    PriceHistorySeries,
)
from cardchase_ai.weekly_scoring import CARD_QUERY_LABELS


def parse_cs_card_id(cs_card_id: str) -> dict[str, str]:
    parts = cs_card_id.split(":")
    if len(parts) < 4 or parts[2] != "card":
        raise ValueError(f"Invalid cs_card_id format: {cs_card_id}")
    league = parts[0].upper()
    return {
        "league": league,
        "sport": league,
        "player_id": parts[1],
        "query_name": parts[3],
        "cs_player_id": f"{parts[0]}:{parts[1]}",
    }


def _resolve_card_identity(snapshot: dict[str, Any], query_name: str) -> CardIdentity | None:
    stored = snapshot.get("identity") or snapshot.get("registry")
    if isinstance(stored, dict) and any(stored.get(k) for k in ("year", "brand", "set")):
        return CardIdentity(
            year=stored.get("card_year") or stored.get("year"),
            brand=stored.get("brand"),
            set=stored.get("set"),
            parallel=stored.get("parallel"),
            card_number=stored.get("card_number"),
            grade=stored.get("grade"),
            grading_company=stored.get("grading_company"),
            serial_number=stored.get("serial_number"),
        )
    return None


def _build_market(snapshot: dict[str, Any]) -> CardReportMarket:
    evidence = snapshot.get("evidence") or {}
    missing = snapshot.get("missing_inputs") or []
    listings = evidence.get("listings_count") or evidence.get("active_listings")

    data_quality = "Complete"
    if missing:
        data_quality = "Partial" if len(missing) <= 2 else "Building"

    sales_activity = None
    if listings is not None and int(listings) > 0:
        sales_activity = f"{listings} active listing{'s' if int(listings) != 1 else ''} in stored snapshots"

    return CardReportMarket(
        median_price=evidence.get("median_price") or evidence.get("median_active_price"),
        average_price=evidence.get("avg_price") or evidence.get("average_price"),
        active_listings=listings,
        auction_count=evidence.get("auction_count"),
        listings_with_bids=evidence.get("listings_with_bids") or evidence.get("bid_count"),
        market_depth=evidence.get("market_depth"),
        data_quality=data_quality if snapshot else None,
        sales_activity=sales_activity,
    )


def _build_population(snapshot: dict[str, Any]) -> CardReportPopulation:
    evidence = snapshot.get("evidence") or {}
    tags = evidence.get("tags") or {}
    identity = snapshot.get("identity") or snapshot.get("registry") or {}

    psa_pop = tags.get("psa10_count")
    if psa_pop is not None:
        psa_pop = int(psa_pop)

    return CardReportPopulation(
        psa_population=psa_pop,
        population_grade=identity.get("grade") or tags.get("grade"),
        serial_number=identity.get("serial_number"),
        parallel=identity.get("parallel"),
        print_run=identity.get("print_run"),
        scarcity_score=snapshot.get("scarcity_score"),
    )


def _build_market_drivers(snapshot: dict[str, Any]) -> list[CardReportDriver]:
    drivers: list[CardReportDriver] = []
    evidence = snapshot.get("evidence") or {}

    listings = evidence.get("listings_count")
    if listings is not None:
        drivers.append(
            CardReportDriver(
                label="Active Listings",
                detail=f"{listings} active listing{'s' if int(listings) != 1 else ''} in stored market snapshots",
            )
        )

    tags = evidence.get("tags") or {}
    premium = tags.get("premium_count")
    if premium:
        drivers.append(
            CardReportDriver(
                label="Premium Demand",
                detail=f"{premium} premium listing{'s' if int(premium) != 1 else ''} tracked",
                direction="up",
            )
        )

    demand = snapshot.get("demand_score")
    if demand is not None:
        drivers.append(
            CardReportDriver(
                label="Demand Score",
                detail=f"Stored demand score at {demand}",
                direction="up" if float(demand) >= 50 else "down",
            )
        )

    activity = snapshot.get("market_activity_score")
    if activity is not None:
        drivers.append(
            CardReportDriver(
                label="Market Activity",
                detail=f"Market activity score at {activity}",
                direction="up" if float(activity) >= 50 else "down",
            )
        )

    for reason in evidence.get("market_reasons") or []:
        drivers.append(CardReportDriver(label="Market Signal", detail=str(reason)))

    for reason in evidence.get("listing_velocity") or []:
        drivers.append(CardReportDriver(label="Listing Velocity", detail=str(reason), direction="up"))

    return drivers


def _build_scarcity_drivers(snapshot: dict[str, Any]) -> list[CardReportDriver]:
    drivers: list[CardReportDriver] = []
    evidence = snapshot.get("evidence") or {}
    tags = evidence.get("tags") or {}

    psa10 = tags.get("psa10_count")
    if psa10 is not None:
        drivers.append(
            CardReportDriver(
                label="PSA 10 Listings",
                detail=f"{psa10} PSA 10 listing{'s' if int(psa10) != 1 else ''} in market snapshots",
            )
        )

    numbered = tags.get("numbered_count")
    if numbered:
        drivers.append(
            CardReportDriver(
                label="Numbered Parallels",
                detail=f"{numbered} numbered listing{'s' if int(numbered) != 1 else ''} tracked",
            )
        )

    scarcity = snapshot.get("scarcity_score")
    if scarcity is not None:
        drivers.append(
            CardReportDriver(
                label="Scarcity Score",
                detail=f"Stored scarcity score at {scarcity}",
                direction="up",
            )
        )

    for reason in evidence.get("scarcity_evidence") or []:
        drivers.append(CardReportDriver(label="Scarcity Signal", detail=str(reason)))

    return drivers


def _build_price_history(history: list[dict[str, Any]]) -> PriceHistorySeries:
    points: list[PriceHistoryPoint] = []
    for item in history:
        evidence = item.get("evidence") or {}
        week = item.get("week_number")
        points.append(
            PriceHistoryPoint(
                period_label=f"Week {week}" if week is not None else "Period",
                captured_at=item.get("captured_at"),
                median_price=evidence.get("median_price") or evidence.get("median_active_price"),
                average_price=evidence.get("avg_price") or evidence.get("average_price"),
                card_signal_score=item.get("card_signal_score"),
            )
        )

    status = "coming_soon" if points else "empty"
    return PriceHistorySeries(
        series=points,
        period_labels=[p.period_label for p in points],
        chart_adapter="pending",
        status=status,
    )


def _build_outlook(snapshot: dict[str, Any]) -> CardOutlook:
    evidence_data = snapshot.get("evidence") or {}
    return build_card_outlook(
        stored_recommendation=snapshot.get("recommendation"),
        stored_evidence_tier=snapshot.get("conviction"),
        evidence_data=evidence_data,
        stored_risk=snapshot.get("risk"),
        stored_time_horizon=snapshot.get("time_horizon"),
        missing_inputs=snapshot.get("missing_inputs") or [],
        algorithm_version=snapshot.get("algorithm_version", "WEEKLY_INTELLIGENCE_V1"),
    )


def build_card_report(snapshot: dict[str, Any], history: list[dict[str, Any]] | None = None) -> CardReport:
    """Assemble a CardReport from the latest stored card weekly snapshot."""
    if not snapshot:
        raise ValueError("No card snapshot available.")

    cs_card_id = snapshot["cs_card_id"]
    parsed = parse_cs_card_id(cs_card_id)
    evidence_data = snapshot.get("evidence") or {}
    query_name = evidence_data.get("query_name") or parsed["query_name"]
    card_label = snapshot.get("card_label") or CARD_QUERY_LABELS.get(query_name, query_name)

    history = history or [snapshot]
    outlook = _build_outlook(snapshot)
    return CardReport(
        cs_card_id=cs_card_id,
        player_id=parsed["player_id"],
        sport=parsed["sport"],
        league=parsed["league"],
        player_name=snapshot.get("player_name"),
        card_label=card_label,
        card_identity=_resolve_card_identity(snapshot, query_name),
        card_score=snapshot.get("card_signal_score"),
        recommendation=outlook.recommendation,
        evidence=outlook.evidence,  # type: ignore[arg-type]
        status=snapshot.get("status"),
        market=_build_market(snapshot),
        population=_build_population(snapshot),
        price_history=_build_price_history(history),
        signal_drivers=[],
        market_drivers=_build_market_drivers(snapshot),
        scarcity_drivers=_build_scarcity_drivers(snapshot),
        outlook_summary=outlook.summary,
        outlook_evidence=outlook.supporting_evidence,
        risk=outlook.risk,
        time_horizon=outlook.time_horizon,
        market_activity_score=snapshot.get("market_activity_score"),
        demand_score=snapshot.get("demand_score"),
        momentum_score=snapshot.get("momentum_score"),
        scarcity_score=snapshot.get("scarcity_score"),
        missing_inputs=outlook.missing_inputs,
        updated_at=snapshot.get("captured_at"),
        algorithm_version=outlook.algorithm_version,
    )
