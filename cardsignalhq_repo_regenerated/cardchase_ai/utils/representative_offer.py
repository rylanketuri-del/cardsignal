"""Deterministic representative listing picker for CardSignal search categories."""

from __future__ import annotations

import re
from typing import Any

from cardchase_ai.models.schemas import ListingSummary

NAME_SUFFIXES = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv", "v"}
MEDIAN_BAND_LOW = 0.25
MEDIAN_BAND_HIGH = 3.0
REPRESENTATIVE_SOURCE_EBAY = "ebay"


def _listing_dict(listing: Any) -> dict[str, Any]:
    if isinstance(listing, ListingSummary):
        return listing.model_dump()
    if isinstance(listing, dict):
        return dict(listing)
    return {
        "item_id": getattr(listing, "item_id", ""),
        "title": getattr(listing, "title", ""),
        "price": getattr(listing, "price", None),
        "currency": getattr(listing, "currency", None),
        "condition": getattr(listing, "condition", None),
        "item_web_url": getattr(listing, "item_web_url", None),
        "image_url": getattr(listing, "image_url", None),
    }


def _player_names(player_name: str) -> tuple[str, str]:
    parts = [part.strip(".,") for part in str(player_name or "").split() if part.strip(".,")]
    if not parts:
        return "", ""
    full = " ".join(parts).lower()
    last = parts[-1].lower()
    if last in NAME_SUFFIXES and len(parts) >= 2:
        last = parts[-2].lower()
    return full, last


def title_matches_player(title: str, player_name: str) -> bool:
    lowered = str(title or "").lower()
    full, last = _player_names(player_name)
    if not last:
        return False
    if full and full in lowered:
        return True
    return re.search(rf"\b{re.escape(last)}\b", lowered) is not None


def title_matches_category(title: str, query_name: str) -> bool:
    lowered = str(title or "").lower()
    query = str(query_name or "").strip().lower()
    if query in {"", "broad"}:
        return True
    if query == "bowman_chrome":
        return "bowman" in lowered and "chrome" in lowered
    if query == "auto":
        return "autograph" in lowered or "signed" in lowered or bool(re.search(r"\bauto\b", lowered))
    if query == "psa10":
        return bool(re.search(r"\bpsa\b", lowered) and re.search(r"\b10\b", lowered))
    if query == "rookie":
        return "rookie" in lowered or bool(re.search(r"\brc\b", lowered))
    if query == "prizm":
        return "prizm" in lowered
    return True


def _usable_listing(listing: dict[str, Any]) -> bool:
    title = str(listing.get("title") or "").strip()
    image_url = str(listing.get("image_url") or "").strip()
    if not title or not image_url:
        return False
    lowered = image_url.lower()
    if not (lowered.startswith("http://") or lowered.startswith("https://")):
        return False
    try:
        price = float(listing.get("price"))
    except (TypeError, ValueError):
        return False
    return price > 0


def _median_price(listings: list[dict[str, Any]]) -> float | None:
    prices = sorted(float(item["price"]) for item in listings)
    if not prices:
        return None
    mid = len(prices) // 2
    if len(prices) % 2:
        return prices[mid]
    return (prices[mid - 1] + prices[mid]) / 2


def _closest_to_median(listings: list[dict[str, Any]], median: float) -> dict[str, Any]:
    return min(
        listings,
        key=lambda item: (
            abs(float(item["price"]) - median),
            str(item.get("item_id") or ""),
            str(item.get("title") or ""),
        ),
    )


def _pick_from_candidates(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not candidates:
        return None
    median = _median_price(candidates)
    if median is None:
        return None
    band = [
        item
        for item in candidates
        if MEDIAN_BAND_LOW * median <= float(item["price"]) <= MEDIAN_BAND_HIGH * median
    ]
    pool = band or candidates
    return _closest_to_median(pool, median)


def select_representative_listing(
    listings: list[Any] | None,
    player_name: str,
    query_name: str,
) -> dict[str, Any] | None:
    """Return one listing dict, or None when no usable representative exists."""
    usable = [_listing_dict(item) for item in listings or []]
    usable = [item for item in usable if _usable_listing(item)]
    if not usable:
        return None

    named = [item for item in usable if title_matches_player(item.get("title") or "", player_name)]
    guarded = [item for item in named if title_matches_category(item.get("title") or "", query_name)]
    return _pick_from_candidates(guarded) or _pick_from_candidates(named)


def listing_to_representative_offer(listing: dict[str, Any], query_name: str) -> dict[str, Any]:
    return {
        "source": REPRESENTATIVE_SOURCE_EBAY,
        "external_id": str(listing.get("item_id") or "") or None,
        "title": str(listing.get("title") or "") or None,
        "image_url": str(listing.get("image_url") or "") or None,
        "price": listing.get("price"),
        "currency": listing.get("currency") or "USD",
        "condition": str(listing.get("condition") or "") or None,
        "listing_url": str(listing.get("item_web_url") or "") or None,
        "query_name": query_name,
    }


def build_representative_offer(
    listings: list[Any] | None,
    player_name: str,
    query_name: str,
) -> dict[str, Any] | None:
    chosen = select_representative_listing(listings, player_name, query_name)
    if not chosen:
        return None
    return listing_to_representative_offer(chosen, query_name)
