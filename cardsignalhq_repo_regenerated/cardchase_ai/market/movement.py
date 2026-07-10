"""Historical card-market movement calculations from append-only snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from cardchase_ai.models.schemas import CardMarketMovement

CARD_MARKET_MOVEMENT_ALGORITHM_VERSION = "card-market-movement-v1"

SUPPORTED_WINDOWS = frozenset({"previous", "7d", "30d"})


@dataclass(frozen=True)
class MovementToleranceConfig:
    tolerance_7d_days: int = 3
    tolerance_30d_days: int = 7
    max_gap_7d_days: int = 10
    max_gap_30d_days: int = 14


def _round_money(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 2)


def _round_pct(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 2)


def _safe_pct_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None:
        return None
    if previous == 0:
        return None
    return _round_pct(((current - previous) / previous) * 100)


def _safe_int_change(current: int | None, previous: int | None) -> int | None:
    if current is None or previous is None:
        return None
    return int(current) - int(previous)


def parse_captured_at(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        moment = value
    else:
        raw = str(value).strip()
        if not raw:
            return None
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            moment = datetime.fromisoformat(raw)
        except ValueError:
            return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def normalize_snapshot_row(snapshot: dict[str, Any]) -> dict[str, Any]:
    metrics = snapshot.get("metrics") or {}
    if metrics.get("active_listing_count") is None and snapshot.get("active_listing_count") is not None:
        metrics = snapshot

    captured_at = parse_captured_at(snapshot.get("captured_at") or snapshot.get("created_at"))
    if captured_at is None:
        raise ValueError("snapshot missing captured_at")

    return {
        "cs_card_id": str(snapshot.get("cs_card_id") or ""),
        "cs_player_id": str(snapshot.get("cs_player_id") or ""),
        "league": metrics.get("league") or snapshot.get("league") or "MLB",
        "source": str(snapshot.get("source") or "ebay"),
        "captured_at": captured_at,
        "algorithm_version": snapshot.get("algorithm_version") or metrics.get("algorithm_version") or "",
        "active_listing_count": int(metrics.get("active_listing_count") or 0),
        "auction_count": int(metrics.get("auction_count") or 0),
        "buy_it_now_count": int(metrics.get("buy_it_now_count") or 0),
        "listings_with_bids": int(metrics.get("listings_with_bids") or 0),
        "total_bid_count": int(metrics.get("total_bid_count") or 0),
        "average_price": metrics.get("average_price"),
        "median_price": metrics.get("median_price"),
        "minimum_price": metrics.get("minimum_price"),
        "maximum_price": metrics.get("maximum_price"),
        "sample_size": int(metrics.get("sample_size") or 0),
        "data_quality": str(metrics.get("data_quality") or "INSUFFICIENT").upper(),
        "currency": str(metrics.get("currency") or "USD").upper(),
    }


def sort_snapshots_asc(snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for snapshot in snapshots:
        try:
            normalized.append(normalize_snapshot_row(snapshot))
        except ValueError:
            continue
    return sorted(normalized, key=lambda row: row["captured_at"])


def _window_days(window: str) -> int | None:
    if window == "7d":
        return 7
    if window == "30d":
        return 30
    return None


def _max_gap_for_window(window: str, config: MovementToleranceConfig) -> int | None:
    if window == "7d":
        return config.max_gap_7d_days
    if window == "30d":
        return config.max_gap_30d_days
    return None


def _tolerance_for_window(window: str, config: MovementToleranceConfig) -> int:
    if window == "30d":
        return config.tolerance_30d_days
    return config.tolerance_7d_days


def find_comparison_snapshot(
    snapshots: list[dict[str, Any]],
    current: dict[str, Any],
    window: str,
    *,
    config: MovementToleranceConfig | None = None,
) -> tuple[dict[str, Any] | None, int | None]:
    """Return comparison snapshot and target gap in days (if applicable)."""
    config = config or MovementToleranceConfig()
    window = str(window or "7d").lower()
    ordered = sort_snapshots_asc(snapshots)
    current_at: datetime = current["captured_at"]
    source = current.get("source") or "ebay"

    same_source = [row for row in ordered if row.get("source") == source and row["captured_at"] < current_at]
    if not same_source:
        return None, None

    if window == "previous":
        return same_source[-1], None

    window_days = _window_days(window)
    if window_days is None:
        return None, None

    target_at = current_at - timedelta(days=window_days)
    candidates = [row for row in same_source if row["captured_at"] <= target_at]
    if not candidates:
        return None, window_days

    comparison = max(candidates, key=lambda row: row["captured_at"])
    gap_days = (target_at.date() - comparison["captured_at"].date()).days
    max_gap = _max_gap_for_window(window, config)
    if max_gap is not None and gap_days > max_gap:
        return None, gap_days
    return comparison, gap_days


def classify_movement_quality(
    *,
    current: dict[str, Any],
    previous: dict[str, Any] | None,
    window: str,
    target_gap_days: int | None,
    config: MovementToleranceConfig | None = None,
) -> str:
    config = config or MovementToleranceConfig()
    if previous is None:
        return "INSUFFICIENT"

    current_sample = int(current.get("sample_size") or 0)
    previous_sample = int(previous.get("sample_size") or 0)
    current_quality = str(current.get("data_quality") or "INSUFFICIENT").upper()
    previous_quality = str(previous.get("data_quality") or "INSUFFICIENT").upper()

    if current_sample < 2 or previous_sample < 2:
        return "INSUFFICIENT"

    gap_penalty = 0
    if window in {"7d", "30d"} and target_gap_days is not None:
        tolerance = _tolerance_for_window(window, config)
        if target_gap_days > tolerance:
            gap_penalty = 1
        if target_gap_days > tolerance * 2:
            gap_penalty = 2

    quality_rank = {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "INSUFFICIENT": 0}
    sample_rank = 2 if current_sample >= 10 and previous_sample >= 10 else 1 if current_sample >= 5 and previous_sample >= 5 else 0
    data_rank = min(quality_rank.get(current_quality, 0), quality_rank.get(previous_quality, 0))

    score = sample_rank + data_rank - gap_penalty
    if window == "previous":
        score += 0

    if score >= 5 and gap_penalty == 0:
        return "HIGH"
    if score >= 3:
        return "MEDIUM"
    if score >= 1:
        return "LOW"
    return "INSUFFICIENT"


def calculate_card_market_movement(
    snapshots: list[dict[str, Any]],
    *,
    window: str = "7d",
    config: MovementToleranceConfig | None = None,
) -> CardMarketMovement | None:
    config = config or MovementToleranceConfig()
    window = str(window or "7d").lower()
    if window not in SUPPORTED_WINDOWS:
        raise ValueError(f"Unsupported comparison window: {window}")

    ordered = sort_snapshots_asc(snapshots)
    if not ordered:
        return None

    current = ordered[-1]
    comparison, target_gap_days = find_comparison_snapshot(ordered, current, window, config=config)
    movement_quality = classify_movement_quality(
        current=current,
        previous=comparison,
        window=window,
        target_gap_days=target_gap_days,
        config=config,
    )

    if comparison is None or movement_quality == "INSUFFICIENT":
        return CardMarketMovement(
            cs_card_id=current["cs_card_id"],
            cs_player_id=current["cs_player_id"],
            current_captured_at=current["captured_at"],
            comparison_captured_at=None,
            comparison_window=window,
            current_median_price=_round_money(current.get("median_price")),
            current_average_price=_round_money(current.get("average_price")),
            sample_size_current=int(current.get("sample_size") or 0),
            current_data_quality=str(current.get("data_quality") or "INSUFFICIENT"),
            movement_quality="INSUFFICIENT",
            algorithm_version=CARD_MARKET_MOVEMENT_ALGORITHM_VERSION,
        )

    if str(current.get("currency") or "USD").upper() != str(comparison.get("currency") or "USD").upper():
        return CardMarketMovement(
            cs_card_id=current["cs_card_id"],
            cs_player_id=current["cs_player_id"],
            current_captured_at=current["captured_at"],
            comparison_captured_at=comparison["captured_at"],
            comparison_window=window,
            current_median_price=_round_money(current.get("median_price")),
            current_average_price=_round_money(current.get("average_price")),
            sample_size_current=int(current.get("sample_size") or 0),
            sample_size_previous=int(comparison.get("sample_size") or 0),
            current_data_quality=str(current.get("data_quality") or "INSUFFICIENT"),
            previous_data_quality=str(comparison.get("data_quality") or "INSUFFICIENT"),
            movement_quality="INSUFFICIENT",
            algorithm_version=CARD_MARKET_MOVEMENT_ALGORITHM_VERSION,
        )

    current_median = _round_money(current.get("median_price"))
    previous_median = _round_money(comparison.get("median_price"))
    current_average = _round_money(current.get("average_price"))
    previous_average = _round_money(comparison.get("average_price"))

    listing_change = _safe_int_change(current.get("active_listing_count"), comparison.get("active_listing_count"))
    bid_change = _safe_int_change(current.get("total_bid_count"), comparison.get("total_bid_count"))
    auction_change = _safe_int_change(current.get("auction_count"), comparison.get("auction_count"))

    return CardMarketMovement(
        cs_card_id=current["cs_card_id"],
        cs_player_id=current["cs_player_id"],
        current_captured_at=current["captured_at"],
        comparison_captured_at=comparison["captured_at"],
        comparison_window=window,
        current_median_price=current_median,
        previous_median_price=previous_median,
        median_price_change=_round_money(
            (current_median - previous_median) if current_median is not None and previous_median is not None else None
        ),
        median_price_change_pct=_safe_pct_change(current_median, previous_median),
        current_average_price=current_average,
        previous_average_price=previous_average,
        average_price_change=_round_money(
            (current_average - previous_average)
            if current_average is not None and previous_average is not None
            else None
        ),
        average_price_change_pct=_safe_pct_change(current_average, previous_average),
        listing_count_change=listing_change,
        listing_count_change_pct=_safe_pct_change(
            float(current.get("active_listing_count") or 0),
            float(comparison.get("active_listing_count") or 0),
        ),
        bid_count_change=bid_change,
        bid_count_change_pct=_safe_pct_change(
            float(current.get("total_bid_count") or 0),
            float(comparison.get("total_bid_count") or 0),
        ),
        auction_count_change=auction_change,
        sample_size_current=int(current.get("sample_size") or 0),
        sample_size_previous=int(comparison.get("sample_size") or 0),
        current_data_quality=str(current.get("data_quality") or "INSUFFICIENT"),
        previous_data_quality=str(comparison.get("data_quality") or "INSUFFICIENT"),
        movement_quality=movement_quality,
        algorithm_version=CARD_MARKET_MOVEMENT_ALGORITHM_VERSION,
    )


def movement_to_public_dict(movement: CardMarketMovement) -> dict[str, Any]:
    payload = movement.model_dump(mode="json")
    if movement.median_price_change_pct is None and movement.comparison_captured_at is None:
        payload["has_movement"] = False
    else:
        payload["has_movement"] = movement.movement_quality != "INSUFFICIENT" and movement.median_price_change_pct is not None
    return payload
