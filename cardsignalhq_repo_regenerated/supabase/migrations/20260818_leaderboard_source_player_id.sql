-- Preserve the original MLB (MLBAM) player ID separately from the
-- Supabase players.id UUID used as leaderboard_entries.player_id.
-- Headshot URLs are derived at read time from this ID; do not backfill
-- production rows manually.
ALTER TABLE public.leaderboard_entries
  ADD COLUMN IF NOT EXISTS source_player_id text;
