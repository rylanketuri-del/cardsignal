"""Regression: MLB full-season stats are distinct from the 30-day scoring baseline."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import unittest

from fastapi.testclient import TestClient

from cardchase_ai.models.schemas import HitterGameLogRow, HitterHotnessBreakdown, MarketSnapshot, RollingHitterStats
from cardchase_ai.pipeline import PlayerPipelineOutput
from cardchase_ai.score import build_hotness_breakdown, score_hitter_performance
from cardchase_ai.storage import SupabaseStorage, _stats_season_payload
from cardchase_ai.utils.rolling import summarize_mlb_hitter_windows
from cardchase_ai.weekly_intelligence import build_player_snapshot, process_player_for_weekly


SEASON_END = date(2026, 8, 17)
SEVEN_DAY_GAMES = 7
THIRTY_DAY_GAMES = 27
SEASON_GAMES = 123
SEVEN_DAY_HR = 3
SEVEN_DAY_RBI = 8
THIRTY_DAY_HR = 7
THIRTY_DAY_RBI = 20
SEASON_HR = 16
SEASON_RBI = 61


def _row(day: date, *, home_runs: int = 0, rbi: int = 0, at_bats: int = 4, hits: int = 1) -> HitterGameLogRow:
    return HitterGameLogRow(
        date=day.isoformat(),
        at_bats=at_bats,
        hits=hits,
        home_runs=home_runs,
        rbi=rbi,
    )


def _assign_counting_stats(days: list[date], home_runs: int, rbi: int) -> list[HitterGameLogRow]:
    rows: list[HitterGameLogRow] = []
    hr_left = home_runs
    rbi_left = rbi
    for index, day in enumerate(days):
        remaining_games = len(days) - index
        hr = min(1, hr_left) if hr_left else 0
        if remaining_games == 1:
            hr = hr_left
        hr_left -= hr
        rbi = min(2, rbi_left) if remaining_games > 1 else rbi_left
        rbi_left -= rbi
        rows.append(_row(day, home_runs=hr, rbi=rbi))
    return rows


def build_split_gamelog() -> list[HitterGameLogRow]:
    """123 season games, 27 in the last 30 days, 7 in the last 7 days."""
    last7_days = [SEASON_END - timedelta(days=offset) for offset in range(SEVEN_DAY_GAMES)]
    thirty_only_days = [SEASON_END - timedelta(days=7 + offset) for offset in range(THIRTY_DAY_GAMES - SEVEN_DAY_GAMES)]
    prior_count = SEASON_GAMES - THIRTY_DAY_GAMES
    prior_days = [SEASON_END - timedelta(days=30 + offset) for offset in range(prior_count)]

    last7 = _assign_counting_stats(last7_days, SEVEN_DAY_HR, SEVEN_DAY_RBI)
    thirty_only = _assign_counting_stats(
        thirty_only_days,
        THIRTY_DAY_HR - SEVEN_DAY_HR,
        THIRTY_DAY_RBI - SEVEN_DAY_RBI,
    )
    prior = _assign_counting_stats(prior_days, SEASON_HR - THIRTY_DAY_HR, SEASON_RBI - THIRTY_DAY_RBI)
    return prior + thirty_only + last7


def _hotness(name: str = "Alex Bregman") -> HitterHotnessBreakdown:
    return HitterHotnessBreakdown(
        player_name=name,
        performance_score=70.0,
        market_score=60.0,
        total_score=66.0,
        confidence_multiplier=1.0,
        tag="RISING",
        reasons=["elite 7-day OPS"],
    )


class MlbWindowSummaryTests(unittest.TestCase):
    def test_seven_thirty_and_season_windows_are_distinct(self) -> None:
        stats_7d, stats_30d, stats_season = summarize_mlb_hitter_windows(build_split_gamelog())

        self.assertEqual(stats_7d.games, SEVEN_DAY_GAMES)
        self.assertEqual(stats_30d.games, THIRTY_DAY_GAMES)
        self.assertEqual(stats_season.games, SEASON_GAMES)
        self.assertNotEqual(stats_7d.games, stats_30d.games)
        self.assertNotEqual(stats_30d.games, stats_season.games)

        self.assertEqual(stats_7d.home_runs, SEVEN_DAY_HR)
        self.assertEqual(stats_7d.rbi, SEVEN_DAY_RBI)
        self.assertEqual(stats_30d.home_runs, THIRTY_DAY_HR)
        self.assertEqual(stats_30d.rbi, THIRTY_DAY_RBI)
        self.assertEqual(stats_season.home_runs, SEASON_HR)
        self.assertEqual(stats_season.rbi, SEASON_RBI)

    def test_hotness_scoring_receives_only_7d_and_30d(self) -> None:
        stats_7d, stats_30d, stats_season = summarize_mlb_hitter_windows(build_split_gamelog())
        captured: dict[str, RollingHitterStats] = {}

        def wrapped(stats_7d_arg, stats_30d_arg):
            captured["stats_7d"] = stats_7d_arg
            captured["stats_30d"] = stats_30d_arg
            return score_hitter_performance(stats_7d_arg, stats_30d_arg)

        with patch("cardchase_ai.score.score_hitter_performance", side_effect=wrapped) as mock_score:
            build_hotness_breakdown(
                player_name="Alex Bregman",
                stats_7d=stats_7d,
                stats_30d=stats_30d,
                market_snapshots={},
            )

        mock_score.assert_called_once()
        self.assertEqual(captured["stats_7d"].games, SEVEN_DAY_GAMES)
        self.assertEqual(captured["stats_30d"].games, THIRTY_DAY_GAMES)
        self.assertNotEqual(captured["stats_30d"].games, stats_season.games)
        self.assertEqual(len(mock_score.call_args.args), 2)


class MlbPipelineSeasonStatsTests(unittest.TestCase):
    def test_process_player_scores_with_7d_and_30d_only(self) -> None:
        gamelog = build_split_gamelog()
        mlb_client = MagicMock()
        mlb_client.get_hitter_gamelog.return_value = gamelog
        settings = MagicMock()
        settings.mlb_season = 2026
        captured: dict[str, RollingHitterStats] = {}

        def capture_hotness(*, player_name, stats_7d, stats_30d, market_snapshots):
            captured["stats_7d"] = stats_7d
            captured["stats_30d"] = stats_30d
            return _hotness(player_name)

        with patch("cardchase_ai.weekly_intelligence.build_hotness_breakdown", side_effect=capture_hotness):
            output, _, error = process_player_for_weekly(
                {"player_id": 136860, "player_name": "Alex Bregman", "team": "BOS"},
                mlb_client,
                None,
                settings,
                market_enabled=False,
            )

        self.assertIsNone(error)
        self.assertIsNotNone(output)
        self.assertEqual(output.stats_7d.games, SEVEN_DAY_GAMES)
        self.assertEqual(output.stats_30d.games, THIRTY_DAY_GAMES)
        self.assertEqual(output.stats_season.games, SEASON_GAMES)
        self.assertEqual(captured["stats_7d"].games, SEVEN_DAY_GAMES)
        self.assertEqual(captured["stats_30d"].games, THIRTY_DAY_GAMES)
        self.assertNotIn("stats_season", captured)

    def test_weekly_season_evidence_uses_full_season_not_30d(self) -> None:
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from cardchase_ai.models.weekly import WeeklyIntelligenceRun
        from cardchase_ai.utils.reporting_period import build_reporting_period
        from cardchase_ai.weekly_storage import WeeklyJsonStorage, WeeklyStorage

        stats_7d, stats_30d, stats_season = summarize_mlb_hitter_windows(build_split_gamelog())
        output = PlayerPipelineOutput(
            player_name="Alex Bregman",
            player_id=136860,
            stats_7d=stats_7d,
            stats_30d=stats_30d,
            stats_season=stats_season,
            market_snapshots={"broad": MarketSnapshot(query_name="broad", listings_count=8, avg_price=20.0)},
            hotness=_hotness(),
            team="BOS",
            position="3B",
        )
        period = build_reporting_period("MLB", timezone_name="America/New_York", season=2026)
        run = WeeklyIntelligenceRun(
            run_id="mlb-season-stats",
            league="MLB",
            sport="MLB",
            season=2026,
            year=2026,
            week_number=period.week_number,
            period_start=period.period_start,
            period_end=period.period_end,
            status="RUNNING",
            triggered_by="test",
            market_snapshots_created=1,
        )
        with TemporaryDirectory() as tmp:
            storage = WeeklyStorage(None, WeeklyJsonStorage(Path(tmp)))
            snap = build_player_snapshot(output, run, period, 1, storage)
        games_metric = next(item for item in snap.season_performance if item.get("metric") == "games")
        self.assertEqual(games_metric["value"], SEASON_GAMES)
        self.assertEqual(games_metric["period_type"], "REGULAR_SEASON")
        self.assertEqual(snap.evidence["stats_season"]["games"], SEASON_GAMES)
        self.assertNotEqual(snap.evidence["stats_season"]["games"], THIRTY_DAY_GAMES)


class MlbStorageSeasonStatsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.storage = SupabaseStorage("https://example.supabase.co", "service-role-key")

    def test_insert_payload_includes_stats_season(self) -> None:
        entries = [
            {
                "player_name": "Alex Bregman",
                "stats_7d": {"games": SEVEN_DAY_GAMES},
                "stats_30d": {"games": THIRTY_DAY_GAMES},
                "stats_season": {"games": SEASON_GAMES, "home_runs": SEASON_HR, "rbi": SEASON_RBI},
                "market_snapshots": {},
                "hotness": {
                    "performance_score": 70,
                    "market_score": 60,
                    "total_score": 66,
                    "confidence_multiplier": 1.0,
                    "tag": "RISING",
                    "reasons": [],
                },
            }
        ]
        response = MagicMock()
        response.status_code = 201
        response.text = "[]"
        response.json.return_value = []
        with patch("cardchase_ai.storage.requests.post", return_value=response) as mock_post:
            self.storage.insert_leaderboard_entries(9, entries, {"Alex Bregman": "player-uuid"})

        payload = mock_post.call_args.kwargs["json"][0]
        self.assertEqual(payload["stats_season"]["games"], SEASON_GAMES)
        self.assertEqual(payload["stats_30d"]["games"], THIRTY_DAY_GAMES)

    def test_fetch_leaderboard_and_player_select_stats_season(self) -> None:
        row = {
            "player_name": "Alex Bregman",
            "player_id": "player-uuid",
            "rank": 1,
            "performance_score": 70,
            "market_score": 60,
            "total_score": 66,
            "confidence_multiplier": 1.0,
            "tag": "RISING",
            "reasons": [],
            "stats_7d": {"games": SEVEN_DAY_GAMES},
            "stats_30d": {"games": THIRTY_DAY_GAMES},
            "stats_season": {"games": SEASON_GAMES, "home_runs": SEASON_HR, "rbi": SEASON_RBI},
            "market_snapshots": {},
        }
        with patch.object(self.storage, "_get", return_value=[row]) as mock_get:
            board = self.storage.fetch_run_leaderboard(9)
        self.assertEqual(board[0]["stats_season"]["games"], SEASON_GAMES)
        self.assertIn("stats_season", mock_get.call_args.args[1]["select"])

        with patch.object(self.storage, "fetch_latest_run", return_value={"id": 9, "created_at": "2026-08-17T00:00:00Z"}):
            with patch.object(self.storage, "_get", return_value=[row]) as mock_player_get:
                player = self.storage.fetch_player_latest("player-uuid")
        self.assertEqual(player["stats_season"]["games"], SEASON_GAMES)
        self.assertIn("stats_season", mock_player_get.call_args.args[1]["select"])
        self.assertEqual(_stats_season_payload({"stats_season": None}), {})


class MlbSeasonStatsApiTests(unittest.TestCase):
    def test_leaderboard_and_player_endpoints_return_stats_season(self) -> None:
        from api.main import app

        entry = {
            "player_name": "Alex Bregman",
            "player_id": "player-uuid",
            "rank": 1,
            "stats_7d": {"games": SEVEN_DAY_GAMES},
            "stats_30d": {"games": THIRTY_DAY_GAMES},
            "stats_season": {"games": SEASON_GAMES, "home_runs": SEASON_HR, "rbi": SEASON_RBI},
            "market_snapshots": {},
            "hotness": {
                "performance_score": 70,
                "market_score": 60,
                "total_score": 66,
                "tag": "RISING",
            },
        }
        store = MagicMock()
        store.fetch_latest_leaderboard.return_value = [entry]
        store.fetch_player_latest.return_value = entry
        client = TestClient(app)
        with patch("api.main._storage", return_value=store):
            leaderboard = client.get("/api/leaderboard/latest").json()
            player = client.get("/api/players/player-uuid").json()

        self.assertEqual(leaderboard["items"][0]["stats_season"]["games"], SEASON_GAMES)
        self.assertEqual(player["stats_season"]["games"], SEASON_GAMES)
        self.assertEqual(player["stats_30d"]["games"], THIRTY_DAY_GAMES)


if __name__ == "__main__":
    unittest.main()
