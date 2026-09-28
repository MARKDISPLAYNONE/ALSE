# session-handover.md

## Handover Entry — 28 September 2026 — Session #1

**Tasks completed this block (5):**
1. Repo scaffold + security hygiene: `.gitignore` (secrets excluded from the first commit), `.env.example`, `pyproject.toml`, pre-commit (gitleaks, private-key detection), CI (ruff + pytest + gitleaks).
2. Supabase schema v1 (`supabase/migrations/0001_phase1_core_schema.sql`): immutable audit tables enforced by **triggers** (not just RLS), dual timestamps, `schema_version` on every table, provisional parameters as append-only config rows seeded from Doc 2 §9/§9.5, tick table with a 30–60 day purge function, read-only `authenticated` access for the dashboard, and a Realtime publication.
3. Session clock + trading calendar (`engine/session/`): NY zoneinfo, the Doc 2 §2 windows, the Thu→Fri hard kill, Mon–Thu only, computed US bank holidays, and FOMC 2026–2027. It fails closed after 2027. Decimal helpers (`engine/decimal_math.py`) reject float.
4. Data layer: `SupabaseWriter` (2s hard timeout, fsync'd JSONL buffer, in-order flush, INSERT-only API) and `MT5Client` (the only MT5 boundary, native or mt5linux bridge, all outputs Decimal).
5. Ops: Discord notifier (every alert recorded in `alerts_log`), heartbeat service (09:00 NY daily plus 5-minute active window), `/health` endpoint for UptimeRobot, systemd units, and the Phase 1 smoke-test script. 18 unit tests pass.

**Current phase:** Phase 1 — IN PROGRESS. The code side is done. The environment side is blocked on owner provisioning.

**Decisions made & rationale (within implementer authority, Doc 1 §9):**
- **Write-ordering vs immutability:** Doc 3 §3.2 says to "update" the pending row, but §3.3 and Doc 4 §1.2 forbid UPDATE. The broker response is written as a NEW compensating row with the same `client_order_ref`. The `orphaned_order_events` view shows refs that only have a pending row. This matches the compensating-row principle in Doc 3 §3.3. **Doc 3 wording needs a Change Log patch.**
- **Immutability is enforced by triggers.** Supabase's `service_role` bypasses RLS, so RLS alone could not stop the engine key from editing history.
- **Dashboard access:** the `anon` role gets no access. The dashboard signs in as the single owner Auth user (`authenticated`, SELECT only). This is stricter than Doc 4 §1.1's "anon key read-only" and still meets its intent.
- **HTTP to Supabase goes through httpx/PostgREST**, not supabase-py, so the 2s timeout is controlled exactly.
- Decimal values are serialised as strings so Postgres `numeric` receives them exactly.

**Open questions / blockers waiting on owner input:**
1. 🔴 **ESCALATION: ARM vs x86.** Doc 3 names the Oracle **ARM Ampere A1** as the primary host. MT5 is an x86 Windows binary, and Wine does not emulate CPUs. On ARM it needs box64/FEX-style emulation on top of Wine, which adds real instability. Options: (a) Oracle Always-Free **AMD E2.1.Micro** (x86, but only 1 GB RAM, very tight for Wine + MT5), (b) **AWS t3.micro** fallback (x86, 12-month limit), (c) ARM + box64 (not recommended). Choosing needs owner sign-off plus a Doc 3 Change Log entry.
2. 🟠 **FOMC exclusion day.** Doc 2 §1 just says "FOMC dates". Both meeting days are excluded for now as the conservative choice. Should it be decision-day only? This needs a Doc 2 Change Log entry.
3. 🟠 **Holiday-adjacent hard kill.** If the day after a session is a US holiday (e.g. Wed session → Thanksgiving Thu), broker hours may be shortened, and the 16:16 NY kill could fall after an early close. This needs checking against FX Pesa's holiday schedule.
4. Owner provisioning (Doc 6 Phase 1 blockers): Supabase project, Discord webhooks, MT5 demo credentials, VPS, UptimeRobot. See the README checklist.
5. Still open from Doc 6 §3: item 1 (broker spec PDF artifact), item 8 (uptime monitor — code ready, not configured), item 13 (broker entity).
6. Minor doc inconsistency: Doc 6 §7 says Doc 1 is "pending final patch", but Doc 1 v1.1 already includes those patches. Doc 6 should be updated to match.

**Files/documents touched or created:** `.gitignore`, `.env.example`, `.pre-commit-config.yaml`, `pyproject.toml`, `.github/workflows/ci.yml`, `README.md`, `supabase/migrations/0001_phase1_core_schema.sql`, `engine/decimal_math.py`, `engine/session/{calendar,clock}.py`, `data/settings.py`, `data/supabase_client/client.py`, `data/mt5_client/client.py`, `alerts/discord/notifier.py`, `ops/heartbeat.py`, `ops/systemd/*.service`, `scripts/phase1_smoke_test.py`, `tests/*`, `docs/05_PHASE_TRACKER_AND_ROADMAP.md` (status row).

**Next 5 tasks queued:**
1. Owner: resolve escalation #1 (host CPU arch), then provision the accounts per the README.
2. Run the migration on Supabase and run `phase1_smoke_test --no-mt5` (Supabase + Discord + buffer).
3. VPS + Wine + MT5 bridge bring-up, then the full smoke test and the UptimeRobot monitor. That is Phase 1 sign-off.
4. (Parallel, pure logic, no live orders) Phase 2 `engine/range`: range marker + fib levels with Doc 2 §3 tests.
5. Phase 2 `engine/risk`: lot sizing, min-lot / margin checks, and the full state-machine transition table with tests.

**Anything a replacement dev MUST read before touching code:** Doc 1 §8–9, Doc 2 in full (especially §4 through §8 and §10), Doc 3 §3.2/§3.3/§6, and this entry's escalations. Never add float to `engine/` (CI enforces this). Never add an update/delete path to audit tables.

### Addendum — 28 Sept 2026 — Session #1 (Phase 1 verification)
- ✅ Supabase schema v1 + 0002 (row_uuid idempotency) live. 23 immutability triggers verified in pg_trigger. A manual UPDATE in the SQL editor was blocked with `42501 ALSE: UPDATE ... forbidden`.
- ✅ Smoke test (`--no-mt5`) all PASS: insert proven by read-back, service-role PATCH/DELETE → 403 with the row unchanged, 2s timeout → buffer, Discord delivered.
- Bugs found and fixed during bring-up: (a) the post-hoc timeout could duplicate rows, fixed with row_uuid + ON CONFLICT DO NOTHING and a strict wall-clock deadline; (b) a wrong SUPABASE_URL (the dashboard URL) returned HTML 200s that counted as successful writes, fixed with URL validation and rejection of HTML responses; (c) the reset script failed when tables were missing.
- Phase 1 exit criteria remaining: MT5 via Wine on the VPS (blocked on escalation #1, host CPU architecture) and the external uptime monitor.
- Owner note: the engine `.env` must never use `NEXT_PUBLIC_*` names for secrets. The dashboard (Phase 6) gets its own env with the publishable/anon key only.


## Handover Entry — 28 September 2026 — Session #2

**Tasks completed this block (5):**
1. Escalation #1 resolved with owner sign-off: AWS EC2 x86 is now primary (Doc 3 v1.2 Change Log). Found and recorded that new AWS accounts get $200 in credits for 6 months, not 12 months free (Doc 6 risk register).
2. VPS runbook (`docs/runbooks/01_aws_vps_setup.md`), idempotent `ops/setup/bootstrap_ubuntu.sh` (swap, WineHQ, Windows Python 3.11 + MetaTrader5 + mt5linux under Wine), and a corrected `alse-mt5.service`.
3. Phase 2 core math: `engine/params.py` (Doc 2 defaults, overridable from `config_current`), `engine/range/levels.py`, `engine/orders/plan.py` (entry/SL/TP, 15/100pt caps, entry-only spread gate), `engine/risk/sizing.py` (closed-form lot formula, min-lot skip, margin/max-lot).
4. `engine/risk/state_machine.py`: the exhaustive Doc 2 §7 table, win definition (> $0.01), and circuit breaker (strictly below −4%). `engine/management/partial.py`: 1.5R trigger, remainder-floor partial close, BE+5.
5. `engine/signal/detector.py`: sweep, displacement (10pt + 60% body ratio, flat candle = fail), FIFO, resting-order invalidation, 21:00 expiry. 51 tests pass, covering every edge case listed in Doc 6's Phase 2 exit criteria.

**Current phase:** Phase 1 IN PROGRESS (VPS/MT5/uptime monitor, on the owner side). Phase 2 IN PROGRESS in parallel (owner-approved): pure logic done. Remaining: engine orchestrator loop, order execution through mt5_client with the audit write-ordering, state recovery on restart, hard kill, dry-run mode.

**Decisions made (implementer authority) — review welcome:**
- Price rounding to the tick is conservative (bull entry/SL rounded down, bear rounded up). SL points and TP are derived from the rounded prices, so TP is exactly 3× the real SL and lot sizing uses the real distance. The effect is under one tick.
- A 5m candle closing exactly at 21:00:00 is not acted on, because its order would expire in the same instant.
- One entry order per trading day. After a setup-level rejection (caps/spread/min-lot/margin) the day is over, following "do not retry within the same setup instance". This is the conservative reading.

**Open questions / escalations waiting on owner:**
- 🔴 **#4: Doc 2 §4 contradiction.** "Opposite side permanently suppressed the instant an order is placed" vs "Resting-order invalidation: cancel, then process the newly validated opposite setup." Implemented as `InvalidationPolicy`: the default is `CANCEL_ONLY` (cancel the stale order, place nothing), and the alternative is `CANCEL_AND_REVERSE`. The owner must choose; the choice then needs a Doc 2 Change Log entry.
- 🟠 #2 FOMC day(s), and 🟠 #3 holiday-adjacent hard kill: still open from Session #1.
- 🟠 **#5: SL-cap rejected setup.** When one side's setup is rejected (e.g. SL > 100pt), can the opposite side still trade later that window? Currently no (the day ends). Note: SL distance is 1.25 × range for both sides, so if one side fails the caps the other fails too. This only matters for spread and margin rejections.
- Owner: AWS account month-5 decision (the credits expire).

**Next 5 tasks queued:**
1. Owner: follow runbook 01 → run the smoke test on the VPS with MT5 → UptimeRobot (Phase 1 sign-off).
2. `data/mt5_client` order methods (order_send / modify / remove / close) with pending→confirmed audit rows.
3. Engine orchestrator: session loop, range marking at 20:30, detector wiring, 250ms poll, heartbeat integration.
4. Trade management loop + hard kill + circuit breaker flatten (never spread-gated) + state recovery from Supabase/MT5 on restart.
5. Dry-run mode against recorded/simulated data (Phase 2 exit, Phase 3 entry).

**Must read before touching code:** escalation #4 above. `engine/` is float-free, and CI enforces it.


## Handover Entry — 28 September 2026 — Session #3

**Tasks completed this block (5):**
1. Hosting re-decided after a proper 2026 review (Doc 3 v1.3): **GCP e2-micro Always Free, us-east1**. Rejected: AWS ($200/6-month credits, not sustainable), Oracle (ARM incompatible; AMD micro has heavy steal; idle reclamation; 2026 allowance cut). The AWS runbook was replaced by `docs/runbooks/01_gcp_vps_setup.md`. Bootstrap tuned for 1 GB RAM (3 GB swap, zram, vnstat); engine has `MemoryMax=300M`.
2. Doc 2 v5.1 hold-window rule. Found a factual error in Doc 2 §1: NFP/CPI are NOT confined to Fridays (BLS: NFP Tue 16 Dec 2025, Wed 11 Feb 2026, Thu 2 Jul 2026), and only the entry window had been checked, never the hold window through 16:16 next day. New `engine/session/events.py` (official FOMC/BLS dates) and rewritten calendar rules: exclude FOMC decision days, sessions whose hold window contains FOMC/CPI/NFP, and sessions whose Hard-Kill day is a market closure or early close. Fail-closed at the calendar horizon (currently 31 Dec 2026).
3. Escalations #4/#5 resolved (Doc 2 v5.1): cancel → broker confirms → reverse, max one reversal/day, one filled trade/day. A setup-level rejection ends only that side's setup instance.
4. Heartbeat: RAM/swap in the payload (F10); 30-day calendar-horizon alert (high, critical at 7 days).
5. Docs synchronized: Doc 2 v5.1, Doc 3 v1.3, Doc 6 v1.6 (risk register + ~11-month forward-test estimate), README. 57 tests pass.

**Current phase:** Phase 1 IN PROGRESS (owner: create the GCP VM per runbook 01). Phase 2 IN PROGRESS (pure logic done).

**Decisions made & rationale:** all recorded in Doc 2 v5.1 / Doc 3 v1.3 Change Logs (owner delegated these to the lead dev on 28 Sept 2026). Measured impact: 155/208 Mon–Thu sessions tradeable in 2026 (74.5%).

**Open items:**
- 2027 CPI/NFP dates: add when BLS publishes them (usually Q4). The engine alerts from 1 Dec 2026. Owner/dev action.
- Doc 6 item 1 (broker spec PDF) and item 13 (broker entity): owner paperwork.

**Next 5 tasks queued:**
1. Owner: GCP VM per runbook 01 → smoke test with MT5 → UptimeRobot. That is Phase 1 sign-off.
2. mt5_client order methods (send/modify/remove/close) with pending→confirmed audit rows.
3. Engine orchestrator (session loop, range marking, detector wiring, 250ms poll, 1s spread sampling).
4. Trade management + Hard-Kill + circuit-breaker flatten + restart state recovery.
5. Dry-run mode over recorded data (Phase 2 exit).
