"""CardSignal identity helpers — deterministic IDs for players, cards, signals, and forecasts."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

SUPPORTED_LEAGUES = frozenset(
    {
        "MLB",
        "NFL",
        "NBA",
        "NHL",
        "SOCCER",
        "F1",
        "UFC",
        "POKEMON",
        "TCG",
    }
)

SPORT_TO_LEAGUE = {
    "MLB": "MLB",
    "NFL": "NFL",
    "NBA": "NBA",
    "NHL": "NHL",
    "SOCCER": "SOCCER",
    "F1": "F1",
    "UFC": "UFC",
    "POKEMON": "POKEMON",
    "TCG": "TCG",
}

MIN_YEAR = 1900
MAX_YEAR = 2100
MIN_WEEK = 1
MAX_WEEK = 53

IDENTITY_SOURCE_PLACEHOLDER_REGISTRY = "placeholder_registry"


class IdentityValidationError(ValueError):
    """Raised when identity inputs fail validation."""


def normalize_league(league: str) -> str:
    normalized = str(league or "").strip().upper()
    if normalized not in SUPPORTED_LEAGUES:
        raise IdentityValidationError(f"Unsupported league namespace: {league}")
    return normalized


def normalize_source_id(source_id: Any) -> str:
    value = str(source_id or "").strip()
    if not value:
        raise IdentityValidationError("source_player_id is required")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise IdentityValidationError(f"Invalid source_player_id: {source_id}")
    return value


def validate_year(year: int) -> int:
    value = int(year)
    if value < MIN_YEAR or value > MAX_YEAR:
        raise IdentityValidationError(f"Invalid year: {year}")
    return value


def validate_week(week: int) -> int:
    value = int(week)
    if value < MIN_WEEK or value > MAX_WEEK:
        raise IdentityValidationError(f"Invalid week number: {week}")
    return value


def _stable_hash(parts: list[str]) -> str:
    normalized = "|".join(str(part or "").strip().lower() for part in parts)
    hash_value = 2166136261
    for char in normalized:
        hash_value ^= ord(char)
        hash_value = (hash_value * 16777619) & 0xFFFFFFFF

    hex_one = f"{hash_value:08x}"
    hash_two = (hash_value * 2246822519) & 0xFFFFFFFF
    hash_two ^= hash_two >> 13
    hash_two = (hash_two * 3266489917) & 0xFFFFFFFF
    hex_two = f"{hash_two:08x}"
    return f"{hex_one}{hex_two}"[:12]


def sport_to_league(sport: str | None) -> str:
    key = str(sport or "MLB").strip().upper()
    return SPORT_TO_LEAGUE.get(key, key if key in SUPPORTED_LEAGUES else "MLB")


def create_player_cs_id(league: str, source_player_id: Any) -> str:
    league_code = normalize_league(league)
    stable_id = normalize_source_id(source_player_id)
    return f"CS-{league_code}-P-{stable_id}"


def create_player_cs_id_from_name(league: str, player_name: str) -> str:
    league_code = normalize_league(league)
    name = str(player_name or "").strip().lower()
    if not name:
        raise IdentityValidationError("player_name is required when source_player_id is missing")
    stable_id = _stable_hash([league_code, "player-name", name])
    return f"CS-{league_code}-P-{stable_id}"


def parse_set_identity(set_value: str) -> tuple[str, str, str]:
    raw = str(set_value or "").strip()
    year_match = re.match(r"^(\d{4})\s+(.+)$", raw)
    if year_match:
        year, remainder = year_match.groups()
    else:
        year = ""
        remainder = raw

    parts = remainder.split(None, 1)
    manufacturer = parts[0] if parts else ""
    set_name = remainder or raw
    return year, manufacturer, set_name


def normalize_grading_fields(grade: str | None, grading_company: str | None = None) -> tuple[str, str | None]:
    grade_value = str(grade or "Raw").strip() or "Raw"
    if grade_value.lower() == "raw":
        return "Raw", None

    if grading_company:
        return grade_value, str(grading_company).strip() or None

    psa_match = re.match(r"^PSA\s*(\d+(?:\.\d+)?)$", grade_value, re.IGNORECASE)
    if psa_match:
        return psa_match.group(1), "PSA"

    bgs_match = re.match(r"^BGS\s*(\d+(?:\.\d+)?)$", grade_value, re.IGNORECASE)
    if bgs_match:
        return bgs_match.group(1), "BGS"

    sgc_match = re.match(r"^SGC\s*(\d+(?:\.\d+)?)$", grade_value, re.IGNORECASE)
    if sgc_match:
        return sgc_match.group(1), "SGC"

    return grade_value, grading_company


def create_card_stable_id(
    league: str,
    source_player_id: Any,
    *,
    year: str | int,
    manufacturer: str,
    set_name: str,
    card_name: str,
    parallel: str,
    grade: str = "Raw",
    grading_company: str | None = None,
) -> str:
    league_code = normalize_league(league)
    player_id = normalize_source_id(source_player_id)
    grade_value, grading_company_value = normalize_grading_fields(grade, grading_company)

    return _stable_hash(
        [
            league_code,
            player_id,
            str(year or ""),
            manufacturer,
            set_name,
            card_name,
            parallel,
            grade_value,
            grading_company_value or "",
        ]
    )


def create_card_cs_id(league: str, card_identity: dict[str, Any]) -> str:
    league_code = normalize_league(league)
    source_player_id = card_identity.get("source_player_id") or card_identity.get("cs_player_id", "").split("-")[-1]
    if not source_player_id and card_identity.get("player_name"):
        source_player_id = _stable_hash(["player-name", card_identity["player_name"]])

    stable_card_id = create_card_stable_id(
        league_code,
        source_player_id,
        year=card_identity.get("year") or "",
        manufacturer=card_identity.get("manufacturer") or "",
        set_name=card_identity.get("set_name") or card_identity.get("set") or "",
        card_name=card_identity.get("card_name") or card_identity.get("card") or "",
        parallel=card_identity.get("parallel") or "",
        grade=card_identity.get("grade") or "Raw",
        grading_company=card_identity.get("grading_company"),
    )
    return f"CS-{league_code}-C-{stable_card_id}"


def create_signal_cs_id(league: str, year: int, week: int, source_player_id: Any) -> str:
    league_code = normalize_league(league)
    year_value = validate_year(year)
    week_value = validate_week(week)
    stable_id = normalize_source_id(source_player_id)
    return f"CS-{league_code}-S-{year_value}W{week_value}-{stable_id}"


def create_forecast_cs_id(league: str, year: int, week: int, source_player_id: Any) -> str:
    league_code = normalize_league(league)
    year_value = validate_year(year)
    week_value = validate_week(week)
    stable_id = normalize_source_id(source_player_id)
    return f"CS-{league_code}-F-{year_value}W{week_value}-{stable_id}"


def current_iso_week_year(reference: datetime | None = None) -> tuple[int, int]:
    moment = reference or datetime.now(timezone.utc)
    iso = moment.isocalendar()
    return int(iso.year), int(iso.week)


def resolve_source_player_id(entry: dict[str, Any]) -> str | None:
    for key in ("source_player_id", "player_id"):
        value = entry.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def build_player_identity(entry: dict[str, Any]) -> dict[str, Any]:
    sport = str(entry.get("sport") or "MLB").strip().upper()
    league = str(entry.get("league") or sport_to_league(sport)).strip().upper()
    player_name = entry.get("player_name") or entry.get("full_name") or ""
    source_player_id = resolve_source_player_id(entry)

    if source_player_id:
        cs_player_id = create_player_cs_id(league, source_player_id)
    else:
        cs_player_id = create_player_cs_id_from_name(league, player_name)
        source_player_id = None

    year, week = current_iso_week_year()
    signal_source = source_player_id or cs_player_id.split("-")[-1]
    forecast_source = signal_source

    identity = {
        "cs_player_id": cs_player_id,
        "source_player_id": source_player_id,
        "league": league,
        "sport": sport,
        "player_name": player_name,
        "cs_signal_id": create_signal_cs_id(league, year, week, signal_source),
        "cs_forecast_id": create_forecast_cs_id(league, year, week, forecast_source),
        "signal_year": year,
        "signal_week": week,
    }
    return identity


def enrich_player_entry(entry: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(entry)
    enriched.update(build_player_identity(entry))
    return enriched


def enrich_card_registry_entry(
    card: dict[str, Any],
    *,
    league: str,
    source_player_id: Any,
    cs_player_id: str,
    player_name: str = "",
) -> dict[str, Any]:
    set_value = card.get("set") or ""
    year = str(card.get("year") or parse_set_identity(set_value)[0] or "")
    manufacturer = card.get("manufacturer") or parse_set_identity(set_value)[1]
    set_name = card.get("set_name") or parse_set_identity(set_value)[2]
    card_name = card.get("card_name") or card.get("card") or ""
    parallel = card.get("parallel") or ""
    grade, grading_company = normalize_grading_fields(
        card.get("grade"),
        card.get("grading_company"),
    )

    identity_fields = {
        "year": year,
        "manufacturer": manufacturer,
        "set_name": set_name,
        "card_name": card_name,
        "parallel": parallel,
        "grade": grade,
        "grading_company": grading_company,
        "league": normalize_league(league),
        "source_player_id": str(source_player_id) if source_player_id is not None else None,
        "cs_player_id": cs_player_id,
        "player_name": player_name,
        "source": card.get("source") or IDENTITY_SOURCE_PLACEHOLDER_REGISTRY,
    }

    identity_fields["cs_card_id"] = create_card_cs_id(
        league,
        {
            **identity_fields,
            "set": set_value,
            "card": card_name,
        },
    )

    return {**card, **identity_fields}
