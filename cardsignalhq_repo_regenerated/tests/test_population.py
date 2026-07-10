"""Tests for optional population stage behavior."""

from __future__ import annotations

import unittest

from cardchase_ai.population import run_population_stage


class PopulationStageTests(unittest.TestCase):
    def test_disabled_skips_cleanly(self):
        result = run_population_stage(enabled=False, provider=None, league="MLB", player_ids=["1"])
        self.assertEqual(result.status, "SKIPPED")
        self.assertEqual(result.snapshots_created, 0)

    def test_enabled_without_provider_is_unavailable(self):
        result = run_population_stage(enabled=True, provider=None, league="MLB", player_ids=["1"])
        self.assertEqual(result.status, "UNAVAILABLE")
        self.assertEqual(result.snapshots_created, 0)
        self.assertTrue(result.warnings)


if __name__ == "__main__":
    unittest.main()
