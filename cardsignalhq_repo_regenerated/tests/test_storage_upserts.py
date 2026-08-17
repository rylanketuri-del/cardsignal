"""Focused tests for PostgREST upsert on_conflict params."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from cardchase_ai.storage import SupabaseStorage


class StorageUpsertOnConflictTests(unittest.TestCase):
    def setUp(self) -> None:
        self.storage = SupabaseStorage("https://example.supabase.co", "service-role-key")

    def _mock_ok_response(self, payload: list | dict | None = None) -> MagicMock:
        response = MagicMock()
        response.status_code = 201
        body = payload if payload is not None else [{"id": 1}]
        response.text = "[]" if body == [] else "ok"
        response.json.return_value = body
        return response

    def test_upsert_players_sends_on_conflict_name(self) -> None:
        with patch("cardchase_ai.storage.requests.post", return_value=self._mock_ok_response([])) as mock_post:
            self.storage.upsert_players(["Yordan Alvarez"])

        mock_post.assert_called_once()
        kwargs = mock_post.call_args.kwargs
        self.assertEqual(kwargs["params"], {"on_conflict": "name"})
        self.assertEqual(kwargs["headers"]["Prefer"], "resolution=merge-duplicates")
        self.assertEqual(kwargs["json"], [{"name": "Yordan Alvarez"}])
        self.assertTrue(str(mock_post.call_args.args[0]).endswith("/rest/v1/players"))

    def test_add_tracked_player_sends_on_conflict_player_name(self) -> None:
        row = {"id": 1, "player_name": "Elly De La Cruz", "active": True, "notes": ""}
        with patch("cardchase_ai.storage.requests.post", return_value=self._mock_ok_response([row])) as mock_post:
            result = self.storage.add_tracked_player("Elly De La Cruz")

        self.assertEqual(result, row)
        kwargs = mock_post.call_args.kwargs
        self.assertEqual(kwargs["params"], {"on_conflict": "player_name"})
        self.assertEqual(kwargs["headers"]["Prefer"], "resolution=merge-duplicates,return=representation")
        self.assertTrue(str(mock_post.call_args.args[0]).endswith("/rest/v1/tracked_player_configs"))

    def test_watchlist_upsert_sends_on_conflict_user_id_player_name(self) -> None:
        row = {"id": 1, "player_id": None, "player_name": "Bobby Witt Jr."}
        with patch("cardchase_ai.storage.requests.post", return_value=self._mock_ok_response([row])) as mock_post:
            result = self.storage.add_user_watchlist_player(
                user_id="user-1",
                player_id=None,
                player_name="Bobby Witt Jr.",
                user_token="user-token",
            )

        self.assertEqual(result, row)
        kwargs = mock_post.call_args.kwargs
        self.assertEqual(kwargs["params"], {"on_conflict": "user_id,player_name"})
        self.assertEqual(kwargs["headers"]["Prefer"], "resolution=merge-duplicates,return=representation")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer user-token")
        self.assertTrue(str(mock_post.call_args.args[0]).endswith("/rest/v1/watchlists"))

    def test_alert_rule_upsert_sends_on_conflict_user_id_player_name(self) -> None:
        row = {"id": 1, "user_id": "user-1", "player_name": "Gunnar Henderson"}
        with patch("cardchase_ai.storage.requests.post", return_value=self._mock_ok_response([row])) as mock_post:
            result = self.storage.upsert_user_player_alert_rule(
                user_id="user-1",
                player_name="Gunnar Henderson",
                payload={"min_hotness_delta": 10},
                user_token="user-token",
            )

        self.assertEqual(result, row)
        kwargs = mock_post.call_args.kwargs
        self.assertEqual(kwargs["params"], {"on_conflict": "user_id,player_name"})
        self.assertEqual(kwargs["headers"]["Prefer"], "resolution=merge-duplicates,return=representation")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer user-token")
        self.assertTrue(str(mock_post.call_args.args[0]).endswith("/rest/v1/player_alert_rules"))


if __name__ == "__main__":
    unittest.main()
