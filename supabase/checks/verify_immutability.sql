-- Run in Supabase SQL Editor. Expected: 11 immutability triggers listed (12 tables incl. ticks guard),
-- then the UPDATE and DELETE below must each FAIL with "ALSE: ... is forbidden".
select tgrelid::regclass as table_name, tgname
from pg_trigger
where tgname like 'trg_immutable_%' or tgname = 'trg_ticks_guard'
order by 1, 2;

-- Run these two lines ONE AT A TIME — each must ERROR:
-- update system_events set detail = 'tamper' where id = (select min(id) from system_events);
-- delete from system_events where id = (select min(id) from system_events);
