-- =====================================================================
-- ALSE — 0002: idempotent writes (schema_version stays 1; additive column)
-- Why: a write can succeed at the DB but exceed the engine's 2s deadline
-- (Doc 3 §3.2) → engine buffers it → later flush would DUPLICATE the audit
-- row. Every row now carries a client-generated row_uuid (UNIQUE); the
-- writer inserts with ON CONFLICT (row_uuid) DO NOTHING.
-- ADD COLUMN does not fire row-level UPDATE triggers, so immutability holds.
-- =====================================================================
do $$
declare t text;
begin
  foreach t in array array['order_events','trade_events','range_log','signal_events','risk_state_events',
                           'daily_equity','heartbeats','system_events','alerts_log','manual_interventions',
                           'config_parameter_changes','ticks']
  loop
    execute format('alter table %I add column if not exists row_uuid uuid not null default gen_random_uuid()', t);
    execute format('create unique index if not exists %I on %I (row_uuid)', t || '_row_uuid_key', t);
  end loop;
end $$;
