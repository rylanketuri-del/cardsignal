"""Historical market movement from stored snapshots only."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cardchase_ai.models.market_movement import CardMarketMovement, MovementStatus
from cardchase_ai.models.schemas import MarketSnapshot
from cardchase_ai.weekly_scoring import cs_card_id, cs_player_id

MOVEMENT_PENDING_LABEL = "Movement pending"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def calculate_price_change_pct(current: float | None, prior: float | None) -> float | None:
    if current is None or prior is None:
        return None
    if prior == 0:
        return None
    return round(((current - prior) / prior) * 100, 2)


def calculate_movement(
    *,
    source_player_id: str,
    query_name: str,
    league: str,
    run_id: str,
    year: int,
    week_number: int,
    current: MarketSnapshot,
    prior: dict[str, Any] | None,
    currency: str = "USD",
    captured_at: datetime | None = None,
) -> CardMarketMovement:
    csp = cs_player_id(source_player_id, league)
    card_id = cs_card_id(source_player_id, query_name, league)

    base = CardMarketMovement(
        cs_player_id=csp,
        cs_card_id=card_id,
        query_name=query_name,
        run_id=run_id,
        league=league.upper() if len(league) <= 4 else league,
        year=year,
        week_number=week_number,
        current_avg_price=current.avg_price,
        current_listings_count=current.listings_count,
        currency=currency,
        captured_at=captured_at or _utcnow(),
    )

    if prior is None:
        return base.model_copy(update={"status": "pending", "label": MOVEMENT_PENDING_LABEL})

    prior_price = prior.get("avg_price")
    prior_count = prior.get("listings_count")
    prior_currency = prior.get("currency") or "USD"

    if prior_currency and currency and prior_currency.upper() != currency.upper():
        return base.model_copy(
            update={
                "prior_avg_price": prior_price,
                "prior_listings_count": prior_count,
                "prior_currency": prior_currency,
                "status": "unavailable",
                "label": MOVEMENT_PENDING_LABEL,
                "evidence": {"reason": "currency_mismatch"},
            }
        )

    price_change = calculate_price_change_pct(current.avg_price, prior_price)
    listings_change = None
    if prior_count is not None:
        listings_change = current.listings_count - int(prior_count)

    if current.avg_price is None or prior_price is None:
        return base.model_copy(
            update={
                "prior_avg_price": prior_price,
                "prior_listings_count": prior_count,
                "prior_currency": prior_currency,
                "listings_change": listings_change,
                "status": "pending",
                "label": MOVEMENT_PENDING_LABEL,
                "evidence": {"reason": "insufficient_price_history"},
            }
        )

    return base.model_copy(
        update={
            "prior_avg_price": prior_price,
            "prior_listings_count": prior_count,
            "prior_currency": prior_currency,
            "price_change_pct": price_change,
            "listings_change": listings_change,
            "status": "calculated",
            "label": f"{price_change:+.1f}%" if price_change is not None else MOVEMENT_PENDING_LABEL,
            "evidence": {"comparison": "prior_stored_snapshot"},
        }
    )


class MarketSnapshotHistory:
    """Append-only local storage for market snapshots used in movement calculation."""

    def __init__(self, base_dir: Path):
        self.path = base_dir / "weekly" / "market_snapshot_history.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")

    def append(
        self,
        *,
        run_id: str,
        cs_player_id: str,
        query_name: str,
        snapshot: MarketSnapshot,
        captured_at: datetime,
        currency: str = "USD",
    ) -> None:
        row = {
            "run_id": run_id,
            "cs_player_id": cs_player_id,
            "query_name": query_name,
            "avg_price": snapshot.avg_price,
            "listings_count": snapshot.listings_count,
            "currency": currency,
            "captured_at": captured_at.isoformat(),
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row) + "\n")

    def fetch_prior(
        self,
        cs_player_id: str,
        query_name: str,
        *,
        before_iso: str | None = None,
    ) -> dict[str, Any] | None:
        if not self.path.exists():
            return None
        matches: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("cs_player_id") != cs_player_id or row.get("query_name") != query_name:
                continue
            if before_iso and row.get("captured_at", "") >= before_iso:
                continue
            matches.append(row)
        if not matches:
            return None
        matches.sort(key=lambda item: item.get("captured_at", ""))
        return matches[-1]

    def compute_movements_for_player(
        self,
        *,
        run_id: str,
        league: str,
        year: int,
        week_number: int,
        source_player_id: str,
        market_snapshots: dict[str, MarketSnapshot],
        captured_at: datetime,
        currency: str = "USD",
    ) -> list[CardMarketMovement]:
        movements: list[CardMarketMovement] = []
        csp = cs_player_id(source_player_id, league)
        captured_iso = captured_at.isoformat()
        for query_name, snapshot in market_snapshots.items():
            prior = self.fetch_prior(csp, query_name, before_iso=captured_iso)
            movement = calculate_movement(
                source_player_id=source_player_id,
                query_name=query_name,
                league=league,
                run_id=run_id,
                year=year,
                week_number=week_number,
                current=snapshot,
                prior=prior,
                currency=currency,
                captured_at=captured_at,
            )
            movements.append(movement)
            self.append(
                run_id=run_id,
                cs_player_id=csp,
                query_name=query_name,
                snapshot=snapshot,
                captured_at=captured_at,
                currency=currency,
            )
        return movements
