"""Pytest wrapper for Scouting Report metric mapping tests and static guards."""

from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND = REPO_ROOT / "frontend"


class ScoutingReportMetricsJsTests(unittest.TestCase):
    def test_node_metric_suite_passes(self):
        result = subprocess.run(
            ["node", str(REPO_ROOT / "tests" / "test_scouting_report_metrics.js")],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=f"JS tests failed:\n{result.stdout}\n{result.stderr}",
        )


class ScoutingReportStaticGuardTests(unittest.TestCase):
    def test_snapshot_count_not_labeled_auction_count(self):
        app_js = (FRONTEND / "app.js").read_text(encoding="utf-8")
        self.assertNotIn("snapshotCount", app_js)
        self.assertNotRegex(
            app_js,
            re.compile(r"Auction Count.*snapshot", re.IGNORECASE),
        )

    def test_no_frontend_market_depth_thresholds(self):
        app_js = (FRONTEND / "app.js").read_text(encoding="utf-8")
        self.assertNotIn('"Deep"', app_js)
        self.assertNotIn('"Thin"', app_js)
        self.assertNotRegex(
            app_js,
            re.compile(r"listings\s*>=\s*\d+\s*\?\s*\"(?:Deep|Moderate|Thin)\""),
        )
        market_fn = app_js.split("function renderReportMarket")[1].split("function ")[0]
        for label in ("Deep", "Thin"):
            self.assertNotIn(label, market_fn, msg=f"market depth label {label} in renderReportMarket")

    def test_momentum_not_passed_to_percent_in_card_panel(self):
        app_js = (FRONTEND / "app.js").read_text(encoding="utf-8")
        self.assertNotRegex(
            app_js,
            re.compile(r"csIntelFormatPercent\s*\(\s*(?:card\.)?momentum_score"),
        )

    def test_scouting_metrics_module_loaded_before_app(self):
        index_html = (FRONTEND / "index.html").read_text(encoding="utf-8")
        metrics_pos = index_html.find("scouting-report-metrics.js")
        app_pos = index_html.find("app.js")
        self.assertGreater(metrics_pos, -1)
        self.assertGreater(app_pos, metrics_pos)


if __name__ == "__main__":
    unittest.main()
