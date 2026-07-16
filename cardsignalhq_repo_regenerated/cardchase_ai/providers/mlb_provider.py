"""MLB performance provider — Stats API retrieval and normalization only."""

from __future__ import annotations

from typing import Any

from cardchase_ai.clients.mlb import MLBClient
from cardchase_ai.config import Settings, get_settings


class MLBProvider:
    """Wraps MLBClient. Does not calculate CardSignal scores."""

    league = "MLB"
    source_method = "MLB_STATS_API"

    def __init__(self, client: MLBClient | None = None, settings: Settings | None = None) -> None:
        self._client = client or MLBClient()
        self._settings = settings or get_settings()

    def is_available(self) -> bool:
        return True

    @property
    def client(self) -> MLBClient:
        return self._client

    def search_players(self, query: str, limit: int = 10) -> list[Any]:
        try:
            player = self._client.search_player(query)
        except Exception:
            return []
        if not player:
            return []
        return [
            {
                "player_id": int(player.player_id),
                "player_name": player.full_name,
                "source_player_id": str(player.player_id),
                "league": "MLB",
            }
        ][:limit]

    def fetch_player_universe(self, limit: int = 100) -> list[dict[str, Any]]:
        candidates = self._client.get_dynamic_hitter_candidates(
            season=self._settings.mlb_season,
            days=7,
            limit=limit,
        )
        return [
            {
                "player_id": int(c["player_id"]),
                "player_name": c["player_name"],
                "source_player_id": str(c["player_id"]),
                "team": c.get("team"),
                "team_id": c.get("team_id"),
                "position": c.get("position"),
                "headshot_url": c.get("headshot_url"),
                "team_logo_url": c.get("team_logo_url"),
                "league": "MLB",
                "candidate_source": "dynamic",
                "breakout_score": c.get("breakout_score", 0),
            }
            for c in candidates[:limit]
        ]

    def fetch_recent_games(self, source_player_id: str, limit: int = 7) -> list[Any]:
        from cardchase_ai.utils.rolling import filter_last_n_days

        gamelog = self._client.get_hitter_gamelog(int(source_player_id), self._settings.mlb_season)
        return filter_last_n_days(gamelog, limit)

    def fetch_season_stats(self, source_player_id: str, season: int) -> dict[str, Any] | None:
        from cardchase_ai.utils.rolling import summarize_hitter_window

        gamelog = self._client.get_hitter_gamelog(int(source_player_id), season)
        if not gamelog:
            return None
        stats = summarize_hitter_window(gamelog)
        return stats.model_dump() if hasattr(stats, "model_dump") else dict(stats)

    def fetch_hitter_gamelog(self, source_player_id: str, season: int | None = None) -> list[Any]:
        return self._client.get_hitter_gamelog(
            int(source_player_id),
            season if season is not None else self._settings.mlb_season,
        )


def get_mlb_provider(settings: Settings | None = None) -> MLBProvider:
    return MLBProvider(settings=settings or get_settings())
