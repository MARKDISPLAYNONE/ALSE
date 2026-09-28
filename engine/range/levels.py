"""Range marking + Fib levels (Doc 2 §3). Decimal only; levels computed programmatically."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from engine.decimal_math import D

EXECUTION_RATIOS = ("-1.0", "0.0", "0.25", "0.75", "1.0", "2.0")
VIZ_ONLY_RATIOS = ("-2.0", "1.5", "3.0")  # dashboard only — NEVER used in execution logic


@dataclass(frozen=True)
class Range:
    high: Decimal
    low: Decimal

    @property
    def size(self) -> Decimal:
        return self.high - self.low

    def level(self, ratio: str) -> Decimal:
        return self.low + self.size * D(ratio)

    @property
    def bullish_sl(self) -> Decimal:
        return self.level("-1.0")

    @property
    def bullish_entry(self) -> Decimal:
        return self.level("0.25")

    @property
    def bearish_entry(self) -> Decimal:
        return self.level("0.75")

    @property
    def bearish_sl(self) -> Decimal:
        return self.level("2.0")

    def levels_json(self) -> dict[str, str]:
        out = {r: str(self.level(r)) for r in EXECUTION_RATIOS}
        out.update({f"viz:{r}": str(self.level(r)) for r in VIZ_ONLY_RATIOS})
        return out


class EmptyRangeError(ValueError):
    pass


def mark_range(highs_lows: Iterable[tuple[Decimal, Decimal]]) -> Range:
    """highs_lows: (high, low) of every 1m candle 20:00:00–20:29:59 NY."""
    hs, ls = [], []
    for h, lo in highs_lows:
        hs.append(D(h))
        ls.append(D(lo))
    if not hs:
        raise EmptyRangeError("no 1m candles in range window")
    return Range(high=max(hs), low=min(ls))
