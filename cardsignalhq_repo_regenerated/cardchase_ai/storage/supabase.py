"""Supabase production storage façade.

Production pipeline path:
  Cron Pipeline → Supabase → API → Frontend

Local JSON under output/ remains a debug/fallback artifact only.
The API must prefer Supabase when credentials are configured.
"""

from __future__ import annotations

from cardchase_ai.config import Settings, get_settings
from cardchase_ai.storage.client import SupabaseError, SupabaseStorage

__all__ = [
    "SupabaseError",
    "SupabaseStorage",
    "build_production_storage",
    "build_weekly_storage",
    "production_storage_configured",
]


def production_storage_configured(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return bool(settings.supabase_url and settings.supabase_service_role_key)


def build_production_storage(settings: Settings | None = None) -> SupabaseStorage | None:
    """Return a Supabase client when production credentials are present."""
    settings = settings or get_settings()
    if not production_storage_configured(settings):
        return None
    return SupabaseStorage(settings.supabase_url, settings.supabase_service_role_key)


def build_weekly_storage(settings: Settings | None = None):
    """Weekly intelligence storage: Supabase primary, JSON debug fallback."""
    from cardchase_ai.weekly_storage import WeeklyJsonStorage, WeeklyStorage

    settings = settings or get_settings()
    supabase = build_production_storage(settings)
    json_store = WeeklyJsonStorage(settings.output_dir)
    return WeeklyStorage(supabase, json_store)
