"""Import and manual beta seed population provider — Sprint 8.6."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from cardchase_ai.models.population import PSACardMatch
from cardchase_ai.population.matching import build_psa_card_match, match_score, resolve_match_status
from cardchase_ai.population.provider import PopulationProvider
from cardchase_ai.population.snapshot import build_card_population_snapshot, normalize_population_by_grade


class ImportPopulationProvider(PopulationProvider):
    provider_name = "import"

    def __init__(self, catalog_rows: list[dict[str, Any]] | None = None) -> None:
        self._catalog_rows = catalog_rows or []
        self._by_cs_card_id = {
            str(row["cs_card_id"]): row for row in self._catalog_rows if row.get("cs_card_id")
        }
        self._match_catalog = [
            row
            for row in self._catalog_rows
            if row.get("cs_card_id") or row.get("psa_card_id") or row.get("set_name")
        ]

    def search_card_matches(self, card_identity: dict[str, Any]) -> list[PSACardMatch]:
        cs_card_id = str(card_identity.get("cs_card_id") or "")
        direct = self._by_cs_card_id.get(cs_card_id)
        if direct:
            match = build_psa_card_match(
                card_identity,
                source_method=str(direct.get("source_method") or "approved_import"),
                psa_card_id=direct.get("psa_card_id"),
                psa_set_id=direct.get("psa_set_id"),
                psa_subject_id=direct.get("psa_subject_id"),
                card_number=str(direct.get("card_number") or ""),
                variety=str(direct.get("variety") or ""),
                notes=str(direct.get("notes") or ""),
            )
            match.match_status = "MATCHED"
            match.match_confidence = "HIGH"
            return [match]

        scored: list[tuple[int, PSACardMatch]] = []
        for row in self._match_catalog:
            score, _ = match_score(card_identity, row)
            if score <= 0:
                continue
            candidate = build_psa_card_match(
                card_identity,
                source_method=str(row.get("source_method") or "approved_import"),
                psa_card_id=row.get("psa_card_id"),
                psa_set_id=row.get("psa_set_id"),
                psa_subject_id=row.get("psa_subject_id"),
                card_number=str(row.get("card_number") or ""),
                variety=str(row.get("variety") or ""),
                notes=str(row.get("notes") or "Catalog candidate match"),
            )
            scored.append((score, candidate))

        return resolve_match_status(scored)

    def fetch_population(self, card_match: PSACardMatch) -> dict[str, Any] | None:
        row = self._by_cs_card_id.get(card_match.cs_card_id)
        if row is None and card_match.psa_card_id:
            for candidate in self._catalog_rows:
                if str(candidate.get("psa_card_id") or "") == str(card_match.psa_card_id):
                    row = candidate
                    break
        if row is None:
            return None

        provider_updated_at = row.get("provider_updated_at")
        if provider_updated_at and isinstance(provider_updated_at, str):
            try:
                provider_updated_at = datetime.fromisoformat(provider_updated_at.replace("Z", "+00:00"))
            except ValueError:
                provider_updated_at = None

        return {
            "source_method": row.get("source_method") or card_match.source_method,
            "psa_card_id": row.get("psa_card_id") or card_match.psa_card_id,
            "total_population": row.get("total_population"),
            "population_by_grade": row.get("population_by_grade") or {},
            "psa_10_population": row.get("psa_10_population"),
            "psa_9_population": row.get("psa_9_population"),
            "provider_updated_at": provider_updated_at,
            "notes": row.get("notes") or "",
        }

    def normalize_population(
        self,
        raw_result: dict[str, Any],
        *,
        card_match: PSACardMatch,
        card_identity: dict[str, Any],
    ) -> dict[str, Any]:
        by_grade = normalize_population_by_grade(raw_result.get("population_by_grade"))
        if raw_result.get("psa_10_population") is not None:
            by_grade["10"] = int(raw_result["psa_10_population"])
        if raw_result.get("psa_9_population") is not None:
            by_grade["9"] = int(raw_result["psa_9_population"])

        snapshot = build_card_population_snapshot(
            card_identity,
            source_method=str(raw_result.get("source_method") or card_match.source_method),
            population_by_grade=by_grade,
            total_population=raw_result.get("total_population"),
            psa_card_id=raw_result.get("psa_card_id") or card_match.psa_card_id,
            match_confidence=card_match.match_confidence,
            provider_updated_at=raw_result.get("provider_updated_at"),
            notes=str(raw_result.get("notes") or ""),
        )
        return snapshot.model_dump(mode="json")
