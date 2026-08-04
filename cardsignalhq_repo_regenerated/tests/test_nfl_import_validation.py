"""Tests for NFL provider-file validation and import safety gates."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cardchase_ai.nfl_data_validation import (
    validate_nfl_data_file,
    validate_nfl_data_payload,
)


def _minimal_valid_payload() -> dict:
    return {
        "source_method": "APPROVED_IMPORT",
        "season": 2025,
        "last_updated": "2026-07-01T00:00:00Z",
        "players": [
            {
                "source_player_id": "00-0033873",
                "player_name": "Example Verified Player",
                "team": "KC",
                "team_id": "KC",
                "position": "QB",
                "active_status": "ACTIVE",
            }
        ],
        "games": {
            "00-0033873": [
                {
                    "game_id": "g1",
                    "game_date": "2025-09-07",
                    "season": 2025,
                    "participated": True,
                    "stats": {"passing_yards": 280, "passing_touchdowns": 2, "interceptions": 0},
                }
            ]
        },
        "season_stats": {
            "00-0033873": {
                "season": 2025,
                "stats": {
                    "games_played": 17,
                    "passing_yards": 4000,
                    "passing_touchdowns": 30,
                    "interceptions": 8,
                },
            }
        },
    }


class NflDataValidationTests(unittest.TestCase):
    def test_valid_payload_is_safe(self) -> None:
        report = validate_nfl_data_payload(_minimal_valid_payload())
        self.assertTrue(report.valid)
        self.assertTrue(report.safe_to_import)
        self.assertEqual(report.player_count, 1)

    def test_missing_source_method_rejected(self) -> None:
        payload = _minimal_valid_payload()
        payload.pop("source_method")
        report = validate_nfl_data_payload(payload)
        self.assertFalse(report.safe_to_import)
        self.assertTrue(any("source_method" in e for e in report.errors))

    def test_empty_players_rejected(self) -> None:
        payload = _minimal_valid_payload()
        payload["players"] = []
        report = validate_nfl_data_payload(payload)
        self.assertFalse(report.safe_to_import)

    def test_duplicate_player_ids_rejected(self) -> None:
        payload = _minimal_valid_payload()
        payload["players"].append(dict(payload["players"][0]))
        report = validate_nfl_data_payload(payload)
        self.assertFalse(report.safe_to_import)
        self.assertEqual(report.duplicate_player_ids, ["00-0033873"])

    def test_malformed_game_stat_rejected(self) -> None:
        payload = _minimal_valid_payload()
        payload["games"]["00-0033873"][0]["stats"]["passing_yards"] = "many"
        report = validate_nfl_data_payload(payload)
        self.assertFalse(report.safe_to_import)

    def test_negative_stat_rejected(self) -> None:
        payload = _minimal_valid_payload()
        payload["season_stats"]["00-0033873"]["stats"]["passing_yards"] = -1
        report = validate_nfl_data_payload(payload)
        self.assertFalse(report.safe_to_import)

    def test_synthetic_fixture_rejected_for_production(self) -> None:
        payload = _minimal_valid_payload()
        payload["players"][0]["source_player_id"] = "TEST-QB-01"
        payload["players"][0]["player_name"] = "Test Quarterback"
        payload["games"] = {"TEST-QB-01": payload["games"].pop("00-0033873")}
        payload["season_stats"] = {"TEST-QB-01": payload["season_stats"].pop("00-0033873")}
        report = validate_nfl_data_payload(payload, allow_synthetic=False)
        self.assertFalse(report.safe_to_import)
        report_allowed = validate_nfl_data_payload(payload, allow_synthetic=True)
        self.assertTrue(report_allowed.safe_to_import)

    def test_file_validation_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nfl_data.json"
            path.write_text(json.dumps(_minimal_valid_payload()), encoding="utf-8")
            report = validate_nfl_data_file(path)
            self.assertTrue(report.safe_to_import)

    def test_invalid_json_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text("{not-json", encoding="utf-8")
            report = validate_nfl_data_file(path)
            self.assertFalse(report.safe_to_import)


class NflImportScriptGateTests(unittest.TestCase):
    def test_import_helper_dry_run_refuses_synthetic(self) -> None:
        import importlib.util

        script_path = Path(__file__).resolve().parents[1] / "scripts" / "import_nfl_data.py"
        spec = importlib.util.spec_from_file_location("import_nfl_data", script_path)
        assert spec and spec.loader
        importer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(importer)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nfl_data.json"
            payload = _minimal_valid_payload()
            payload["players"][0]["source_player_id"] = "TEST-QB-01"
            payload["players"][0]["player_name"] = "Test Quarterback"
            payload["games"] = {"TEST-QB-01": payload["games"].pop("00-0033873")}
            payload["season_stats"] = {"TEST-QB-01": payload["season_stats"].pop("00-0033873")}
            path.write_text(json.dumps(payload), encoding="utf-8")
            result = importer._install_provider_file(path, Path(tmp) / "out" / "nfl_data.json", dry_run=True)
            self.assertEqual(result["status"], "failed_validation")
            self.assertFalse(result["written"])


if __name__ == "__main__":
    unittest.main()
