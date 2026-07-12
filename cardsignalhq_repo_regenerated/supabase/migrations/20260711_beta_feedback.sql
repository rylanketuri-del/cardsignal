-- Beta feedback table for closed-beta collector submissions.
-- Users may insert their own feedback; no public reads.

create table if not exists public.beta_feedback (
  id bigint generated always as identity primary key,
  user_id uuid references auth.users(id) on delete set null,
  feedback_type text not null check (feedback_type in ('CONFUSING', 'BUG', 'IDEA', 'LOVE', 'OTHER')),
  message text not null check (char_length(message) between 3 and 2000),
  page_url text,
  current_route text,
  entity_type text,
  entity_id text,
  sport text,
  app_version text not null,
  build_id text not null,
  browser_summary text,
  viewport_width integer,
  viewport_height integer,
  status text not null default 'NEW' check (status in ('NEW', 'REVIEWED', 'PLANNED', 'CLOSED')),
  client_ip text,
  screenshot_ref text,
  created_at timestamptz not null default now()
);

create index if not exists idx_beta_feedback_created_at on public.beta_feedback (created_at desc);
create index if not exists idx_beta_feedback_status on public.beta_feedback (status, created_at desc);
create index if not exists idx_beta_feedback_type on public.beta_feedback (feedback_type, created_at desc);

alter table public.beta_feedback enable row level security;

-- Authenticated users may insert feedback linked to their account.
drop policy if exists "users insert own beta feedback" on public.beta_feedback;
create policy "users insert own beta feedback"
  on public.beta_feedback
  for insert
  with check (user_id is null or auth.uid() = user_id);

-- Anonymous inserts are performed via service role from the backend API only.
-- No public select policies — feedback is admin-reviewed through protected API routes.
