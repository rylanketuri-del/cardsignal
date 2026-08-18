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

    def test_app_namespaces_attach_window_globals(self):
        index_html = (FRONTEND / "index.html").read_text(encoding="utf-8")
        namespaces = {
            "SRIntel": "scouting-report-intel.js",
            "SRMetrics": "scouting-report-metrics.js",
            "SRNfl": "scouting-report-nfl.js",
            "SRNba": "scouting-report-nba.js",
            "WeeklyMovement": "weekly-movement.js",
            "WeeklyConvergence": "weekly-convergence.js",
        }
        app_pos = index_html.find("./app.js")
        self.assertGreater(app_pos, -1)
        for name, filename in namespaces.items():
            source = (FRONTEND / filename).read_text(encoding="utf-8")
            self.assertIn(f"window.{name} = {name}", source)
            file_pos = index_html.find(filename)
            self.assertGreater(file_pos, -1, msg=f"{filename} missing from index.html")
            self.assertLess(file_pos, app_pos, msg=f"{filename} must load before app.js")



if __name__ == "__main__":
    unittest.main()
