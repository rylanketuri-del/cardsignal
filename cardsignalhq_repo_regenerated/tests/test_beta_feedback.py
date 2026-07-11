"""Tests for beta feedback validation and API behavior."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from cardchase_ai.beta_feedback import (
    BetaFeedbackRequest,
    build_feedback_record,
    check_rate_limit,
    contains_sensitive_data,
    sanitize_text,
)


class BetaFeedbackValidationTests(unittest.TestCase):
    def test_message_required(self):
        with self.assertRaises(ValueError):
            BetaFeedbackRequest(feedback_type="BUG", message="  ")

    def test_invalid_feedback_type(self):
        with self.assertRaises(ValueError):
            BetaFeedbackRequest(feedback_type="INVALID", message="Something broke")

    def test_sanitize_strips_control_chars(self):
        self.assertEqual(sanitize_text("hello\x00world"), "helloworld")

    def test_sensitive_payload_detection(self):
        self.assertTrue(contains_sensitive_data({"message": "password=secret"}))
        self.assertFalse(contains_sensitive_data({"message": "Button was confusing"}))

    def test_build_feedback_record_uses_defaults(self):
        payload = BetaFeedbackRequest(feedback_type="LOVE", message="Great scouting report")
        record = build_feedback_record(payload)
        self.assertEqual(record["feedback_type"], "LOVE")
        self.assertEqual(record["status"], "NEW")
        self.assertEqual(record["app_version"], "0.14.1")
        self.assertIsNone(record["screenshot_ref"])

    def test_rate_limit_blocks_spam(self):
        key = "test-client-spam:BUG"
        for _ in range(5):
            self.assertTrue(check_rate_limit(key))
        self.assertFalse(check_rate_limit(key))

    def test_safe_metadata_capture(self):
        payload = BetaFeedbackRequest(
            feedback_type="BUG",
            message="Modal stuck open",
            page_url="https://cardsignal.app/#/player/1",
            current_route="#/player/1",
            entity_type="player",
            entity_id="mlb:1",
            sport="MLB",
            browser_summary="Linux",
            viewport_width=390,
            viewport_height=844,
        )
        record = build_feedback_record(payload)
        self.assertEqual(record["entity_type"], "player")
        self.assertEqual(record["viewport_width"], 390)
        self.assertNotIn("password", record["message"].lower())


class BetaFeedbackRouteTests(unittest.TestCase):
    def test_submit_route_registered(self):
        from api.main import app

        paths = [route.path for route in app.routes]
        self.assertIn("/api/beta-feedback", paths)
        self.assertNotIn("/api/beta-feedback/list", paths)

    @patch("api.main._storage")
    def test_submit_beta_feedback_persists(self, storage_mock):
        from api.main import submit_beta_feedback

        storage = MagicMock()
        storage.insert_beta_feedback.return_value = {"id": 1}
        storage_mock.return_value = storage

        payload = BetaFeedbackRequest(feedback_type="IDEA", message="Add card compare")
        response = submit_beta_feedback(
            payload,
            MagicMock(client=MagicMock(host="127.0.0.1")),
            authorization=None,
        )
        self.assertIn(b'"status"', response.body)
        self.assertIn(b'"ok"', response.body)
        storage.insert_beta_feedback.assert_called_once()

    @patch("api.main._storage")
    def test_submit_beta_feedback_unavailable(self, storage_mock):
        from api.main import submit_beta_feedback
        from fastapi import HTTPException

        storage_mock.return_value = None
        payload = BetaFeedbackRequest(feedback_type="OTHER", message="General note")
        with self.assertRaises(HTTPException) as ctx:
            submit_beta_feedback(
                payload,
                MagicMock(client=MagicMock(host="127.0.0.1")),
                authorization=None,
            )
        self.assertEqual(ctx.exception.status_code, 503)


if __name__ == "__main__":
    unittest.main()
