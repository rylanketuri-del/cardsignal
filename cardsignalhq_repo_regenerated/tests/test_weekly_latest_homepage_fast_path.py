"""GET /api/weekly/latest homepage_payload fast-path regressions."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from cardchase_ai.clients.mlb import mlb_headshot_url
from cardchase_ai.config import Settings
from cardchase_ai.models.weekly import WEEKLY_INTELLIGENCE_V1, PlayerWeeklySignalSnapshot
from cardchase_ai.weekly_intelligence import build_latest_weekly_api_payload
from cardchase_ai.weekly_storage import WeeklyJsonStorage, WeeklyStorage


BREGMAN_MLBAM = "608324"
BREGMAN_HEADSHOT = mlb_headshot_url(BREGMAN_MLBAM)
RUN_ID = "0978ee9a-0cb0-4194-9f3b-c63c899c2ce2"
PLAYER_SNAPSHOT_COUNT = 100
CARD_SNAPSHOT_COUNT = 400
FAST_PATH_STORAGE_READS = 1


def _settings(tmp: str) -> Settings:
    return Settings(
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


def _bregman_leader(rank: int = 1) -> dict:
    return {
        "rank": rank,
        "cs_player_id": f"mlb:{BREGMAN_MLBAM}",
        "source_player_id": BREGMAN_MLBAM,
        "player_name": "Alex Bregman",
        "score": 87.03,
        "performance": 81.25,
        "market": 95.70,
        "collector": 72.0,
        "momentum": 80.0,
        "recommendation": "BUY",
        "weekly_change": 1.2,
        "status": "HOT",
        "team": "CHC",
        "position": "3B",
        "headshot_url": BREGMAN_HEADSHOT,
        "team_logo_url": None,
    }


def _leader(rank: int, player_id: str, name: str, score: float) -> dict:
    if name == "Alex Bregman":
        return _bregman_leader(rank)
    return {
        "rank": rank,
        "cs_player_id": f"mlb:{player_id}",
        "source_player_id": player_id,
        "player_name": name,
        "score": score,
        "performance": round(score - 5, 2),
        "market": round(score + 3, 2),
        "collector": 50.0,
        "momentum": 55.0,
        "recommendation": "HOLD",
        "weekly_change": 0.4,
        "status": "WATCH",
        "team": "NYY",
        "position": "OF",
        "headshot_url": mlb_headshot_url(player_id),
        "team_logo_url": None,
    }


def _card_row(cs_card_id: str, player_name: str, score: float, **extra) -> dict:
    row = {
        "cs_card_id": cs_card_id,
        "player_name": player_name,
        "score": score,
        "demand_score": score - 4,
        "momentum_score": score - 10,
        "recommendation": "HOLD",
    }
    row.update(extra)
    return row


def _homepage(*, league: str = "MLB", sport: str = "MLB") -> dict:
    leaders = [_leader(1, BREGMAN_MLBAM, "Alex Bregman", 87.03)]
    leaders.extend(_leader(i, str(700000 + i), f"Player {i}", 80.0 - i) for i in range(2, 21))
    return {
        "run": {"run_id": RUN_ID, "league": league, "sport": sport, "week_number": 34},
        "signal_of_the_week": {
            "run_id": RUN_ID,
            "cs_player_id": f"mlb:{BREGMAN_MLBAM}",
            "player_name": "Alex Bregman",
            "rank": 1,
            "score": 87.03,
            "reason": "Elite weekly CardSignal with strong market confirmation.",
            "headshot_url": BREGMAN_HEADSHOT,
            "team": "CHC",
            "position": "3B",
            "source_player_id": BREGMAN_MLBAM,
        },
        "todays_leaders": leaders,
        "trending_cards": [_card_row("c-trend", "Alex Bregman", 88.0, demand_score=91.0)],
        "biggest_movers": [_card_row("c-move", "Player 2", 71.0, momentum_score=95.0)],
        "buy_low_watch": [_card_row("c-buy", "Player 3", 55.0, recommendation="BUY")],
        "most_chased": [_card_row("c-chase", "Alex Bregman", 88.0, demand_score=91.0)],
        "next_refresh": "2026-08-24T10:00:00+00:00",
        "data_quality_summary": {
            "total_players": 100,
            "sufficient_evidence": 100,
            "partial_evidence": 0,
            "insufficient_evidence": 0,
            "sufficient_pct": 100.0,
        },
    }


def _run_row(homepage: dict | None, *, league: str = "MLB", sport: str = "MLB") -> dict:
    return {
        "run_id": RUN_ID,
        "league": league,
        "sport": sport,
        "season": 2026,
        "year": 2026,
        "week_number": 34,
        "period_start": "2026-08-11T00:00:00+00:00",
        "period_end": "2026-08-17T23:59:59+00:00",
        "status": "COMPLETED",
        "completed_at": "2026-08-18T10:00:00+00:00",
        "triggered_by": "scheduler",
        "force": False,
        "algorithm_version": WEEKLY_INTELLIGENCE_V1,
        "players_processed": PLAYER_SNAPSHOT_COUNT,
        "cards_processed": CARD_SNAPSHOT_COUNT,
        "homepage_payload": homepage,
    }


def _dummy_player_snapshots(count: int = PLAYER_SNAPSHOT_COUNT) -> list[dict]:
    now = datetime(2026, 8, 18, 10, tzinfo=ZoneInfo("UTC")).isoformat()
    return [
        {
            "snapshot_id": f"p-{i}",
            "run_id": RUN_ID,
            "cs_player_id": f"mlb:{700000 + i}",
            "source_player_id": str(700000 + i),
            "league": "MLB",
            "sport": "MLB",
            "season": 2026,
            "year": 2026,
            "week_number": 34,
            "period_start": now,
            "period_end": now,
            "card_signal_score": 50.0,
            "rank": i,
            "player_name": f"Snapshot Player {i}",
            "evidence": {"market_snapshots": {"listings": [{"title": "x"}] * 50}},
        }
        for i in range(1, count + 1)
    ]


def _dummy_card_snapshots(count: int = CARD_SNAPSHOT_COUNT) -> list[dict]:
    return [
        {
            "snapshot_id": f"c-{i}",
            "run_id": RUN_ID,
            "cs_card_id": f"card-{i}",
            "cs_player_id": f"mlb:{700000 + ((i - 1) // 4) + 1}",
            "league": "MLB",
            "year": 2026,
            "week_number": 34,
            "card_signal_score": 40.0,
            "player_name": f"Snapshot Player {((i - 1) // 4) + 1}",
        }
        for i in range(1, count + 1)
    ]


def _minimal_player_snapshot() -> dict:
    now = datetime(2026, 8, 18, 10, tzinfo=ZoneInfo("UTC"))
    return PlayerWeeklySignalSnapshot(
        snapshot_id="legacy-1",
        run_id=RUN_ID,
        cs_player_id="mlb:1",
        source_player_id="1",
        league="MLB",
        sport="MLB",
        season=2026,
        year=2026,
        week_number=34,
        period_start=now,
        period_end=now,
        card_signal_score=70.0,
        performance_score=65.0,
        market_score=60.0,
        rank=1,
        player_name="Legacy Player",
        algorithm_version=WEEKLY_INTELLIGENCE_V1,
    ).model_dump(mode="json")


class CountingStorage:
    def __init__(self, run_row: dict | None, full_payload: dict | None = None):
        self.calls: list[str] = []
        self.run_row = run_row
        self.full_payload = full_payload

    def fetch_latest_official_run_row(self, league: str = "MLB") -> dict | None:
        self.calls.append("fetch_latest_official_run_row")
        return self.run_row

    def fetch_latest_completed_payload(self, league: str = "MLB") -> dict | None:
        self.calls.append("fetch_latest_completed_payload")
        return self.full_payload

    def fetch_player_weekly_history(self, cs_player_id: str, limit: int = 12) -> list:
        self.calls.append("fetch_player_weekly_history")
        return []

    def fetch_card_weekly_history(self, cs_card_id: str, limit: int = 12) -> list:
        self.calls.append("fetch_card_weekly_history")
        return []


class FakeSupabase:
    def __init__(self, run_row: dict, players: list, cards: list, signal: dict | None = None):
        self.get_calls: list[str] = []
        self.run_row = run_row
        self.players = players
        self.cards = cards
        self.signal = signal

    def _get(self, table: str, params: dict) -> list:
        self.get_calls.append(table)
        if table == WeeklyStorage.RUNS_TABLE:
            return [self.run_row]
        if table == WeeklyStorage.PLAYER_SNAPSHOTS_TABLE:
            return self.players
        if table == WeeklyStorage.CARD_SNAPSHOTS_TABLE:
            return self.cards
        if table == WeeklyStorage.SIGNAL_TABLE:
            return [self.signal] if self.signal else []
        raise AssertionError(f"unexpected table {table}")


class HomepageFastPathTests(unittest.TestCase):
    def test_valid_homepage_is_o1_and_skips_reconstruction(self) -> None:
        homepage = _homepage()
        run_row = _run_row(homepage)
        storage = CountingStorage(
            run_row,
            full_payload={
                "run": run_row,
                "player_snapshots": _dummy_player_snapshots(),
                "card_snapshots": _dummy_card_snapshots(),
                "signal_of_the_week": homepage["signal_of_the_week"],
                "homepage": homepage,
            },
        )
        self.assertEqual(len(storage.full_payload["player_snapshots"]), PLAYER_SNAPSHOT_COUNT)
        self.assertEqual(len(storage.full_payload["card_snapshots"]), CARD_SNAPSHOT_COUNT)

        with tempfile.TemporaryDirectory() as tmp, \
             patch("cardchase_ai.intelligence_service.batch_get_player_intelligence") as mock_batch, \
             patch("cardchase_ai.intelligence_service.build_normalized_leader_rows") as mock_rows:
            payload = build_latest_weekly_api_payload("MLB", storage, _settings(tmp))

        self.assertEqual(storage.calls, ["fetch_latest_official_run_row"])
        self.assertEqual(len(storage.calls), FAST_PATH_STORAGE_READS)
        mock_batch.assert_not_called()
        mock_rows.assert_not_called()
        self.assertNotIn("fetch_latest_completed_payload", storage.calls)
        self.assertNotIn("fetch_player_weekly_history", storage.calls)

        self.assertEqual(payload["run"]["run_id"], RUN_ID)
        self.assertEqual(len(payload["todays_leaders"]), len(homepage["todays_leaders"]))
        for got, expected in zip(payload["todays_leaders"], homepage["todays_leaders"]):
            for key in (
                "rank",
                "player_name",
                "score",
                "performance",
                "market",
                "headshot_url",
                "team",
                "position",
            ):
                self.assertEqual(got[key], expected[key], key)
            self.assertEqual(got["league"], "MLB")
        self.assertEqual(payload["card_intelligence"]["trending_cards"], homepage["trending_cards"])
        self.assertEqual(payload["card_intelligence"]["biggest_movers"], homepage["biggest_movers"])
        self.assertEqual(payload["card_intelligence"]["buy_low_watch"], homepage["buy_low_watch"])
        self.assertEqual(payload["card_intelligence"]["most_chased"], homepage["most_chased"])
        self.assertEqual(payload["signal_of_the_week"]["player_name"], "Alex Bregman")
        self.assertEqual(payload["data_quality_summary"]["total_players"], 100)
        self.assertIn("next_refresh", payload)
        self.assertEqual(payload["homepage"]["todays_leaders"][0]["player_name"], "Alex Bregman")

    def test_bregman_homepage_fixture_preserves_scores_and_identity(self) -> None:
        homepage = _homepage()
        storage = CountingStorage(_run_row(homepage))
        with tempfile.TemporaryDirectory() as tmp:
            payload = build_latest_weekly_api_payload("MLB", storage, _settings(tmp))

        bregman = payload["todays_leaders"][0]
        self.assertEqual(bregman["player_name"], "Alex Bregman")
        self.assertAlmostEqual(bregman["score"], 87.03, places=2)
        self.assertAlmostEqual(bregman["performance"], 81.25, places=2)
        self.assertAlmostEqual(bregman["market"], 95.70, places=2)
        self.assertEqual(bregman["headshot_url"], BREGMAN_HEADSHOT)
        self.assertIn(BREGMAN_MLBAM, bregman["headshot_url"])
        self.assertEqual(bregman["team"], "CHC")
        self.assertEqual(bregman["position"], "3B")
        self.assertTrue(payload["card_intelligence"]["trending_cards"])
        self.assertTrue(payload["card_intelligence"]["biggest_movers"])
        self.assertTrue(payload["card_intelligence"]["buy_low_watch"])
        self.assertTrue(payload["card_intelligence"]["most_chased"])

    def test_fast_path_is_shared_across_leagues(self) -> None:
        for league, sport in (("MLB", "MLB"), ("NFL", "FOOTBALL"), ("NBA", "BASKETBALL")):
            with self.subTest(league=league):
                homepage = _homepage(league=league, sport=sport)
                homepage["todays_leaders"][0]["cs_player_id"] = f"{league.lower()}:{BREGMAN_MLBAM}"
                storage = CountingStorage(_run_row(homepage, league=league, sport=sport))
                with tempfile.TemporaryDirectory() as tmp, \
                     patch("cardchase_ai.intelligence_service.batch_get_player_intelligence") as mock_batch:
                    payload = build_latest_weekly_api_payload(league, storage, _settings(tmp))
                self.assertEqual(storage.calls, ["fetch_latest_official_run_row"])
                mock_batch.assert_not_called()
                self.assertEqual(payload["todays_leaders"][0]["league"], league)
                self.assertEqual(payload["run"]["league"], league)
                self.assertTrue(payload["card_intelligence"]["trending_cards"])

    def test_supabase_fast_path_is_single_runs_table_get(self) -> None:
        homepage = _homepage()
        run_row = _run_row(homepage)
        supabase = FakeSupabase(
            run_row=run_row,
            players=_dummy_player_snapshots(),
            cards=_dummy_card_snapshots(),
            signal=homepage["signal_of_the_week"],
        )
        with tempfile.TemporaryDirectory() as tmp, \
             patch("cardchase_ai.intelligence_service.batch_get_player_intelligence") as mock_batch:
            storage = WeeklyStorage(supabase, WeeklyJsonStorage(Path(tmp)))
            payload = build_latest_weekly_api_payload("MLB", storage, _settings(tmp))

        self.assertEqual(supabase.get_calls, [WeeklyStorage.RUNS_TABLE])
        self.assertEqual(len(supabase.get_calls), FAST_PATH_STORAGE_READS)
        mock_batch.assert_not_called()
        self.assertAlmostEqual(payload["todays_leaders"][0]["score"], 87.03, places=2)
        self.assertEqual(payload["card_intelligence"]["buy_low_watch"][0]["recommendation"], "BUY")

    def test_fast_path_passes_representative_offer_without_listings_arrays(self) -> None:
        homepage = _homepage()
        offer = {
            "source": "ebay",
            "external_id": "v1|1|0",
            "title": "Alex Bregman Bowman Chrome",
            "image_url": "https://i.ebayimg.com/images/g/bregman/s-l1600.jpg",
            "price": 44.0,
            "currency": "USD",
            "condition": "Used",
            "listing_url": "https://www.ebay.com/itm/1",
            "query_name": "bowman_chrome",
        }
        homepage["trending_cards"][0]["evidence"] = {
            "query_name": "bowman_chrome",
            "listings_count": 12,
            "avg_price": 44.0,
            "representative_offer": offer,
        }
        storage = CountingStorage(_run_row(homepage))
        with tempfile.TemporaryDirectory() as tmp, \
             patch("cardchase_ai.intelligence_service.batch_get_player_intelligence") as mock_batch:
            payload = build_latest_weekly_api_payload("MLB", storage, _settings(tmp))

        self.assertEqual(storage.calls, ["fetch_latest_official_run_row"])
        self.assertEqual(len(storage.calls), FAST_PATH_STORAGE_READS)
        mock_batch.assert_not_called()
        row = payload["card_intelligence"]["trending_cards"][0]
        self.assertEqual(row["evidence"]["representative_offer"]["image_url"], offer["image_url"])
        self.assertEqual(row["evidence"]["representative_offer"]["listing_url"], offer["listing_url"])
        self.assertNotIn("listings", row)
        self.assertNotIn("listings", row["evidence"])
        blob = str(payload["card_intelligence"])
        self.assertNotIn("'listings': [", blob)
        self.assertNotIn('"listings": [', blob)


class HomepageFastPathFallbackTests(unittest.TestCase):
    def test_missing_homepage_uses_legacy_reconstruction(self) -> None:
        run_row = _run_row(None)
        snap = _minimal_player_snapshot()
        canned = [{
            "rank": 1,
            "cs_player_id": "mlb:1",
            "source_player_id": "1",
            "player_name": "Legacy Player",
            "score": 70.0,
            "league": "MLB",
        }]
        storage = CountingStorage(
            run_row,
            full_payload={
                "run": run_row,
                "player_snapshots": [snap],
                "card_snapshots": [],
                "signal_of_the_week": None,
                "homepage": None,
            },
        )
        with tempfile.TemporaryDirectory() as tmp, \
             patch(
                 "cardchase_ai.intelligence_service.build_normalized_leader_rows",
                 return_value=canned,
             ) as mock_rows:
            payload = build_latest_weekly_api_payload("MLB", storage, _settings(tmp))

        self.assertIn("fetch_latest_official_run_row", storage.calls)
        self.assertIn("fetch_latest_completed_payload", storage.calls)
        mock_rows.assert_called_once()
        self.assertEqual(payload["todays_leaders"], canned)
        self.assertEqual(payload["todays_leaders"][0]["player_name"], "Legacy Player")

    def test_empty_leaders_homepage_uses_legacy_reconstruction(self) -> None:
        homepage = _homepage()
        homepage["todays_leaders"] = []
        run_row = _run_row(homepage)
        canned = [{"rank": 1, "player_name": "Rebuilt Leader", "score": 11.0, "league": "MLB"}]
        storage = CountingStorage(
            run_row,
            full_payload={
                "run": run_row,
                "player_snapshots": [_minimal_player_snapshot()],
                "card_snapshots": [],
                "homepage": homepage,
                "signal_of_the_week": None,
            },
        )
        with tempfile.TemporaryDirectory() as tmp, \
             patch(
                 "cardchase_ai.intelligence_service.build_normalized_leader_rows",
                 return_value=canned,
             ) as mock_rows:
            payload = build_latest_weekly_api_payload("MLB", storage, _settings(tmp))
        mock_rows.assert_called_once()
        self.assertEqual(payload["todays_leaders"][0]["player_name"], "Rebuilt Leader")

    def test_malformed_homepage_uses_legacy_reconstruction(self) -> None:
        for malformed in ("not-a-dict", [], {"todays_leaders": "bad"}):
            with self.subTest(homepage=malformed):
                run_row = _run_row(malformed)  # type: ignore[arg-type]
                canned = [{"rank": 1, "player_name": "Fallback", "score": 1.0}]
                storage = CountingStorage(
                    run_row,
                    full_payload={
                        "run": run_row,
                        "player_snapshots": [_minimal_player_snapshot()],
                        "card_snapshots": [],
                        "homepage": malformed,
                        "signal_of_the_week": None,
                    },
                )
                with tempfile.TemporaryDirectory() as tmp, \
                     patch(
                         "cardchase_ai.intelligence_service.build_normalized_leader_rows",
                         return_value=canned,
                     ) as mock_rows:
                    payload = build_latest_weekly_api_payload("MLB", storage, _settings(tmp))
                mock_rows.assert_called_once()
                self.assertEqual(payload["todays_leaders"][0]["player_name"], "Fallback")


if __name__ == "__main__":
    unittest.main()
