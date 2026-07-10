"""Official PSA provider — cert verification only; population via import catalog."""

from __future__ import annotations

from typing import Any

from cardchase_ai.clients.psa import PSAClient
from cardchase_ai.models.population import PSACardMatch
from cardchase_ai.population.import_provider import ImportPopulationProvider
from cardchase_ai.population.matching import build_psa_card_match
from cardchase_ai.population.provider import PopulationProvider


class PSAPopulationProvider(PopulationProvider):
    """Uses official PSA cert API for slab verification; population from approved catalog only."""

    provider_name = "psa"

    def __init__(
        self,
        *,
        psa_client: PSAClient | None = None,
        catalog_provider: ImportPopulationProvider | None = None,
    ) -> None:
        self.psa_client = psa_client or PSAClient()
        self.catalog_provider = catalog_provider or ImportPopulationProvider([])

    def is_available(self) -> bool:
        return self.psa_client.is_configured or bool(self.catalog_provider._catalog_rows)

    def search_card_matches(self, card_identity: dict[str, Any]) -> list[PSACardMatch]:
        cert_number = str(card_identity.get("certification_number") or "").strip()
        if cert_number and self.psa_client.is_configured:
            try:
                payload = self.psa_client.get_cert_by_number(cert_number)
            except Exception as error:
                return [
                    build_psa_card_match(
                        card_identity,
                        source_method="official_api",
                        certification_number=cert_number,
                        notes=f"PSA cert lookup failed: {error}",
                    )
                ]

            psa_card_id = payload.get("SpecID") or payload.get("SpecId") or payload.get("specId")
            psa_set_id = payload.get("SetID") or payload.get("SetId") or payload.get("setId")
            psa_subject_id = payload.get("SubjectID") or payload.get("SubjectId") or payload.get("subjectId")
            match = build_psa_card_match(
                card_identity,
                source_method="official_api",
                psa_card_id=str(psa_card_id) if psa_card_id is not None else None,
                psa_set_id=str(psa_set_id) if psa_set_id is not None else None,
                psa_subject_id=str(psa_subject_id) if psa_subject_id is not None else None,
                certification_number=cert_number,
                card_number=str(payload.get("CardNumber") or payload.get("cardNumber") or ""),
                variety=str(payload.get("Variety") or payload.get("variety") or ""),
                notes="Matched via official PSA cert verification API.",
            )
            match.match_status = "MATCHED"
            match.match_confidence = "HIGH"
            return [match]

        return self.catalog_provider.search_card_matches(card_identity)

    def fetch_population(self, card_match: PSACardMatch) -> dict[str, Any] | None:
        if card_match.source_method == "official_api":
            # Official PSA Public API does not expose population report counts.
            return self.catalog_provider.fetch_population(card_match)
        return self.catalog_provider.fetch_population(card_match)

    def normalize_population(
        self,
        raw_result: dict[str, Any],
        *,
        card_match: PSACardMatch,
        card_identity: dict[str, Any],
    ) -> dict[str, Any]:
        return self.catalog_provider.normalize_population(
            raw_result,
            card_match=card_match,
            card_identity=card_identity,
        )
