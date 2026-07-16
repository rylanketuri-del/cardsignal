"""MLB leaderboard pipeline.

Schedule: every 3 days.
Flow: pull performance → pull market → CardSignal → persist leaderboard/history to Supabase.

MLB does not produce weekly intelligence snapshots and has no Tuesday logic.
"""

from __future__ import annotations

from cardchase_ai.config import Settings, get_settings
from cardchase_ai.pipelines.schedule import is_mlb_pipeline_due, record_mlb_pipeline_run


def run_mlb_pipeline(
    *,
    settings: Settings | None = None,
    force: bool = False,
    respect_schedule: bool = False,
):
    """Execute the MLB leaderboard pipeline via the shared CardSignal path.

    When ``respect_schedule`` is True, skips if the 3-day interval has not elapsed.
    Manual/API invocations should leave ``respect_schedule=False`` (default).
    """
    settings = settings or get_settings()

    if respect_schedule and not is_mlb_pipeline_due(settings, force=force):
        from cardchase_ai.pipeline import PipelineResult

        return PipelineResult(
            leaderboard_path="",
            weekly_intelligence=[{"league": "MLB", "status": "SKIPPED", "skipped_reason": "MLB pipeline not due (3-day interval)"}],
        )

    # Delegate to existing pipeline implementation (preserves behavior + tests).
    from cardchase_ai.pipeline import run_pipeline

    # Avoid recursive weekly hooks when called from the scheduled dispatcher;
    # the dispatcher invokes weekly separately. For direct calls, keep current
    # behavior (weekly due-check still runs inside run_pipeline).
    result = run_pipeline()
    record_mlb_pipeline_run(settings)
    return result
