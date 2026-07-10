"""Official PSA API client — cert verification only (no population reports)."""

from __future__ import annotations

from typing import Any

import requests


class PSAClientError(RuntimeError):
    pass


class PSAClient:
    """Thin wrapper around documented PSA Public API cert endpoints."""

    def __init__(
        self,
        *,
        access_token: str = "",
        base_url: str = "https://api.psacard.com/publicapi",
        timeout: int = 30,
    ) -> None:
        self.access_token = access_token.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @property
    def is_configured(self) -> bool:
        return bool(self.access_token)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }

    def get_cert_by_number(self, certification_number: str) -> dict[str, Any]:
        if not self.is_configured:
            raise PSAClientError("PSA access token is not configured.")
        cert = str(certification_number or "").strip()
        if not cert:
            raise PSAClientError("Certification number is required.")

        endpoint = f"{self.base_url}/cert/GetByCertNumber/{cert}"
        response = requests.get(endpoint, headers=self._headers(), timeout=self.timeout)
        if response.status_code >= 400:
            raise PSAClientError(f"PSA cert lookup failed: {response.status_code}")
        return response.json()
