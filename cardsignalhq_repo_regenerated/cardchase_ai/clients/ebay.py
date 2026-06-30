import base64
import time
from typing import Any, Dict
from urllib.parse import quote_plus

import requests


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
            raise ValueError(
                "Missing eBay credentials. Add EBAY_CLIENT_ID and EBAY_CLIENT_SECRET to Render."
            )

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
