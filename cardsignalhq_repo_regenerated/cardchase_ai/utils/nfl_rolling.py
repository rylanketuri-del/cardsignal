"""NFL recent-game window and stat aggregation helpers."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from cardchase_ai.models.nfl import NFLGameLogRow, NFLPerformanceWindow, NFLSourceMethod


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
    games: list[NFLGameLogRow],
    *,
    as_of: date | None = None,
) -> list[NFLGameLogRow]:
    """Exclude future games, bye weeks, and non-participation games."""
    today = as_of or date.today()
    valid: list[NFLGameLogRow] = []
    for game in games:
        if game.is_bye_week:
            continue
        if not game.participated:
            continue
        game_day = _parse_game_date(game.game_date)
        if game_day and game_day > today:
            continue
        valid.append(game)
    return valid


def select_recent_games(games: list[NFLGameLogRow], limit: int = 3) -> list[NFLGameLogRow]:
    """Select the most recent completed games up to limit."""
    valid = filter_completed_games(games)
    valid.sort(key=lambda g: g.game_date, reverse=True)
    return valid[:limit]


def aggregate_qb_stats(games: list[NFLGameLogRow]) -> dict[str, Any]:
    totals: dict[str, float | int] = {
        "passing_yards": 0,
        "passing_touchdowns": 0,
        "interceptions": 0,
        "completions": 0,
        "attempts": 0,
        "rushing_yards": 0,
        "rushing_touchdowns": 0,
        "sacks": 0,
        "fumbles": 0,
        "games_played": 0,
    }
    for game in games:
        stats = game.stats
        totals["games_played"] += 1
        for key in totals:
            if key == "games_played":
                continue
            totals[key] += _num(stats.get(key))
    attempts = int(totals["attempts"])
    completions = int(totals["completions"])
    totals["completion_percentage"] = round((completions / attempts) * 100, 1) if attempts else None
    totals["yards_per_attempt"] = round(totals["passing_yards"] / attempts, 2) if attempts else None
    if totals.get("passer_rating") is None:
        rating = _avg([_num(g.stats.get("passer_rating")) for g in games if g.stats.get("passer_rating") is not None])
        totals["passer_rating"] = round(rating, 1) if rating is not None else None
    return totals


def aggregate_rb_stats(games: list[NFLGameLogRow]) -> dict[str, Any]:
    totals: dict[str, Any] = {
        "rushing_attempts": 0,
        "rushing_yards": 0,
        "rushing_touchdowns": 0,
        "targets": 0,
        "receptions": 0,
        "receiving_yards": 0,
        "receiving_touchdowns": 0,
        "fumbles": 0,
        "games_played": 0,
    }
    for game in games:
        stats = game.stats
        totals["games_played"] += 1
        for key in totals:
            if key == "games_played":
                continue
            totals[key] += _num(stats.get(key))
    rush_att = int(totals["rushing_attempts"])
    totals["yards_per_carry"] = round(totals["rushing_yards"] / rush_att, 2) if rush_att else None
    totals["total_yards"] = int(totals["rushing_yards"]) + int(totals["receiving_yards"])
    totals["total_touchdowns"] = int(totals["rushing_touchdowns"]) + int(totals["receiving_touchdowns"])
    return totals


def aggregate_receiver_stats(games: list[NFLGameLogRow]) -> dict[str, Any]:
    totals: dict[str, Any] = {
        "targets": 0,
        "receptions": 0,
        "receiving_yards": 0,
        "receiving_touchdowns": 0,
        "rushing_yards": 0,
        "fumbles": 0,
        "games_played": 0,
    }
    for game in games:
        stats = game.stats
        totals["games_played"] += 1
        for key in totals:
            if key == "games_played":
                continue
            totals[key] += _num(stats.get(key))
    targets = int(totals["targets"])
    receptions = int(totals["receptions"])
    rec_yards = int(totals["receiving_yards"])
    totals["yards_per_reception"] = round(rec_yards / receptions, 2) if receptions else None
    totals["catch_rate"] = round((receptions / targets) * 100, 1) if targets else None
    totals["total_touchdowns"] = int(totals["receiving_touchdowns"]) + int(totals.get("rushing_touchdowns", 0))
    return totals


def aggregate_position_stats(position_group: str, games: list[NFLGameLogRow]) -> dict[str, Any]:
    group = position_group.upper()
    if group == "QB":
        return aggregate_qb_stats(games)
    if group == "RB":
        return aggregate_rb_stats(games)
    if group in {"WR", "TE"}:
        return aggregate_receiver_stats(games)
    return {"games_played": len(games)}


def build_performance_window(
    games: list[NFLGameLogRow],
    *,
    source_method: NFLSourceMethod = "UNAVAILABLE",
    target_games: int = 3,
) -> NFLPerformanceWindow:
    selected = select_recent_games(games, limit=target_games)
    quality = evaluate_window_quality(len(selected), target_games)
    dates = [g.game_date for g in selected if g.game_date]
    return NFLPerformanceWindow(
        games_in_window=len(selected),
        window_start=min(dates) if dates else None,
        window_end=max(dates) if dates else None,
        source_method=source_method,
        captured_at=_utcnow(),
        data_quality=quality,
    )


def evaluate_window_quality(games_available: int, target: int = 3) -> str:
    if games_available >= target:
        return "HIGH"
    if games_available == 2:
        return "MEDIUM"
    if games_available == 1:
        return "LOW"
    return "INSUFFICIENT"


def _num(value: Any) -> float:
    if value in (None, "", "-"):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _avg(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)
