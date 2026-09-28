-- ⚠️ DEV ONLY — drops the entire ALSE schema so 0001 + 0002 can be re-run from scratch.
-- Refuses to run if any real order/trade history exists. NEVER run once Phase 4 (demo) starts.
do $$
declare n bigint;
begin
  if to_regclass('public.order_events') is not null then
    execute 'select count(*) from public.order_events' into n;
    if n > 0 then raise exception 'Refusing: order_events has % rows — audit history, not dev junk.', n; end if;
  end if;
  if to_regclass('public.trade_events') is not null then
    execute 'select count(*) from public.trade_events' into n;
    if n > 0 then raise exception 'Refusing: trade_events has % rows.', n; end if;
  end if;
end $$;

drop view  if exists config_current, orphaned_order_events cascade;
drop table if exists order_events, trade_events, range_log, signal_events, risk_state_events, daily_equity,
                     heartbeats, system_events, alerts_log, manual_interventions, config_parameter_changes, ticks cascade;
drop function if exists alse_block_mutation(), alse_make_immutable(regclass), alse_ticks_guard(),
                        alse_purge_old_ticks(integer) cascade;
drop type if exists order_status, order_action, setup_side, risk_state, heartbeat_kind, severity cascade;
