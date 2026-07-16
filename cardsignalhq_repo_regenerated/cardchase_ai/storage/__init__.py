"""Storage package — Supabase is the production source of truth.

Backward-compatible exports: ``from cardchase_ai.storage import SupabaseStorage``
continues to work after the module→package migration.
"""

from cardchase_ai.storage.client import SupabaseError, SupabaseStorage
from cardchase_ai.storage.supabase import (
    build_production_storage,
    build_weekly_storage,
    production_storage_configured,
)

__all__ = [
    "SupabaseError",
    "SupabaseStorage",
    "build_production_storage",
    "build_weekly_storage",
    "production_storage_configured",
]
