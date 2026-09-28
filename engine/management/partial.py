"""1.5R partial close + BE+5 (Doc 2 §6). Proportional-with-remainder-floor, round DOWN."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from engine.decimal_math import D, floor_step
from engine.orders.plan import Side

BE_OFFSET_POINTS = D("5")
PARTIAL_FRACTION = D("0.75")
LOT_STEP = D("0.01")


@dataclass(frozen=True)
class PartialPlan:
    close_lots: Decimal        # 0 => skip the partial close
    remaining_lots: Decimal
    move_sl_to: Decimal | None  # None => position fully closed, SL move skipped


def partial_trigger_price(side: Side, entry: Decimal, sl_points: Decimal) -> Decimal:
    off = D(sl_points) * D("1.5")
    return entry + off if side is Side.BULLISH else entry - off


def partial_triggered(side: Side, m5_close: Decimal, entry: Decimal, sl_points: Decimal) -> bool:
    """A 5m candle CLOSES beyond 1.5R in the trade's favour."""
    t = partial_trigger_price(side, entry, sl_points)
    return D(m5_close) > t if side is Side.BULLISH else D(m5_close) < t


def be_plus_5(side: Side, entry: Decimal) -> Decimal:
    return entry + BE_OFFSET_POINTS if side is Side.BULLISH else entry - BE_OFFSET_POINTS


def plan_partial(side: Side, lots: Decimal, entry: Decimal) -> PartialPlan:
    L = D(lots)
    target = floor_step(L * PARTIAL_FRACTION, LOT_STEP)
    if (L - target) < LOT_STEP:
        return PartialPlan(close_lots=L, remaining_lots=D("0"), move_sl_to=None)
    if target == 0:
        return PartialPlan(close_lots=D("0"), remaining_lots=L, move_sl_to=be_plus_5(side, entry))
    return PartialPlan(close_lots=target, remaining_lots=L - target, move_sl_to=be_plus_5(side, entry))
