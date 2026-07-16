"""Integration contract: weekly runner → COMPLETED Supabase run → homepage + history.

Covers NFL (activation path) and NBA (fixture contract even if production stays Coming Soon).
Player history alone must NOT activate /api/weekly/latest.
"""

from __future__ import annotations

import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch

from cardchase_ai.config import Settings
from cardchase_ai.models.weekly import (
    WEEKLY_INTELLIGENCE_V1,
    PlayerWeeklySignalSnapshot,
    WeeklyHomepageIntelligence,
    WeeklyIntelligenceRun,
)
from cardchase_ai.storage import SupabaseError
from cardchase_ai.weekly_intelligence import build_latest_weekly_api_payload
from cardchase_ai.weekly_storage import WeeklyJsonStorage, WeeklyStorage, _is_official_completed_row


def _settings(tmp: str) -> Settings:
    return Settings(
        ebay_token="",
        ebay_client_id="",
        ebay_client_secret="",
        ebay_marketplace_id="EBAY_US",
        tracked_players=[],
        output_dir=Path(tmp),
        mlb_season=2026,
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="service-role",
        supabase_anon_key="",
        pipeline_trigger_token="",
        alert_webhook_url="",
        alert_webhook_bearer_token="",
        alert_from_email="alerts@example.com",
        alert_sender_name="CardChase AI",
        app_base_url="",
        resend_api_key="",
        alert_cooldown_hours=12,
        daily_digest_cooldown_hours=20,
        notification_limit=50,
        admin_api_token="",
        weekly_player_limit=20,
        weekly_card_limit_per_player=4,
        weekly_market_enabled=False,
        weekly_population_enabled=False,
        weekly_timezone="America/New_York",
        weekly_refresh_day=1,
        weekly_refresh_hour=6,
        nfl_season=2025,
        nfl_player_limit=100,
        nfl_enabled=True,
        nba_season=2025,
        nba_player_limit=100,
        nba_enabled=True,
    )


class InMemorySupabase:
    """Minimal Supabase stand-in for weekly table contracts."""

    def __init__(self) -> None:
        self.tables: dict[str, list[dict[str, Any]]] = {
            "weekly_intelligence_runs": [],
            "player_weekly_signal_snapshots": [],
            "card_weekly_intelligence_snapshots": [],
            "signal_of_the_week": [],
        }

    def _match(self, row: dict[str, Any], params: dict[str, str]) -> bool:
        for key, raw in params.items():
            if key in {"select", "order", "limit"}:
                continue
            if not raw.startswith("eq."):
                if key == "status" and raw.startswith("in."):
                    allowed = raw[len("in.(") : -1].split(",")
                    if str(row.get(key)) not in allowed:
                        return False
                    continue
                continue
            expected = raw[3:]
            if str(row.get(key)) != expected:
                return False
        return True

    def _get(self, table: str, params: dict[str, str]) -> list[dict[str, Any]]:
        rows = [r for r in self.tables.get(table, []) if self._match(r, params)]
        order = params.get("order", "")
        if "completed_at" in order:
            rows = sorted(rows, key=lambda r: str(r.get("completed_at") or ""), reverse=True)
        elif "created_at" in order:
            rows = sorted(rows, key=lambda r: str(r.get("created_at") or ""), reverse=True)
        elif "captured_at.asc" in order:
            rows = sorted(rows, key=lambda r: str(r.get("captured_at") or ""))
        elif "rank.asc" in order:
            rows = sorted(rows, key=lambda r: int(r.get("rank") or 0))
        limit = int(params.get("limit") or len(rows) or 0)
        return [dict(r) for r in rows[:limit]] if limit else [dict(r) for r in rows]

    def _post(self, table: str, payload: Any, prefer: str | None = None) -> list[dict[str, Any]]:
        rows = payload if isinstance(payload, list) else [payload]
        stored = []
        for row in rows:
            item = dict(row)
            item.setdefault("created_at", datetime.now(timezone.utc).isoformat())
            self.tables.setdefault(table, []).append(item)
            stored.append(dict(item))
        return stored

    def _patch(self, table: str, params: dict[str, str], payload: Any, prefer: str | None = None) -> list[dict[str, Any]]:
        updated = []
        for row in self.tables.get(table, []):
            if self._match(row, params):
                row.update(payload)
                updated.append(dict(row))
        return updated


def _player_snap(league: str, run_id: str, cs_player_id: str, *, rank: int = 1) -> PlayerWeeklySignalSnapshot:
    return PlayerWeeklySignalSnapshot(
        snapshot_id=str(uuid.uuid4()),
        run_id=run_id,
        cs_player_id=cs_player_id,
        source_player_id=cs_player_id.split("-")[-1],
        league=league,
        sport="FOOTBALL" if league == "NFL" else "BASKETBALL",
        season=2025,
        year=2026,
        week_number=29,
        period_start=datetime(2026, 7, 7, tzinfo=timezone.utc),
        period_end=datetime(2026, 7, 13, tzinfo=timezone.utc),
        card_signal_score=72.0,
        performance_score=70.0,
        market_score=60.0,
        collector_score=55.0,
        momentum_score=50.0,
        scarcity_score=40.0,
        news_score=0.0,
        recommendation="WATCH",
        conviction="MEDIUM",
        status="WATCH",
        rank=rank,
        evidence={"season_phase": "OFFSEASON", "period_type": "PREVIOUS_SEASON"},
        missing_inputs=[],
        algorithm_version=WEEKLY_INTELLIGENCE_V1,
        captured_at=datetime.now(timezone.utc),
    )


class OfficialRowFilterTests(unittest.TestCase):
    def test_excludes_force_and_test_runs(self) -> None:
        self.assertTrue(
            _is_official_completed_row({"status": "COMPLETED", "force": False, "triggered_by": "scheduler"})
        )
        self.assertFalse(_is_official_completed_row({"status": "RUNNING", "force": False, "triggered_by": "scheduler"}))
        self.assertFalse(_is_official_completed_row({"status": "COMPLETED", "force": True, "triggered_by": "scheduler"}))
        self.assertFalse(_is_official_completed_row({"status": "COMPLETED", "force": False, "triggered_by": "test"}))


class WeeklyHomepageContractTests(unittest.TestCase):
    def _storage(self, tmp: str) -> tuple[WeeklyStorage, InMemorySupabase]:
        fake = InMemorySupabase()
        storage = WeeklyStorage(fake, WeeklyJsonStorage(Path(tmp)))  # type: ignore[arg-type]
        return storage, fake

    def _persist_official(self, storage: WeeklyStorage, league: str, cs_player_id: str) -> WeeklyIntelligenceRun:
        run = WeeklyIntelligenceRun(
            run_id=str(uuid.uuid4()),
            league=league,
            sport="FOOTBALL" if league == "NFL" else "BASKETBALL",
            season=2025,
            year=2026,
            week_number=29,
            period_start=datetime(2026, 7, 7, tzinfo=timezone.utc),
            period_end=datetime(2026, 7, 13, tzinfo=timezone.utc),
            started_at=datetime.now(timezone.utc),
            status="RUNNING",
            triggered_by="scheduler",
            force=False,
            algorithm_version=WEEKLY_INTELLIGENCE_V1,
            player_limit=20,
            created_at=datetime.now(timezone.utc),
        )
        run = storage.create_run(run)
        snap = _player_snap(league, run.run_id, cs_player_id)
        run.status = "COMPLETED"
        run.completed_at = datetime.now(timezone.utc)
        run.players_processed = 1
        homepage = WeeklyHomepageIntelligence(
            run=run,
            signal_of_the_week=None,
            todays_leaders=[
                {
                    "rank": 1,
                    "cs_player_id": cs_player_id,
                    "source_player_id": cs_player_id.split("-")[-1],
                    "player_name": "Contract Player",
                    "score": 72.0,
                }
            ],
            trending_cards=[],
            biggest_movers=[],
            buy_low_watch=[],
            most_chased=[],
            next_refresh=datetime(2026, 7, 21, 10, 0, tzinfo=timezone.utc),
            data_quality_summary={"total_players": 1},
        )
        storage.persist_run_results(run, [snap], [], None, homepage)
        storage.update_run(run)
        return run

    def test_nfl_runner_persist_homepage_and_history_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = _settings(tmp)
            storage, fake = self._storage(tmp)
            cs_id = "CS-NFL-P-contract-1"
            run = self._persist_official(storage, "NFL", cs_id)

            # Orphan history without homepage must not activate.
            orphan_run_id = str(uuid.uuid4())
            fake.tables["player_weekly_signal_snapshots"].append(
                _player_snap("NFL", orphan_run_id, "CS-NFL-P-orphan").model_dump(mode="json")
            )

            payload = storage.fetch_latest_completed_payload("NFL")
            self.assertIsNotNone(payload)
            assert payload is not None
            self.assertEqual(payload["run"]["run_id"], run.run_id)
            self.assertEqual(payload["run"]["status"], "COMPLETED")
            self.assertIsNotNone(payload["homepage"])
            self.assertEqual(payload["homepage"]["todays_leaders"][0]["cs_player_id"], cs_id)

            with patch("cardchase_ai.repositories.factory.build_repository_bundle") as mock_repos, patch(
                "cardchase_ai.intelligence_service.build_normalized_leader_rows",
                return_value=payload["homepage"]["todays_leaders"],
            ):
                mock_repos.return_value = object()
                api_payload = build_latest_weekly_api_payload("NFL", storage, settings)

            self.assertTrue(api_payload["available"])
            self.assertEqual(api_payload["activation"], "ACTIVE")
            self.assertEqual(api_payload["data_source"], "supabase")
            self.assertEqual(api_payload["run"]["league"], "NFL")
            self.assertGreaterEqual(len(api_payload["todays_leaders"]), 1)

            history = storage.fetch_player_weekly_history(cs_id, limit=5)
            self.assertEqual(len(history), 1)
            self.assertEqual(history[0]["run_id"], run.run_id)

    def test_nba_fixture_homepage_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = _settings(tmp)
            storage, _fake = self._storage(tmp)
            cs_id = "CS-NBA-P-contract-1"
            run = self._persist_official(storage, "NBA", cs_id)

            payload = storage.fetch_latest_completed_payload("NBA")
            self.assertIsNotNone(payload)
            assert payload is not None
            self.assertEqual(payload["run"]["league"], "NBA")
            self.assertEqual(payload["run"]["run_id"], run.run_id)
            self.assertIsNotNone(payload["homepage"])

            with patch("cardchase_ai.repositories.factory.build_repository_bundle") as mock_repos, patch(
                "cardchase_ai.intelligence_service.build_normalized_leader_rows",
                return_value=payload["homepage"]["todays_leaders"],
            ):
                mock_repos.return_value = object()
                api_payload = build_latest_weekly_api_payload("NBA", storage, settings)

            self.assertTrue(api_payload["available"])
            self.assertEqual(api_payload["activation"], "ACTIVE")
            self.assertEqual(api_payload["run"]["league"], "NBA")
            history = storage.fetch_player_weekly_history(cs_id, limit=5)
            self.assertEqual(history[0]["league"], "NBA")

    def test_player_history_alone_does_not_activate_homepage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage, fake = self._storage(tmp)
            # RUNNING run + player snapshots (the production failure mode).
            running = {
                "run_id": str(uuid.uuid4()),
                "league": "NFL",
                "sport": "FOOTBALL",
                "season": 2025,
                "year": 2026,
                "week_number": 29,
                "status": "RUNNING",
                "force": False,
                "triggered_by": "scheduler",
                "homepage_payload": None,
                "completed_at": None,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            fake.tables["weekly_intelligence_runs"].append(running)
            fake.tables["player_weekly_signal_snapshots"].append(
                _player_snap("NFL", running["run_id"], "CS-NFL-P-hist").model_dump(mode="json")
            )

            self.assertIsNone(storage.fetch_latest_completed_payload("NFL"))
            history = storage.fetch_player_weekly_history("CS-NFL-P-hist", limit=5)
            self.assertEqual(len(history), 1)

    def test_persist_refuses_orphaned_player_inserts_when_run_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage, _fake = self._storage(tmp)
            run = WeeklyIntelligenceRun(
                run_id=str(uuid.uuid4()),
                league="NFL",
                sport="FOOTBALL",
                season=2025,
                year=2026,
                week_number=29,
                period_start=datetime(2026, 7, 7, tzinfo=timezone.utc),
                period_end=datetime(2026, 7, 13, tzinfo=timezone.utc),
                status="COMPLETED",
                triggered_by="scheduler",
                force=False,
                algorithm_version=WEEKLY_INTELLIGENCE_V1,
                completed_at=datetime.now(timezone.utc),
            )
            homepage = WeeklyHomepageIntelligence(
                run=run,
                signal_of_the_week=None,
                todays_leaders=[],
                trending_cards=[],
                biggest_movers=[],
                buy_low_watch=[],
                most_chased=[],
                next_refresh=datetime(2026, 7, 21, 10, 0, tzinfo=timezone.utc),
                data_quality_summary={},
            )
            with self.assertRaises(SupabaseError):
                storage.persist_run_results(
                    run,
                    [_player_snap("NFL", run.run_id, "CS-NFL-P-x")],
                    [],
                    None,
                    homepage,
                )


if __name__ == "__main__":
    unittest.main()
