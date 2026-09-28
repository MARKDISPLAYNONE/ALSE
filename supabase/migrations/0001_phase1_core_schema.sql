-- =====================================================================
-- ALSE — Phase 1 core schema (schema_version = 1)
-- Implements Doc 3 §3.3 principles + Doc 4 §1.2 access control.
--
-- Principles enforced here:
--   1. Audit tables are INSERT-only, enforced STRUCTURALLY by triggers
--      (Supabase's service_role BYPASSES RLS, so RLS alone cannot
--      guarantee immutability — triggers fire for every role).
--   2. Dual timestamps: ts_utc (timestamptz) + ts_ny (NY wall clock),
--      both written explicitly by the engine, never derived at read time.
--   3. Every table carries schema_version.
--   4. Provisional parameters live in DB config rows (append-only log).
--   5. Raw ticks: rolling retention (30–60d) — the ONLY table where
--      DELETE is permitted, and only for rows older than 30 days.
--   6. RLS on every table, default-deny. Dashboard = authenticated
--      read-only SELECT. Engine = service_role (bypasses RLS, still
--      blocked from UPDATE/DELETE by triggers).
--
-- Write-ordering (Doc 3 §3.2) under immutability: the pre-send row is
-- inserted with status 'pending_confirmation'; the broker response is a
-- NEW row (same client_order_ref) with status 'confirmed'/'rejected'.
-- An orphan = a ref whose only row is pending_confirmation (see view).
-- =====================================================================

create extension if not exists pgcrypto;

-- ---------- Immutability guard ------------------------------------------
create or replace function alse_block_mutation() returns trigger
language plpgsql as $$
begin
  raise exception 'ALSE: % on %.% is forbidden — audit tables are INSERT-only (Doc 4 §1.2). Insert a compensating row instead.',
    tg_op, tg_table_schema, tg_table_name
    using errcode = 'insufficient_privilege';
end $$;

create or replace function alse_make_immutable(tbl regclass) returns void
language plpgsql as $$
begin
  execute format('create trigger %I before update or delete on %s for each row execute function alse_block_mutation()',
                 'trg_immutable_' || replace(tbl::text, '.', '_'), tbl);
  execute format('create trigger %I before truncate on %s for each statement execute function alse_block_mutation()',
                 'trg_immutable_trunc_' || replace(tbl::text, '.', '_'), tbl);
  execute format('alter table %s enable row level security', tbl);
end $$;

-- ---------- Enums ------------------------------------------------------
create type order_status  as enum ('pending_confirmation','confirmed','rejected','error');
create type order_action  as enum ('submit','fill','partial_fill','partial_close','modify','cancel','expire','hard_kill_close','circuit_breaker_close');
create type setup_side    as enum ('bullish','bearish');
create type risk_state    as enum ('A','B');
create type heartbeat_kind as enum ('daily_coarse','active_window');
create type severity      as enum ('info','warning','high','critical');

-- ---------- Config: provisional parameters (Doc 2 §9, Doc 3 §3.3) ------
create table config_parameter_changes (
  id              bigint generated always as identity primary key,
  schema_version  smallint    not null default 1,
  ts_utc          timestamptz not null default now(),
  ts_ny           timestamp   not null default (now() at time zone 'America/New_York'),
  param_key       text        not null,
  old_value       text,
  new_value       text        not null,
  is_provisional  boolean     not null default true,
  reason          text        not null,
  changed_by      text        not null,
  doc2_changelog_ref text     -- Doc 2 Change Log version authorising this change
);
select alse_make_immutable('config_parameter_changes');

create view config_current as
select distinct on (param_key) param_key, new_value as value, is_provisional, ts_utc as effective_since, doc2_changelog_ref
from config_parameter_changes
order by param_key, id desc;

insert into config_parameter_changes (param_key, new_value, is_provisional, reason, changed_by, doc2_changelog_ref) values
  ('sl_min_points',               '15',   true,  'Initial seed from Doc 2 §9', 'migration_0001', 'v5.0'),
  ('sl_max_points',               '100',  true,  'Initial seed from Doc 2 §9', 'migration_0001', 'v5.0'),
  ('displacement_min_penetration','10',   true,  'Initial seed from Doc 2 §9', 'migration_0001', 'v5.0'),
  ('displacement_body_ratio',     '0.60', true,  'Initial seed from Doc 2 §9', 'migration_0001', 'v5.0'),
  ('circuit_breaker_pct',         '0.04', true,  'Initial seed from Doc 2 §9', 'migration_0001', 'v5.0'),
  ('risk_pct_state_a',            '0.02', true,  'Initial seed from Doc 2 §9', 'migration_0001', 'v5.0'),
  ('risk_pct_state_b',            '0.005',true,  'Initial seed from Doc 2 §9', 'migration_0001', 'v5.0'),
  ('win_streak_throttle_trigger', '5',    true,  'Initial seed from Doc 2 §9', 'migration_0001', 'v5.0'),
  ('ft_hard_fail_max_dd_pct',     '0.10', true,  'Initial seed from Doc 2 §9.5','migration_0001','v5.0'),
  ('ft_hard_fail_cb_per_month',   '3',    true,  'Initial seed from Doc 2 §9.5','migration_0001','v5.0'),
  ('ft_hard_fail_pf',             '1.2',  true,  'Initial seed from Doc 2 §9.5','migration_0001','v5.0'),
  ('ft_hard_fail_pf_min_trades',  '30',   true,  'Initial seed from Doc 2 §9.5 (net-new)','migration_0001','v5.0'),
  ('ft_pass_pf',                  '1.5',  true,  'Initial seed from Doc 2 §9.5','migration_0001','v5.0'),
  ('ft_pass_expectancy_ratio',    '0.70', true,  'Initial seed from Doc 2 §9.5','migration_0001','v5.0'),
  ('ft_min_trades',               '50',   true,  'Initial seed from Doc 2 §9.5','migration_0001','v5.0'),
  -- Hard rules (not provisional) — stored for visibility, not tunable without Doc 2 change
  ('spread_gate_max_points',      '5',    false, 'Hard rule, Doc 2 §4', 'migration_0001', 'v5.0'),
  ('max_lot',                     '25.00',false, 'Broker cap, Doc 2 §1','migration_0001', 'v5.0'),
  ('min_lot',                     '0.01', false, 'Broker, Doc 2 §1',    'migration_0001', 'v5.0'),
  ('point_value_usd',             '20',   false, 'Broker, Doc 2 §1',    'migration_0001', 'v5.0'),
  ('commission_per_lot_usd',      '10',   false, 'Broker, Doc 2 §1',    'migration_0001', 'v5.0');

-- ---------- Order lifecycle audit trail (Doc 3 §3.2, Doc 4 §4.1) -------
create table order_events (
  id               bigint generated always as identity primary key,
  schema_version   smallint    not null default 1,
  ts_utc           timestamptz not null,
  ts_ny            timestamp   not null,
  trading_day      date        not null,           -- NY trading day the setup belongs to
  client_order_ref uuid        not null,           -- links pending → confirmed/rejected rows
  action           order_action not null,
  status           order_status not null,
  side             setup_side,
  mt5_ticket       bigint,
  mt5_retcode      integer,
  mt5_comment      text,
  order_type       text,                           -- e.g. ORDER_TYPE_BUY_LIMIT
  lots             numeric(10,2),
  price            numeric(14,2),
  sl               numeric(14,2),
  tp               numeric(14,2),
  fill_price       numeric(14,2),
  spread_points    numeric(10,2),
  reason           text,
  payload          jsonb
);
create index on order_events (client_order_ref);
create index on order_events (trading_day);
select alse_make_immutable('order_events');

create view orphaned_order_events as
select client_order_ref, min(ts_utc) as first_seen
from order_events
group by client_order_ref
having bool_and(status = 'pending_confirmation');

-- ---------- Trades (one row per lifecycle event; normalized) ------------
create table trade_events (
  id              bigint generated always as identity primary key,
  schema_version  smallint    not null default 1,
  ts_utc          timestamptz not null,
  ts_ny           timestamp   not null,
  trading_day     date        not null,
  trade_ref       uuid        not null,
  event           text        not null check (event in ('opened','partial_closed','sl_moved_be5','closed_tp','closed_sl','closed_hard_kill','closed_circuit_breaker','closed_other')),
  side            setup_side  not null,
  lots            numeric(10,2),
  price           numeric(14,2),
  gross_pnl_usd   numeric(14,2),
  commission_usd  numeric(14,2),
  net_pnl_usd     numeric(14,2),
  risk_state_at_entry risk_state,
  payload         jsonb
);
create index on trade_events (trade_ref);
select alse_make_immutable('trade_events');

-- ---------- Range & signal logs (Doc 2 §3–4) -----------------------------
create table range_log (
  id              bigint generated always as identity primary key,
  schema_version  smallint    not null default 1,
  ts_utc          timestamptz not null,
  ts_ny           timestamp   not null,
  trading_day     date        not null unique,
  range_high      numeric(14,2) not null,
  range_low       numeric(14,2) not null,
  range_size      numeric(14,2) not null,
  levels          jsonb       not null      -- {-1.0:…, 0.25:…, 0.75:…, 2.0:…} + viz-only extensions
);
select alse_make_immutable('range_log');

create table signal_events (
  id              bigint generated always as identity primary key,
  schema_version  smallint    not null default 1,
  ts_utc          timestamptz not null,
  ts_ny           timestamp   not null,
  trading_day     date        not null,
  event           text        not null check (event in ('sweep','displacement_valid','displacement_rejected','setup_suppressed','resting_order_invalidated','setup_aborted','rejected_sl_too_shallow','rejected_sl_cap','rejected_spread','rejected_min_lot','rejected_margin_max_lot')),
  side            setup_side,
  candle_open     numeric(14,2),
  candle_high     numeric(14,2),
  candle_low      numeric(14,2),
  candle_close    numeric(14,2),
  penetration_pts numeric(10,2),
  body_ratio      numeric(6,4),
  reason          text,
  payload         jsonb
);
create index on signal_events (trading_day);
select alse_make_immutable('signal_events');

-- ---------- Risk state & equity (Doc 2 §7) ------------------------------
create table risk_state_events (
  id              bigint generated always as identity primary key,
  schema_version  smallint    not null default 1,
  ts_utc          timestamptz not null,
  ts_ny           timestamp   not null,
  trading_day     date        not null,
  event           text        not null check (event in ('win','loss','no_trade_day','circuit_breaker_tripped','state_restored')),
  state_before    risk_state  not null,
  state_after     risk_state  not null,
  win_streak_before smallint  not null,
  win_streak_after  smallint  not null,
  trade_ref       uuid,
  payload         jsonb
);
select alse_make_immutable('risk_state_events');

create table daily_equity (
  id              bigint generated always as identity primary key,
  schema_version  smallint    not null default 1,
  ts_utc          timestamptz not null,
  ts_ny           timestamp   not null,
  trading_day     date        not null,
  kind            text        not null check (kind in ('start_of_day','end_of_day','snapshot')),
  equity_usd      numeric(14,2) not null,
  balance_usd     numeric(14,2),
  margin_free_usd numeric(14,2)
);
create index on daily_equity (trading_day);
select alse_make_immutable('daily_equity');

-- ---------- System health (Doc 2 §2.5, Doc 3 §6) ------------------------
create table heartbeats (
  id              bigint generated always as identity primary key,
  schema_version  smallint    not null default 1,
  ts_utc          timestamptz not null,
  ts_ny           timestamp   not null,
  kind            heartbeat_kind not null,
  mt5_connected   boolean,
  buffer_backlog  integer,
  host            text,
  payload         jsonb
);
create index on heartbeats (kind, ts_utc desc);
select alse_make_immutable('heartbeats');

create table system_events (
  id              bigint generated always as identity primary key,
  schema_version  smallint    not null default 1,
  ts_utc          timestamptz not null,
  ts_ny           timestamp   not null,
  event           text        not null,   -- e.g. process_start, crash, mt5_disconnect, mt5_reconnect, write_timeout_fallback, buffer_flushed
  severity        severity    not null default 'info',
  detail          text,
  payload         jsonb
);
create index on system_events (event, ts_utc desc);
select alse_make_immutable('system_events');

create table alerts_log (
  id              bigint generated always as identity primary key,
  schema_version  smallint    not null default 1,
  ts_utc          timestamptz not null,
  ts_ny           timestamp   not null,
  channel         text        not null,
  severity        severity    not null,
  title           text        not null,
  body            text,
  delivered       boolean     not null,   -- Discord is convenience only; this row is the record (Doc 3 §6)
  delivery_error  text
);
select alse_make_immutable('alerts_log');

-- ---------- Manual interventions (Doc 4 §2.3) ---------------------------
create table manual_interventions (
  id              bigint generated always as identity primary key,
  schema_version  smallint    not null default 1,
  ts_utc          timestamptz not null default now(),
  ts_ny           timestamp   not null default (now() at time zone 'America/New_York'),
  performed_by    text        not null,
  action          text        not null,
  reason          text        not null,
  mt5_tickets     bigint[]
);
select alse_make_immutable('manual_interventions');

-- ---------- Raw ticks (analytics only; rolling retention) ---------------
create table ticks (
  id              bigint generated always as identity primary key,
  schema_version  smallint    not null default 1,
  ts_utc          timestamptz not null,
  ts_ny           timestamp   not null,
  bid             numeric(14,2) not null,
  ask             numeric(14,2) not null,
  spread_points   numeric(10,2) not null
);
create index on ticks (ts_utc);
alter table ticks enable row level security;

create or replace function alse_ticks_guard() returns trigger
language plpgsql as $$
begin
  if tg_op = 'UPDATE' then
    raise exception 'ALSE: UPDATE on ticks forbidden';
  end if;
  if tg_op = 'DELETE' and old.ts_utc > now() - interval '30 days' then
    raise exception 'ALSE: ticks younger than 30 days cannot be deleted (retention window, Doc 3 §3.3)';
  end if;
  return old;
end $$;
create trigger trg_ticks_guard before update or delete on ticks
  for each row execute function alse_ticks_guard();

create or replace function alse_purge_old_ticks(keep_days integer default 45) returns integer
language plpgsql security definer set search_path = public as $$
declare n integer;
begin
  if keep_days < 30 or keep_days > 60 then
    raise exception 'keep_days must be within 30–60 (Doc 3 §3.3)';
  end if;
  delete from ticks where ts_utc < now() - make_interval(days => keep_days);
  get diagnostics n = row_count;
  insert into system_events (ts_utc, ts_ny, event, severity, detail)
  values (now(), now() at time zone 'America/New_York', 'tick_retention_purge', 'info', n || ' rows purged, keep_days=' || keep_days);
  return n;
end $$;
revoke all on function alse_purge_old_ticks(integer) from public, anon, authenticated;

-- ---------- Access control (Doc 4 §1.2) ---------------------------------
-- Default deny: strip everything from client roles, then grant SELECT only.
revoke all on all tables in schema public from anon, authenticated;

do $$
declare t text;
begin
  foreach t in array array['order_events','trade_events','range_log','signal_events','risk_state_events',
                           'daily_equity','heartbeats','system_events','alerts_log','manual_interventions',
                           'config_parameter_changes','ticks']
  loop
    execute format('grant select on %I to authenticated', t);
    execute format('create policy %I on %I for select to authenticated using (true)', 'dash_read_' || t, t);
  end loop;
end $$;
grant select on config_current, orphaned_order_events to authenticated;
-- anon role: no access at all. Dashboard must sign in (single owner account).

-- ---------- Realtime (Doc 3 §4.1) ---------------------------------------
alter publication supabase_realtime add table
  order_events, trade_events, signal_events, risk_state_events, daily_equity, heartbeats, system_events;

-- ---------- Optional: schedule tick purge via pg_cron --------------------
-- Enable pg_cron in Supabase Dashboard → Database → Extensions, then run:
--   select cron.schedule('alse_tick_purge', '15 12 * * *', $$select alse_purge_old_ticks(45)$$);
