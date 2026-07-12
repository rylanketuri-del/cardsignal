"""Tests for beta readiness audit calculation."""

from __future__ import annotations

import unittest

from cardchase_ai.beta_readiness import run_beta_readiness_audit


class BetaReadinessTests(unittest.TestCase):
    def test_audit_returns_structured_result(self):
        result = run_beta_readiness_audit(supabase_configured=False)
        payload = result.to_dict()
        self.assertIn(result.status, {"READY", "READY_WITH_WARNINGS", "NOT_READY"})
        self.assertEqual(payload["app_version"], "0.14.1")
        self.assertIn("blockers", payload)
        self.assertIn("warnings", payload)
        self.assertIn("checks_passed", payload)

    def test_required_surfaces_pass_after_sprint(self):
        result = run_beta_readiness_audit(supabase_configured=True)
        surface_checks = [c for c in result.checks_passed if c.startswith("Surface present:")]
        self.assertGreaterEqual(len(surface_checks), 3)

    def test_no_placeholder_blockers_after_cleanup(self):
        result = run_beta_readiness_audit()
        placeholder_blockers = [
            b for b in result.blockers if "placeholder" in b.message.lower()
        ]
        self.assertEqual(placeholder_blockers, [])


if __name__ == "__main__":
    unittest.main()
