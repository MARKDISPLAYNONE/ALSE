"""Heartbeat daemon (Doc 2 §2.5) + health endpoint for the external uptime monitor (Doc 3 §6).

Cadences:
  * daily_coarse  — 09:00:00 NY every calendar day.
  * active_window — every 5 min from 20:00 NY through hard kill (or while positions open).
GET /health returns 200 only if the process loop is alive (last tick < 90s ago), else 503.
Exposes NO trading data and accepts NO commands.
"""
from __future__ import annotations

import json
import logging
import signal
import socket
import threading
import time
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from engine.session.clock import (
    ACTIVE_HEARTBEAT_EVERY,
    NY,
    in_active_heartbeat_window,
    next_daily_ping,
    now_utc,
    stamp,
)

log = logging.getLogger("alse.heartbeat")


class HeartbeatService:
    def __init__(self, writer, mt5=None, notifier=None, positions_open=lambda: False):
        self.writer, self.mt5, self.notifier = writer, mt5, notifier
        self.positions_open = positions_open
        self.last_loop = time.monotonic()
        self._next_daily = next_daily_ping()
        self._next_active: datetime | None = None
        self._mt5_was_connected: bool | None = None
        self._stop = threading.Event()

    def beat(self, kind: str, at: datetime | None = None) -> None:
        connected = self.mt5.is_connected() if self.mt5 else None
        self.writer.insert("heartbeats", {**stamp(at).as_row(), "kind": kind, "mt5_connected": connected,
                                          "buffer_backlog": self.writer.backlog(), "host": socket.gethostname()})

    def tick(self, at: datetime | None = None) -> None:
        now = at or now_utc()
        self.last_loop = time.monotonic()
        if now >= self._next_daily:
            self.beat("daily_coarse", now)
            self._next_daily = next_daily_ping(now + timedelta(seconds=1))
        if in_active_heartbeat_window(now, self.positions_open()):
            if self._next_active is None or now >= self._next_active:
                self.beat("active_window", now)
                self._next_active = now + ACTIVE_HEARTBEAT_EVERY
        else:
            self._next_active = None
        self._check_mt5()
        if self.writer.backlog():
            self.writer.try_flush()

    def _check_mt5(self) -> None:
        if not self.mt5:
            return
        ok = self.mt5.is_connected()
        if self._mt5_was_connected is not None and ok != self._mt5_was_connected:
            event, sev = ("mt5_reconnect", "warning") if ok else ("mt5_disconnect", "high")
            self.writer.insert("system_events", {**stamp().as_row(), "event": event, "severity": sev})
            if self.notifier:
                self.notifier.send(f"MT5 {'reconnected' if ok else 'DISCONNECTED'}", "", sev)
        self._mt5_was_connected = ok

    def run(self, poll_s: float = 1.0) -> None:
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception:
                log.exception("heartbeat tick failed")
            self._stop.wait(poll_s)

    def stop(self, *_):
        self._stop.set()


def serve_health(svc: HeartbeatService, port: int) -> ThreadingHTTPServer:
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != "/health":
                self.send_response(404)
                self.end_headers()
                return
            alive = time.monotonic() - svc.last_loop < 90
            body = json.dumps({"status": "ok" if alive else "stale",
                               "ts_ny": now_utc().astimezone(NY).isoformat(timespec="seconds")}).encode()
            self.send_response(200 if alive else 503)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("0.0.0.0", port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main() -> None:
    from alerts.discord.notifier import DiscordNotifier
    from data.mt5_client.client import MT5Client
    from data.settings import Settings
    from data.supabase_client.client import SupabaseWriter

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    s = Settings.load()
    writer = SupabaseWriter(s.supabase_url, s.supabase_service_key, s.buffer_dir)
    notifier = DiscordNotifier(s.discord_webhook, s.discord_critical_webhook, writer, s.env)
    mt5 = MT5Client(s.mt5_mode, s.mt5_login, s.mt5_password, s.mt5_server, s.mt5_symbol,
                    s.mt5_bridge_host, s.mt5_bridge_port)
    try:
        mt5.connect()
    except Exception as e:
        notifier.send("MT5 connect failed at startup", str(e), "high")
    writer.insert("system_events", {**stamp().as_row(), "event": "process_start", "severity": "warning",
                                    "detail": "engine/heartbeat started (systemd restart or boot)"})
    notifier.send("ALSE process started", "If unexpected, a crash/restart occurred — check logs.", "warning")
    svc = HeartbeatService(writer, mt5, notifier)
    serve_health(svc, s.health_port)
    signal.signal(signal.SIGTERM, svc.stop)
    signal.signal(signal.SIGINT, svc.stop)
    svc.run()


if __name__ == "__main__":
    main()
