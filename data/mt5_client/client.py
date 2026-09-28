"""Thin MT5 wrapper — the ONLY module allowed to touch the MetaTrader5 API (Doc 3 §7).

Deployment reality on Linux+Wine (Doc 3 §5): the official MetaTrader5 package is
Windows-only, so it runs inside a Windows Python under Wine. Two supported modes:
  * native — this process IS the Wine/Windows Python and imports MetaTrader5 directly.
  * bridge — this process is native Linux Python and talks to the Wine-side Python via
             the mt5linux RPyC bridge (same API surface).
All numeric values leaving this module are Decimal (Doc 2 §0).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from engine.decimal_math import from_broker

log = logging.getLogger("alse.mt5")


@dataclass(frozen=True)
class Tick:
    time_msc: int
    bid: Decimal
    ask: Decimal

    @property
    def spread_points(self) -> Decimal:
        return self.ask - self.bid


@dataclass(frozen=True)
class Bar:
    time: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal


@dataclass(frozen=True)
class Account:
    login: int
    equity: Decimal
    balance: Decimal
    margin_free: Decimal
    currency: str


class MT5Unavailable(RuntimeError):
    pass


class MT5Client:
    def __init__(self, mode: str, login: str, password: str, server: str, symbol: str,
                 bridge_host: str = "127.0.0.1", bridge_port: int = 18812, api: Any = None):
        self.symbol = symbol
        self._creds = (int(login) if login else 0, password, server)
        if api is not None:
            self._mt5 = api
        elif mode == "native":
            import MetaTrader5 as mt5  # type: ignore
            self._mt5 = mt5
        elif mode == "bridge":
            from mt5linux import MetaTrader5  # type: ignore
            self._mt5 = MetaTrader5(host=bridge_host, port=bridge_port)
        else:
            raise ValueError(f"unknown MT5_MODE {mode!r}")

    # ---------- connection ---------------------------------------------
    def connect(self) -> None:
        login, password, server = self._creds
        if not self._mt5.initialize(login=login, password=password, server=server):
            raise MT5Unavailable(f"initialize failed: {self._mt5.last_error()}")
        if not self._mt5.symbol_select(self.symbol, True):
            raise MT5Unavailable(f"symbol_select({self.symbol}) failed: {self._mt5.last_error()}")
        log.info("MT5 connected, symbol %s selected", self.symbol)

    def is_connected(self) -> bool:
        """Doc 3 §6: terminal_info() null/failure or not connected => disconnected."""
        try:
            info = self._mt5.terminal_info()
        except Exception:
            return False
        return bool(info) and bool(getattr(info, "connected", False))

    def shutdown(self) -> None:
        try:
            self._mt5.shutdown()
        except Exception:
            log.exception("mt5 shutdown failed")

    # ---------- reads (Phase 1 scope) -----------------------------------
    def tick(self) -> Tick:
        t = self._mt5.symbol_info_tick(self.symbol)
        if t is None:
            raise MT5Unavailable(f"symbol_info_tick None: {self._mt5.last_error()}")
        return Tick(time_msc=int(t.time_msc), bid=from_broker(t.bid), ask=from_broker(t.ask))

    def bars_m1(self, count: int) -> list[Bar]:
        rates = self._mt5.copy_rates_from_pos(self.symbol, self._mt5.TIMEFRAME_M1, 0, count)
        if rates is None:
            raise MT5Unavailable(f"copy_rates_from_pos None: {self._mt5.last_error()}")
        return [Bar(int(r["time"]), from_broker(float(r["open"])), from_broker(float(r["high"])),
                    from_broker(float(r["low"])), from_broker(float(r["close"]))) for r in rates]

    def account(self) -> Account:
        a = self._mt5.account_info()
        if a is None:
            raise MT5Unavailable(f"account_info None: {self._mt5.last_error()}")
        return Account(int(a.login), from_broker(a.equity), from_broker(a.balance),
                       from_broker(a.margin_free), str(a.currency))

    # Order submission/modify/cancel arrive in Phase 2 (engine/orders), routed through here.
