"""High-impact scheduled US events (Doc 2 §1 v5.1 hold-window rule).

Sources (official): FOMC — federalreserve.gov calendar; CPI & Employment Situation (NFP) —
bls.gov/schedule/news_release/{cpi,empsit}.htm (retrieved 28 Sept 2026).
BLS publishes ~12 months ahead; 2027 CPI/NFP dates must be added when BLS publishes them.
Beyond EVENT_HORIZON the calendar FAILS CLOSED (no trading) and the engine alerts 30 days ahead.
"""
from __future__ import annotations

from datetime import date, time

FOMC_STATEMENT_TIME = time(14, 0)
BLS_RELEASE_TIME = time(8, 30)

# FOMC statement (decision) days — day 2 of each meeting.
FOMC_DECISION_DAYS = frozenset({
    date(2026, 1, 28), date(2026, 3, 18), date(2026, 4, 29), date(2026, 6, 17),
    date(2026, 7, 29), date(2026, 9, 16), date(2026, 10, 28), date(2026, 12, 9),
    date(2027, 1, 27), date(2027, 3, 17), date(2027, 4, 28), date(2027, 6, 9),
    date(2027, 7, 28), date(2027, 9, 15), date(2027, 10, 27), date(2027, 12, 8),
})

CPI_DAYS = frozenset({
    date(2025, 12, 18), date(2026, 1, 13), date(2026, 2, 13), date(2026, 3, 11), date(2026, 4, 10),
    date(2026, 5, 12), date(2026, 6, 10), date(2026, 7, 14), date(2026, 8, 12), date(2026, 9, 11),
    date(2026, 10, 14), date(2026, 11, 10), date(2026, 12, 10),
})

NFP_DAYS = frozenset({
    date(2025, 12, 16), date(2026, 1, 9), date(2026, 2, 11), date(2026, 3, 6), date(2026, 4, 3),
    date(2026, 5, 8), date(2026, 6, 5), date(2026, 7, 2), date(2026, 8, 7), date(2026, 9, 4),
    date(2026, 10, 2), date(2026, 11, 6), date(2026, 12, 4),
})

# Last date for which ALL event lists are complete (BLS 2026 schedule ends with Dec releases).
EVENT_HORIZON = date(2026, 12, 31)


def events_on(d: date) -> list[str]:
    out = []
    if d in FOMC_DECISION_DAYS:
        out.append("fomc_statement")
    if d in CPI_DAYS:
        out.append("cpi")
    if d in NFP_DAYS:
        out.append("nfp")
    return out
