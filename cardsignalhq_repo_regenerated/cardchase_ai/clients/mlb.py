from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List

import requests

from cardchase_ai.models.schemas import HitterGameLogRow, PlayerLookup

MLB_BASE_URL = "https://statsapi.mlb.com/api/v1"


class MLBClient:
    def __init__(self, timeout: int = 30) -> None:
        self.timeout = timeout

    def _get(self, path: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
        response = requests.get(
            f"{MLB_BASE_URL}{path}",
            params=params,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def search_player(self, name: str) -> PlayerLookup:
        data = self._get("/people/search", params={"names": name})
        people = data.get("people", [])

        if not people:
            raise ValueError(f"No MLB player found for: {name}")

        first = people[0]

        return PlayerLookup(
            player_id=first["id"],
            full_name=first["fullName"],
        )

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

  def get_dynamic_hitter_candidates(
    self,
    season: int,
    days: int = 7,
    limit: int = 100,
) -> list[dict[str, Any]]:
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    data = self._get(
        "/stats",
        params={
            "stats": "byDateRange",
            "group": "hitting",
            "playerPool": "ALL",
            "sportIds": 1,
            "season": season,
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "limit": 1000,
        },
    )

    stats = data.get("stats", [])
    if not stats:
        return []

    splits = stats[0].get("splits", [])
    candidates = []

    for split in splits:
        player = split.get("player") or {}
        team = split.get("team") or {}
        position = split.get("position") or {}
        stat = split.get("stat") or {}

        player_id = player.get("id")
        player_name = player.get("fullName")
        team_id = team.get("id")

        if not player_id or not player_name:
            continue

        at_bats = _safe_int(stat.get("atBats"))
        hits = _safe_int(stat.get("hits"))
        home_runs = _safe_int(stat.get("homeRuns"))
        rbi = _safe_int(stat.get("rbi"))
        runs = _safe_int(stat.get("runs"))
        stolen_bases = _safe_int(stat.get("stolenBases"))
        ops = _safe_float(stat.get("ops")) or 0.0
        avg = _safe_float(stat.get("avg")) or 0.0

        if at_bats < 5:
            continue

        breakout_score = _breakout_score(
            at_bats=at_bats,
            hits=hits,
            home_runs=home_runs,
            rbi=rbi,
            runs=runs,
            stolen_bases=stolen_bases,
            ops=ops,
            avg=avg,
        )

        candidates.append(
            {
                "player_id": int(player_id),
                "player_name": player_name,
                "team": team.get("abbreviation") or team.get("name") or "MLB",
                "team_id": int(team_id) if team_id else None,
                "position": position.get("abbreviation") or position.get("name") or "",
                "headshot_url": f"https://img.mlbstatic.com/mlb-photos/image/upload/w_213,q_100/v1/people/{player_id}/headshot/current",
                "team_logo_url": f"https://www.mlbstatic.com/team-logos/{team_id}.svg" if team_id else "",
                "breakout_score": breakout_score,
                "stats": {
                    "at_bats": at_bats,
                    "hits": hits,
                    "home_runs": home_runs,
                    "rbi": rbi,
                    "runs": runs,
                    "stolen_bases": stolen_bases,
                    "ops": ops,
                    "avg": avg,
                },
            }
        )

    candidates.sort(key=lambda item: item["breakout_score"], reverse=True)
    return candidates[:limit]

        candidates.sort(key=lambda item: item["breakout_score"], reverse=True)
        return candidates[:limit]


def _breakout_score(
    *,
    at_bats: int,
    hits: int,
    home_runs: int,
    rbi: int,
    runs: int,
    stolen_bases: int,
    ops: float,
    avg: float,
) -> float:
    ops_score = min((ops / 1.200) * 100, 100)
    hr_score = min((home_runs / 4) * 100, 100)
    rbi_score = min((rbi / 10) * 100, 100)
    runs_score = min((runs / 10) * 100, 100)
    sb_score = min((stolen_bases / 4) * 100, 100)
    avg_score = min((avg / 0.400) * 100, 100)
    playing_time_score = min((at_bats / 25) * 100, 100)

    score = (
        0.25 * ops_score
        + 0.18 * hr_score
        + 0.14 * rbi_score
        + 0.12 * runs_score
        + 0.10 * sb_score
        + 0.11 * avg_score
        + 0.10 * playing_time_score
    )

    return round(score, 2)


def _safe_float(value: Any) -> float | None:
    if value in (None, "", "-"):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int:
    if value in (None, "", "-"):
        return 0

    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
