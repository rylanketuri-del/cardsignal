from __future__ import annotations

from cardchase_ai.config import get_settings
from cardchase_ai.population.pipeline import run_population_snapshots
from cardchase_ai.storage import SupabaseStorage


if __name__ == "__main__":
    settings = get_settings()
    storage = None
    if settings.supabase_url and settings.supabase_service_role_key:
        storage = SupabaseStorage(settings.supabase_url, settings.supabase_service_role_key)

    result = run_population_snapshots(settings=settings, storage=storage, persist=True)
    print(f"Population snapshots written: {result.snapshot_count}")
    print(f"PSA matches recorded: {result.match_count}")
    print(f"Players scanned: {result.player_count}")
    print(f"Cards considered: {result.card_count}")
    print(f"Errors: {result.error_count}")
    if result.output_path:
        print(f"Output path: {result.output_path}")
