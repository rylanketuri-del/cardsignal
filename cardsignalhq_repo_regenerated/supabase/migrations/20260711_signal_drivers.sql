-- Signal Drivers & Seasonal Intelligence (Sprint 9.3 / v0.11.1)

CREATE TABLE IF NOT EXISTS signal_drivers (
    driver_id TEXT PRIMARY KEY,
    identity_key TEXT NOT NULL UNIQUE,
    cs_player_id TEXT NOT NULL,
    source_player_id TEXT NOT NULL,
    league TEXT NOT NULL,
    sport TEXT NOT NULL,
    driver_type TEXT NOT NULL,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    metric_name TEXT,
    metric_value JSONB,
    comparison_value JSONB,
    impact TEXT NOT NULL DEFAULT 'UNKNOWN',
    evidence_quality TEXT NOT NULL DEFAULT 'INSUFFICIENT',
    source_type TEXT NOT NULL,
    source_reference TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    algorithm_version TEXT NOT NULL DEFAULT 'SIGNAL_DRIVERS_V1',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_signal_drivers_player ON signal_drivers (cs_player_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_signal_drivers_league_type ON signal_drivers (league, driver_type);

CREATE TABLE IF NOT EXISTS league_season_metadata (
    league TEXT NOT NULL,
    season INTEGER NOT NULL,
    sport TEXT NOT NULL,
    regular_season_start TIMESTAMPTZ,
    regular_season_end TIMESTAMPTZ,
    postseason_start TIMESTAMPTZ,
    postseason_end TIMESTAMPTZ,
    preseason_start TIMESTAMPTZ,
    preseason_end TIMESTAMPTZ,
    offseason_start TIMESTAMPTZ,
    offseason_end TIMESTAMPTZ,
    source_type TEXT NOT NULL,
    source_reference TEXT NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    algorithm_version TEXT NOT NULL DEFAULT 'SIGNAL_DRIVERS_V1',
    PRIMARY KEY (league, season)
);

CREATE TABLE IF NOT EXISTS player_developments (
    development_id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    cs_player_id TEXT NOT NULL,
    source_player_id TEXT NOT NULL,
    league TEXT NOT NULL,
    driver_type TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    source_type TEXT NOT NULL,
    source_reference TEXT NOT NULL UNIQUE,
    impact TEXT NOT NULL DEFAULT 'UNKNOWN',
    evidence_quality TEXT NOT NULL DEFAULT 'INSUFFICIENT',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_player_developments_player ON player_developments (cs_player_id, occurred_at DESC);

ALTER TABLE signal_drivers ENABLE ROW LEVEL SECURITY;
ALTER TABLE league_season_metadata ENABLE ROW LEVEL SECURITY;
ALTER TABLE player_developments ENABLE ROW LEVEL SECURITY;

CREATE POLICY signal_drivers_public_read ON signal_drivers FOR SELECT USING (true);
CREATE POLICY league_season_metadata_public_read ON league_season_metadata FOR SELECT USING (true);
CREATE POLICY player_developments_public_read ON player_developments FOR SELECT USING (true);

-- Future-compatible score relationship (optional on weekly snapshots)
ALTER TABLE player_weekly_signal_snapshots
    ADD COLUMN IF NOT EXISTS supporting_driver_ids JSONB NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE player_weekly_signal_snapshots
    ADD COLUMN IF NOT EXISTS driver_evidence_used JSONB NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE player_weekly_signal_snapshots
    ADD COLUMN IF NOT EXISTS driver_missing_evidence JSONB NOT NULL DEFAULT '[]'::jsonb;
