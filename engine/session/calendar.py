"""Trading calendar (Doc 2 §1, v5.1).

A session on NY date D = range 20:00 D → hold until Hard-Kill 16:16 on the next weekday (K).
Session D is EXCLUDED if any of:
  1. D is not Mon–Thu                                             (hard rule, Doc 2 §1)
  2. D is a US bank holiday                                       (hard rule, Doc 2 §1)
  3. D is an FOMC decision day — post-statement repricing regime  (v5.1)
  4. Hold-window event: K has an FOMC statement (14:00), CPI or NFP (08:30) — all of which fall
     between entry and the 16:16 Hard-Kill                        (v5.1 — closes Doc 2 §1 gap)
  5. Hold-window closure: K is a market holiday or early-close day, so the 16:16 Hard-Kill could
     fall after the market has closed                             (v5.1)
Beyond the maintained event horizon the calendar fails closed.
"""
from __future__ import annotations

from datetime import date, timedelta

from engine.session.events import EVENT_HORIZON, FOMC_DECISION_DAYS, events_on

TRADING_WEEKDAYS = frozenset({0, 1, 2, 3})  # Mon=0 … Thu=3


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    d = date(year, month, 1)
    d += timedelta(days=(weekday - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def _last_weekday(year: int, month: int, weekday: int) -> date:
    d = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year, 12, 31)
    return d - timedelta(days=(d.weekday() - weekday) % 7)


def _observed(d: date) -> date:
    if d.weekday() == 5:
        return d - timedelta(days=1)
    if d.weekday() == 6:
        return d + timedelta(days=1)
    return d


def _easter(year: int) -> date:
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    month = (h + l_ - 7 * m + 114) // 31
    day = ((h + l_ - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def us_bank_holidays(year: int) -> frozenset[date]:
    """Federal Reserve / US federal bank holidays with observed-date rules."""
    return frozenset({
        _observed(date(year, 1, 1)),
        _nth_weekday(year, 1, 0, 3),       # MLK Day
        _nth_weekday(year, 2, 0, 3),       # Presidents Day
        _last_weekday(year, 5, 0),         # Memorial Day
        _observed(date(year, 6, 19)),      # Juneteenth
        _observed(date(year, 7, 4)),       # Independence Day
        _nth_weekday(year, 9, 0, 1),       # Labor Day
        _nth_weekday(year, 10, 0, 2),      # Columbus Day
        _observed(date(year, 11, 11)),     # Veterans Day
        _nth_weekday(year, 11, 3, 4),      # Thanksgiving
        _observed(date(year, 12, 25)),     # Christmas
    })


def market_closed_or_early(d: date) -> bool:
    """US index-futures closure/early-close days (CME equity schedule), superset for safety."""
    y = d.year
    thanksgiving = _nth_weekday(y, 11, 3, 4)
    special = {
        _easter(y) - timedelta(days=2),        # Good Friday
        thanksgiving + timedelta(days=1),      # day after Thanksgiving (early close)
        date(y, 12, 24),                       # Christmas Eve (early close)
        date(y, 7, 3),                         # Independence Day eve (early close / observed)
    }
    return d in us_bank_holidays(y) or d in special


def hard_kill_day(d: date) -> date:
    k = d + timedelta(days=1)
    while k.weekday() >= 5:
        k += timedelta(days=1)
    return k


class CalendarExpiredError(RuntimeError):
    """Raised past the maintained event horizon — fail closed until events.py is updated."""


def exclusion_reason(d: date) -> str | None:
    """Why NY session date `d` is excluded, or None if tradeable."""
    if d.weekday() not in TRADING_WEEKDAYS:
        return "non_trading_weekday"
    k = hard_kill_day(d)
    if k > EVENT_HORIZON:
        raise CalendarExpiredError(f"event calendar only maintained through {EVENT_HORIZON}; update engine/session/events.py")
    if d in us_bank_holidays(d.year):
        return "us_bank_holiday"
    if d in FOMC_DECISION_DAYS:
        return "fomc_decision_day"
    if ev := events_on(k):
        return "hold_window_event:" + "+".join(ev)
    if market_closed_or_early(k):
        return "hold_window_market_closure"
    return None


def is_trading_day(d: date) -> bool:
    return exclusion_reason(d) is None


def days_until_horizon(today: date) -> int:
    return (EVENT_HORIZON - today).days


def next_trading_day(d: date) -> date:
    n = d + timedelta(days=1)
    while not is_trading_day(n):
        n += timedelta(days=1)
    return n
