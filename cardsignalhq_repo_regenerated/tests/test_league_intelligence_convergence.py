"""Sprint 11.2 — League Intelligence Convergence tests."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from cardchase_ai.capabilities import declare_mlb_capabilities, declare_nfl_capabilities
from cardchase_ai.intelligence_serializer import payload_top_level_keys, serialize_player_intelligence
from cardchase_ai.mlb_signal_drivers import generate_mlb_signal_drivers
from cardchase_ai.models.intelligence import NormalizedPerformanceEvidence, PlayerIntelligencePayload
from cardchase_ai.models.schemas import RollingHitterStats
from cardchase_ai.models.weekly import WEEKLY_INTELLIGENCE_V1, PlayerWeeklySignalSnapshot
from cardchase_ai.performance_evidence import build_mlb_recent_evidence, build_mlb_season_evidence
from cardchase_ai.league_evidence import has_sufficient_evidence
from cardchase_ai.weekly_scoring import (
    compute_weekly_change,
    derive_momentum_from_prior_snapshots,
    derive_nfl_status,
)


def _base_snap(**overrides) -> PlayerWeeklySignalSnapshot:
    now = datetime(2026, 7, 8, 12, 0, tzinfo=ZoneInfo("UTC"))
    base = dict(
        snapshot_id="snap-1",
        run_id="run-1",
        cs_player_id="mlb:1",
        source_player_id="1",
        league="MLB",
        sport="MLB",
        season=2026,
        year=2026,
        week_number=28,
        period_start=now,
        period_end=now,
        card_signal_score=75.0,
        performance_score=70.0,
        market_score=65.0,
        recommendation="HOLD",
        conviction="High",
        status="RISING",
        missing_inputs=[],
        algorithm_version=WEEKLY_INTELLIGENCE_V1,
        captured_at=now,
        player_name="Test Player",
    )
    base.update(overrides)
    return PlayerWeeklySignalSnapshot(**base)


class ContractTests(unittest.TestCase):
    def test_mlb_and_nfl_payload_share_top_level_keys(self):
        mlb = serialize_player_intelligence(_base_snap())
        nfl = serialize_player_intelligence(_base_snap(
            cs_player_id="CS-NFL-P-TEST-01",
            source_player_id="TEST-01",
            league="NFL",
            sport="FOOTBALL",
            algorithm_version="NFL_PLAYER_SIGNAL_V1",
            capabilities=declare_nfl_capabilities(has_prior_weekly_snapshot=False),
        ))
        self.assertEqual(set(payload_top_level_keys()), set(mlb.model_dump().keys()))
        self.assertEqual(set(payload_top_level_keys()), set(nfl.model_dump().keys()))

    def test_capabilities_explicit(self):
        caps = declare_nfl_capabilities(has_prior_weekly_snapshot=False)
        self.assertEqual(caps["alerts"], "DISABLED")
        self.assertEqual(caps["legacy_supabase"], "UNAVAILABLE")
        self.assertEqual(declare_mlb_capabilities()["alerts"], "SUPPORTED")

    def test_unsupported_fields_remain_null(self):
        snap = _base_snap(card_signal_score=None, momentum_score=None, weekly_change=None)
        payload = serialize_player_intelligence(snap)
        self.assertIsNone(payload.card_signal_score)
        self.assertIsNone(payload.momentum_score)
        self.assertIsNone(payload.weekly_change)

    def test_missing_values_not_zero(self):
        snap = _base_snap(card_signal_score=None, performance_score=None, market_score=None)
        payload = serialize_player_intelligence(snap)
        self.assertNotEqual(payload.card_signal_score, 0)
        self.assertNotEqual(payload.performance_score, 0)


class MlbConvergenceTests(unittest.TestCase):
    def test_structured_recent_evidence(self):
        stats_7d = RollingHitterStats(games=7, ops=1.050, home_runs=3, avg=0.320)
        stats_30d = RollingHitterStats(games=25, ops=0.850, home_runs=8, avg=0.280)
        evidence = build_mlb_recent_evidence(stats_7d, stats_30d)
        self.assertTrue(evidence)
        self.assertTrue(all(isinstance(e, NormalizedPerformanceEvidence) for e in evidence))
        self.assertEqual(evidence[0].type, "PERFORMANCE")

    def test_structured_season_evidence(self):
        stats_30d = RollingHitterStats(games=25, ops=0.850, home_runs=8)
        evidence = build_mlb_season_evidence(stats_30d)
        self.assertTrue(evidence)
        self.assertEqual(evidence[0].period_type, "LAST_30_DAYS")

    def test_mlb_signal_drivers_serialize(self):
        stats_7d = RollingHitterStats(games=7, ops=1.100, home_runs=4, stolen_bases=3)
        stats_30d = RollingHitterStats(games=25, ops=0.800)
        drivers = generate_mlb_signal_drivers(stats_7d=stats_7d, stats_30d=stats_30d)
        self.assertTrue(any(d.driver_type == "POWER_PRODUCTION" for d in drivers))
        snap = _base_snap(signal_drivers=[d.model_dump(mode="json") for d in drivers])
        payload = serialize_player_intelligence(snap)
        self.assertGreater(payload.driver_count, 0)

    def test_normalized_evidence_gate_accepts_mlb_stats_7d(self):
        self.assertTrue(has_sufficient_evidence("MLB", 70.0, 60.0, []))
        self.assertFalse(has_sufficient_evidence("MLB", 70.0, 60.0, ["stats_7d"]))
        self.assertFalse(has_sufficient_evidence("MLB", 70.0, 60.0, ["stats_7d", "stats_recent"]))


class NflConvergenceTests(unittest.TestCase):
    def test_weekly_change_from_prior_snapshot(self):
        self.assertEqual(compute_weekly_change(80.0, 75.0), 5.0)

    def test_no_prior_snapshot_pending_movement(self):
        self.assertIsNone(compute_weekly_change(80.0, None))

    def test_nfl_status_league_neutral(self):
        status = derive_nfl_status(
            performance_score=78.0,
            weekly_change=6.0,
            card_signal_score=72.0,
            recommendation="BUY",
        )
        self.assertIn(status, {"HOT", "RISING", "STABLE", "COOLING", "WATCH"})
        self.assertNotIn(status, {"BUY LOW", "CHASED"})

    def test_momentum_only_with_prior_snapshot(self):
        self.assertIsNone(derive_momentum_from_prior_snapshots(70.0, None))
        score = derive_momentum_from_prior_snapshots(75.0, 65.0)
        self.assertIsNotNone(score)
        self.assertGreater(score, 50)

    def test_nfl_alerts_disabled(self):
        caps = declare_nfl_capabilities()
        self.assertEqual(caps["alerts"], "DISABLED")

    def test_market_movement_unavailable_without_history(self):
        snap = _base_snap(
            cs_player_id="CS-NFL-P-1",
            league="NFL",
            sport="FOOTBALL",
            capabilities=declare_nfl_capabilities(has_market_history=False),
        )
        payload = serialize_player_intelligence(snap, has_market_history=False)
        self.assertEqual(payload.capabilities["market_movement"], "UNAVAILABLE")
        self.assertEqual(payload.market_movement, [])


class SerializationTests(unittest.TestCase):
    def test_upstream_fields_not_dropped(self):
        stats_7d = RollingHitterStats(games=7, ops=0.950)
        stats_30d = RollingHitterStats(games=25, ops=0.820)
        recent = [e.model_dump(mode="json") for e in build_mlb_recent_evidence(stats_7d, stats_30d)]
        season = [e.model_dump(mode="json") for e in build_mlb_season_evidence(stats_30d)]
        drivers = [d.model_dump(mode="json") for d in generate_mlb_signal_drivers(stats_7d=stats_7d, stats_30d=stats_30d)]
        snap = _base_snap(
            recent_performance=recent,
            season_performance=season,
            signal_drivers=drivers,
            weekly_change=3.5,
            momentum_score=62.0,
            capabilities=declare_mlb_capabilities(),
        )
        payload = serialize_player_intelligence(snap)
        self.assertEqual(len(payload.recent_performance), len(recent))
        self.assertEqual(len(payload.season_performance), len(season))
        self.assertEqual(payload.driver_count, len(drivers))
        self.assertEqual(payload.weekly_change, 3.5)
        self.assertEqual(payload.momentum_score, 62.0)

    def test_momentum_weekly_change_market_distinct(self):
        snap = _base_snap(momentum_score=55.0, weekly_change=4.0)
        payload = serialize_player_intelligence(snap)
        self.assertNotEqual(payload.momentum_score, payload.weekly_change)


class IntelligenceApiTests(unittest.TestCase):
    def test_fetch_not_found(self):
        from cardchase_ai.config import Settings
        from cardchase_ai.intelligence_api import fetch_player_intelligence_payload
        from cardchase_ai.repositories.factory import build_repository_bundle
        from cardchase_ai.weekly_storage import WeeklyJsonStorage, WeeklyStorage

        with tempfile.TemporaryDirectory() as tmp:
            settings = Settings(
                ebay_token="",
                ebay_client_id="",
                ebay_client_secret="",
                ebay_marketplace_id="EBAY_US",
                tracked_players=[],
                output_dir=Path(tmp),
                mlb_season=2026,
                supabase_url="",
                supabase_service_role_key="",
                supabase_anon_key="",
                pipeline_trigger_token="",
                alert_webhook_url="",
                alert_webhook_bearer_token="",
                alert_from_email="",
                alert_sender_name="",
                app_base_url="",
                resend_api_key="",
                alert_cooldown_hours=12,
                daily_digest_cooldown_hours=20,
                notification_limit=50,
                admin_api_token="",
                weekly_player_limit=100,
                weekly_card_limit_per_player=4,
                weekly_market_enabled=False,
                weekly_population_enabled=False,
                weekly_timezone="America/New_York",
                weekly_refresh_day=1,
                weekly_refresh_hour=6,
                nfl_season=2025,
                nfl_player_limit=100,
                nfl_enabled=False,
                nba_season=2025,
                nba_player_limit=100,
                nba_enabled=False,
            )
            repos = build_repository_bundle(settings)
            result = fetch_player_intelligence_payload("MLB", "999", repos=repos)
            self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
