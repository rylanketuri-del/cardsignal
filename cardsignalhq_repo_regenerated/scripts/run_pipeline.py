from __future__ import annotations

from cardchase_ai.pipeline import run_pipeline


if __name__ == "__main__":
    result = run_pipeline()
    print(f"Wrote leaderboard output to: {result.leaderboard_path}")
    if result.run_id:
        print(f"Supabase run id: {result.run_id}")
        print(f"Alerts created: {result.alerts_created}")
        print(f"Deliveries attempted: {result.deliveries_attempted}")
