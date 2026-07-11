"""Fetch and store league season metadata from official APIs (pipeline only)."""

from __future__ import annotations

from datetime import datetime, timezone

from cardchase_ai.clients.mlb import MLBClient
from cardchase_ai.models.signal_driver import LeagueSeasonMetadata, SIGNAL_DRIVERS_V1
from cardchase_ai.signal_driver_storage import SignalDriverStorage


def _parse_mlb_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt
    except ValueError:
        return None


def fetch_mlb_season_metadata(season: int, mlb_client: MLBClient | None = None) -> LeagueSeasonMetadata | None:
    """Fetch MLB season phase boundaries from the official Stats API."""
    client = mlb_client or MLBClient()
    try:
        data = client._get(f"/seasons/{season}/types", params={"sportId": 1})
    except Exception:
        return None

    seasons = data.get("seasons", [])
    if not seasons:
        return None

    season_obj = seasons[0]
    types = season_obj.get("seasonTypes", []) or season_obj.get("types", [])

    regular_start = regular_end = postseason_start = postseason_end = None
    preseason_start = preseason_end = None

    for phase in types:
        code = str(phase.get("code", "")).lower()
        start = _parse_mlb_date(phase.get("startDate") or phase.get("regularSeasonStartDate"))
        end = _parse_mlb_date(phase.get("endDate") or phase.get("regularSeasonEndDate"))

        if code in {"r", "reg", "regular"}:
            regular_start = start
            regular_end = end
        elif code in {"p", "post", "postseason"}:
            postseason_start = start
            postseason_end = end
        elif code in {"s", "spring", "spring_training"}:
            preseason_start = start
            preseason_end = end

    # Fallback to top-level season dates
    if regular_start is None:
        regular_start = _parse_mlb_date(season_obj.get("regularSeasonStartDate"))
    if regular_end is None:
        regular_end = _parse_mlb_date(season_obj.get("regularSeasonEndDate"))
    if postseason_start is None:
        postseason_start = _parse_mlb_date(season_obj.get("postSeasonStartDate"))
    if postseason_end is None:
        postseason_end = _parse_mlb_date(season_obj.get("postSeasonEndDate"))

    if not any([regular_start, regular_end, postseason_start, preseason_start]):
        return None

    offseason_start = None
    offseason_end = None
    if regular_end:
        offseason_start = regular_end
    if regular_start:
        offseason_end = regular_start

    return LeagueSeasonMetadata(
        league="MLB",
        sport="MLB",
        season=season,
        regular_season_start=regular_start,
        regular_season_end=regular_end,
        postseason_start=postseason_start,
        postseason_end=postseason_end,
        preseason_start=preseason_start,
        preseason_end=preseason_end,
        offseason_start=offseason_start,
        offseason_end=offseason_end,
        source_type="OFFICIAL_API",
        source_reference=f"mlb_stats_api:seasons/{season}/types",
        captured_at=datetime.now(timezone.utc),
        algorithm_version=SIGNAL_DRIVERS_V1,
    )


def refresh_league_season_metadata(
    league: str,
    season: int,
    storage: SignalDriverStorage,
    mlb_client: MLBClient | None = None,
) -> LeagueSeasonMetadata | None:
    """Refresh stored metadata during pipeline runs — not for GET handlers."""
    league = league.upper()
    if league == "MLB":
        metadata = fetch_mlb_season_metadata(season, mlb_client)
        if metadata:
            storage.upsert_league_metadata(metadata)
        return metadata
    return None
