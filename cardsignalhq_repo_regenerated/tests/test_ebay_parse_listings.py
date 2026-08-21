"""eBay Browse listing parse + normalize image_url."""

from __future__ import annotations

import unittest

from cardchase_ai.clients.ebay import EbayClient
from cardchase_ai.models.schemas import ListingSummary, MarketSnapshot
from cardchase_ai.utils.normalize import normalize_listing, summarize_market


class EbayParseListingsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = EbayClient()

    def test_parse_captures_image_url_and_item_web_url(self) -> None:
        payload = {
            "itemSummaries": [
                {
                    "itemId": "v1|123|0",
                    "title": "Shohei Ohtani Bowman Chrome rookie",
                    "price": {"value": "42.50", "currency": "USD"},
                    "condition": "Used",
                    "itemCreationDate": "2026-08-01T00:00:00Z",
                    "itemWebUrl": "https://www.ebay.com/itm/123",
                    "image": {"imageUrl": "https://i.ebayimg.com/images/g/abc/s-l1600.jpg"},
                }
            ]
        }
        listings = self.client.parse_listings(payload)
        self.assertEqual(len(listings), 1)
        listing = listings[0]
        self.assertEqual(listing["item_id"], "v1|123|0")
        self.assertEqual(listing["title"], "Shohei Ohtani Bowman Chrome rookie")
        self.assertEqual(listing["price"], 42.5)
        self.assertEqual(listing["currency"], "USD")
        self.assertEqual(listing["condition"], "Used")
        self.assertEqual(listing["item_web_url"], "https://www.ebay.com/itm/123")
        self.assertEqual(listing["image_url"], "https://i.ebayimg.com/images/g/abc/s-l1600.jpg")

    def test_missing_or_malformed_image_does_not_fail_parsing(self) -> None:
        payload = {
            "itemSummaries": [
                {"itemId": "1", "title": "Card A", "price": {"value": "10", "currency": "USD"}, "itemWebUrl": "https://www.ebay.com/itm/1"},
                {"itemId": "2", "title": "Card B", "price": {"value": "11", "currency": "USD"}, "image": None, "itemWebUrl": "https://www.ebay.com/itm/2"},
                {"itemId": "3", "title": "Card C", "price": {"value": "12", "currency": "USD"}, "image": {}, "itemWebUrl": "https://www.ebay.com/itm/3"},
                {"itemId": "4", "title": "Card D", "price": {"value": "13", "currency": "USD"}, "image": {"imageUrl": ""}, "itemWebUrl": "https://www.ebay.com/itm/4"},
                {"itemId": "5", "title": "Card E", "price": {"value": "14", "currency": "USD"}, "image": {"imageUrl": "not-a-url"}, "itemWebUrl": "https://www.ebay.com/itm/5"},
                {"itemId": "6", "title": "Card F", "price": {"value": "15", "currency": "USD"}, "image": "https://i.ebayimg.com/bad", "itemWebUrl": "https://www.ebay.com/itm/6"},
            ]
        }
        listings = self.client.parse_listings(payload)
        self.assertEqual(len(listings), 6)
        for listing in listings:
            self.assertIsNone(listing["image_url"])
            self.assertTrue(listing["item_web_url"].startswith("https://www.ebay.com/itm/"))
            self.assertGreater(listing["price"], 0)

    def test_normalize_listing_retains_image_url(self) -> None:
        parsed = {
            "item_id": "v1|9|0",
            "title": "Test Auto",
            "price": 20.0,
            "currency": "USD",
            "condition": "New",
            "created_at": None,
            "item_web_url": "https://www.ebay.com/itm/9",
            "image_url": "https://i.ebayimg.com/images/g/xyz/s-l1600.jpg",
            "tags": [],
            "dropped": "should-not-survive",
        }
        normalized = normalize_listing(parsed)
        self.assertEqual(normalized["image_url"], "https://i.ebayimg.com/images/g/xyz/s-l1600.jpg")
        self.assertEqual(normalized["item_web_url"], "https://www.ebay.com/itm/9")
        self.assertNotIn("dropped", normalized)

    def test_listing_summary_and_market_snapshot_preserve_image_url(self) -> None:
        listings = self.client.parse_listings({
            "itemSummaries": [
                {
                    "itemId": "v1|77|0",
                    "title": "Jose Altuve autograph",
                    "price": {"value": "141.29", "currency": "USD"},
                    "itemWebUrl": "https://www.ebay.com/itm/77",
                    "image": {"imageUrl": "https://i.ebayimg.com/images/g/altuve/s-l1600.jpg"},
                }
            ]
        })
        snapshot = summarize_market("auto", listings)
        self.assertIsInstance(snapshot, MarketSnapshot)
        self.assertEqual(len(snapshot.listings), 1)
        listing = snapshot.listings[0]
        self.assertIsInstance(listing, ListingSummary)
        self.assertEqual(listing.image_url, "https://i.ebayimg.com/images/g/altuve/s-l1600.jpg")
        self.assertEqual(listing.item_web_url, "https://www.ebay.com/itm/77")
        dumped = snapshot.model_dump()
        self.assertEqual(dumped["listings"][0]["image_url"], listing.image_url)
        self.assertNotIn("itemSummaries", dumped)

    def test_malformed_price_does_not_dilute_market_snapshot_or_scores(self) -> None:
        payload = {
            "itemSummaries": [
                {
                    "itemId": "valid",
                    "title": "Shohei Ohtani baseball card",
                    "price": {"value": "100", "currency": "USD"},
                    "itemWebUrl": "https://www.ebay.com/itm/valid",
                    "image": {"imageUrl": "https://i.ebayimg.com/images/g/valid/s-l1600.jpg"},
                },
                {
                    "itemId": "malformed",
                    "title": "Shohei Ohtani auto baseball card",
                    "price": {"value": "not-a-price", "currency": "USD"},
                    "itemWebUrl": "https://www.ebay.com/itm/malformed",
                    "image": {"imageUrl": "https://i.ebayimg.com/images/g/bad/s-l1600.jpg"},
                },
                {
                    "itemId": "missing",
                    "title": "Shohei Ohtani PSA 10 baseball card",
                    "itemWebUrl": "https://www.ebay.com/itm/missing",
                    "image": {"imageUrl": "https://i.ebayimg.com/images/g/missing/s-l1600.jpg"},
                },
                {
                    "itemId": "zero",
                    "title": "Shohei Ohtani Bowman Chrome",
                    "price": {"value": "0", "currency": "USD"},
                    "itemWebUrl": "https://www.ebay.com/itm/zero",
                    "image": {"imageUrl": "https://i.ebayimg.com/images/g/zero/s-l1600.jpg"},
                },
            ]
        }
        listings = self.client.parse_listings(payload)
        self.assertEqual(len(listings), 4)
        self.assertEqual(listings[0]["price"], 100.0)
        self.assertIsNone(listings[1]["price"])
        self.assertIsNone(listings[2]["price"])
        self.assertIsNone(listings[3]["price"])

        snapshot = summarize_market("broad", listings)
        self.assertEqual(snapshot.listings_count, 1)
        self.assertEqual(snapshot.avg_price, 100.0)
        self.assertEqual(snapshot.min_price, 100.0)
        self.assertEqual(snapshot.max_price, 100.0)
        self.assertEqual(snapshot.tags.auto_count, 0)
        self.assertEqual(snapshot.tags.psa10_count, 0)
        self.assertEqual(snapshot.tags.premium_count, 0)

        from cardchase_ai.weekly_scoring import card_intelligence_from_snapshot

        intel = card_intelligence_from_snapshot("broad", snapshot, "Shohei Ohtani")
        self.assertEqual(intel["evidence"]["listings_count"], 1)
        self.assertEqual(intel["evidence"]["avg_price"], 100.0)
        self.assertEqual(intel["market_activity_score"], round((1 / 30) * 100, 2))
        self.assertEqual(intel["demand_score"], 0.0)
        self.assertNotEqual(intel["market_activity_score"], round((4 / 30) * 100, 2))
        self.assertEqual(intel["evidence"]["representative_offer"]["external_id"], "valid")


if __name__ == "__main__":
    unittest.main()
