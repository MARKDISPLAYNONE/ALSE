"""Trading calendar (Doc 2 §1).

Hard rules:
  * Trading days: Mon–Thu only (no Fri — structural; no Sun — risk decision).
  * US bank holidays and FOMC dates: static exclusion list, checked before range-marking.

OPEN QUESTION (logged in session-handover.md, awaiting owner):
  Doc 2 §1 says "FOMC dates" without specifying which day of a 2-day meeting.
  Conservative default applied here: BOTH meeting days are excluded (excluding more
  days can only reduce trading, never add risk). Switch via FOMC_EXCLUDE_BOTH_DAYS
  only after owner sign-off + Doc 2 Change Log entry.
"""
from __future__ import annotations

from datetime import date, timedelta

TRADING_WEEKDAYS = frozenset({0, 1, 2, 3})  # Mon=0 … Thu=3

FOMC_EXCLUDE_BOTH_DAYS = True

# (day1, day2) — source: Federal Reserve published calendar (2026 & 2027).
FOMC_MEETINGS: tuple[tuple[date, date], ...] = (
    (date(2026, 1, 27), date(2026, 1, 28)),
    (date(2026, 3, 17), date(2026, 3, 18)),
    (date(2026, 4, 28), date(2026, 4, 29)),
    (date(2026, 6, 16), date(2026, 6, 17)),
    (date(2026, 7, 28), date(2026, 7, 29)),
    (date(2026, 9, 15), date(2026, 9, 16)),
    (date(2026, 10, 27), date(2026, 10, 28)),
    (date(2026, 12, 8), date(2026, 12, 9)),
    (date(2027, 1, 26), date(2027, 1, 27)),
    (date(2027, 3, 16), date(2027, 3, 17)),
    (date(2027, 4, 27), date(2027, 4, 28)),
    (date(2027, 6, 8), date(2027, 6, 9)),
    (date(2027, 7, 27), date(2027, 7, 28)),
    (date(2027, 9, 14), date(2027, 9, 15)),
    (date(2027, 10, 26), date(2027, 10, 27)),
    (date(2027, 12, 7), date(2027, 12, 8)),
)
FOMC_LAST_KNOWN_YEAR = 2027


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


def fomc_excluded_days() -> frozenset[date]:
    out: set[date] = set()
    for d1, d2 in FOMC_MEETINGS:
        out.add(d2)
        if FOMC_EXCLUDE_BOTH_DAYS:
            out.add(d1)
    return frozenset(out)


class CalendarExpiredError(RuntimeError):
    """Raised when asked about a year beyond the maintained FOMC list — fail closed."""


def exclusion_reason(d: date) -> str | None:
    """Return why NY trading day `d` is excluded, or None if it is tradeable."""
    if d.year > FOMC_LAST_KNOWN_YEAR:
        raise CalendarExpiredError(f"FOMC list only maintained through {FOMC_LAST_KNOWN_YEAR}; update calendar.py")
    if d.weekday() not in TRADING_WEEKDAYS:
        return "non_trading_weekday"
    if d in us_bank_holidays(d.year):
        return "us_bank_holiday"
    if d in fomc_excluded_days():
        return "fomc"
    return None


def is_trading_day(d: date) -> bool:
    return exclusion_reason(d) is None


def next_trading_day(d: date) -> date:
    n = d + timedelta(days=1)
    while not is_trading_day(n):
        n += timedelta(days=1)
    return n
