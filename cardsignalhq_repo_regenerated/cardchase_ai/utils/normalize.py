from __future__ import annotations

from typing import Iterable, List

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



def tag_listing_title(title: str) -> List[str]:
    lowered = f" {title.lower()} "
    tags: List[str] = []
    for tag, terms in KEYWORDS.items():
        if any(term in lowered for term in terms):
            tags.append(tag)
    if any(tag in tags for tag in ["psa10", "auto", "bowman_1st", "chrome", "numbered"]):
        tags.append("premium")
    return sorted(set(tags))



def enrich_listings(listings: Iterable[ListingSummary]) -> List[ListingSummary]:
    enriched: List[ListingSummary] = []
    for listing in listings:
        listing.tags = tag_listing_title(listing.title)
        enriched.append(listing)
    return enriched



def summarize_market(query_name: str, listings: List[ListingSummary]) -> MarketSnapshot:
    enriched = enrich_listings(listings)
    prices = sorted([listing.price for listing in enriched if listing.price is not None])
    tag_summary = ListingTagSummary()
    premium_count = 0

    for listing in enriched:
        for tag in listing.tags:
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
        listings_count=len(enriched),
        avg_price=avg_price,
        min_price=min_price,
        max_price=max_price,
        tags=tag_summary,
        listings=enriched,
    )
