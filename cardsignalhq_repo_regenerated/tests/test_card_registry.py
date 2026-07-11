"""Tests for centralized Card Registry mapper."""

from __future__ import annotations

import unittest

from cardchase_ai.card_registry import card_identity_from_snapshot, enrich_card_row, resolve_card_identity
from cardchase_ai.models.card_identity import CardIdentity


class CardRegistryTests(unittest.TestCase):
    def test_bowman_chrome_identity_from_query(self):
        identity = resolve_card_identity(
            cs_card_id="mlb:660271:card:bowman_chrome",
            player_name="Elly De La Cruz",
            evidence={"query_name": "bowman_chrome", "listings_count": 18, "avg_price": 42.5},
            captured_at="2026-07-08T12:00:00+00:00",
        )
        self.assertEqual(identity.brand, "Bowman")
        self.assertEqual(identity.set, "Chrome")
        self.assertTrue(identity.rookie_flag)
        self.assertEqual(identity.active_listings, 18)
        self.assertEqual(identity.average_price, 42.5)
        self.assertTrue(identity.has_collector_identity())
        self.assertEqual(identity.title_line(), "Bowman Chrome")
        self.assertEqual(identity.grade_line(), "Raw")

    def test_broad_query_has_no_collector_identity(self):
        identity = resolve_card_identity(
            cs_card_id="mlb:660271:card:broad",
            evidence={"query_name": "broad", "listings_count": 40},
        )
        self.assertFalse(identity.has_collector_identity())
        self.assertIsNone(identity.title_line())
        self.assertIsNone(identity.grade_line())

    def test_psa10_sets_grade_without_product_identity(self):
        identity = resolve_card_identity(
            cs_card_id="mlb:660271:card:psa10",
            evidence={"query_name": "psa10"},
        )
        self.assertFalse(identity.has_collector_identity())
        self.assertEqual(identity.grading_company, "PSA")
        self.assertEqual(identity.grade, "10")

    def test_api_dict_excludes_null_fields(self):
        identity = CardIdentity(cs_card_id="mlb:1:card:auto", autograph_flag=True)
        payload = identity.to_api_dict()
        self.assertEqual(payload["cs_card_id"], "mlb:1:card:auto")
        self.assertTrue(payload["autograph_flag"])
        self.assertNotIn("brand", payload)
        self.assertNotIn("year", payload)

    def test_enrich_card_row_attaches_identity(self):
        row = {
            "cs_card_id": "mlb:660271:card:bowman_chrome",
            "evidence": {"query_name": "bowman_chrome", "avg_price": 30},
        }
        enriched = enrich_card_row(row)
        self.assertIn("identity", enriched)
        self.assertEqual(enriched["identity"]["brand"], "Bowman")
        self.assertEqual(enriched["identity"]["set"], "Chrome")

    def test_snapshot_helper_matches_resolve(self):
        snapshot = {
            "cs_card_id": "mlb:660271:card:bowman_chrome",
            "player_name": "Elly De La Cruz",
            "evidence": {"query_name": "bowman_chrome", "listings_count": 5},
        }
        payload = card_identity_from_snapshot(snapshot)
        self.assertEqual(payload["brand"], "Bowman")
        self.assertEqual(payload["set"], "Chrome")
        self.assertEqual(payload["active_listings"], 5)


if __name__ == "__main__":
    unittest.main()
