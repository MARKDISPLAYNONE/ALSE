"""Decimal-only arithmetic helpers (Doc 1 §8, Doc 2 §0 — float is banned in this pipeline)."""
from __future__ import annotations

from decimal import ROUND_DOWN, Decimal, getcontext

getcontext().prec = 28

LOT_STEP = Decimal("0.01")
PRICE_STEP = Decimal("0.01")


def D(value: str | int | Decimal) -> Decimal:
    """Construct a Decimal. Rejects float to stop float contamination at the boundary."""
    if isinstance(value, float):
        raise TypeError("float is banned in ALSE money/price/lot math — pass str, int or Decimal")
    if isinstance(value, bool):
        raise TypeError("bool is not a numeric input")
    return value if isinstance(value, Decimal) else Decimal(value)


def from_broker(value: object) -> Decimal:
    """MT5 returns Python floats. Convert via repr-string (shortest round-trip), never Decimal(float)."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, str)):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(repr(value))
    raise TypeError(f"unsupported broker numeric type: {type(value)!r}")


def floor_step(value: Decimal, step: Decimal = LOT_STEP) -> Decimal:
    """Round DOWN to step (Doc 2 §6/§8 — never nearest, never up)."""
    value, step = D(value), D(step)
    if step <= 0:
        raise ValueError("step must be positive")
    return (value / step).to_integral_value(rounding=ROUND_DOWN) * step


def quantize_price(value: Decimal) -> Decimal:
    return D(value).quantize(PRICE_STEP)
