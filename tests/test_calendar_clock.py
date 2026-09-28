from datetime import UTC, date, datetime

import pytest

from engine.session import calendar as cal
from engine.session.clock import NY, Phase, current_session, next_daily_ping, windows_for


def test_weekdays():
    assert cal.is_trading_day(date(2026, 9, 28))       # Mon
    assert cal.is_trading_day(date(2026, 10, 1))       # Thu
    assert not cal.is_trading_day(date(2026, 10, 2))   # Fri
    assert not cal.is_trading_day(date(2026, 10, 4))   # Sun

def test_holidays_and_fomc():
    assert cal.exclusion_reason(date(2026, 11, 26)) == "us_bank_holiday"   # Thanksgiving
    assert cal.exclusion_reason(date(2026, 10, 12)) == "us_bank_holiday"   # Columbus
    assert cal.exclusion_reason(date(2026, 10, 28)) == "fomc"
    assert cal.exclusion_reason(date(2026, 10, 27)) == "fomc"             # conservative both-days default

def test_calendar_fails_closed_beyond_list():
    with pytest.raises(cal.CalendarExpiredError):
        cal.is_trading_day(date(2028, 1, 4))

def test_thursday_hard_kill_is_friday():
    w = windows_for(date(2026, 10, 1))
    assert w.hard_kill == datetime(2026, 10, 2, 16, 16, tzinfo=NY)

def test_dst_transition_week():
    # US DST ends Sun 1 Nov 2026. Mon 2 Nov 20:00 NY = 01:00 UTC Tue (EST, UTC-5)
    w = windows_for(date(2026, 11, 2))
    assert w.range_start.astimezone(UTC).hour == 1
    w2 = windows_for(date(2026, 10, 29))  # EDT, UTC-4
    assert w2.range_start.astimezone(UTC).hour == 0

def test_phases():
    def mk(h, m, s=0, d=28):
        return datetime(2026, 9, d, h, m, s, tzinfo=NY)
    assert current_session(mk(19, 59, 59))[0] is Phase.IDLE
    assert current_session(mk(20, 0))[0] is Phase.RANGE
    assert current_session(mk(20, 29, 59))[0] is Phase.RANGE
    assert current_session(mk(20, 30))[0] is Phase.EXECUTION
    assert current_session(mk(21, 0))[0] is Phase.MANAGEMENT
    assert current_session(mk(16, 15, 59, d=29))[0] is Phase.MANAGEMENT
    assert current_session(mk(16, 16, 0, d=29))[0] is Phase.IDLE

def test_daily_ping():
    assert next_daily_ping(datetime(2026, 9, 28, 8, 0, tzinfo=NY)) == datetime(2026, 9, 28, 9, 0, tzinfo=NY)
    assert next_daily_ping(datetime(2026, 9, 28, 9, 0, tzinfo=NY)) == datetime(2026, 9, 29, 9, 0, tzinfo=NY)
