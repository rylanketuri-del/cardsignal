from __future__ import annotations

from typing import Any, Dict, List

import requests

from cardchase_ai.models.schemas import HitterGameLogRow, PlayerLookup


MLB_BASE_URL = "https://statsapi.mlb.com/api/v1"


class MLBClient:
    def __init__(self, timeout: int = 30) -> None:
        self.timeout = timeout

    def _get(self, path: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
        response = requests.get(f"{MLB_BASE_URL}{path}", params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def search_player(self, name: str) -> PlayerLookup:
        data = self._get("/people/search", params={"names": name})
        people = data.get("people", [])
        if not people:
            raise ValueError(f"No MLB player found for: {name}")
        first = people[0]
        return PlayerLookup(player_id=first["id"], full_name=first["fullName"])

    def get_hitter_gamelog(self, player_id: int, season: int) -> List[HitterGameLogRow]:
        data = self._get(
            f"/people/{player_id}/stats",
            params={
                "stats": "gameLog",
                "group": "hitting",
                "sportIds": 1,
                "season": season,
            },
        )
        stats = data.get("stats", [])
        if not stats:
            return []
        splits = stats[0].get("splits", [])
        rows: List[HitterGameLogRow] = []
        for split in splits:
            stat = split.get("stat", {})
            rows.append(
                HitterGameLogRow(
                    date=split.get("date", ""),
                    at_bats=int(stat.get("atBats", 0) or 0),
                    hits=int(stat.get("hits", 0) or 0),
                    home_runs=int(stat.get("homeRuns", 0) or 0),
                    rbi=int(stat.get("rbi", 0) or 0),
                    stolen_bases=int(stat.get("stolenBases", 0) or 0),
                    walks=int(stat.get("baseOnBalls", 0) or 0),
                    strikeouts=int(stat.get("strikeOuts", 0) or 0),
                    avg=_safe_float(stat.get("avg")),
                    obp=_safe_float(stat.get("obp")),
                    slg=_safe_float(stat.get("slg")),
                    ops=_safe_float(stat.get("ops")),
                )
            )
        return rows


def _safe_float(value: Any) -> float | None:
    if value in (None, "", "-"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
