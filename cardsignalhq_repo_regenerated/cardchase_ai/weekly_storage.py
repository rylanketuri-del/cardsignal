"""Persistence layer for weekly intelligence (Supabase + local JSON fallback)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cardchase_ai.models.weekly import (
    CardWeeklyIntelligenceSnapshot,
    PlayerWeeklySignalSnapshot,
    SignalOfTheWeek,
    WeeklyHomepageIntelligence,
    WeeklyIntelligenceRun,
)
from cardchase_ai.storage import SupabaseStorage, SupabaseError


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _serialize(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    return obj


class WeeklyJsonStorage:
    """Append-only local JSON storage when Supabase is unavailable."""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir / "weekly"
        self.runs_dir = self.base_dir / "runs"
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.base_dir / "index.json"
        self.latest_path = self.base_dir / "latest_completed.json"

    def _load_index(self) -> list[dict[str, Any]]:
        if not self.index_path.exists():
            return []
        return json.loads(self.index_path.read_text(encoding="utf-8"))

    def _save_index(self, index: list[dict[str, Any]]) -> None:
        self.index_path.write_text(json.dumps(index, indent=2, default=_serialize), encoding="utf-8")

    def _run_path(self, run_id: str) -> Path:
        return self.runs_dir / f"{run_id}.json"

    def find_official_completed_run(
        self,
        league: str,
        year: int,
        week_number: int,
        *,
        force: bool = False,
    ) -> WeeklyIntelligenceRun | None:
        for entry in self._load_index():
            if (
                entry.get("league") == league.upper()
                and entry.get("year") == year
                and entry.get("week_number") == week_number
                and entry.get("status") in {"COMPLETED", "PARTIAL"}
                and not entry.get("force")
                and entry.get("triggered_by") != "test"
            ):
                run_id = entry["run_id"]
                data = json.loads(self._run_path(run_id).read_text(encoding="utf-8"))
                return WeeklyIntelligenceRun.model_validate(data["run"])
        return None

    def create_run(self, run: WeeklyIntelligenceRun) -> WeeklyIntelligenceRun:
        payload = {
            "run": run.model_dump(mode="json"),
            "player_snapshots": [],
            "card_snapshots": [],
            "signal_of_the_week": None,
            "homepage": None,
        }
        self._run_path(run.run_id).write_text(json.dumps(payload, indent=2, default=_serialize), encoding="utf-8")
        index = self._load_index()
        index.append(
            {
                "run_id": run.run_id,
                "league": run.league,
                "year": run.year,
                "week_number": run.week_number,
                "status": run.status,
                "force": run.force,
                "triggered_by": run.triggered_by,
                "created_at": run.created_at.isoformat() if run.created_at else None,
            }
        )
        self._save_index(index)
        return run

    def update_run(self, run: WeeklyIntelligenceRun) -> None:
        path = self._run_path(run.run_id)
        data = json.loads(path.read_text(encoding="utf-8"))
        data["run"] = run.model_dump(mode="json")
        path.write_text(json.dumps(data, indent=2, default=_serialize), encoding="utf-8")
        index = self._load_index()
        for entry in index:
            if entry["run_id"] == run.run_id:
                entry["status"] = run.status
                break
        self._save_index(index)

    def append_run_payload(
        self,
        run: WeeklyIntelligenceRun,
        player_snapshots: list[PlayerWeeklySignalSnapshot],
        card_snapshots: list[CardWeeklyIntelligenceSnapshot],
        signal: SignalOfTheWeek | None,
        homepage: WeeklyHomepageIntelligence,
        *,
        market_movements: list | None = None,
    ) -> None:
        path = self._run_path(run.run_id)
        data = json.loads(path.read_text(encoding="utf-8"))
        data["run"] = run.model_dump(mode="json")
        data["player_snapshots"] = [s.model_dump(mode="json") for s in player_snapshots]
        data["card_snapshots"] = [s.model_dump(mode="json") for s in card_snapshots]
        data["signal_of_the_week"] = signal.model_dump(mode="json") if signal else None
        data["homepage"] = homepage.model_dump(mode="json")
        data["market_movements"] = [
            m.model_dump(mode="json") if hasattr(m, "model_dump") else m for m in (market_movements or [])
        ]
        data["stage_outcomes"] = run.stage_outcomes
        path.write_text(json.dumps(data, indent=2, default=_serialize), encoding="utf-8")
        self.update_run(run)
        if run.status in {"COMPLETED", "PARTIAL"} and not run.force and run.triggered_by != "test":
            self.latest_path.write_text(
                json.dumps({"run_id": run.run_id, "league": run.league}, indent=2),
                encoding="utf-8",
            )

    def fetch_latest_completed(self, league: str = "MLB") -> dict[str, Any] | None:
        if self.latest_path.exists():
            pointer = json.loads(self.latest_path.read_text(encoding="utf-8"))
            if pointer.get("league", "MLB").upper() == league.upper():
                run_id = pointer["run_id"]
                if self._run_path(run_id).exists():
                    return json.loads(self._run_path(run_id).read_text(encoding="utf-8"))

        candidates = [
            e for e in self._load_index()
            if e.get("league") == league.upper()
            and e.get("status") in {"COMPLETED", "PARTIAL"}
            and not e.get("force")
            and e.get("triggered_by") != "test"
        ]
        if not candidates:
            return None
        run_id = candidates[-1]["run_id"]
        return json.loads(self._run_path(run_id).read_text(encoding="utf-8"))

    def fetch_player_weekly_history(self, cs_player_id: str, limit: int = 12) -> list[dict[str, Any]]:
        history: list[dict[str, Any]] = []
        for entry in self._load_index():
            run_id = entry["run_id"]
            path = self._run_path(run_id)
            if not path.exists():
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            for snap in data.get("player_snapshots", []):
                if snap.get("cs_player_id") == cs_player_id:
                    history.append(snap)
        history.sort(key=lambda s: s.get("captured_at") or "")
        return history[-limit:]

    def fetch_card_weekly_history(self, cs_card_id: str, limit: int = 12) -> list[dict[str, Any]]:
        history: list[dict[str, Any]] = []
        for entry in self._load_index():
            path = self._run_path(entry["run_id"])
            if not path.exists():
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            for snap in data.get("card_snapshots", []):
                if snap.get("cs_card_id") == cs_card_id:
                    history.append(snap)
        history.sort(key=lambda s: s.get("captured_at") or "")
        return history[-limit:]


class WeeklyStorage:
    """Unified weekly storage with Supabase primary and JSON fallback."""

    RUNS_TABLE = "weekly_intelligence_runs"
    PLAYER_SNAPSHOTS_TABLE = "player_weekly_signal_snapshots"
    CARD_SNAPSHOTS_TABLE = "card_weekly_intelligence_snapshots"
    SIGNAL_TABLE = "signal_of_the_week"

    def __init__(self, supabase: SupabaseStorage | None, json_storage: WeeklyJsonStorage):
        self.supabase = supabase
        self.json = json_storage

    @property
    def uses_supabase(self) -> bool:
        return self.supabase is not None

    def find_official_completed_run(
        self,
        league: str,
        year: int,
        week_number: int,
    ) -> WeeklyIntelligenceRun | None:
        if self.supabase:
            try:
                rows = self.supabase._get(
                    self.RUNS_TABLE,
                    {
                        "select": "*",
                        "league": f"eq.{league.upper()}",
                        "year": f"eq.{year}",
                        "week_number": f"eq.{week_number}",
                        "status": "in.(COMPLETED,PARTIAL)",
                        "force": "eq.false",
                        "triggered_by": "neq.test",
                        "order": "created_at.desc",
                        "limit": "1",
                    },
                )
                if rows:
                    return self._row_to_run(rows[0])
            except SupabaseError:
                pass
        return self.json.find_official_completed_run(league, year, week_number)

    def create_run(self, run: WeeklyIntelligenceRun) -> WeeklyIntelligenceRun:
        if self.supabase:
            try:
                row = self._run_to_row(run)
                rows = self.supabase._post(self.RUNS_TABLE, row, prefer="return=representation")
                return self._row_to_run(rows[0])
            except SupabaseError:
                pass
        return self.json.create_run(run)

    def update_run(self, run: WeeklyIntelligenceRun) -> None:
        if self.supabase:
            try:
                payload = self._run_to_row(run)
                del payload["run_id"]
                self.supabase._patch(
                    self.RUNS_TABLE,
                    {"run_id": f"eq.{run.run_id}"},
                    payload,
                )
                return
            except SupabaseError:
                pass
        self.json.update_run(run)

    def persist_run_results(
        self,
        run: WeeklyIntelligenceRun,
        player_snapshots: list[PlayerWeeklySignalSnapshot],
        card_snapshots: list[CardWeeklyIntelligenceSnapshot],
        signal: SignalOfTheWeek | None,
        homepage: WeeklyHomepageIntelligence,
        *,
        market_movements: list | None = None,
    ) -> None:
        if self.supabase:
            try:
                payload = self._run_to_row(run)
                payload["homepage_payload"] = homepage.model_dump(mode="json")
                payload["stage_outcomes"] = run.stage_outcomes
                self.supabase._patch(
                    self.RUNS_TABLE,
                    {"run_id": f"eq.{run.run_id}"},
                    payload,
                )
                if player_snapshots:
                    self.supabase._post(
                        self.PLAYER_SNAPSHOTS_TABLE,
                        [self._player_snapshot_to_row(s) for s in player_snapshots],
                    )
                if card_snapshots:
                    self.supabase._post(
                        self.CARD_SNAPSHOTS_TABLE,
                        [self._card_snapshot_to_row(s) for s in card_snapshots],
                    )
                if signal:
                    self.supabase._post(self.SIGNAL_TABLE, [self._signal_to_row(signal)])
                return
            except SupabaseError:
                pass
        self.json.append_run_payload(
            run,
            player_snapshots,
            card_snapshots,
            signal,
            homepage,
            market_movements=market_movements,
        )

    def fetch_latest_completed_payload(self, league: str = "MLB") -> dict[str, Any] | None:
        if self.supabase:
            try:
                rows = self.supabase._get(
                    self.RUNS_TABLE,
                    {
                        "select": "*",
                        "league": f"eq.{league.upper()}",
                        "status": "in.(COMPLETED,PARTIAL)",
                        "force": "eq.false",
                        "triggered_by": "neq.test",
                        "order": "completed_at.desc",
                        "limit": "1",
                    },
                )
                if not rows:
                    return None
                run_row = rows[0]
                run_id = run_row["run_id"]
                player_rows = self.supabase._get(
                    self.PLAYER_SNAPSHOTS_TABLE,
                    {"select": "*", "run_id": f"eq.{run_id}", "order": "rank.asc"},
                )
                card_rows = self.supabase._get(
                    self.CARD_SNAPSHOTS_TABLE,
                    {"select": "*", "run_id": f"eq.{run_id}"},
                )
                signal_rows = self.supabase._get(
                    self.SIGNAL_TABLE,
                    {"select": "*", "run_id": f"eq.{run_id}", "limit": "1"},
                )
                return {
                    "run": run_row,
                    "player_snapshots": player_rows,
                    "card_snapshots": card_rows,
                    "signal_of_the_week": signal_rows[0] if signal_rows else None,
                    "homepage": run_row.get("homepage_payload"),
                }
            except SupabaseError:
                pass
        return self.json.fetch_latest_completed(league)

    def fetch_player_weekly_history(self, cs_player_id: str, limit: int = 12) -> list[dict[str, Any]]:
        if self.supabase:
            try:
                rows = self.supabase._get(
                    self.PLAYER_SNAPSHOTS_TABLE,
                    {
                        "select": "*",
                        "cs_player_id": f"eq.{cs_player_id}",
                        "order": "captured_at.asc",
                        "limit": str(limit),
                    },
                )
                return rows
            except SupabaseError:
                pass
        return self.json.fetch_player_weekly_history(cs_player_id, limit)

    def fetch_card_weekly_history(self, cs_card_id: str, limit: int = 12) -> list[dict[str, Any]]:
        if self.supabase:
            try:
                rows = self.supabase._get(
                    self.CARD_SNAPSHOTS_TABLE,
                    {
                        "select": "*",
                        "cs_card_id": f"eq.{cs_card_id}",
                        "order": "captured_at.asc",
                        "limit": str(limit),
                    },
                )
                return rows
            except SupabaseError:
                pass
        return self.json.fetch_card_weekly_history(cs_card_id, limit)

    def fetch_prior_official_player_snapshot(
        self,
        cs_player_id: str,
        league: str,
        year: int,
        week_number: int,
    ) -> PlayerWeeklySignalSnapshot | None:
        if self.supabase:
            try:
                rows = self.supabase._get(
                    self.PLAYER_SNAPSHOTS_TABLE,
                    {
                        "select": "*",
                        "cs_player_id": f"eq.{cs_player_id}",
                        "league": f"eq.{league.upper()}",
                        "order": "captured_at.desc",
                        "limit": "5",
                    },
                )
                for row in rows:
                    row_year = int(row.get("year") or 0)
                    row_week = int(row.get("week_number") or 0)
                    if (row_year, row_week) < (year, week_number):
                        return PlayerWeeklySignalSnapshot.model_validate(self._player_row_to_dict(row))
            except SupabaseError:
                pass
        history = self.json.fetch_player_weekly_history(cs_player_id, limit=24)
        prior = [
            h for h in history
            if (int(h.get("year") or 0), int(h.get("week_number") or 0)) < (year, week_number)
        ]
        if prior:
            return PlayerWeeklySignalSnapshot.model_validate(prior[-1])
        return None

    @staticmethod
    def new_run_id() -> str:
        return str(uuid.uuid4())

    def _run_to_row(self, run: WeeklyIntelligenceRun) -> dict[str, Any]:
        return {
            "run_id": run.run_id,
            "league": run.league,
            "sport": run.sport,
            "season": run.season,
            "year": run.year,
            "week_number": run.week_number,
            "period_start": run.period_start.isoformat(),
            "period_end": run.period_end.isoformat(),
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "status": run.status,
            "triggered_by": run.triggered_by,
            "force": run.force,
            "algorithm_version": run.algorithm_version,
            "player_limit": run.player_limit,
            "players_processed": run.players_processed,
            "cards_processed": run.cards_processed,
            "market_snapshots_created": run.market_snapshots_created,
            "population_snapshots_created": run.population_snapshots_created,
            "intelligence_records_created": run.intelligence_records_created,
            "warnings": run.warnings,
            "errors": run.errors,
            "stage_outcomes": run.stage_outcomes,
        }

    def _row_to_run(self, row: dict[str, Any]) -> WeeklyIntelligenceRun:
        return WeeklyIntelligenceRun(
            run_id=row["run_id"],
            league=row["league"],
            sport=row["sport"],
            season=int(row["season"]),
            year=int(row["year"]),
            week_number=int(row["week_number"]),
            period_start=row["period_start"],
            period_end=row["period_end"],
            started_at=row.get("started_at"),
            completed_at=row.get("completed_at"),
            status=row["status"],
            triggered_by=row.get("triggered_by", "manual"),
            force=bool(row.get("force", False)),
            algorithm_version=row.get("algorithm_version", "WEEKLY_INTELLIGENCE_V1"),
            player_limit=int(row.get("player_limit", 100)),
            players_processed=int(row.get("players_processed", 0)),
            cards_processed=int(row.get("cards_processed", 0)),
            market_snapshots_created=int(row.get("market_snapshots_created", 0)),
            population_snapshots_created=int(row.get("population_snapshots_created", 0)),
            intelligence_records_created=int(row.get("intelligence_records_created", 0)),
            warnings=row.get("warnings") or [],
            errors=row.get("errors") or [],
            stage_outcomes=row.get("stage_outcomes") or [],
            created_at=row.get("created_at"),
        )

    def _player_snapshot_to_row(self, snap: PlayerWeeklySignalSnapshot) -> dict[str, Any]:
        return {
            "snapshot_id": snap.snapshot_id,
            "run_id": snap.run_id,
            "cs_player_id": snap.cs_player_id,
            "source_player_id": snap.source_player_id,
            "league": snap.league,
            "sport": snap.sport,
            "season": snap.season,
            "year": snap.year,
            "week_number": snap.week_number,
            "period_start": snap.period_start.isoformat(),
            "period_end": snap.period_end.isoformat(),
            "card_signal_score": snap.card_signal_score,
            "performance_score": snap.performance_score,
            "market_score": snap.market_score,
            "collector_score": snap.collector_score,
            "momentum_score": snap.momentum_score,
            "scarcity_score": snap.scarcity_score,
            "news_score": snap.news_score,
            "recommendation": snap.recommendation,
            "conviction": snap.conviction,
            "status": snap.status,
            "weekly_change": snap.weekly_change,
            "rank": snap.rank,
            "evidence": snap.evidence,
            "missing_inputs": snap.missing_inputs,
            "algorithm_version": snap.algorithm_version,
            "captured_at": snap.captured_at.isoformat() if snap.captured_at else None,
            "player_name": snap.player_name,
            "team": snap.team,
            "position": snap.position,
            "headshot_url": snap.headshot_url,
            "team_logo_url": snap.team_logo_url,
        }

    def _card_snapshot_to_row(self, snap: CardWeeklyIntelligenceSnapshot) -> dict[str, Any]:
        return {
            "snapshot_id": snap.snapshot_id,
            "run_id": snap.run_id,
            "cs_card_id": snap.cs_card_id,
            "cs_player_id": snap.cs_player_id,
            "league": snap.league,
            "year": snap.year,
            "week_number": snap.week_number,
            "period_start": snap.period_start.isoformat(),
            "period_end": snap.period_end.isoformat(),
            "card_signal_score": snap.card_signal_score,
            "recommendation": snap.recommendation,
            "conviction": snap.conviction,
            "risk": snap.risk,
            "time_horizon": snap.time_horizon,
            "market_activity_score": snap.market_activity_score,
            "demand_score": snap.demand_score,
            "momentum_score": snap.momentum_score,
            "scarcity_score": snap.scarcity_score,
            "evidence": snap.evidence,
            "missing_inputs": snap.missing_inputs,
            "algorithm_version": snap.algorithm_version,
            "captured_at": snap.captured_at.isoformat() if snap.captured_at else None,
            "card_label": snap.card_label,
            "player_name": snap.player_name,
        }

    def _signal_to_row(self, signal: SignalOfTheWeek) -> dict[str, Any]:
        return {
            "run_id": signal.run_id,
            "cs_player_id": signal.cs_player_id,
            "player_name": signal.player_name,
            "rank": signal.rank,
            "score": signal.score,
            "weekly_change": signal.weekly_change,
            "recommendation": signal.recommendation,
            "conviction": signal.conviction,
            "status": signal.status,
            "reason": signal.reason,
            "evidence": signal.evidence,
            "algorithm_version": signal.algorithm_version,
            "selected_at": signal.selected_at.isoformat() if signal.selected_at else None,
            "headshot_url": signal.headshot_url,
            "team": signal.team,
            "position": signal.position,
            "team_logo_url": signal.team_logo_url,
            "source_player_id": signal.source_player_id,
        }

    @staticmethod
    def _player_row_to_dict(row: dict[str, Any]) -> dict[str, Any]:
        return row
