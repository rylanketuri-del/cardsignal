-- Sprint 8.3 — append-only card market snapshot observations

create table if not exists public.card_market_snapshots (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  cs_card_id text not null,
  cs_player_id text not null,
  captured_at timestamptz not null,
  source text not null default 'ebay',
  query text not null default '',
  algorithm_version text not null default '',
  metrics jsonb not null default '{}'::jsonb
);

create index if not exists idx_card_market_snapshots_card_captured
  on public.card_market_snapshots (cs_card_id, captured_at desc);

create index if not exists idx_card_market_snapshots_player_captured
  on public.card_market_snapshots (cs_player_id, captured_at desc);

alter table public.card_market_snapshots enable row level security;

drop policy if exists "public read card market snapshots" on public.card_market_snapshots;
create policy "public read card market snapshots"
  on public.card_market_snapshots
  for select
  using (true);
