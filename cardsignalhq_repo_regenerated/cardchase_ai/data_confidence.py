"""Compute Data Confidence from stored signals only — never from recommendations."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from cardchase_ai.models.data_confidence import (
    DATA_CONFIDENCE_V1,
    MLB_PLAYER_SIGNAL_V1,
    ConfidenceApiResponse,
    DataConfidence,
    EvidenceSummary,
    ExplainabilityCategory,
    FreshnessInfo,
)
from cardchase_ai.models.weekly import CardWeeklyIntelligenceSnapshot, PlayerWeeklySignalSnapshot
from cardchase_ai.weekly_scoring import cs_player_id

# Freshness thresholds (minutes)
_LIVE_MAX = 60
_RECENT_MAX = 24 * 60
_CURRENT_MAX = 7 * 24 * 60

# Missing-input explanations — honest, keyed to stored missing_inputs only
_MISSING_MESSAGES: dict[str, str] = {
    "stats_7d": "Only one recent player snapshot available.",
    "stats_30d": "Season performance baseline is not yet available.",
    "market_snapshots": "Market activity has not been refreshed today.",
    "listing_volume": "Active listing volume is insufficient in stored snapshots.",
    "listings": "No active listings found in stored market snapshots.",
    "population": "Population data unavailable.",
    "registry": "Card registry data is still being linked.",
    "signal_drivers": "Signal driver inputs are pending.",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        text = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def compute_freshness_bucket(
    latest_at: datetime | None,
    *,
    now: datetime | None = None,
) -> FreshnessInfo:
    """Map latest snapshot timestamp to a freshness bucket. Unknown timestamps stay UNKNOWN."""
    if latest_at is None:
        return FreshnessInfo(bucket="UNKNOWN")

    reference = now or _utcnow()
    delta = reference - latest_at
    minutes = max(0, int(delta.total_seconds() / 60))

    if minutes < _LIVE_MAX:
        bucket = "LIVE"
    elif minutes < _RECENT_MAX:
        bucket = "RECENT"
    elif minutes < _CURRENT_MAX:
        bucket = "CURRENT"
    else:
        bucket = "STALE"

    return FreshnessInfo(
        bucket=bucket,
        freshness_minutes=minutes,
        latest_snapshot_at=latest_at,
    )


def _collect_timestamps(*values: Any) -> list[datetime]:
    timestamps: list[datetime] = []
    for value in values:
        parsed = _parse_timestamp(value)
        if parsed is not None:
            timestamps.append(parsed)
    return timestamps


def _explain_missing(missing_keys: list[str]) -> list[str]:
    messages: list[str] = []
    seen: set[str] = set()
    for key in missing_keys:
        if key in seen:
            continue
        seen.add(key)
        message = _MISSING_MESSAGES.get(key)
        if message:
            messages.append(message)
    return messages


def _count_signal_drivers(evidence: dict[str, Any]) -> int:
    count = 0
    for key in (
        "performance_reasons",
        "market_reasons",
        "collector_evidence",
        "momentum_evidence",
        "scarcity_evidence",
    ):
        items = evidence.get(key) or []
        if items:
            count += 1
    return count


def _category_status(
    available: bool,
    *,
    pending: bool = False,
) -> str:
    if available:
        return "available"
    if pending:
        return "pending"
    return "missing"


def _build_player_explainability(
    entry: dict[str, Any],
    weekly_snap: PlayerWeeklySignalSnapshot | None,
    evidence_summary: EvidenceSummary,
    missing_keys: list[str],
) -> list[ExplainabilityCategory]:
    missing_set = set(missing_keys)
    stats_7d = entry.get("stats_7d") or {}
    has_performance = bool(stats_7d.get("games", 0))
    has_market = evidence_summary.market_snapshots > 0
    has_collector = weekly_snap is not None and weekly_snap.collector_score is not None
    has_scarcity = weekly_snap is not None and weekly_snap.scarcity_score is not None
    has_drivers = evidence_summary.signal_drivers > 0
    market_snapshots = entry.get("market_snapshots") or {}

    return [
        ExplainabilityCategory(
            category="Performance",
            status=_category_status(has_performance, pending="stats_7d" in missing_set),
            detail="Stored player performance snapshots." if has_performance else None,
        ),
        ExplainabilityCategory(
            category="Market",
            status=_category_status(has_market, pending="market_snapshots" in missing_set),
            detail=f"{evidence_summary.market_snapshots} stored market snapshot(s)." if has_market else None,
        ),
        ExplainabilityCategory(
            category="Collector Demand",
            status=_category_status(has_collector, pending="listing_volume" in missing_set),
        ),
        ExplainabilityCategory(
            category="Scarcity",
            status=_category_status(
                has_scarcity or evidence_summary.population_available,
                pending="population" in missing_set,
            ),
        ),
        ExplainabilityCategory(
            category="Signal Drivers",
            status=_category_status(has_drivers, pending="signal_drivers" in missing_set),
            detail=f"{evidence_summary.signal_drivers} signal driver group(s)." if has_drivers else None,
        ),
        ExplainabilityCategory(
            category="Registry",
            status=_category_status(bool(market_snapshots), pending=not market_snapshots),
        ),
    ]


def _build_card_explainability(
    card_snap: CardWeeklyIntelligenceSnapshot | None,
    evidence_summary: EvidenceSummary,
    missing_keys: list[str],
    *,
    registry_linked: bool,
) -> list[ExplainabilityCategory]:
    missing_set = set(missing_keys)
    evidence = (card_snap.evidence if card_snap else {}) or {}

    return [
        ExplainabilityCategory(
            category="Performance",
            status="pending",
            detail="Card reports use market and registry evidence.",
        ),
        ExplainabilityCategory(
            category="Market",
            status=_category_status(
                evidence_summary.market_snapshots > 0 or bool(evidence.get("listings_count")),
                pending="listings" in missing_set or "market_snapshots" in missing_set,
            ),
        ),
        ExplainabilityCategory(
            category="Collector Demand",
            status=_category_status(
                card_snap is not None and card_snap.demand_score is not None,
                pending="listing_volume" in missing_set,
            ),
        ),
        ExplainabilityCategory(
            category="Scarcity",
            status=_category_status(
                evidence_summary.population_available or (card_snap and card_snap.scarcity_score is not None),
                pending="population" in missing_set,
            ),
        ),
        ExplainabilityCategory(
            category="Signal Drivers",
            status=_category_status(evidence_summary.signal_drivers > 0),
        ),
        ExplainabilityCategory(
            category="Registry",
            status=_category_status(registry_linked, pending="registry" in missing_set),
        ),
    ]


def _score_to_level(score: float, missing_count: int) -> str:
    if missing_count >= 3 or score < 20:
        return "INSUFFICIENT"
    if score >= 85 and missing_count == 0:
        return "VERY_HIGH"
    if score >= 70:
        return "HIGH"
    if score >= 45:
        return "MEDIUM"
    return "LOW"


def _compute_confidence_score(
    *,
    snapshot_count: int,
    market_count: int,
    signal_drivers: int,
    population_available: bool,
    registry_linked: bool,
    missing_count: int,
    freshness_bucket: str,
) -> float:
    """Internal scoring from stored evidence counts — weights are not exposed via API."""
    score = 0.0
    score += min(snapshot_count * 8, 32)
    score += min(market_count * 5, 25)
    score += min(signal_drivers * 6, 18)
    if population_available:
        score += 10
    if registry_linked:
        score += 8
    score -= missing_count * 7

    freshness_bonus = {"LIVE": 12, "RECENT": 8, "CURRENT": 4, "STALE": 0, "UNKNOWN": 0}
    score += freshness_bonus.get(freshness_bucket, 0)

    return max(0.0, min(100.0, round(score, 2)))


def _player_evidence_summary(
    entry: dict[str, Any],
    weekly_snap: PlayerWeeklySignalSnapshot | None,
    player_history: list[dict[str, Any] | PlayerWeeklySignalSnapshot],
) -> EvidenceSummary:
    market_snapshots = entry.get("market_snapshots") or {}
    market_count = len(market_snapshots) if isinstance(market_snapshots, dict) else 0
    evidence = (weekly_snap.evidence if weekly_snap else {}) or {}

    auction_count = 0
    for snap in market_snapshots.values() if isinstance(market_snapshots, dict) else []:
        if isinstance(snap, dict):
            auction_count += int(snap.get("listings_count") or 0)
        else:
            auction_count += int(getattr(snap, "listings_count", 0) or 0)

    tags = evidence.get("tags") or {}
    population_available = bool(tags.get("psa10_count") is not None)

    snapshot_count = len(player_history) if player_history else (1 if weekly_snap else 0)
    signal_drivers = _count_signal_drivers(evidence)

    sources = sum(
        1
        for flag in (
            snapshot_count > 0,
            market_count > 0,
            signal_drivers > 0,
            population_available,
        )
        if flag
    )

    return EvidenceSummary(
        player_snapshots=snapshot_count,
        market_snapshots=market_count,
        signal_drivers=signal_drivers,
        auction_observations=auction_count,
        registry_linked=market_count > 0,
        population_available=population_available,
        source_count=sources,
    )


def _card_evidence_summary(
    card_snap: CardWeeklyIntelligenceSnapshot | None,
    card_history: list[dict[str, Any] | CardWeeklyIntelligenceSnapshot],
    *,
    registry_linked: bool = False,
) -> EvidenceSummary:
    evidence = (card_snap.evidence if card_snap else {}) or {}
    tags = evidence.get("tags") or {}
    listings = int(evidence.get("listings_count") or 0)
    population_available = tags.get("psa10_count") is not None

    snapshot_count = len(card_history) if card_history else (1 if card_snap else 0)
    signal_drivers = _count_signal_drivers(evidence)
    market_count = 1 if listings > 0 or card_snap else 0

    sources = sum(
        1
        for flag in (
            snapshot_count > 0,
            market_count > 0,
            signal_drivers > 0,
            population_available,
            registry_linked,
        )
        if flag
    )

    return EvidenceSummary(
        player_snapshots=0,
        market_snapshots=market_count,
        signal_drivers=signal_drivers,
        auction_observations=listings,
        registry_linked=registry_linked,
        population_available=bool(population_available),
        source_count=sources,
    )


def build_player_confidence(
    player_id: str,
    entry: dict[str, Any],
    weekly_snap: PlayerWeeklySignalSnapshot | None,
    player_history: list[dict[str, Any] | PlayerWeeklySignalSnapshot] | None = None,
) -> ConfidenceApiResponse:
    """Build player data confidence from stored signals. Never uses recommendation."""
    history = player_history or []
    if weekly_snap and not any(
        getattr(h, "snapshot_id", h.get("snapshot_id") if isinstance(h, dict) else None) == weekly_snap.snapshot_id
        for h in history
    ):
        history = list(history) + [weekly_snap]

    csp_id = player_id if ":" in str(player_id) else cs_player_id(player_id)
    evidence_summary = _player_evidence_summary(entry, weekly_snap, history)

    missing_keys = list((weekly_snap.missing_inputs if weekly_snap else []) or [])
    missing_messages = _explain_missing(missing_keys)

    timestamps = _collect_timestamps(
        weekly_snap.captured_at if weekly_snap else None,
        entry.get("generated_at"),
        *(h.get("captured_at") if isinstance(h, dict) else getattr(h, "captured_at", None) for h in history),
    )
    latest_at = max(timestamps) if timestamps else None
    oldest_at = min(timestamps) if timestamps else None

    freshness = compute_freshness_bucket(latest_at)
    freshness.oldest_snapshot_at = oldest_at

    stale_inputs: list[str] = []
    if freshness.bucket == "STALE":
        stale_inputs.append("market_snapshots")

    confidence_score = _compute_confidence_score(
        snapshot_count=evidence_summary.player_snapshots,
        market_count=evidence_summary.market_snapshots,
        signal_drivers=evidence_summary.signal_drivers,
        population_available=evidence_summary.population_available,
        registry_linked=evidence_summary.registry_linked,
        missing_count=len(missing_keys),
        freshness_bucket=freshness.bucket,
    )
    confidence_level = _score_to_level(confidence_score, len(missing_keys))

    algorithm_version = (
        weekly_snap.algorithm_version if weekly_snap else entry.get("algorithm_version") or MLB_PLAYER_SIGNAL_V1
    )

    explainability = _build_player_explainability(entry, weekly_snap, evidence_summary, missing_keys)

    evidence_count = (
        evidence_summary.player_snapshots
        + evidence_summary.market_snapshots
        + evidence_summary.signal_drivers
    )

    confidence = DataConfidence(
        confidence_id=str(uuid.uuid4()),
        entity_type="player",
        entity_id=csp_id,
        model_version=DATA_CONFIDENCE_V1,
        confidence_level=confidence_level,
        confidence_score=confidence_score,
        evidence_count=evidence_count,
        source_count=evidence_summary.source_count,
        snapshot_count=evidence_summary.player_snapshots,
        latest_snapshot_at=latest_at,
        oldest_snapshot_at=oldest_at,
        freshness_minutes=freshness.freshness_minutes,
        freshness_bucket=freshness.bucket,
        missing_inputs=missing_messages,
        stale_inputs=stale_inputs,
        algorithm_version=algorithm_version,
        generated_at=_utcnow(),
        evidence_summary=evidence_summary,
        explainability=explainability,
    )

    trust_summary = _build_trust_summary(confidence, evidence_summary)

    return ConfidenceApiResponse(
        entity_type="player",
        entity_id=csp_id,
        confidence=confidence,
        freshness=freshness,
        evidence_summary=evidence_summary,
        missing_inputs=missing_messages,
        explainability=explainability,
        trust_summary=trust_summary,
        model_version=DATA_CONFIDENCE_V1,
    )


def build_card_confidence(
    cs_card_id: str,
    card_snap: CardWeeklyIntelligenceSnapshot | None,
    card_history: list[dict[str, Any] | CardWeeklyIntelligenceSnapshot] | None = None,
    *,
    registry_linked: bool = False,
) -> ConfidenceApiResponse:
    """Build card data confidence from stored signals. Never uses recommendation."""
    history = card_history or []
    if card_snap and not any(
        getattr(h, "snapshot_id", h.get("snapshot_id") if isinstance(h, dict) else None) == card_snap.snapshot_id
        for h in history
    ):
        history = list(history) + [card_snap]

    evidence_summary = _card_evidence_summary(card_snap, history, registry_linked=registry_linked)

    missing_keys = list((card_snap.missing_inputs if card_snap else []) or [])
    if not registry_linked and "registry" not in missing_keys:
        missing_keys.append("registry")
    missing_messages = _explain_missing(missing_keys)

    timestamps = _collect_timestamps(
        card_snap.captured_at if card_snap else None,
        *(h.get("captured_at") if isinstance(h, dict) else getattr(h, "captured_at", None) for h in history),
    )
    latest_at = max(timestamps) if timestamps else None
    oldest_at = min(timestamps) if timestamps else None

    freshness = compute_freshness_bucket(latest_at)
    freshness.oldest_snapshot_at = oldest_at

    stale_inputs: list[str] = []
    if freshness.bucket == "STALE":
        stale_inputs.append("market_snapshots")

    confidence_score = _compute_confidence_score(
        snapshot_count=evidence_summary.player_snapshots + len(history),
        market_count=evidence_summary.market_snapshots,
        signal_drivers=evidence_summary.signal_drivers,
        population_available=evidence_summary.population_available,
        registry_linked=registry_linked,
        missing_count=len(missing_keys),
        freshness_bucket=freshness.bucket,
    )
    confidence_level = _score_to_level(confidence_score, len(missing_keys))

    algorithm_version = (card_snap.algorithm_version if card_snap else MLB_PLAYER_SIGNAL_V1)

    explainability = _build_card_explainability(card_snap, evidence_summary, missing_keys, registry_linked=registry_linked)

    evidence_count = evidence_summary.market_snapshots + evidence_summary.signal_drivers + len(history)

    confidence = DataConfidence(
        confidence_id=str(uuid.uuid4()),
        entity_type="card",
        entity_id=cs_card_id,
        model_version=DATA_CONFIDENCE_V1,
        confidence_level=confidence_level,
        confidence_score=confidence_score,
        evidence_count=evidence_count,
        source_count=evidence_summary.source_count,
        snapshot_count=len(history) if history else (1 if card_snap else 0),
        latest_snapshot_at=latest_at,
        oldest_snapshot_at=oldest_at,
        freshness_minutes=freshness.freshness_minutes,
        freshness_bucket=freshness.bucket,
        missing_inputs=missing_messages,
        stale_inputs=stale_inputs,
        algorithm_version=algorithm_version,
        generated_at=_utcnow(),
        evidence_summary=evidence_summary,
        explainability=explainability,
    )

    trust_summary = _build_trust_summary(confidence, evidence_summary)

    return ConfidenceApiResponse(
        entity_type="card",
        entity_id=cs_card_id,
        confidence=confidence,
        freshness=freshness,
        evidence_summary=evidence_summary,
        missing_inputs=missing_messages,
        explainability=explainability,
        trust_summary=trust_summary,
        model_version=DATA_CONFIDENCE_V1,
    )


def _build_trust_summary(confidence: DataConfidence, evidence: EvidenceSummary) -> dict[str, Any]:
    verified: list[str] = []
    if evidence.player_snapshots:
        label = "player snapshot" if evidence.player_snapshots == 1 else "player snapshots"
        verified.append(f"{evidence.player_snapshots} {label}")
    if evidence.market_snapshots:
        label = "market snapshot" if evidence.market_snapshots == 1 else "market snapshots"
        verified.append(f"{evidence.market_snapshots} {label}")
    if evidence.signal_drivers:
        label = "Signal Driver" if evidence.signal_drivers == 1 else "Signal Drivers"
        verified.append(f"{evidence.signal_drivers} {label}")
    if evidence.registry_linked:
        verified.append("Card Registry")
    if evidence.population_available:
        verified.append("Population data")

    latest_label = None
    if confidence.freshness_minutes is not None:
        minutes = confidence.freshness_minutes
        if minutes < 60:
            latest_label = f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif minutes < 24 * 60:
            hours = minutes // 60
            latest_label = f"{hours} hour{'s' if hours != 1 else ''} ago"
        else:
            days = minutes // (24 * 60)
            latest_label = f"{days} day{'s' if days != 1 else ''} ago"

    return {
        "verified_using": verified,
        "latest_update": latest_label,
        "model": confidence.algorithm_version,
        "evidence_level": confidence.confidence_level,
        "freshness": confidence.freshness_bucket,
    }


def confidence_response_to_public_dict(response: ConfidenceApiResponse) -> dict[str, Any]:
    """Serialize for API — no internal weighting or formula details."""
    payload = response.model_dump(mode="json")
    confidence = payload.get("confidence") or {}
    evidence = confidence.get("evidence") or {}
    evidence.pop("confidence_multiplier", None)
    for key in list(evidence.keys()):
        if "weight" in key.lower() or "percent" in key.lower():
            evidence.pop(key, None)
    return payload
