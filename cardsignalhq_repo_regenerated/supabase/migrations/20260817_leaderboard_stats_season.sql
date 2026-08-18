-- Distinct full-season MLB hitter stats, separate from the rolling 30-day
-- baseline used by hotness scoring. Existing rows default to empty JSON until
-- the next pipeline persist. Do not backfill production manually.
ALTER TABLE public.leaderboard_entries
  ADD COLUMN IF NOT EXISTS stats_season jsonb NOT NULL DEFAULT '{}'::jsonb;
