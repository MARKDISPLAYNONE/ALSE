# ALSE — NAS100 Autonomous Liquidity Sweep Engine

Specs live in [`docs/`](docs/) (read `00_…` first, then `05_…`, then `session-handover.md`).
**Current phase: 1 — Infrastructure & Data Pipeline (code ready; waiting on owner provisioning).**

## Layout (Doc 3 §7)
```
engine/session/     session clock (NY/zoneinfo, DST-safe) + Mon–Thu/holiday/FOMC calendar
engine/decimal_math Decimal-only helpers (float banned)
data/supabase_client  INSERT-only writer, 2s timeout → local JSONL buffer → ordered flush
data/mt5_client       sole MT5 API boundary (native or mt5linux bridge under Wine)
alerts/discord        webhook alerts, always recorded in alerts_log
ops/heartbeat.py      09:00 NY daily + 5-min active-window heartbeat, /health endpoint
ops/systemd/          Restart=always units for engine + Wine MT5 bridge
supabase/migrations/  schema v1 (immutable audit tables, RLS, dual timestamps, config rows)
scripts/phase1_smoke_test.py  Phase 1 exit-criteria check
```

## Local dev (VS Code)
```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install          # secret scanning before every commit (Doc 4 §1.1)
pytest -q && ruff check .
```

## Owner provisioning checklist (unblocks Phase 1 — Doc 6 §2)
1. **Supabase** (free tier): create project → SQL Editor → paste & run `supabase/migrations/0001_phase1_core_schema.sql`.
   Copy the project URL + `service_role` key into `.env` (engine only). Create one Auth user for yourself (dashboard login).
2. **Discord**: create two channels (`#alse-trades`, `#alse-critical`) → Integrations → Webhooks → paste URLs into `.env`.
3. **MT5 demo** at FX Pesa: note login / password / server name → `.env`.
4. **VPS** — Google Cloud e2-micro Always Free, us-east1 (Doc 3 v1.3) — follow docs/runbooks/01_gcp_vps_setup.md:
   - SSH key-only; security list: SSH from your IP, TCP 8080 for the uptime monitor only.
   - `sudo apt install wine64 xvfb python3.11-venv`; install Windows Python 3.11 + `pip install MetaTrader5 mt5linux` inside Wine; install the FX Pesa MT5 terminal under Wine.
   - Clone repo to `/opt/alse`, create `.venv`, `pip install -e ".[mt5-bridge]"`, copy `.env`.
   - `sudo cp ops/systemd/*.service /etc/systemd/system/ && sudo systemctl enable --now alse-mt5 alse-engine`
   - ⚠️ Oracle ARM (Ampere) + Wine x86 needs box64/emulation — if it's unstable, use an Oracle AMD Always-Free micro or AWS t3.micro instead.
5. **UptimeRobot** (free): HTTP monitor on `http://<VPS_IP>:8080/health`, 5-min interval, alert to email + critical webhook.
6. Run `python -m scripts.phase1_smoke_test` → all PASS ⇒ Phase 1 exit criteria met.

> This system trades leveraged CFD instruments and carries substantial risk of loss, potentially exceeding deposited capital
> depending on broker margin terms. Past or backtested performance does not guarantee future results. This system is provided
> for the operator's own use in managing their own trading account and does not constitute financial advice.
