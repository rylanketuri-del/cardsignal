-- Sprint 11.3: durable previous-season performance snapshots
CREATE TABLE IF NOT EXISTS performance_snapshots (
    id BIGSERIAL PRIMARY KEY,
    cs_player_id TEXT NOT NULL,
    source_player_id TEXT NOT NULL,
    league TEXT NOT NULL,
    sport TEXT NOT NULL,
    season INTEGER NOT NULL,
    position TEXT,
    team TEXT,
    games_played INTEGER NOT NULL DEFAULT 0,
    starts INTEGER,
    stats JSONB NOT NULL DEFAULT '{}'::jsonb,
    data_quality TEXT NOT NULL DEFAULT 'INSUFFICIENT',
    source_method TEXT NOT NULL DEFAULT 'APPROVED_IMPORT',
    source_reference TEXT NOT NULL DEFAULT '',
    provider_updated_at TIMESTAMPTZ,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    algorithm_version TEXT NOT NULL DEFAULT 'PREVIOUS_SEASON_V1',
    period_type TEXT NOT NULL DEFAULT 'PREVIOUS_SEASON',
    player_name TEXT,
    headshot_url TEXT,
    team_logo_url TEXT,
    UNIQUE (cs_player_id, league, season, period_type)
);

CREATE INDEX IF NOT EXISTS idx_performance_snapshots_league_season
    ON performance_snapshots (league, season, period_type);

CREATE INDEX IF NOT EXISTS idx_performance_snapshots_cs_player
    ON performance_snapshots (cs_player_id, league);
