"""Regression: MLB headshots are derived from MLBAM source_player_id, never UUIDs."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import unittest

from fastapi.testclient import TestClient

from cardchase_ai.clients.mlb import mlb_headshot_url, mlb_source_player_id
from cardchase_ai.storage import SupabaseStorage


BREGMAN_MLBAM = "608324"
BREGMAN_UUID = "9ed6461a-a34b-4205-b55d-4da9dd203796"


def _hotness() -> dict:
    return {
        "performance_score": 70,
        "market_score": 60,
        "total_score": 66,
        "confidence_multiplier": 1.0,
        "tag": "RISING",
        "reasons": [],
    }


class MlbHeadshotHelperTests(unittest.TestCase):
    def test_numeric_mlbam_id_builds_cdn_url(self) -> None:
        url = mlb_headshot_url(BREGMAN_MLBAM)
        self.assertIsNotNone(url)
        self.assertIn(f"/people/{BREGMAN_MLBAM}/", url)

    def test_uuid_never_builds_mlb_photo_url(self) -> None:
        self.assertIsNone(mlb_source_player_id(BREGMAN_UUID))
        self.assertIsNone(mlb_headshot_url(BREGMAN_UUID))
        self.assertIsNone(mlb_headshot_url(f"mlb:{BREGMAN_UUID}"))
        self.assertIsNone(mlb_headshot_url(None))
        self.assertIsNone(mlb_headshot_url(""))
        self.assertNotIn(BREGMAN_UUID, mlb_headshot_url(BREGMAN_MLBAM) or "")


class MlbHeadshotPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.storage = SupabaseStorage("https://example.supabase.co", "service-role-key")

    def test_insert_keeps_mlbam_source_id_and_uuid_relation(self) -> None:
        entries = [
            {
                "player_name": "Alex Bregman",
                "player_id": int(BREGMAN_MLBAM),
                "stats_7d": {"games": 7},
                "stats_30d": {"games": 27},
                "stats_season": {"games": 123},
                "market_snapshots": {},
                "hotness": _hotness(),
            }
        ]
        response = MagicMock()
        response.status_code = 201
        response.text = "[]"
        response.json.return_value = []
        with patch("cardchase_ai.storage.requests.post", return_value=response) as mock_post:
            self.storage.insert_leaderboard_entries(9, entries, {"Alex Bregman": BREGMAN_UUID})

        payload = mock_post.call_args.kwargs["json"][0]
        self.assertEqual(payload["source_player_id"], BREGMAN_MLBAM)
        self.assertEqual(payload["player_id"], BREGMAN_UUID)
        self.assertNotEqual(payload["player_id"], payload["source_player_id"])
        self.assertNotIn("headshot_url", payload)
        self.assertEqual(payload["stats_season"]["games"], 123)

    def test_insert_ignores_uuid_pipeline_player_id(self) -> None:
        entries = [
            {
                "player_name": "Alex Bregman",
                "player_id": BREGMAN_UUID,
                "stats_7d": {"games": 7},
                "stats_30d": {"games": 27},
                "stats_season": {"games": 123},
                "market_snapshots": {},
                "hotness": _hotness(),
            }
        ]
        response = MagicMock()
        response.status_code = 201
        response.text = "[]"
        response.json.return_value = []
        with patch("cardchase_ai.storage.requests.post", return_value=response) as mock_post:
            self.storage.insert_leaderboard_entries(9, entries, {"Alex Bregman": BREGMAN_UUID})

        payload = mock_post.call_args.kwargs["json"][0]
        self.assertIsNone(payload["source_player_id"])
        self.assertEqual(payload["player_id"], BREGMAN_UUID)


class MlbHeadshotFetchApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.storage = SupabaseStorage("https://example.supabase.co", "service-role-key")
        self.row = {
            "player_name": "Alex Bregman",
            "player_id": BREGMAN_UUID,
            "source_player_id": BREGMAN_MLBAM,
            "rank": 1,
            "performance_score": 70,
            "market_score": 60,
            "total_score": 66,
            "confidence_multiplier": 1.0,
            "tag": "RISING",
            "reasons": [],
            "stats_7d": {"games": 7},
            "stats_30d": {"games": 27},
            "stats_season": {"games": 123, "home_runs": 16, "rbi": 61},
            "market_snapshots": {},
        }

    def test_fetch_derives_headshot_from_source_id(self) -> None:
        with patch.object(self.storage, "_get", return_value=[self.row]) as mock_get:
            board = self.storage.fetch_run_leaderboard(9)
        entry = board[0]
        self.assertEqual(entry["player_id"], BREGMAN_UUID)
        self.assertEqual(entry["source_player_id"], BREGMAN_MLBAM)
        self.assertIn(f"/people/{BREGMAN_MLBAM}/", entry["headshot_url"])
        self.assertNotIn(BREGMAN_UUID, entry["headshot_url"])
        self.assertEqual(entry["stats_season"]["games"], 123)
        self.assertIn("source_player_id", mock_get.call_args.args[1]["select"])

        with patch.object(self.storage, "fetch_latest_run", return_value={"id": 9, "created_at": "2026-08-17T00:00:00Z"}):
            with patch.object(self.storage, "_get", return_value=[self.row]):
                player = self.storage.fetch_player_latest(BREGMAN_UUID)
        self.assertEqual(player["player_id"], BREGMAN_UUID)
        self.assertEqual(player["source_player_id"], BREGMAN_MLBAM)
        self.assertIn(f"/people/{BREGMAN_MLBAM}/", player["headshot_url"])
        self.assertEqual(player["stats_season"]["games"], 123)

    def test_missing_or_uuid_source_id_omits_headshot(self) -> None:
        legacy = dict(self.row)
        legacy["source_player_id"] = None
        with patch.object(self.storage, "_get", return_value=[legacy]):
            board = self.storage.fetch_run_leaderboard(9)
        self.assertIsNone(board[0]["source_player_id"])
        self.assertNotIn("headshot_url", board[0])

        uuid_as_source = dict(self.row)
        uuid_as_source["source_player_id"] = BREGMAN_UUID
        with patch.object(self.storage, "_get", return_value=[uuid_as_source]):
            board = self.storage.fetch_run_leaderboard(9)
        self.assertIsNone(board[0]["source_player_id"])
        self.assertNotIn("headshot_url", board[0])

    def test_api_returns_source_id_and_headshot(self) -> None:
        from api.main import app

        derived = {
            "player_name": "Alex Bregman",
            "player_id": BREGMAN_UUID,
            "source_player_id": BREGMAN_MLBAM,
            "headshot_url": mlb_headshot_url(BREGMAN_MLBAM),
            "rank": 1,
            "stats_7d": {"games": 7},
            "stats_30d": {"games": 27},
            "stats_season": {"games": 123},
            "market_snapshots": {},
            "hotness": _hotness(),
        }
        store = MagicMock()
        store.fetch_latest_leaderboard.return_value = [derived]
        store.fetch_player_latest.return_value = derived
        client = TestClient(app)
        with patch("api.main._storage", return_value=store):
            leaderboard = client.get("/api/leaderboard/latest").json()
            player = client.get(f"/api/players/{BREGMAN_UUID}").json()

        self.assertEqual(leaderboard["items"][0]["source_player_id"], BREGMAN_MLBAM)
        self.assertIn(f"/people/{BREGMAN_MLBAM}/", leaderboard["items"][0]["headshot_url"])
        self.assertEqual(player["source_player_id"], BREGMAN_MLBAM)
        self.assertIn(f"/people/{BREGMAN_MLBAM}/", player["headshot_url"])
        self.assertEqual(player["stats_season"]["games"], 123)
        self.assertNotIn(BREGMAN_UUID, player["headshot_url"])


if __name__ == "__main__":
    unittest.main()
