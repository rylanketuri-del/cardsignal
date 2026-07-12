"""NBA recent-game window and stat aggregation helpers."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from cardchase_ai.models.nba import (
    NBAGameLogRow,
    NBAPerformanceWindow,
    NBASourceMethod,
    recent_window_value,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_game_date(game_date: str) -> date | None:
    if not game_date:
        return None
    try:
        return date.fromisoformat(game_date[:10])
    except ValueError:
        return None


def filter_completed_games(
    games: list[NBAGameLogRow],
    *,
    as_of: date | None = None,
) -> list[NBAGameLogRow]:
    """Exclude future games and non-participation games."""
    today = as_of or date.today()
    valid: list[NBAGameLogRow] = []
    for game in games:
        if not game.participated:
            continue
        game_day = _parse_game_date(game.game_date)
        if game_day and game_day > today:
            continue
        valid.append(game)
    return valid


def select_recent_games(games: list[NBAGameLogRow], limit: int | None = None) -> list[NBAGameLogRow]:
    """Select the most recent completed games up to the configured window."""
    target = limit if limit is not None else recent_window_value()
    valid = filter_completed_games(games)
    valid.sort(key=lambda g: g.game_date, reverse=True)
    return valid[:target]


def aggregate_basketball_stats(games: list[NBAGameLogRow]) -> dict[str, Any]:
    totals: dict[str, Any] = {
        "points": 0,
        "rebounds": 0,
        "assists": 0,
        "steals": 0,
        "blocks": 0,
        "turnovers": 0,
        "field_goals_made": 0,
        "field_goals_attempted": 0,
        "three_pointers_made": 0,
        "three_pointers_attempted": 0,
        "free_throws_made": 0,
        "free_throws_attempted": 0,
        "minutes": 0.0,
        "games_played": 0,
    }
    for game in games:
        stats = game.stats
        totals["games_played"] += 1
        for key in totals:
            if key == "games_played":
                continue
            totals[key] += _num(stats.get(key))
    games_played = int(totals["games_played"])
    if games_played > 0:
        totals["points_per_game"] = round(totals["points"] / games_played, 1)
        totals["rebounds_per_game"] = round(totals["rebounds"] / games_played, 1)
        totals["assists_per_game"] = round(totals["assists"] / games_played, 1)
        totals["steals_per_game"] = round(totals["steals"] / games_played, 1)
        totals["blocks_per_game"] = round(totals["blocks"] / games_played, 1)
        totals["minutes_per_game"] = round(totals["minutes"] / games_played, 1)
    fga = int(totals["field_goals_attempted"])
    fgm = int(totals["field_goals_made"])
    tpa = int(totals["three_pointers_attempted"])
    tpm = int(totals["three_pointers_made"])
    fta = int(totals["free_throws_attempted"])
    ftm = int(totals["free_throws_made"])
    totals["field_goal_percentage"] = round((fgm / fga) * 100, 1) if fga else None
    totals["three_point_percentage"] = round((tpm / tpa) * 100, 1) if tpa else None
    totals["free_throw_percentage"] = round((ftm / fta) * 100, 1) if fta else None
    return totals


def build_performance_window(
    games: list[NBAGameLogRow],
    *,
    source_method: NBASourceMethod = "UNAVAILABLE",
    target_games: int | None = None,
) -> NBAPerformanceWindow:
    target = target_games if target_games is not None else recent_window_value()
    selected = select_recent_games(games, limit=target)
    quality = evaluate_window_quality(len(selected), target)
    dates = [g.game_date for g in selected if g.game_date]
    return NBAPerformanceWindow(
        games_in_window=len(selected),
        window_start=min(dates) if dates else None,
        window_end=max(dates) if dates else None,
        source_method=source_method,
        captured_at=_utcnow(),
        data_quality=quality,
    )


def evaluate_window_quality(games_available: int, target: int | None = None) -> str:
    target = target if target is not None else recent_window_value()
    if games_available >= target:
        return "HIGH"
    if games_available >= max(1, target - 2):
        return "MEDIUM"
    if games_available >= 1:
        return "LOW"
    return "INSUFFICIENT"


def _num(value: Any) -> float:
    if value in (None, "", "-"):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
