"""Validation for the NFL provider import file (`output/nfl/import/nfl_data.json`).

Derived from `cardchase_ai.clients.nfl_import.NFLImportProvider` and unit fixtures.
Does not invent schema rules beyond what the loader and models consume.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from cardchase_ai.models.nfl import POSITION_MAP

ALLOWED_SOURCE_METHODS = frozenset({
    "OFFICIAL_API",
    "LICENSED_API",
    "APPROVED_IMPORT",
    "MANUAL_VERIFIED",
})

# Availability requires at least one player + source_method (see NFLImportProvider.is_available).
MIN_PLAYERS_FOR_AVAILABILITY = 1

SYNTHETIC_ID_PREFIXES = ("TEST-", "DEMO-", "MOCK-", "FAKE-", "SAMPLE-")
SYNTHETIC_NAME_MARKERS = (
    "test quarterback",
    "test running back",
    "test wide receiver",
    "test tight end",
    "test qb",
    "test player",
    "demo player",
)

@dataclass
class NflDataValidationReport:
    valid: bool
    safe_to_import: bool
    player_count: int = 0
    active_player_count: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    duplicate_player_ids: list[str] = field(default_factory=list)
    synthetic_markers: list[str] = field(default_factory=list)
    source_method: str | None = None
    season: int | None = None
    games_player_keys: int = 0
    season_stats_player_keys: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "safe_to_import": self.safe_to_import,
            "player_count": self.player_count,
            "active_player_count": self.active_player_count,
            "errors": self.errors,
            "warnings": self.warnings,
            "duplicate_player_ids": self.duplicate_player_ids,
            "synthetic_markers": self.synthetic_markers,
            "source_method": self.source_method,
            "season": self.season,
            "games_player_keys": self.games_player_keys,
            "season_stats_player_keys": self.season_stats_player_keys,
            "minimum_players_required": MIN_PLAYERS_FOR_AVAILABILITY,
        }


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _looks_synthetic_id(source_id: str) -> bool:
    upper = source_id.upper()
    return any(upper.startswith(prefix) for prefix in SYNTHETIC_ID_PREFIXES)


def _looks_synthetic_name(name: str) -> bool:
    lowered = name.strip().lower()
    return any(marker in lowered for marker in SYNTHETIC_NAME_MARKERS)


def _parse_iso_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def validate_nfl_data_payload(
    data: dict[str, Any],
    *,
    allow_synthetic: bool = False,
    require_season_stats: bool = False,
    require_games: bool = False,
    expected_season: int | None = None,
) -> NflDataValidationReport:
    """Validate an in-memory NFL provider import payload."""
    report = NflDataValidationReport(valid=True, safe_to_import=True)

    if not isinstance(data, dict):
        report.errors.append("Top-level JSON must be an object")
        report.valid = False
        report.safe_to_import = False
        return report

    source_method = data.get("source_method")
    if not source_method:
        report.errors.append("Top-level source_method is required for availability")
    else:
        method = str(source_method).upper()
        report.source_method = method
        if method not in ALLOWED_SOURCE_METHODS:
            report.errors.append(
                f"source_method must be one of {sorted(ALLOWED_SOURCE_METHODS)}; got {source_method!r}"
            )
        elif method == "UNAVAILABLE":
            report.errors.append("source_method UNAVAILABLE cannot activate the NFL provider")

    season = data.get("season")
    if season is not None:
        try:
            report.season = int(season)
        except (TypeError, ValueError):
            report.errors.append(f"Top-level season must be an integer; got {season!r}")
        else:
            if expected_season is not None and report.season != expected_season:
                report.errors.append(
                    f"Top-level season {report.season} does not match expected {expected_season}"
                )
            if report.season < 1970 or report.season > 2100:
                report.errors.append(f"Top-level season out of range: {report.season}")
    elif expected_season is not None:
        report.warnings.append(
            f"Top-level season missing; expected season for production is {expected_season}"
        )

    if data.get("last_updated"):
        try:
            datetime.fromisoformat(str(data["last_updated"]).replace("Z", "+00:00"))
        except ValueError:
            report.warnings.append("last_updated is not ISO-8601 parseable")

    players = data.get("players")
    if not isinstance(players, list):
        report.errors.append("Top-level players must be an array")
        players = []
    report.player_count = len(players)

    if report.player_count < MIN_PLAYERS_FOR_AVAILABILITY:
        report.errors.append(
            f"At least {MIN_PLAYERS_FOR_AVAILABILITY} player is required for /api/nfl/status available:true"
        )

    seen_ids: set[str] = set()
    active_count = 0
    position_by_id: dict[str, str | None] = {}

    for index, player in enumerate(players):
        if not isinstance(player, dict):
            report.errors.append(f"players[{index}] must be an object")
            continue

        source_id = str(player.get("source_player_id") or "").strip()
        if not source_id:
            report.errors.append(f"players[{index}].source_player_id is required")
        elif source_id in seen_ids:
            report.duplicate_player_ids.append(source_id)
            report.errors.append(f"Duplicate source_player_id: {source_id}")
        else:
            seen_ids.add(source_id)

        name = str(player.get("player_name") or "").strip()
        if not name:
            report.errors.append(f"players[{index}] ({source_id or '?'}).player_name is required")

        position = player.get("position")
        if not position:
            report.warnings.append(
                f"players[{index}] ({source_id or '?'}).position missing — scores as UNKNOWN"
            )
        else:
            mapped = POSITION_MAP.get(str(position).strip().upper())
            if mapped is None:
                report.warnings.append(
                    f"players[{index}] ({source_id}).position {position!r} maps to UNKNOWN"
                )

        if source_id:
            position_by_id[source_id] = str(position).strip().upper() if position else None

        status = str(player.get("active_status", "ACTIVE")).upper()
        if status != "RETIRED":
            active_count += 1

        if source_id and _looks_synthetic_id(source_id):
            report.synthetic_markers.append(f"id:{source_id}")
        if name and _looks_synthetic_name(name):
            report.synthetic_markers.append(f"name:{name}")

        player_season = player.get("season")
        if player_season is not None:
            try:
                int(player_season)
            except (TypeError, ValueError):
                report.errors.append(
                    f"players[{index}] ({source_id}).season must be an integer"
                )

    report.active_player_count = active_count
    if report.player_count and active_count == 0:
        report.errors.append("All players are RETIRED — provider active universe would be empty")

    games = data.get("games") or {}
    if games and not isinstance(games, dict):
        report.errors.append("games must be an object keyed by source_player_id")
        games = {}
    report.games_player_keys = len(games) if isinstance(games, dict) else 0

    if require_games and report.games_player_keys == 0:
        report.errors.append("games map is required by validation flags but missing/empty")

    for sid, rows in games.items() if isinstance(games, dict) else []:
        if sid not in seen_ids:
            report.warnings.append(f"games key {sid!r} has no matching players[].source_player_id")
        if not isinstance(rows, list):
            report.errors.append(f"games[{sid}] must be an array")
            continue
        for g_index, raw in enumerate(rows):
            if not isinstance(raw, dict):
                report.errors.append(f"games[{sid}][{g_index}] must be an object")
                continue
            game_date = str(raw.get("game_date") or "").strip()
            if not game_date and not raw.get("is_bye_week"):
                report.errors.append(f"games[{sid}][{g_index}].game_date is required for non-bye rows")
            elif game_date and _parse_iso_date(game_date) is None:
                report.errors.append(f"games[{sid}][{g_index}].game_date invalid: {game_date!r}")

            if "season" not in raw:
                report.warnings.append(f"games[{sid}][{g_index}].season missing")
            else:
                try:
                    game_season = int(raw["season"])
                except (TypeError, ValueError):
                    report.errors.append(f"games[{sid}][{g_index}].season must be an integer")
                else:
                    if expected_season is not None and game_season != expected_season:
                        report.warnings.append(
                            f"games[{sid}][{g_index}].season {game_season} != expected {expected_season}"
                        )

            stats = raw.get("stats") or {}
            if stats and not isinstance(stats, dict):
                report.errors.append(f"games[{sid}][{g_index}].stats must be an object")
                continue
            for key, value in (stats or {}).items():
                if value is None:
                    continue
                if not _is_number(value):
                    report.errors.append(
                        f"games[{sid}][{g_index}].stats.{key} must be numeric; got {value!r}"
                    )
                elif float(value) < 0:
                    report.errors.append(
                        f"games[{sid}][{g_index}].stats.{key} must be nonnegative"
                    )

    season_stats = data.get("season_stats") or {}
    if season_stats and not isinstance(season_stats, dict):
        report.errors.append("season_stats must be an object keyed by source_player_id")
        season_stats = {}
    report.season_stats_player_keys = len(season_stats) if isinstance(season_stats, dict) else 0

    if require_season_stats and report.season_stats_player_keys == 0:
        report.errors.append("season_stats map is required by validation flags but missing/empty")

    for sid, entry in season_stats.items() if isinstance(season_stats, dict) else []:
        if sid not in seen_ids:
            report.warnings.append(
                f"season_stats key {sid!r} has no matching players[].source_player_id"
            )
        if not isinstance(entry, dict):
            report.errors.append(f"season_stats[{sid}] must be an object")
            continue
        entry_season = entry.get("season")
        if entry_season is not None:
            try:
                int(entry_season)
            except (TypeError, ValueError):
                report.errors.append(f"season_stats[{sid}].season must be an integer")
        stats = entry.get("stats") if isinstance(entry.get("stats"), dict) else entry
        if not isinstance(stats, dict):
            report.errors.append(f"season_stats[{sid}] stats payload invalid")
            continue
        for key, value in stats.items():
            if key in {"season", "source_method"} or value is None:
                continue
            if not _is_number(value):
                # allow nested non-stat metadata only when under explicit stats key path
                if entry.get("stats") is stats:
                    report.errors.append(
                        f"season_stats[{sid}].stats.{key} must be numeric; got {value!r}"
                    )
            elif float(value) < 0:
                report.errors.append(
                    f"season_stats[{sid}].stats.{key} must be nonnegative"
                )

    schedule = data.get("schedule")
    if schedule is not None and not isinstance(schedule, list):
        report.errors.append("schedule must be an array when present")

    developments = data.get("developments")
    if developments is not None and not isinstance(developments, dict):
        report.errors.append("developments must be an object keyed by source_player_id when present")

    if report.synthetic_markers and not allow_synthetic:
        report.errors.append(
            "Synthetic/test markers detected — refusing production import: "
            + ", ".join(sorted(set(report.synthetic_markers))[:12])
        )

    if report.duplicate_player_ids:
        # already in errors; keep safe_to_import false
        pass

    report.valid = len(report.errors) == 0
    report.safe_to_import = report.valid
    if report.valid and report.season_stats_player_keys == 0 and report.games_player_keys == 0:
        report.warnings.append(
            "No games or season_stats present — status can become available, "
            "but scouting/recent windows will be evidence-light / offseason-only"
        )
    return report


def validate_nfl_data_file(
    path: str | Path,
    *,
    allow_synthetic: bool = False,
    require_season_stats: bool = False,
    require_games: bool = False,
    expected_season: int | None = None,
) -> NflDataValidationReport:
    """Load and validate an NFL provider import JSON file. Never writes."""
    file_path = Path(path)
    if not file_path.exists():
        return NflDataValidationReport(
            valid=False,
            safe_to_import=False,
            errors=[f"File not found: {file_path}"],
        )
    try:
        raw = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return NflDataValidationReport(
            valid=False,
            safe_to_import=False,
            errors=[f"Invalid JSON: {exc}"],
        )
    except OSError as exc:
        return NflDataValidationReport(
            valid=False,
            safe_to_import=False,
            errors=[f"Unable to read file: {exc}"],
        )
    if not isinstance(raw, dict):
        return NflDataValidationReport(
            valid=False,
            safe_to_import=False,
            errors=["Top-level JSON must be an object"],
        )
    return validate_nfl_data_payload(
        raw,
        allow_synthetic=allow_synthetic,
        require_season_stats=require_season_stats,
        require_games=require_games,
        expected_season=expected_season,
    )


def looks_like_provider_file(payload: Any) -> bool:
    return isinstance(payload, dict) and isinstance(payload.get("players"), list)


def looks_like_previous_season_records(payload: Any) -> bool:
    return isinstance(payload, list)


_SLUG_RE = re.compile(r"[^A-Za-z0-9._-]+")


def suggest_import_path(output_dir: Path) -> Path:
    return Path(output_dir) / "nfl" / "import" / "nfl_data.json"
