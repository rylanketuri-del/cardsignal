-- Sprint 8.8: Weekly Intelligence Pipeline tables
-- Reversible: drop tables in reverse order

create table if not exists public.weekly_intelligence_runs (
  run_id uuid primary key,
  league text not null,
  sport text not null,
  season integer not null,
  year integer not null,
  week_number integer not null,
  period_start timestamptz not null,
  period_end timestamptz not null,
  started_at timestamptz,
  completed_at timestamptz,
  status text not null default 'PENDING',
  triggered_by text not null default 'manual',
  force boolean not null default false,
  algorithm_version text not null default 'WEEKLY_INTELLIGENCE_V1',
  player_limit integer not null default 100,
  players_processed integer not null default 0,
  cards_processed integer not null default 0,
  market_snapshots_created integer not null default 0,
  population_snapshots_created integer not null default 0,
  intelligence_records_created integer not null default 0,
  warnings jsonb not null default '[]'::jsonb,
  errors jsonb not null default '[]'::jsonb,
  homepage_payload jsonb,
  created_at timestamptz not null default now()
);

create unique index if not exists idx_weekly_runs_official_unique
  on public.weekly_intelligence_runs (league, year, week_number)
  where status in ('COMPLETED', 'PARTIAL') and force = false and triggered_by <> 'test';

create index if not exists idx_weekly_runs_league_week on public.weekly_intelligence_runs (league, year, week_number);
create index if not exists idx_weekly_runs_status on public.weekly_intelligence_runs (status);
create index if not exists idx_weekly_runs_completed_at on public.weekly_intelligence_runs (completed_at desc);

create table if not exists public.player_weekly_signal_snapshots (
  snapshot_id uuid primary key,
  run_id uuid not null references public.weekly_intelligence_runs(run_id) on delete cascade,
  cs_player_id text not null,
  source_player_id text not null,
  league text not null,
  sport text not null,
  season integer not null,
  year integer not null,
  week_number integer not null,
  period_start timestamptz not null,
  period_end timestamptz not null,
  card_signal_score numeric(6,2),
  performance_score numeric(6,2),
  market_score numeric(6,2),
  collector_score numeric(6,2),
  momentum_score numeric(6,2),
  scarcity_score numeric(6,2),
  news_score numeric(6,2),
  recommendation text,
  conviction text,
  status text,
  weekly_change numeric(6,2),
  rank integer,
  evidence jsonb not null default '{}'::jsonb,
  missing_inputs jsonb not null default '[]'::jsonb,
  algorithm_version text not null default 'WEEKLY_INTELLIGENCE_V1',
  captured_at timestamptz not null default now(),
  player_name text,
  team text,
  position text,
  headshot_url text,
  team_logo_url text
);

create index if not exists idx_player_weekly_cs_player on public.player_weekly_signal_snapshots (cs_player_id, captured_at);
create index if not exists idx_player_weekly_run on public.player_weekly_signal_snapshots (run_id);
create index if not exists idx_player_weekly_league_week on public.player_weekly_signal_snapshots (league, year, week_number);

create table if not exists public.card_weekly_intelligence_snapshots (
  snapshot_id uuid primary key,
  run_id uuid not null references public.weekly_intelligence_runs(run_id) on delete cascade,
  cs_card_id text not null,
  cs_player_id text not null,
  league text not null,
  year integer not null,
  week_number integer not null,
  period_start timestamptz not null,
  period_end timestamptz not null,
  card_signal_score numeric(6,2),
  recommendation text,
  conviction text,
  risk text,
  time_horizon text,
  market_activity_score numeric(6,2),
  demand_score numeric(6,2),
  momentum_score numeric(6,2),
  scarcity_score numeric(6,2),
  evidence jsonb not null default '{}'::jsonb,
  missing_inputs jsonb not null default '[]'::jsonb,
  algorithm_version text not null default 'WEEKLY_INTELLIGENCE_V1',
  captured_at timestamptz not null default now(),
  card_label text,
  player_name text
);

create index if not exists idx_card_weekly_cs_card on public.card_weekly_intelligence_snapshots (cs_card_id, captured_at);
create index if not exists idx_card_weekly_run on public.card_weekly_intelligence_snapshots (run_id);
create index if not exists idx_card_weekly_league_week on public.card_weekly_intelligence_snapshots (league, year, week_number);

create table if not exists public.signal_of_the_week (
  id bigint generated always as identity primary key,
  run_id uuid not null references public.weekly_intelligence_runs(run_id) on delete cascade,
  cs_player_id text not null,
  player_name text not null,
  rank integer,
  score numeric(6,2),
  weekly_change numeric(6,2),
  recommendation text,
  conviction text,
  status text,
  reason text not null,
  evidence jsonb not null default '{}'::jsonb,
  algorithm_version text not null default 'WEEKLY_INTELLIGENCE_V1',
  selected_at timestamptz not null default now(),
  headshot_url text,
  team text,
  position text,
  team_logo_url text,
  source_player_id text
);

create index if not exists idx_signal_of_week_run on public.signal_of_the_week (run_id);
create index if not exists idx_signal_of_week_selected_at on public.signal_of_the_week (selected_at desc);

alter table public.weekly_intelligence_runs enable row level security;
alter table public.player_weekly_signal_snapshots enable row level security;
alter table public.card_weekly_intelligence_snapshots enable row level security;
alter table public.signal_of_the_week enable row level security;

drop policy if exists "public read weekly_intelligence_runs" on public.weekly_intelligence_runs;
create policy "public read weekly_intelligence_runs" on public.weekly_intelligence_runs for select using (true);

drop policy if exists "public read player_weekly_signal_snapshots" on public.player_weekly_signal_snapshots;
create policy "public read player_weekly_signal_snapshots" on public.player_weekly_signal_snapshots for select using (true);

drop policy if exists "public read card_weekly_intelligence_snapshots" on public.card_weekly_intelligence_snapshots;
create policy "public read card_weekly_intelligence_snapshots" on public.card_weekly_intelligence_snapshots for select using (true);

drop policy if exists "public read signal_of_the_week" on public.signal_of_the_week;
create policy "public read signal_of_the_week" on public.signal_of_the_week for select using (true);

-- Rollback:
-- drop table if exists public.signal_of_the_week;
-- drop table if exists public.card_weekly_intelligence_snapshots;
-- drop table if exists public.player_weekly_signal_snapshots;
-- drop table if exists public.weekly_intelligence_runs;
