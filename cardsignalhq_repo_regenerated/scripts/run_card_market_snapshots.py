from __future__ import annotations

from cardchase_ai.config import get_settings
from cardchase_ai.market.pipeline import run_card_market_snapshots
from cardchase_ai.storage import SupabaseStorage


if __name__ == "__main__":
    settings = get_settings()
    storage = None
    if settings.supabase_url and settings.supabase_service_role_key:
        storage = SupabaseStorage(settings.supabase_url, settings.supabase_service_role_key)

    result = run_card_market_snapshots(settings=settings, storage=storage, persist=True)
    print(f"Card market snapshots written: {result.snapshot_count}")
    print(f"Players scanned: {result.player_count}")
    print(f"Cards considered: {result.card_count}")
    print(f"Errors: {result.error_count}")
    if result.output_path:
        print(f"Output path: {result.output_path}")
