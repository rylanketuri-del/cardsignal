"""Approved import path for verified NFL performance data."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cardchase_ai.config import Settings, get_settings
from cardchase_ai.identity import cs_nfl_player_id
from cardchase_ai.models.nfl import (
    NFLGameLogRow,
    NFLPlayerIdentity,
    NFLPlayerSearchResult,
    map_nfl_position,
)
from cardchase_ai.providers.nfl_performance import NFLPerformanceProvider


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UnavailableNFLProvider:
    """Placeholder provider when no NFL data source is configured."""

    source_method = "UNAVAILABLE"

    def is_available(self) -> bool:
        return False

    def search_players(self, query: str, limit: int = 10) -> list[NFLPlayerSearchResult]:
        return []

    def fetch_player_profile(self, source_player_id: str) -> NFLPlayerIdentity | None:
        return None

    def fetch_recent_games(self, source_player_id: str, limit: int = 3) -> list[NFLGameLogRow]:
        return []

    def fetch_season_stats(self, source_player_id: str, season: int) -> dict[str, Any] | None:
        return None

    def fetch_team_roster(self, team_id: str, season: int) -> list[NFLPlayerIdentity]:
        return []

    def fetch_league_schedule(self, season: int) -> list[dict[str, Any]]:
        return []

    def fetch_player_status(self, source_player_id: str) -> dict[str, Any] | None:
        return None

    def fetch_player_universe(self, limit: int = 100) -> list[NFLPlayerIdentity]:
        return []


class NFLImportProvider:
    """Load verified NFL data from approved import JSON files."""

    source_method = "APPROVED_IMPORT"

    def __init__(self, import_dir: Path, season: int, player_limit: int = 100) -> None:
        self.import_dir = import_dir
        self.season = season
        self.player_limit = player_limit
        self._data: dict[str, Any] | None = None
        self._loaded = False

    def _import_file(self) -> Path:
        return self.import_dir / "nfl_data.json"

    def _load(self) -> dict[str, Any] | None:
        if self._loaded:
            return self._data
        self._loaded = True
        path = self._import_file()
        if not path.exists():
            self._data = None
            return None
        try:
            self._data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            self._data = None
        return self._data

    def is_available(self) -> bool:
        data = self._load()
        if not data:
            return False
        players = data.get("players") or []
        return len(players) > 0 and bool(data.get("source_method"))

    def _active_players(self) -> list[dict[str, Any]]:
        data = self._load()
        if not data:
            return []
        players = data.get("players") or []
        active = [
            p for p in players
            if str(p.get("active_status", "ACTIVE")).upper() != "RETIRED"
        ]
        return active[: self.player_limit]

    def _find_player(self, source_player_id: str) -> dict[str, Any] | None:
        sid = str(source_player_id)
        for player in self._active_players():
            if str(player.get("source_player_id")) == sid:
                return player
        return None

    def _to_identity(self, player: dict[str, Any]) -> NFLPlayerIdentity:
        sid = str(player["source_player_id"])
        position = player.get("position")
        return NFLPlayerIdentity(
            cs_player_id=cs_nfl_player_id(sid),
            source_player_id=sid,
            player_name=player["player_name"],
            team=player.get("team"),
            team_id=str(player["team_id"]) if player.get("team_id") else None,
            position=position,
            position_group=map_nfl_position(position),
            jersey_number=player.get("jersey_number"),
            active_status=player.get("active_status", "ACTIVE"),
            headshot_url=player.get("headshot_url"),
            team_logo_url=player.get("team_logo_url"),
            season=player.get("season", self.season),
            source_method=self.source_method,
            last_updated=_parse_dt(player.get("last_updated")),
        )

    def search_players(self, query: str, limit: int = 10) -> list[NFLPlayerSearchResult]:
        needle = query.strip().lower()
        if len(needle) < 2:
            return []
        results: list[NFLPlayerSearchResult] = []
        for player in self._active_players():
            name = str(player.get("player_name", "")).lower()
            team = str(player.get("team", "")).lower()
            position = str(player.get("position", "")).lower()
            if needle not in name and needle not in team and needle not in position:
                continue
            sid = str(player["source_player_id"])
            pos = player.get("position")
            results.append(
                NFLPlayerSearchResult(
                    cs_player_id=cs_nfl_player_id(sid),
                    source_player_id=sid,
                    player_name=player["player_name"],
                    team=player.get("team") or "NFL",
                    team_id=str(player["team_id"]) if player.get("team_id") else None,
                    position=pos,
                    position_group=map_nfl_position(pos),
                    headshot_url=player.get("headshot_url") or "",
                    team_logo_url=player.get("team_logo_url") or "",
                    active_status=player.get("active_status", "ACTIVE"),
                )
            )
            if len(results) >= limit:
                break
        return results

    def fetch_player_profile(self, source_player_id: str) -> NFLPlayerIdentity | None:
        player = self._find_player(source_player_id)
        if not player:
            return None
        return self._to_identity(player)

    def fetch_recent_games(self, source_player_id: str, limit: int = 3) -> list[NFLGameLogRow]:
        data = self._load()
        if not data:
            return []
        games_map = data.get("games") or {}
        raw_games = games_map.get(str(source_player_id)) or []
        rows = [_parse_game_row(g) for g in raw_games]
        valid = [r for r in rows if _is_valid_completed_game(r)]
        valid.sort(key=lambda r: r.game_date, reverse=True)
        return valid[:limit]

    def fetch_season_stats(self, source_player_id: str, season: int) -> dict[str, Any] | None:
        data = self._load()
        if not data:
            return None
        stats_map = data.get("season_stats") or {}
        entry = stats_map.get(str(source_player_id))
        if not entry:
            return None
        if entry.get("season") and int(entry["season"]) != season:
            return None
        return dict(entry.get("stats") or entry)

    def fetch_team_roster(self, team_id: str, season: int) -> list[NFLPlayerIdentity]:
        return [
            self._to_identity(p)
            for p in self._active_players()
            if str(p.get("team_id")) == str(team_id) and (p.get("season", self.season) == season)
        ]

    def fetch_league_schedule(self, season: int) -> list[dict[str, Any]]:
        data = self._load()
        if not data:
            return []
        schedule = data.get("schedule") or []
        return [s for s in schedule if int(s.get("season", season)) == season]

    def fetch_player_status(self, source_player_id: str) -> dict[str, Any] | None:
        player = self._find_player(source_player_id)
        if not player:
            return None
        return {
            "active_status": player.get("active_status", "ACTIVE"),
            "injury_status": player.get("injury_status"),
            "source_method": self.source_method,
        }

    def fetch_player_universe(self, limit: int = 100) -> list[NFLPlayerIdentity]:
        return [self._to_identity(p) for p in self._active_players()[:limit]]


def _parse_game_row(raw: dict[str, Any]) -> NFLGameLogRow:
    position = raw.get("position")
    return NFLGameLogRow(
        game_id=str(raw.get("game_id", raw.get("game_date", ""))),
        game_date=str(raw.get("game_date", "")),
        season=int(raw.get("season", 0)),
        week=raw.get("week"),
        team=raw.get("team"),
        opponent=raw.get("opponent"),
        home_away=raw.get("home_away"),
        participated=bool(raw.get("participated", True)),
        is_bye_week=bool(raw.get("is_bye_week", False)),
        is_preseason=bool(raw.get("is_preseason", False)),
        is_postseason=bool(raw.get("is_postseason", False)),
        position_group=map_nfl_position(position or raw.get("position_group")),
        stats=dict(raw.get("stats") or {}),
    )


def _is_valid_completed_game(row: NFLGameLogRow) -> bool:
    if row.is_bye_week:
        return False
    if not row.game_date:
        return False
    if not row.participated:
        return False
    return True


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def get_nfl_provider(settings: Settings | None = None) -> NFLPerformanceProvider:
    settings = settings or get_settings()
    import_dir = settings.output_dir / "nfl" / "import"
    provider = NFLImportProvider(
        import_dir=import_dir,
        season=settings.nfl_season,
        player_limit=settings.nfl_player_limit,
    )
    if provider.is_available():
        return provider
    return UnavailableNFLProvider()
