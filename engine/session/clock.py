"""Session clock (Doc 2 §2, §2.5). All session logic in America/New_York via zoneinfo; DB stores UTC + NY."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

from engine.session.calendar import hard_kill_day, is_trading_day, next_trading_day

NY = ZoneInfo("America/New_York")
UTC = UTC

RANGE_START = time(20, 0, 0)
RANGE_END_INCL = time(20, 29, 59)
EXEC_START = time(20, 30, 0)
EXEC_END = time(21, 0, 0)          # also pending-order expiry
HARD_KILL = time(16, 16, 0)        # next NY trading day
DAILY_PING = time(9, 0, 0)
ACTIVE_HEARTBEAT_EVERY = timedelta(minutes=5)
DAILY_PING_EVERY = timedelta(days=1)


class Phase(StrEnum):
    IDLE = "idle"
    RANGE = "range_marking"
    EXECUTION = "execution_window"
    MANAGEMENT = "position_management"   # after 21:00 until hard-kill


@dataclass(frozen=True)
class Stamp:
    ts_utc: datetime
    ts_ny: datetime  # tz-aware NY

    def as_row(self) -> dict[str, str]:
        """Both timestamps stored explicitly (Doc 3 §3.2). ts_ny stored as NY wall-clock."""
        return {"ts_utc": self.ts_utc.isoformat(), "ts_ny": self.ts_ny.replace(tzinfo=None).isoformat()}


def now_utc() -> datetime:
    return datetime.now(UTC)


def stamp(at: datetime | None = None) -> Stamp:
    u = (at or now_utc()).astimezone(UTC)
    return Stamp(ts_utc=u, ts_ny=u.astimezone(NY))


def ny_dt(d: date, t: time) -> datetime:
    return datetime.combine(d, t, tzinfo=NY)


@dataclass(frozen=True)
class SessionWindows:
    trading_day: date          # the NY date on which 20:00 range-marking happens
    range_start: datetime
    range_end_incl: datetime
    exec_start: datetime
    exec_end: datetime
    hard_kill: datetime        # 16:16 NY on the next NY trading day


def windows_for(trading_day: date) -> SessionWindows:
    if not is_trading_day(trading_day):
        raise ValueError(f"{trading_day} is not a trading day")
    nxt = hard_kill_day(trading_day)
    return SessionWindows(
        trading_day=trading_day,
        range_start=ny_dt(trading_day, RANGE_START),
        range_end_incl=ny_dt(trading_day, RANGE_END_INCL),
        exec_start=ny_dt(trading_day, EXEC_START),
        exec_end=ny_dt(trading_day, EXEC_END),
        hard_kill=ny_dt(nxt, HARD_KILL),
    )


def current_session(at: datetime | None = None) -> tuple[Phase, SessionWindows | None]:
    """Which phase are we in at `at`? Looks at today's and the previous trading day's session."""
    ny = (at or now_utc()).astimezone(NY)
    candidates: list[date] = []
    for back in range(0, 5):
        d = ny.date() - timedelta(days=back)
        if is_trading_day(d):
            candidates.append(d)
        if len(candidates) == 2:
            break
    for d in candidates:
        w = windows_for(d)
        if w.range_start <= ny <= w.range_end_incl.replace(microsecond=999999):
            return Phase.RANGE, w
        if w.exec_start <= ny < w.exec_end:
            return Phase.EXECUTION, w
        if w.exec_end <= ny < w.hard_kill:
            return Phase.MANAGEMENT, w
    return Phase.IDLE, None


def in_active_heartbeat_window(at: datetime | None = None, positions_open: bool = False) -> bool:
    """Doc 2 §2.5: 20:00 NY → hard kill, or later while positions/orders remain."""
    phase, _ = current_session(at)
    return phase is not Phase.IDLE or positions_open


def next_daily_ping(at: datetime | None = None) -> datetime:
    ny = (at or now_utc()).astimezone(NY)
    target = ny_dt(ny.date(), DAILY_PING)
    if ny >= target:
        target = ny_dt(ny.date() + timedelta(days=1), DAILY_PING)
    return target


__all__ = [
    "NY", "UTC", "Phase", "SessionWindows", "Stamp", "current_session", "in_active_heartbeat_window",
    "next_daily_ping", "next_trading_day", "stamp", "windows_for",
]
