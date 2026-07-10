import base64
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

import requests

from cardchase_ai.models.schemas import NormalizedActiveListing


class EbayClient:
    def __init__(
        self,
        token: str | None = None,
        marketplace_id: str = "EBAY_US",
        client_id: str | None = None,
        client_secret: str | None = None,
    ):
        self.token = token
        self.marketplace_id = marketplace_id
        self.client_id = client_id
        self.client_secret = client_secret
        self._cached_token: str | None = None
        self._token_expires_at = 0.0

    def _get_access_token(self) -> str:
        if self.token:
            return self.token

        if self._cached_token and time.time() < self._token_expires_at - 60:
            return self._cached_token

        if not self.client_id or not self.client_secret:
            raise ValueError("Missing eBay credentials. Add EBAY_CLIENT_ID and EBAY_CLIENT_SECRET to Render.")

        raw_credentials = f"{self.client_id}:{self.client_secret}".encode("utf-8")
        encoded_credentials = base64.b64encode(raw_credentials).decode("utf-8")

        response = requests.post(
            "https://api.ebay.com/identity/v1/oauth2/token",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Basic {encoded_credentials}",
            },
            data={
                "grant_type": "client_credentials",
                "scope": "https://api.ebay.com/oauth/api_scope",
            },
            timeout=30,
        )
        response.raise_for_status()

        payload = response.json()
        self._cached_token = payload["access_token"]
        self._token_expires_at = time.time() + int(payload.get("expires_in", 7200))
        return self._cached_token

    def search(self, query: str, limit: int = 50, include_auctions: bool = True) -> Dict[str, Any]:
        token = self._get_access_token()

        params = {
            "q": query,
            "limit": str(limit),
        }

        if include_auctions:
            params["filter"] = "buyingOptions:{AUCTION|FIXED_PRICE}"

        response = requests.get(
            "https://api.ebay.com/buy/browse/v1/item_summary/search",
            headers={
                "Authorization": f"Bearer {token}",
                "X-EBAY-C-MARKETPLACE-ID": self.marketplace_id,
                "Accept": "application/json",
            },
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def search_items(self, query: str, limit: int = 50, include_auctions: bool = True) -> Dict[str, Any]:
        return self.search(query=query, limit=limit, include_auctions=include_auctions)

    def _parse_money(self, value: Any) -> float | None:
        if value is None:
            return None
        if isinstance(value, dict):
            raw = value.get("value")
        else:
            raw = value
        try:
            amount = float(raw)
        except (TypeError, ValueError):
            return None
        if amount < 0:
            return None
        return round(amount, 2)

    def _parse_listing_type(self, buying_options: list[str] | None) -> str:
        options = {str(option).upper() for option in (buying_options or [])}
        has_auction = "AUCTION" in options
        has_fixed = "FIXED_PRICE" in options
        if has_auction and not has_fixed:
            return "auction"
        if has_fixed and not has_auction:
            return "buy_it_now"
        if has_auction and has_fixed:
            return "auction_or_buy_it_now"
        return "unknown"

    def parse_active_listings(
        self,
        payload: Dict[str, Any],
        *,
        captured_at: datetime | None = None,
    ) -> List[NormalizedActiveListing]:
        items = payload.get("itemSummaries", []) or []
        moment = captured_at or datetime.now(timezone.utc)
        captured_iso = moment.isoformat()
        listings: list[NormalizedActiveListing] = []

        for item in items:
            try:
                price_block = item.get("price") or {}
                price = self._parse_money(price_block)
                currency = str(price_block.get("currency") or "USD")

                shipping = None
                shipping_options = item.get("shippingOptions") or []
                if shipping_options:
                    shipping = self._parse_money((shipping_options[0] or {}).get("shippingCost"))

                total_price = None
                if price is not None:
                    total_price = round(price + (shipping or 0.0), 2)

                image = item.get("image") or {}
                seller = item.get("seller") or {}

                listings.append(
                    NormalizedActiveListing(
                        source_listing_id=str(item.get("itemId") or ""),
                        title=str(item.get("title") or ""),
                        price=price,
                        shipping=shipping,
                        total_price=total_price,
                        currency=currency,
                        condition=str(item.get("condition") or "") or None,
                        listing_type=self._parse_listing_type(item.get("buyingOptions")),
                        bid_count=int(item.get("bidCount") or 0),
                        item_url=str(item.get("itemWebUrl") or "") or None,
                        image_url=str(image.get("imageUrl") or "") or None,
                        seller=str(seller.get("username") or "") or None,
                        captured_at=captured_iso,
                    )
                )
            except Exception:
                continue

        return listings

    def parse_listings(self, payload: Dict[str, Any]) -> list[Dict[str, Any]]:
        return [
            {
                "item_id": listing.source_listing_id,
                "title": listing.title,
                "price": listing.price or 0.0,
                "currency": listing.currency,
                "condition": listing.condition or "",
                "created_at": listing.captured_at,
                "item_web_url": listing.item_url or "",
                "tags": [],
            }
            for listing in self.parse_active_listings(payload)
        ]
        
    def get_market_data(self, player_name: str) -> Dict[str, Any]:
        searches = {
            "broad": f"{player_name} baseball card",
            "bowman_chrome": f"{player_name} Bowman Chrome rookie",
            "auto": f"{player_name} auto baseball card",
            "psa10": f"{player_name} PSA 10 baseball card",
        }

        return {
            label: self.search(query, limit=50, include_auctions=True)
            for label, query in searches.items()
        }
