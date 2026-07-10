"""Population provider abstraction — Sprint 8.6."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from cardchase_ai.models.population import PSACardMatch


class PopulationProvider(ABC):
    provider_name: str = "unknown"

    @abstractmethod
    def search_card_matches(self, card_identity: dict[str, Any]) -> list[PSACardMatch]:
        """Return candidate PSA matches for a CardSignal card identity."""

    @abstractmethod
    def fetch_population(self, card_match: PSACardMatch) -> dict[str, Any] | None:
        """Fetch raw population payload for a resolved match."""

    @abstractmethod
    def normalize_population(
        self,
        raw_result: dict[str, Any],
        *,
        card_match: PSACardMatch,
        card_identity: dict[str, Any],
    ) -> dict[str, Any]:
        """Normalize provider payload into snapshot field dict."""

    def is_available(self) -> bool:
        return True
