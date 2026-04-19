from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable


@dataclass
class AlertEvent:
    player_id: str | None
    player_name: str
    event_type: str
    title: str
    message: str
    metadata: dict[str, Any]

    def to_row(self, run_id: int, user_id: str, channel: str = "in_app") -> dict[str, Any]:
        return {
            "run_id": run_id,
            "user_id": user_id,
            "player_id": self.player_id,
            "player_name": self.player_name,
            "event_type": self.event_type,
            "channel": channel,
            "title": self.title,
            "message": self.message,
            "metadata": self.metadata,
        }


def _round(value: Any) -> float:
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return 0.0


def _index_by_name(items: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item["player_name"]: item for item in items}


def _hotness(entry: dict[str, Any] | None) -> dict[str, Any]:
    return (entry or {}).get("hotness", {})


def detect_player_events(
    current_entries: list[dict[str, Any]],
    previous_entries: list[dict[str, Any]],
    hotness_jump_threshold: float = 8.0,
) -> dict[str, list[AlertEvent]]:
    previous_map = _index_by_name(previous_entries)
    events_by_player: dict[str, list[AlertEvent]] = {}

    for entry in current_entries:
        player_name = entry["player_name"]
        player_id = entry.get("player_id")
        current_hotness = _hotness(entry)
        current_total = _round(current_hotness.get("total_score"))
        current_perf = _round(current_hotness.get("performance_score"))
        current_market = _round(current_hotness.get("market_score"))
        current_tag = current_hotness.get("tag", "WATCH")

        player_events: list[AlertEvent] = []
        previous_entry = previous_map.get(player_name)
        previous_total = _round(_hotness(previous_entry).get("total_score")) if previous_entry else 0.0
        delta = round(current_total - previous_total, 2)

        if previous_entry and delta >= hotness_jump_threshold:
            player_events.append(
                AlertEvent(
                    player_id=player_id,
                    player_name=player_name,
                    event_type="hotness_jump",
                    title=f"{player_name} jumped {delta} points",
                    message=(
                        f"{player_name} climbed from {previous_total} to {current_total} on the MLB Hotness board. "
                        f"Current tag: {current_tag}."
                    ),
                    metadata={
                        "delta": delta,
                        "previous_total_score": previous_total,
                        "current_total_score": current_total,
                        "tag": current_tag,
                    },
                )
            )

        if current_tag == "BUY LOW" and current_perf >= 75:
            player_events.append(
                AlertEvent(
                    player_id=player_id,
                    player_name=player_name,
                    event_type="buy_low",
                    title=f"Buy low setup: {player_name}",
                    message=(
                        f"{player_name} is showing strong on-field form ({current_perf}) while the market score remains at "
                        f"{current_market}."
                    ),
                    metadata={
                        "performance_score": current_perf,
                        "market_score": current_market,
                        "total_score": current_total,
                        "tag": current_tag,
                    },
                )
            )

        if current_tag == "CHASED" and current_market >= 75:
            player_events.append(
                AlertEvent(
                    player_id=player_id,
                    player_name=player_name,
                    event_type="most_chased",
                    title=f"Chased in the market: {player_name}",
                    message=(
                        f"{player_name} is being chased right now with a market score of {current_market} and tag {current_tag}."
                    ),
                    metadata={
                        "market_score": current_market,
                        "performance_score": current_perf,
                        "total_score": current_total,
                        "tag": current_tag,
                    },
                )
            )

        if player_events:
            events_by_player[player_name] = player_events

    return events_by_player


def build_daily_digest(current_entries: list[dict[str, Any]], watchlist_names: list[str]) -> AlertEvent | None:
    if not current_entries:
        return None

    watch_set = set(watchlist_names)
    watched = [entry for entry in current_entries if entry["player_name"] in watch_set]
    top_board = current_entries[:3]
    focus = watched[:3] if watched else top_board
    lines = []
    for entry in focus:
        hotness = _hotness(entry)
        lines.append(f"{entry['player_name']}: {hotness.get('tag', 'WATCH')} at {hotness.get('total_score', 0)}")
    summary = "; ".join(lines)
    return AlertEvent(
        player_id=None,
        player_name="Daily Digest",
        event_type="daily_digest",
        title="Your daily CardChase MLB digest",
        message=f"Here is your latest MLB card market snapshot: {summary}",
        metadata={
            "watchlist_count": len(watchlist_names),
            "summary_players": [entry["player_name"] for entry in focus],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    )


def event_passes_player_rule(event: AlertEvent, rule: dict[str, Any] | None, default_hotness_jump_threshold: float = 8.0) -> bool:
    if not rule:
        if event.event_type != "hotness_jump":
            return True
        return _round(event.metadata.get("delta")) >= default_hotness_jump_threshold

    muted_until = rule.get("muted_until")
    if muted_until:
        try:
            if datetime.fromisoformat(str(muted_until).replace("Z", "+00:00")) > datetime.now(timezone.utc):
                return False
        except ValueError:
            pass

    event_toggle_map = {
        "hotness_jump": bool(rule.get("alert_on_hotness_jump", True)),
        "buy_low": bool(rule.get("alert_on_buy_low", True)),
        "most_chased": bool(rule.get("alert_on_most_chased", False)),
        "daily_digest": True,
    }
    if not event_toggle_map.get(event.event_type, True):
        return False

    if event.event_type == "hotness_jump":
        required = _round(rule.get("min_hotness_delta") or default_hotness_jump_threshold)
        return _round(event.metadata.get("delta")) >= required

    return True
