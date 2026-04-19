from __future__ import annotations

from typing import Any, Dict, List

import requests

from cardchase_ai.models.schemas import ListingSummary


EBAY_BASE_URL = "https://api.ebay.com/buy/browse/v1"


class EbayClient:
    def __init__(self, token: str, marketplace_id: str = "EBAY_US", timeout: int = 30) -> None:
        if not token:
            raise ValueError("Missing EBAY_TOKEN. Add it to your environment before running the pipeline.")
        self.token = token
        self.marketplace_id = marketplace_id
        self.timeout = timeout

    def search_items(
        self,
        query: str,
        limit: int = 50,
        include_auctions: bool = True,
        sort: str | None = None,
    ) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "X-EBAY-C-MARKETPLACE-ID": self.marketplace_id,
            "Accept": "application/json",
        }
        params: Dict[str, Any] = {"q": query, "limit": limit}
        if include_auctions:
            params["filter"] = "buyingOptions:{AUCTION|FIXED_PRICE}"
        if sort:
            params["sort"] = sort
        response = requests.get(
            f"{EBAY_BASE_URL}/item_summary/search",
            headers=headers,
            params=params,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def parse_listings(self, payload: Dict[str, Any]) -> List[ListingSummary]:
        items = payload.get("itemSummaries", []) or []
        listings: List[ListingSummary] = []
        for item in items:
            price_block = item.get("price") or {}
            listings.append(
                ListingSummary(
                    item_id=item.get("itemId", ""),
                    title=item.get("title", ""),
                    price=_safe_float(price_block.get("value")),
                    currency=price_block.get("currency"),
                    condition=item.get("condition"),
                    created_at=item.get("itemCreationDate"),
                    item_web_url=item.get("itemWebUrl"),
                )
            )
        return listings


def _safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
