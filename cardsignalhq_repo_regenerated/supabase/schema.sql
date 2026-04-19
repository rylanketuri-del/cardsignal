create extension if not exists pgcrypto;

create table if not exists public.players (
  id uuid primary key default gen_random_uuid(),
  name text not null unique,
  created_at timestamptz not null default now()
);

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text,
  created_at timestamptz not null default now()
);

create table if not exists public.pipeline_runs (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  leaderboard_path text,
  tracked_players jsonb not null default '[]'::jsonb,
  entry_count integer not null default 0
);

create table if not exists public.leaderboard_entries (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  run_id bigint not null references public.pipeline_runs(id) on delete cascade,
  player_id uuid references public.players(id) on delete set null,
  player_name text not null,
  rank integer not null,
  performance_score numeric(6,2) not null,
  market_score numeric(6,2) not null,
  total_score numeric(6,2) not null,
  confidence_multiplier numeric(5,2) not null,
  tag text not null,
  reasons jsonb not null default '[]'::jsonb,
  stats_7d jsonb not null,
  stats_30d jsonb not null,
  market_snapshots jsonb not null
);

create table if not exists public.watchlists (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  player_id uuid references public.players(id) on delete set null,
  player_name text not null,
  created_at timestamptz not null default now(),
  unique(user_id, player_name)
);

create table if not exists public.alert_subscriptions (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  email text,
  hotness_jump_enabled boolean not null default true,
  buy_low_enabled boolean not null default true,
  most_chased_enabled boolean not null default false,
  daily_digest_enabled boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(user_id)
);

create index if not exists idx_pipeline_runs_created_at on public.pipeline_runs(created_at desc);
create index if not exists idx_leaderboard_entries_run_id on public.leaderboard_entries(run_id);
create index if not exists idx_leaderboard_entries_player_name on public.leaderboard_entries(player_name);
create index if not exists idx_leaderboard_entries_total_score on public.leaderboard_entries(total_score desc);
create index if not exists idx_watchlists_user_id on public.watchlists(user_id, created_at desc);
create index if not exists idx_alert_subscriptions_user_id on public.alert_subscriptions(user_id);

create table if not exists public.player_alert_rules (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  player_name text not null,
  min_hotness_delta numeric(6,2) not null default 8,
  alert_on_hotness_jump boolean not null default true,
  alert_on_buy_low boolean not null default true,
  alert_on_most_chased boolean not null default false,
  muted_until timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(user_id, player_name)
);

create index if not exists idx_player_alert_rules_user_id on public.player_alert_rules(user_id, updated_at desc);

create table if not exists public.notifications (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  run_id bigint references public.pipeline_runs(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  player_id uuid references public.players(id) on delete set null,
  player_name text,
  event_type text not null,
  channel text not null default 'in_app',
  title text not null,
  message text not null,
  metadata jsonb not null default '{}'::jsonb,
  read_at timestamptz,
  unique(run_id, user_id, event_type, player_name, title)
);

create table if not exists public.notification_deliveries (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  notification_id bigint not null references public.notifications(id) on delete cascade,
  channel text not null,
  status text not null,
  destination text,
  provider text,
  provider_message_id text,
  error text
);

create index if not exists idx_notifications_user_id on public.notifications(user_id, created_at desc);
create index if not exists idx_notifications_run_id on public.notifications(run_id);
create index if not exists idx_notification_deliveries_notification_id on public.notification_deliveries(notification_id, created_at desc);

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, email)
  values (new.id, new.email)
  on conflict (id) do update set email = excluded.email;

  insert into public.alert_subscriptions (user_id, email)
  values (new.id, new.email)
  on conflict (user_id) do update set email = excluded.email, updated_at = now();

  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

create or replace function public.touch_alert_subscriptions_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists trg_alert_subscriptions_updated_at on public.alert_subscriptions;
create trigger trg_alert_subscriptions_updated_at
  before update on public.alert_subscriptions
  for each row execute procedure public.touch_alert_subscriptions_updated_at();

alter table public.players enable row level security;
alter table public.profiles enable row level security;
alter table public.pipeline_runs enable row level security;
alter table public.leaderboard_entries enable row level security;
alter table public.watchlists enable row level security;
alter table public.alert_subscriptions enable row level security;
alter table public.player_alert_rules enable row level security;
alter table public.notifications enable row level security;
alter table public.notification_deliveries enable row level security;

-- Development-friendly public leaderboard reads.
drop policy if exists "public read players" on public.players;
create policy "public read players" on public.players for select using (true);

drop policy if exists "public read pipeline_runs" on public.pipeline_runs;
create policy "public read pipeline_runs" on public.pipeline_runs for select using (true);

drop policy if exists "public read leaderboard_entries" on public.leaderboard_entries;
create policy "public read leaderboard_entries" on public.leaderboard_entries for select using (true);

-- Authenticated user access for personal data.
drop policy if exists "users read own profile" on public.profiles;
create policy "users read own profile" on public.profiles for select using (auth.uid() = id);

drop policy if exists "users update own profile" on public.profiles;
create policy "users update own profile" on public.profiles for update using (auth.uid() = id);

drop policy if exists "users read own watchlists" on public.watchlists;
create policy "users read own watchlists" on public.watchlists for select using (auth.uid() = user_id);

drop policy if exists "users insert own watchlists" on public.watchlists;
create policy "users insert own watchlists" on public.watchlists for insert with check (auth.uid() = user_id);

drop policy if exists "users delete own watchlists" on public.watchlists;
create policy "users delete own watchlists" on public.watchlists for delete using (auth.uid() = user_id);

drop policy if exists "users read own alert subscriptions" on public.alert_subscriptions;
create policy "users read own alert subscriptions" on public.alert_subscriptions for select using (auth.uid() = user_id);

drop policy if exists "users insert own alert subscriptions" on public.alert_subscriptions;
create policy "users insert own alert subscriptions" on public.alert_subscriptions for insert with check (auth.uid() = user_id);

drop policy if exists "users update own alert subscriptions" on public.alert_subscriptions;
create policy "users update own alert subscriptions" on public.alert_subscriptions for update using (auth.uid() = user_id);


drop policy if exists "users read own player alert rules" on public.player_alert_rules;
create policy "users read own player alert rules" on public.player_alert_rules for select using (auth.uid() = user_id);

drop policy if exists "users insert own player alert rules" on public.player_alert_rules;
create policy "users insert own player alert rules" on public.player_alert_rules for insert with check (auth.uid() = user_id);

drop policy if exists "users update own player alert rules" on public.player_alert_rules;
create policy "users update own player alert rules" on public.player_alert_rules for update using (auth.uid() = user_id);

drop policy if exists "users delete own player alert rules" on public.player_alert_rules;
create policy "users delete own player alert rules" on public.player_alert_rules for delete using (auth.uid() = user_id);

create or replace function public.touch_player_alert_rules_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists trg_player_alert_rules_updated_at on public.player_alert_rules;
create trigger trg_player_alert_rules_updated_at
  before update on public.player_alert_rules
  for each row execute procedure public.touch_player_alert_rules_updated_at();

drop policy if exists "users read own notifications" on public.notifications;
create policy "users read own notifications" on public.notifications for select using (auth.uid() = user_id);

drop policy if exists "users update own notifications" on public.notifications;
create policy "users update own notifications" on public.notifications for update using (auth.uid() = user_id);


create table if not exists public.admin_settings (
  key text primary key,
  value jsonb not null default 'null'::jsonb,
  updated_at timestamptz not null default now()
);

create table if not exists public.tracked_player_configs (
  id bigint generated always as identity primary key,
  player_name text not null unique,
  active boolean not null default true,
  notes text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_tracked_player_configs_name on public.tracked_player_configs(player_name);

alter table public.admin_settings enable row level security;
alter table public.tracked_player_configs enable row level security;

drop policy if exists "public read admin settings" on public.admin_settings;
create policy "public read admin settings" on public.admin_settings for select using (true);

drop policy if exists "public read tracked player configs" on public.tracked_player_configs;
create policy "public read tracked player configs" on public.tracked_player_configs for select using (true);

create or replace function public.touch_admin_settings_updated_at()
returns trigger language plpgsql as $$ begin new.updated_at = now(); return new; end; $$;
drop trigger if exists trg_admin_settings_updated_at on public.admin_settings;
create trigger trg_admin_settings_updated_at before update on public.admin_settings for each row execute procedure public.touch_admin_settings_updated_at();

create or replace function public.touch_tracked_player_configs_updated_at()
returns trigger language plpgsql as $$ begin new.updated_at = now(); return new; end; $$;
drop trigger if exists trg_tracked_player_configs_updated_at on public.tracked_player_configs;
create trigger trg_tracked_player_configs_updated_at before update on public.tracked_player_configs for each row execute procedure public.touch_tracked_player_configs_updated_at();

insert into public.admin_settings(key, value) values
  ('tracked_players_csv', to_jsonb('Elly De La Cruz,Bobby Witt Jr.,Gunnar Henderson,Jackson Chourio'::text)),
  ('hotness_jump_threshold', '8'::jsonb),
  ('daily_digest_hour_utc', '13'::jsonb)
on conflict (key) do nothing;
