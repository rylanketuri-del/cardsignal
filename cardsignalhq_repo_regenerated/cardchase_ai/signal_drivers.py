"""Signal Driver generation from stored evidence only."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

from cardchase_ai.development_provider import PlayerDevelopmentProvider, StoredDevelopmentProvider
from cardchase_ai.models.schemas import MarketSnapshot, RollingHitterStats
from cardchase_ai.models.signal_driver import (
    SIGNAL_DRIVERS_V1,
    DriverType,
    EvidenceQuality,
    Impact,
    SeasonState,
    SignalDriver,
    SourceType,
)
from cardchase_ai.season_state import SPORT_DRIVER_CONFIG, resolve_season_state
from cardchase_ai.weekly_scoring import cs_player_id

RECENT_FORM_METRICS: list[tuple[str, str, str, int]] = [
    ("avg", "AVG", "batting average", 3),
    ("obp", "OBP", "on-base percentage", 3),
    ("slg", "SLG", "slugging percentage", 3),
    ("ops", "OPS", "on-base plus slugging", 3),
]

COUNT_METRICS: list[tuple[str, str, str]] = [
    ("home_runs", "HR", "home runs"),
    ("rbi", "RBI", "runs batted in"),
    ("hits", "Hits", "hits"),
    ("stolen_bases", "SB", "stolen bases"),
    ("walks", "BB", "walks"),
]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _driver_id(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]


def _deterministic_impact(delta: float, *, threshold: float = 0.001) -> Impact:
    if delta > threshold:
        return "POSITIVE"
    if delta < -threshold:
        return "NEGATIVE"
    return "NEUTRAL"


def _performance_evidence_quality(
    recent: RollingHitterStats,
    baseline: RollingHitterStats,
) -> EvidenceQuality:
    if recent.games == 0 or baseline.games == 0:
        return "INSUFFICIENT"
    if recent.games >= 3 and baseline.games >= 10:
        return "HIGH"
    if recent.games >= 1 and baseline.games >= 5:
        return "MEDIUM"
    return "LOW"


def _build_base_driver(
    *,
    cs_id: str,
    source_player_id: str,
    league: str,
    sport: str,
    driver_type: DriverType,
    category: str,
    title: str,
    summary: str,
    metric_name: str | None,
    metric_value: float | str | None,
    comparison_value: float | str | None,
    impact: Impact,
    evidence_quality: EvidenceQuality,
    source_type: SourceType,
    source_reference: str,
    occurred_at: datetime,
    expires_days: int | None = 7,
    metadata: dict[str, Any] | None = None,
) -> SignalDriver:
    captured_at = _utcnow()
    expires_at = captured_at + timedelta(days=expires_days) if expires_days else None
    driver = SignalDriver(
        driver_id="",
        cs_player_id=cs_id,
        source_player_id=str(source_player_id),
        league=league.upper(),
        sport=sport.upper(),
        driver_type=driver_type,
        category=category,  # type: ignore[arg-type]
        title=title,
        summary=summary,
        metric_name=metric_name,
        metric_value=metric_value,
        comparison_value=comparison_value,
        impact=impact,
        evidence_quality=evidence_quality,
        source_type=source_type,
        source_reference=source_reference,
        occurred_at=occurred_at,
        captured_at=captured_at,
        expires_at=expires_at,
        algorithm_version=SIGNAL_DRIVERS_V1,
        metadata=metadata or {},
    )
    driver.driver_id = _driver_id(driver.identity_key())
    return driver


def build_mlb_recent_form_drivers(
    *,
    player_name: str,
    source_player_id: str | int,
    stats_7d: RollingHitterStats,
    stats_30d: RollingHitterStats,
    captured_at: datetime | None = None,
    season: int | None = None,
) -> list[SignalDriver]:
    """Create MLB recent-form drivers from stored 7d vs 30d statistics."""
    if stats_7d.games == 0:
        return []

    cs_id = cs_player_id(source_player_id, "MLB")
    occurred_at = captured_at or _utcnow()
    evidence = _performance_evidence_quality(stats_7d, stats_30d)
    drivers: list[SignalDriver] = []

    for field, label, description, decimals in RECENT_FORM_METRICS:
        recent_val = getattr(stats_7d, field, None)
        baseline_val = getattr(stats_30d, field, None)
        if recent_val is None or baseline_val is None:
            continue
        if stats_30d.games == 0:
            eq: EvidenceQuality = "INSUFFICIENT"
            impact: Impact = "UNKNOWN"
        else:
            eq = evidence
            impact = _deterministic_impact(float(recent_val) - float(baseline_val))

        direction = "above" if impact == "POSITIVE" else "below" if impact == "NEGATIVE" else "in line with"
        title = "Recent batting surge" if field == "ops" and impact == "POSITIVE" else f"Recent {label} form"
        summary = (
            f"{player_name}'s 7-day {label} is {direction} the 30-day baseline "
            f"({float(recent_val):.{decimals}f} vs {float(baseline_val):.{decimals}f})."
        )

        drivers.append(
            _build_base_driver(
                cs_id=cs_id,
                source_player_id=str(source_player_id),
                league="MLB",
                sport="MLB",
                driver_type="RECENT_FORM",
                category="PERFORMANCE",
                title=title,
                summary=summary,
                metric_name=field,
                metric_value=round(float(recent_val), decimals),
                comparison_value=round(float(baseline_val), decimals) if stats_30d.games > 0 else None,
                impact=impact,
                evidence_quality=eq,
                source_type="PERFORMANCE_SNAPSHOT",
                source_reference=f"stats_7d_vs_30d:{season or 'current'}",
                occurred_at=occurred_at,
                metadata={"description": description, "window_days": 7, "baseline_days": 30},
            )
        )

    for field, label, description in COUNT_METRICS:
        count = getattr(stats_7d, field, 0)
        if not count or count <= 0:
            continue
        title = "Power production" if field == "home_runs" else f"{label} production"
        summary = f"{int(count)} {description} recorded during the current 7-day recent-form window."
        drivers.append(
            _build_base_driver(
                cs_id=cs_id,
                source_player_id=str(source_player_id),
                league="MLB",
                sport="MLB",
                driver_type="RECENT_FORM",
                category="PERFORMANCE",
                title=title,
                summary=summary,
                metric_name=field,
                metric_value=int(count),
                comparison_value=None,
                impact="POSITIVE" if count > 0 else "NEUTRAL",
                evidence_quality=evidence if stats_7d.games > 0 else "INSUFFICIENT",
                source_type="PERFORMANCE_SNAPSHOT",
                source_reference=f"stats_7d:{season or 'current'}",
                occurred_at=occurred_at,
                metadata={"description": description, "window_days": 7},
            )
        )

    # Strikeout rate when both windows have at-bats
    if stats_7d.at_bats > 0:
        k_rate_7d = stats_7d.strikeouts / stats_7d.at_bats
        if stats_30d.at_bats > 0:
            k_rate_30d = stats_30d.strikeouts / stats_30d.at_bats
            impact = _deterministic_impact(k_rate_30d - k_rate_7d)  # lower K rate is positive
            eq = evidence
            summary = (
                f"{player_name}'s 7-day strikeout rate is "
                f"{k_rate_7d:.3f} vs {k_rate_30d:.3f} over the 30-day baseline."
            )
        else:
            impact = "UNKNOWN"
            eq = "INSUFFICIENT"
            summary = f"{player_name}'s 7-day strikeout rate is {k_rate_7d:.3f}; baseline unavailable."

        drivers.append(
            _build_base_driver(
                cs_id=cs_id,
                source_player_id=str(source_player_id),
                league="MLB",
                sport="MLB",
                driver_type="RECENT_FORM",
                category="PERFORMANCE",
                title="Plate discipline",
                summary=summary,
                metric_name="strikeout_rate",
                metric_value=round(k_rate_7d, 3),
                comparison_value=round(k_rate_30d, 3) if stats_30d.at_bats > 0 else None,
                impact=impact,
                evidence_quality=eq,
                source_type="PERFORMANCE_SNAPSHOT",
                source_reference=f"stats_7d_vs_30d:{season or 'current'}",
                occurred_at=occurred_at,
                metadata={"window_days": 7, "baseline_days": 30},
            )
        )

    return drivers


def build_mlb_season_performance_driver(
    *,
    player_name: str,
    source_player_id: str | int,
    stats_30d: RollingHitterStats,
    season: int,
    captured_at: datetime | None = None,
) -> SignalDriver | None:
    if stats_30d.games == 0:
        return None

    cs_id = cs_player_id(source_player_id, "MLB")
    occurred_at = captured_at or _utcnow()
    return _build_base_driver(
        cs_id=cs_id,
        source_player_id=str(source_player_id),
        league="MLB",
        sport="MLB",
        driver_type="SEASON_PERFORMANCE",
        category="PERFORMANCE",
        title="Season production snapshot",
        summary=(
            f"{player_name}'s stored season window shows {stats_30d.games} games, "
            f"{stats_30d.home_runs} HR, {stats_30d.ops:.3f} OPS."
        ),
        metric_name="ops",
        metric_value=round(stats_30d.ops, 3),
        comparison_value=stats_30d.games,
        impact="NEUTRAL",
        evidence_quality="HIGH" if stats_30d.games >= 10 else "MEDIUM" if stats_30d.games >= 5 else "LOW",
        source_type="PERFORMANCE_SNAPSHOT",
        source_reference=f"stats_30d:{season}",
        occurred_at=occurred_at,
        expires_days=30,
        metadata={"season": season, "games": stats_30d.games},
    )


def build_mlb_previous_season_driver(
    *,
    player_name: str,
    source_player_id: str | int,
    stats_30d: RollingHitterStats,
    season: int,
    captured_at: datetime | None = None,
) -> SignalDriver | None:
    """Previous-season snapshot for offseason presentation."""
    if stats_30d.games == 0:
        return None

    cs_id = cs_player_id(source_player_id, "MLB")
    occurred_at = captured_at or _utcnow()
    return _build_base_driver(
        cs_id=cs_id,
        source_player_id=str(source_player_id),
        league="MLB",
        sport="MLB",
        driver_type="SEASON_PERFORMANCE",
        category="PERFORMANCE",
        title="Previous season snapshot",
        summary=(
            f"{player_name}'s previous-season stored snapshot ({season}): "
            f"{stats_30d.games} games, {stats_30d.home_runs} HR, {stats_30d.ops:.3f} OPS."
        ),
        metric_name="ops",
        metric_value=round(stats_30d.ops, 3),
        comparison_value=stats_30d.games,
        impact="NEUTRAL",
        evidence_quality="HIGH" if stats_30d.games >= 10 else "MEDIUM",
        source_type="PERFORMANCE_SNAPSHOT",
        source_reference=f"previous_season:{season}",
        occurred_at=occurred_at,
        expires_days=None,
        metadata={"season": season, "label": "previous_season"},
    )


def build_market_drivers(
    *,
    player_name: str,
    source_player_id: str | int,
    league: str,
    market_snapshots: dict[str, MarketSnapshot],
    captured_at: datetime | None = None,
) -> list[SignalDriver]:
    if not market_snapshots:
        return []

    cs_id = cs_player_id(source_player_id, league)
    occurred_at = captured_at or _utcnow()
    drivers: list[SignalDriver] = []
    total_listings = sum(s.listings_count for s in market_snapshots.values())
    avg_prices = [s.avg_price for s in market_snapshots.values() if s.avg_price is not None]

    if total_listings > 0:
        drivers.append(
            _build_base_driver(
                cs_id=cs_id,
                source_player_id=str(source_player_id),
                league=league,
                sport=league,
                driver_type="LISTING_SUPPLY",
                category="MARKET",
                title="Active listing supply",
                summary=f"{total_listings} active listings tracked across stored market snapshots for {player_name}.",
                metric_name="listings_count",
                metric_value=total_listings,
                comparison_value=None,
                impact="NEUTRAL",
                evidence_quality="HIGH" if total_listings >= 10 else "MEDIUM" if total_listings >= 3 else "LOW",
                source_type="MARKET_SNAPSHOT",
                source_reference="market_snapshots:aggregate",
                occurred_at=occurred_at,
                expires_days=14,
            )
        )

    psa10 = sum(s.tags.psa10_count for s in market_snapshots.values())
    if psa10 > 0:
        drivers.append(
            _build_base_driver(
                cs_id=cs_id,
                source_player_id=str(source_player_id),
                league=league,
                sport=league,
                driver_type="SCARCITY_CHANGE",
                category="MARKET",
                title="PSA 10 listing presence",
                summary=f"{psa10} PSA 10 listings observed in stored market snapshots for {player_name}.",
                metric_name="psa10_listings",
                metric_value=psa10,
                comparison_value=total_listings,
                impact="NEUTRAL",
                evidence_quality="HIGH" if psa10 >= 3 else "MEDIUM",
                source_type="MARKET_SNAPSHOT",
                source_reference="market_snapshots:psa10",
                occurred_at=occurred_at,
                expires_days=14,
            )
        )

    if avg_prices:
        median_price = sorted(avg_prices)[len(avg_prices) // 2]
        drivers.append(
            _build_base_driver(
                cs_id=cs_id,
                source_player_id=str(source_player_id),
                league=league,
                sport=league,
                driver_type="PRICE_MOVEMENT",
                category="MARKET",
                title="Stored median active price",
                summary=f"Median active listing price across stored snapshots: ${median_price:,.0f}.",
                metric_name="median_active_price",
                metric_value=median_price,
                comparison_value=None,
                impact="NEUTRAL",
                evidence_quality="MEDIUM",
                source_type="MARKET_SNAPSHOT",
                source_reference="market_snapshots:pricing",
                occurred_at=occurred_at,
                expires_days=14,
            )
        )

    return drivers


def build_development_drivers(
    provider: PlayerDevelopmentProvider,
    *,
    cs_player_id: str,
    source_player_id: str,
    league: str,
    sport: str | None = None,
) -> list[SignalDriver]:
    drivers: list[SignalDriver] = []
    for raw in provider.fetch_player_developments(cs_player_id, source_player_id, league):
        valid, _reason = provider.validate_development(raw)
        if not valid:
            continue
        normalized = provider.normalize_development(
            raw,
            cs_player_id=cs_player_id,
            source_player_id=source_player_id,
            league=league,
            sport=sport,
        )
        if normalized:
            drivers.append(normalized)
    return drivers


def build_player_signal_drivers(
    *,
    player_name: str,
    source_player_id: str | int,
    league: str = "MLB",
    stats_7d: RollingHitterStats | None = None,
    stats_30d: RollingHitterStats | None = None,
    market_snapshots: dict[str, MarketSnapshot] | None = None,
    season: int | None = None,
    season_state: SeasonState | None = None,
    development_provider: PlayerDevelopmentProvider | None = None,
    captured_at: datetime | None = None,
) -> list[SignalDriver]:
    """Build all applicable drivers for a player from stored evidence."""
    league = league.upper()
    if league not in {"MLB"}:
        # NBA/NFL prepared but not active — no fabricated data
        return []

    stats_7d = stats_7d or RollingHitterStats()
    stats_30d = stats_30d or RollingHitterStats()
    market_snapshots = market_snapshots or {}
    state = season_state or "REGULAR_SEASON"
    drivers: list[SignalDriver] = []

    active_states = {"REGULAR_SEASON", "POSTSEASON", "PRESEASON"}
    offseason_states = {"OFFSEASON", "INACTIVE", "UNKNOWN"}

    if state in active_states and stats_7d.games > 0:
        drivers.extend(
            build_mlb_recent_form_drivers(
                player_name=player_name,
                source_player_id=source_player_id,
                stats_7d=stats_7d,
                stats_30d=stats_30d,
                captured_at=captured_at,
                season=season,
            )
        )
        season_driver = build_mlb_season_performance_driver(
            player_name=player_name,
            source_player_id=source_player_id,
            stats_30d=stats_30d,
            season=season or 0,
            captured_at=captured_at,
        )
        if season_driver:
            drivers.append(season_driver)

    if state in offseason_states:
        prev = build_mlb_previous_season_driver(
            player_name=player_name,
            source_player_id=source_player_id,
            stats_30d=stats_30d,
            season=season or 0,
            captured_at=captured_at,
        )
        if prev:
            drivers.append(prev)

    drivers.extend(
        build_market_drivers(
            player_name=player_name,
            source_player_id=source_player_id,
            league=league,
            market_snapshots=market_snapshots,
            captured_at=captured_at,
        )
    )

    provider = development_provider or StoredDevelopmentProvider()
    cs_id = cs_player_id(source_player_id, league)
    drivers.extend(
        build_development_drivers(
            provider,
            cs_player_id=cs_id,
            source_player_id=str(source_player_id),
            league=league,
            sport=league,
        )
    )

    return drivers


def filter_current_drivers(
    drivers: list[SignalDriver],
    *,
    now: datetime | None = None,
) -> list[SignalDriver]:
    now = now or _utcnow()
    current: list[SignalDriver] = []
    for driver in drivers:
        if driver.expires_at is not None and _ensure_aware(driver.expires_at) < now:
            continue
        current.append(driver)
    return current


def _ensure_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def group_drivers_by_category(
    drivers: list[SignalDriver],
    season_state: SeasonState,
) -> dict[str, list[SignalDriver]]:
    """Group drivers for Scouting Report presentation."""
    groups: dict[str, list[SignalDriver]] = {
        "recent_performance": [],
        "season_context": [],
        "market_drivers": [],
        "career_team": [],
        "previous_season": [],
        "latest_developments": [],
        "scarcity_drivers": [],
    }

    for driver in drivers:
        if driver.category == "MARKET":
            if driver.driver_type in {"SCARCITY_CHANGE", "POPULATION_MOVEMENT"}:
                groups["scarcity_drivers"].append(driver)
            else:
                groups["market_drivers"].append(driver)
        elif driver.category == "PERFORMANCE":
            if driver.metadata.get("label") == "previous_season" or "previous_season" in driver.source_reference:
                groups["previous_season"].append(driver)
            elif driver.driver_type == "RECENT_FORM":
                groups["recent_performance"].append(driver)
            else:
                groups["season_context"].append(driver)
        elif driver.category in {"CAREER", "TEAM", "AVAILABILITY", "OTHER"}:
            groups["latest_developments"].append(driver)
            groups["career_team"].append(driver)

    if season_state in {"OFFSEASON", "INACTIVE", "UNKNOWN"}:
        # Offseason: emphasize previous season, developments, market, scarcity
        groups["recent_performance"] = []

    return groups
