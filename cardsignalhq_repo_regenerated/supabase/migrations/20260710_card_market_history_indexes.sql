-- Sprint 8.5 — focused card-market history lookup indexes

create index if not exists idx_card_market_snapshots_card_source_captured
  on public.card_market_snapshots (cs_card_id, source, captured_at desc);

create index if not exists idx_card_market_snapshots_player_source_captured
  on public.card_market_snapshots (cs_player_id, source, captured_at desc);
