"""Validation helpers for previous-season performance import arrays."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from cardchase_ai.performance_import import validate_import_row


@dataclass
class PreviousSeasonValidationReport:
    valid: bool
    safe_to_import: bool
    total_rows: int = 0
    valid_rows: int = 0
    rejected_rows: int = 0
    duplicate_ids: list[str] = field(default_factory=list)
    missing_teams: int = 0
    missing_positions: int = 0
    invalid_percentages: int = 0
    synthetic_markers: list[str] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    season: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "safe_to_import": self.safe_to_import,
            "total_rows": self.total_rows,
            "valid_rows": self.valid_rows,
            "rejected_rows": self.rejected_rows,
            "duplicate_ids": self.duplicate_ids,
            "missing_teams": self.missing_teams,
            "missing_positions": self.missing_positions,
            "invalid_percentages": self.invalid_percentages,
            "synthetic_markers": self.synthetic_markers,
            "errors": self.errors,
            "warnings": self.warnings,
            "season": self.season,
        }


def validate_previous_season_records(
    records: list[Any],
    *,
    league: str,
    season: int,
    allow_synthetic: bool = False,
) -> PreviousSeasonValidationReport:
    report = PreviousSeasonValidationReport(valid=True, safe_to_import=True, season=season)
    if not isinstance(records, list):
        report.valid = False
        report.safe_to_import = False
        report.errors.append({"error": "Top-level JSON must be an array of previous-season records"})
        return report

    report.total_rows = len(records)
    seen: set[str] = set()
    for index, row in enumerate(records):
        if not isinstance(row, dict):
            report.rejected_rows += 1
            report.errors.append({"row_index": index, "error": "row must be an object"})
            continue

        sid = str(row.get("source_player_id") or "")
        name = str(row.get("player_name") or "")
        if sid.upper().startswith(("TEST-", "DEMO-", "MOCK-", "FAKE-", "SAMPLE-")) or "test qb" in name.lower():
            report.synthetic_markers.append(sid or name)
            if not allow_synthetic:
                report.rejected_rows += 1
                report.errors.append({
                    "row_index": index,
                    "source_player_id": sid or None,
                    "error": "Synthetic/test record refused",
                })
                continue

        if sid:
            if sid in seen:
                report.duplicate_ids.append(sid)
                report.rejected_rows += 1
                report.errors.append({
                    "row_index": index,
                    "source_player_id": sid,
                    "error": "Duplicate source_player_id",
                })
                continue
            seen.add(sid)

        if not row.get("team"):
            report.missing_teams += 1
        if not row.get("position"):
            report.missing_positions += 1

        snap, err = validate_import_row(row, league=league, season=season, row_index=index)
        if err:
            report.rejected_rows += 1
            report.errors.append(err.model_dump())
            if "must be between 0 and 1" in err.error:
                report.invalid_percentages += 1
            continue
        assert snap is not None
        report.valid_rows += 1

    if report.valid_rows == 0:
        report.errors.append({"error": "No valid rows"})
    if report.duplicate_ids:
        report.warnings.append(f"Duplicate IDs encountered: {sorted(set(report.duplicate_ids))}")
    if report.missing_teams:
        report.warnings.append(f"{report.missing_teams} rows missing team (still may pass validator)")
    if report.synthetic_markers and not allow_synthetic:
        report.warnings.append("Synthetic markers present and rejected")

    report.valid = report.rejected_rows == 0 and report.valid_rows > 0
    report.safe_to_import = report.valid
    return report
