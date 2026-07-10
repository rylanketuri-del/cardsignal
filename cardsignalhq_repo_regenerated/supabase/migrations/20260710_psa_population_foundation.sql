-- Sprint 8.6 — PSA card matches and append-only population snapshots

create table if not exists public.psa_card_matches (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  cs_card_id text not null,
  cs_player_id text not null,
  league text not null default 'MLB',
  provider text not null default 'PSA',
  psa_subject_id text,
  psa_set_id text,
  psa_card_id text,
  certification_number text,
  year text not null default '',
  manufacturer text not null default '',
  set_name text not null default '',
  card_number text not null default '',
  card_name text not null default '',
  parallel text not null default '',
  variety text not null default '',
  player_name text not null default '',
  match_status text not null default 'UNMATCHED',
  match_confidence text not null default 'LOW',
  matched_at timestamptz,
  source_method text not null default 'manual_beta_seed',
  notes text not null default '',
  match_payload jsonb not null default '{}'::jsonb,
  unique (cs_card_id, provider)
);

create index if not exists idx_psa_card_matches_cs_card_id
  on public.psa_card_matches (cs_card_id);

create index if not exists idx_psa_card_matches_cs_player_id
  on public.psa_card_matches (cs_player_id);

create index if not exists idx_psa_card_matches_match_status
  on public.psa_card_matches (match_status);

create index if not exists idx_psa_card_matches_psa_card_id
  on public.psa_card_matches (psa_card_id);

create table if not exists public.card_population_snapshots (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  cs_card_id text not null,
  cs_player_id text not null,
  provider text not null default 'PSA',
  source_method text not null default 'manual_beta_seed',
  captured_at timestamptz not null,
  psa_card_id text,
  algorithm_version text not null default '',
  match_confidence text not null default 'LOW',
  data_quality text not null default 'INSUFFICIENT',
  metrics jsonb not null default '{}'::jsonb
);

create index if not exists idx_card_population_snapshots_card_captured
  on public.card_population_snapshots (cs_card_id, captured_at desc);

create index if not exists idx_card_population_snapshots_player_captured
  on public.card_population_snapshots (cs_player_id, captured_at desc);

create index if not exists idx_card_population_snapshots_provider_captured
  on public.card_population_snapshots (provider, captured_at desc);

alter table public.psa_card_matches enable row level security;
alter table public.card_population_snapshots enable row level security;

drop policy if exists "public read psa card matches" on public.psa_card_matches;
create policy "public read psa card matches"
  on public.psa_card_matches
  for select
  using (true);

drop policy if exists "public read card population snapshots" on public.card_population_snapshots;
create policy "public read card population snapshots"
  on public.card_population_snapshots
  for select
  using (true);
