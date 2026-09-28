"""Discord alerting (Doc 3 §6): Supabase alerts_log is the record; Discord is convenience only."""
from __future__ import annotations

import logging
from typing import Protocol

import httpx

from engine.session.clock import stamp

log = logging.getLogger("alse.discord")

COLORS = {"info": 0x3498DB, "warning": 0xF1C40F, "high": 0xE67E22, "critical": 0xE74C3C}


class Writer(Protocol):
    def insert(self, table: str, row: dict): ...


class DiscordNotifier:
    def __init__(self, webhook: str, critical_webhook: str, writer: Writer | None, env: str = "demo",
                 transport: httpx.BaseTransport | None = None):
        self._webhook = webhook
        self._critical = critical_webhook or webhook
        self._writer = writer
        self._env = env
        self._http = httpx.Client(timeout=httpx.Timeout(2.0), transport=transport)

    def send(self, title: str, body: str = "", severity: str = "info") -> bool:
        url = self._critical if severity in ("high", "critical") else self._webhook
        payload = {"embeds": [{
            "title": f"[{self._env.upper()}] {title}"[:256],
            "description": body[:4000],
            "color": COLORS.get(severity, COLORS["info"]),
            "footer": {"text": f"ALSE • {severity}"},
        }]}
        delivered, err = False, None
        try:
            r = self._http.post(url, json=payload)
            delivered = r.status_code < 300
            if not delivered:
                err = f"status_{r.status_code}"
        except httpx.HTTPError as e:
            err = e.__class__.__name__
        if not delivered:
            log.warning("discord delivery failed: %s", err)
        if self._writer is not None:
            self._writer.insert("alerts_log", {**stamp().as_row(), "channel": "discord", "severity": severity,
                                               "title": title, "body": body, "delivered": delivered,
                                               "delivery_error": err})
        return delivered
