"""Read-only player intelligence API — delegates to normalized read service."""

from __future__ import annotations

from typing import Any

from cardchase_ai.intelligence_service import get_player_intelligence_payload
from cardchase_ai.repositories.factory import build_repository_bundle


def fetch_player_intelligence_payload(
    league: str,
    player_id: str,
    repos=None,
) -> dict[str, Any] | None:
    """Build normalized PlayerIntelligencePayload from stored intelligence only."""
    bundle = repos or build_repository_bundle()
    return get_player_intelligence_payload(league, player_id, bundle)
