"""Deterministic representative listing picker."""

from __future__ import annotations

import unittest

from cardchase_ai.models.schemas import ListingSummary, ListingTagSummary, MarketSnapshot
from cardchase_ai.utils.representative_offer import (
    build_representative_offer,
    select_representative_listing,
)
from cardchase_ai.weekly_scoring import card_intelligence_from_snapshot


def _listing(
    item_id: str,
    title: str,
    price: float,
    *,
    image: str | None = "https://i.ebayimg.com/images/g/x/s-l1600.jpg",
    url: str = "https://www.ebay.com/itm/{id}",
    condition: str = "Used",
) -> dict:
    return {
        "item_id": item_id,
        "title": title,
        "price": price,
        "currency": "USD",
        "condition": condition,
        "item_web_url": url.format(id=item_id),
        "image_url": image,
        "tags": [],
    }


class RepresentativePickerTests(unittest.TestCase):
    def test_chooses_near_median_not_first_or_highest(self) -> None:
        listings = [
            _listing("first", "Shohei Ohtani Bowman Chrome RC", 12.0),
            _listing("low", "Shohei Ohtani Bowman Chrome Paper", 50.0),
            _listing("median", "Shohei Ohtani 2023 Bowman Chrome", 100.0),
            _listing("also", "Shohei Ohtani Bowman Chrome Base", 110.0),
            _listing("high", "Shohei Ohtani Bowman Chrome Superfractor", 900.0),
        ]
        chosen = select_representative_listing(listings, "Shohei Ohtani", "bowman_chrome")
        self.assertIsNotNone(chosen)
        self.assertEqual(chosen["item_id"], "median")
        self.assertNotEqual(chosen["item_id"], "first")
        self.assertNotEqual(chosen["item_id"], "high")

    def test_price_outlier_rejected_when_band_candidates_exist(self) -> None:
        listings = [
            _listing("a", "Jose Altuve Bowman Chrome", 40.0),
            _listing("c", "Jose Altuve Bowman Chrome Lot", 45.0),
            _listing("outlier", "Jose Altuve Bowman Chrome 1/1", 5000.0),
        ]
        chosen = select_representative_listing(listings, "Jose Altuve", "bowman_chrome")
        self.assertEqual(chosen["item_id"], "c")
        self.assertNotEqual(chosen["item_id"], "outlier")

    def test_wrong_player_title_is_rejected(self) -> None:
        listings = [
            _listing("wrong", "Mike Trout Bowman Chrome", 48.0),
            _listing("right", "Shohei Ohtani Bowman Chrome", 52.0),
        ]
        chosen = select_representative_listing(listings, "Shohei Ohtani", "bowman_chrome")
        self.assertEqual(chosen["item_id"], "right")

    def test_bowman_chrome_requires_bowman_and_chrome(self) -> None:
        listings = [
            _listing("chrome-only", "Shohei Ohtani Topps Chrome", 50.0),
            _listing("bowman-only", "Shohei Ohtani Bowman Paper", 51.0),
            _listing("both", "Shohei Ohtani Bowman Chrome", 49.0),
        ]
        chosen = select_representative_listing(listings, "Shohei Ohtani", "bowman_chrome")
        self.assertEqual(chosen["item_id"], "both")

    def test_auto_requires_auto_autograph_or_signed(self) -> None:
        listings = [
            _listing("base", "Jose Altuve baseball card", 40.0),
            _listing("auto", "Jose Altuve auto 2024", 80.0),
            _listing("signed", "Jose Altuve signed card", 90.0),
            _listing("autograph", "Jose Altuve autograph relic", 85.0),
        ]
        chosen = select_representative_listing(listings, "Jose Altuve", "auto")
        self.assertIn(chosen["item_id"], {"auto", "signed", "autograph"})
        self.assertNotEqual(chosen["item_id"], "base")

    def test_psa10_requires_psa_and_10(self) -> None:
        listings = [
            _listing("raw", "Shohei Ohtani baseball card 2018", 40.0),
            _listing("psa9", "Shohei Ohtani PSA 9", 60.0),
            _listing("ok", "Shohei Ohtani PSA 10", 70.0),
        ]
        chosen = select_representative_listing(listings, "Shohei Ohtani", "psa10")
        self.assertEqual(chosen["item_id"], "ok")

    def test_broad_requires_player_identity_only(self) -> None:
        listings = [
            _listing("other", "Random pitcher baseball card", 30.0),
            _listing("player", "Shohei Ohtani baseball card", 35.0),
        ]
        chosen = select_representative_listing(listings, "Shohei Ohtani", "broad")
        self.assertEqual(chosen["item_id"], "player")

    def test_returns_none_when_no_usable_image(self) -> None:
        listings = [_listing("noimg", "Shohei Ohtani baseball card", 20.0, image=None)]
        self.assertIsNone(select_representative_listing(listings, "Shohei Ohtani", "broad"))

    def test_tie_break_is_stable_by_item_id(self) -> None:
        listings = [
            _listing("z-id", "Shohei Ohtani baseball card Z", 50.0),
            _listing("a-id", "Shohei Ohtani baseball card A", 50.0),
        ]
        chosen = select_representative_listing(listings, "Shohei Ohtani", "broad")
        self.assertEqual(chosen["item_id"], "a-id")

    def test_representative_offer_shape(self) -> None:
        listings = [
            _listing("v1|55|0", "Shohei Ohtani Bowman Chrome RC", 88.0, condition="New"),
        ]
        offer = build_representative_offer(listings, "Shohei Ohtani", "bowman_chrome")
        self.assertEqual(offer["source"], "ebay")
        self.assertEqual(offer["external_id"], "v1|55|0")
        self.assertEqual(offer["title"], "Shohei Ohtani Bowman Chrome RC")
        self.assertTrue(str(offer["image_url"]).startswith("https://"))
        self.assertEqual(offer["price"], 88.0)
        self.assertEqual(offer["currency"], "USD")
        self.assertEqual(offer["condition"], "New")
        self.assertEqual(offer["listing_url"], "https://www.ebay.com/itm/v1|55|0")
        self.assertEqual(offer["query_name"], "bowman_chrome")
        self.assertNotIn("listings", offer)

    def test_card_intelligence_evidence_has_offer_not_listings_array(self) -> None:
        listings = [
            ListingSummary(
                item_id="first",
                title="Shohei Ohtani Bowman Chrome",
                price=20.0,
                currency="USD",
                condition="Used",
                item_web_url="https://www.ebay.com/itm/first",
                image_url="https://i.ebayimg.com/images/g/first/s-l1600.jpg",
            ),
            ListingSummary(
                item_id="median",
                title="Shohei Ohtani 2023 Bowman Chrome",
                price=100.0,
                currency="USD",
                condition="Used",
                item_web_url="https://www.ebay.com/itm/median",
                image_url="https://i.ebayimg.com/images/g/median/s-l1600.jpg",
            ),
            ListingSummary(
                item_id="high",
                title="Shohei Ohtani Bowman Chrome Superfractor",
                price=800.0,
                currency="USD",
                condition="Used",
                item_web_url="https://www.ebay.com/itm/high",
                image_url="https://i.ebayimg.com/images/g/high/s-l1600.jpg",
            ),
        ]
        snapshot = MarketSnapshot(
            query_name="bowman_chrome",
            listings_count=3,
            avg_price=306.67,
            tags=ListingTagSummary(chrome_count=3, premium_count=3),
            listings=listings,
        )
        intel = card_intelligence_from_snapshot("bowman_chrome", snapshot, "Shohei Ohtani")
        offer = intel["evidence"]["representative_offer"]
        self.assertEqual(offer["source"], "ebay")
        self.assertEqual(offer["external_id"], "median")
        self.assertEqual(offer["query_name"], "bowman_chrome")
        self.assertNotIn("listings", intel["evidence"])
        self.assertEqual(intel["evidence"]["avg_price"], 306.67)


if __name__ == "__main__":
    unittest.main()
