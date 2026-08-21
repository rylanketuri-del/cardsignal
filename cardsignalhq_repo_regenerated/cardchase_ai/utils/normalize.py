from __future__ import annotations

from typing import Any, Dict, List

from cardchase_ai.models.schemas import ListingSummary, ListingTagSummary, MarketSnapshot


KEYWORDS = {
    "psa10": ["psa 10"],
    "auto": [" auto ", "autograph", "signed"],
    "bowman_1st": ["1st bowman", "bowman 1st"],
    "chrome": ["chrome", "topps chrome", "bowman chrome"],
    "rookie": [" rookie ", " rc "],
    "numbered": ["/", "gold", "orange", "black", "red", "blue refractor", "green refractor"],
}


TAG_TO_SUMMARY_FIELD = {
    "psa10": "psa10_count",
    "auto": "auto_count",
    "bowman_1st": "bowman_1st_count",
    "chrome": "chrome_count",
    "rookie": "rookie_count",
    "numbered": "numbered_count",
}


def _positive_price(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        price = float(value)
    except (TypeError, ValueError):
        return None
    if price <= 0 or price != price:
        return None
    return price


def _normalize_image_url(value: Any) -> str | None:
    if value is None:
        return None
    url = str(value).strip()
    if not url:
        return None
    lowered = url.lower()
    if not (lowered.startswith("http://") or lowered.startswith("https://")):
        return None
    return url


def tag_listing_title(title: str) -> List[str]:
    lowered = f" {title.lower()} "
    tags: List[str] = []

    for tag, terms in KEYWORDS.items():
        if any(term in lowered for term in terms):
            tags.append(tag)

    if any(tag in tags for tag in ["psa10", "auto", "bowman_1st", "chrome", "numbered"]):
        tags.append("premium")

    return sorted(set(tags))


def normalize_listing(listing: Any) -> Dict[str, Any]:
    if isinstance(listing, ListingSummary):
        data = listing.model_dump()
    elif isinstance(listing, dict):
        data = dict(listing)
    else:
        data = {
            "item_id": getattr(listing, "item_id", ""),
            "title": getattr(listing, "title", ""),
            "price": getattr(listing, "price", None),
            "currency": getattr(listing, "currency", None),
            "condition": getattr(listing, "condition", None),
            "created_at": getattr(listing, "created_at", None),
            "item_web_url": getattr(listing, "item_web_url", None),
            "image_url": getattr(listing, "image_url", None),
            "tags": getattr(listing, "tags", []),
        }

    title = data.get("title", "") or ""
    data["tags"] = tag_listing_title(title)

    return {
        "item_id": str(data.get("item_id", "") or ""),
        "title": str(data.get("title", "") or ""),
        "price": _positive_price(data.get("price")),
        "currency": data.get("currency"),
        "condition": data.get("condition"),
        "created_at": data.get("created_at"),
        "item_web_url": data.get("item_web_url"),
        "image_url": _normalize_image_url(data.get("image_url")),
        "tags": data.get("tags", []),
    }


def enrich_listings(listings: List[Any]) -> List[Dict[str, Any]]:
    return [normalize_listing(listing) for listing in listings]


def summarize_market(query_name: str, listings: List[Any]) -> MarketSnapshot:
    enriched = enrich_listings(listings)
    scored = [listing for listing in enriched if listing.get("price") is not None]

    prices = sorted(listing["price"] for listing in scored)

    tag_summary = ListingTagSummary()
    premium_count = 0

    for listing in scored:
        for tag in listing.get("tags", []):
            if tag == "premium":
                premium_count += 1
                continue

            field_name = TAG_TO_SUMMARY_FIELD.get(tag)
            if field_name:
                setattr(tag_summary, field_name, getattr(tag_summary, field_name) + 1)

    tag_summary.premium_count = premium_count

    avg_price = round(sum(prices) / len(prices), 2) if prices else None
    min_price = prices[0] if prices else None
    max_price = prices[-1] if prices else None

    return MarketSnapshot(
        query_name=query_name,
        listings_count=len(scored),
        avg_price=avg_price,
        min_price=min_price,
        max_price=max_price,
        tags=tag_summary,
        listings=enriched,
    )
