"""Pytest wrapper for Card Intelligence Ranking tests and static guards."""

from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND = REPO_ROOT / "frontend"


class CardIntelligenceRankingJsTests(unittest.TestCase):
    def test_node_ranking_suite_passes(self):
        result = subprocess.run(
            ["node", str(REPO_ROOT / "tests" / "test_card_intelligence_ranking.js")],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=f"JS tests failed:\n{result.stdout}\n{result.stderr}",
        )


class CardIntelligenceRankingStaticGuardTests(unittest.TestCase):
    def test_ranking_module_loaded_before_app(self):
        index_html = (FRONTEND / "index.html").read_text(encoding="utf-8")
        ranking_pos = index_html.find("card-intelligence-ranking.js")
        app_pos = index_html.find("app.js")
        self.assertGreater(ranking_pos, -1)
        self.assertGreater(app_pos, ranking_pos)

    def test_app_uses_centralized_rank_player_cards(self):
        app_js = (FRONTEND / "app.js").read_text(encoding="utf-8")
        self.assertIn("rankPlayerCards", app_js)
        self.assertIn("CARD_RANKING_EXPLANATION", app_js)
        self.assertIn("View Card Report", app_js)
        self.assertIn("Top Pick", app_js)

    def test_no_duplicate_card_sort_in_app(self):
        app_js = (FRONTEND / "app.js").read_text(encoding="utf-8")
        self.assertNotRegex(app_js, re.compile(r"\.sort\s*\(\s*\(a,\s*b\)\s*=>\s*.*card_signal_score"))

    def test_ranking_explanation_present_in_cards_section(self):
        app_js = (FRONTEND / "app.js").read_text(encoding="utf-8")
        cards_fn = app_js.split("function renderReportCards")[1].split("function ")[0]
        panel_fn = app_js.split("function renderReportCardPanel")[1].split("function ")[0]
        self.assertIn("sr-cards-ranking-note", cards_fn)
        self.assertIn("sr-card-compare-grid", panel_fn)
        self.assertIn("sr-card-top-pick-badge", panel_fn)


if __name__ == "__main__":
    unittest.main()
