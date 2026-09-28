"""Phase 1 exit-criteria smoke test (Doc 6, Phase 1). Run on the VPS after provisioning:
    python -m scripts.phase1_smoke_test
Checks: Supabase insert, immutability (UPDATE/DELETE must FAIL), buffer fallback, Discord, MT5 read.
"""
from __future__ import annotations

import sys
import tempfile
import uuid
from pathlib import Path

import httpx

from alerts.discord.notifier import DiscordNotifier
from data.settings import Settings
from data.supabase_client.client import SupabaseWriter
from engine.session.clock import stamp

results: list[tuple[str, bool, str]] = []


def check(name, fn):
    try:
        ok, note = fn()
    except Exception as e:  # noqa: BLE001
        ok, note = False, repr(e)
    results.append((name, ok, note))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} — {note}")


s = Settings.load(require_mt5="--no-mt5" not in sys.argv)
w = SupabaseWriter(s.supabase_url, s.supabase_service_key, s.buffer_dir)
hdr = {"apikey": s.supabase_service_key, "Authorization": f"Bearer {s.supabase_service_key}"}

flushed = w.try_flush()
if w.backlog():
    print(f"[WARN] {w.backlog()} rows still in local buffer ({s.buffer_dir}) — Supabase rejecting them; see errors above")
elif flushed:
    print(f"[INFO] flushed {flushed} rows left in local buffer from a previous run")

check("supabase insert", lambda: (lambda r: (r.ok and not r.buffered, str(r)))(
    w.insert("system_events", {**stamp().as_row(), "event": "phase1_smoke_test", "severity": "info"})))


def immut():
    """Insert a probe row, try to PATCH + DELETE it, then READ IT BACK. Status codes alone can lie
    (a filter matching 0 rows also returns 2xx), so the proof is: row still exists, unchanged."""
    probe = str(uuid.uuid4())
    r = w.insert("system_events", {**stamp().as_row(), "event": "immutability_probe", "severity": "info",
                                   "detail": "original", "row_uuid": probe})
    if not r.ok:
        return False, f"probe insert failed: {r}"
    base = f"{s.supabase_url}/rest/v1/system_events?row_uuid=eq.{probe}"
    rep = {**hdr, "Content-Type": "application/json", "Prefer": "return=representation"}
    u = httpx.patch(base, headers=rep, json={"detail": "TAMPERED"})
    d = httpx.delete(base, headers=rep)
    g = httpx.get(base + "&select=detail", headers=hdr)
    try:
        after = g.json()
    except ValueError:
        return False, f"read-back not JSON: GET={g.status_code} body={g.text[:200]!r} PATCH={u.status_code} DELETE={d.status_code}"
    intact = after == [{"detail": "original"}]
    note = (f"PATCH={u.status_code} DELETE={d.status_code} row_after={after}"
            + ("" if intact else f" | PATCH body={u.text[:160]} | DELETE body={d.text[:160]}"))
    return intact and u.status_code >= 400 and d.status_code >= 400, note


check("immutability enforced (service role blocked)", immut)


def fallback():
    tmp = Path(tempfile.mkdtemp())
    bad = SupabaseWriter("http://10.255.255.1", "x", tmp)  # unroutable -> timeout
    r = bad.insert("system_events", {"event": "x"})
    return (r.buffered and bad.backlog() == 1, f"buffered={r.buffered} backlog={bad.backlog()}")


check("2s timeout -> local buffer fallback", fallback)

n = DiscordNotifier(s.discord_webhook, s.discord_critical_webhook, w, s.env)
check("discord test alert", lambda: (n.send("Phase 1 smoke test", "Test alert — ignore."), "sent"))

if "--no-mt5" not in sys.argv:
    from data.mt5_client.client import MT5Client

    def mt5_read():
        c = MT5Client(s.mt5_mode, s.mt5_login, s.mt5_password, s.mt5_server, s.mt5_symbol,
                      s.mt5_bridge_host, s.mt5_bridge_port)
        c.connect()
        t, bars, a = c.tick(), c.bars_m1(5), c.account()
        return (len(bars) == 5, f"bid={t.bid} ask={t.ask} spread={t.spread_points} equity={a.equity}")

    check("mt5 connect + tick/candle/account read", mt5_read)

print("\nExternal uptime monitor: verify manually in UptimeRobot that GET http://<VPS_IP>:8080/health is UP.")
sys.exit(0 if all(ok for _, ok, _ in results) else 1)
