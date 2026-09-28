"""Entry / SL / TP planning + hard SL caps + spread gate (Doc 2 §4–§5).

Price precision (implementer decision, flagged in handover): levels can carry more decimals
than the symbol's tick. Entry and SL are rounded to the tick in the CONSERVATIVE direction
(bull: entry down, SL down; bear: entry up, SL up), which can only widen the SL by < 1 tick.
SL points and TP are then derived from the ROUNDED prices, so TP = exactly 3x the real SL
distance and lot sizing uses the real distance.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from enum import StrEnum

from engine.decimal_math import D
from engine.params import DEFAULT, StrategyParams
from engine.range.levels import Range


class Side(StrEnum):
    BULLISH = "bullish"
    BEARISH = "bearish"

    @property
    def opposite(self) -> Side:
        return Side.BEARISH if self is Side.BULLISH else Side.BULLISH


@dataclass(frozen=True)
class OrderPlan:
    side: Side
    order_type: str        # ORDER_TYPE_BUY_LIMIT / ORDER_TYPE_SELL_LIMIT
    entry: Decimal
    sl: Decimal
    tp: Decimal
    sl_points: Decimal
    tp_points: Decimal


@dataclass(frozen=True)
class Rejection:
    reason: str            # matches signal_events.event names
    detail: str


def _q(x: Decimal, tick: Decimal, rounding: str) -> Decimal:
    return (x / tick).to_integral_value(rounding=rounding) * tick


DEFAULT_TICK = D("0.01")


def plan_order(side: Side, rng: Range, tick: Decimal = DEFAULT_TICK,
               p: StrategyParams = DEFAULT) -> OrderPlan | Rejection:
    if side is Side.BULLISH:
        entry = _q(rng.bullish_entry, tick, ROUND_FLOOR)
        sl = _q(rng.bullish_sl, tick, ROUND_FLOOR)
        sl_pts = entry - sl
        tp = entry + sl_pts * 3
        otype = "ORDER_TYPE_BUY_LIMIT"
    else:
        entry = _q(rng.bearish_entry, tick, ROUND_CEILING)
        sl = _q(rng.bearish_sl, tick, ROUND_CEILING)
        sl_pts = sl - entry
        tp = entry - sl_pts * 3
        otype = "ORDER_TYPE_SELL_LIMIT"
    if sl_pts < p.sl_min_points:
        return Rejection("rejected_sl_too_shallow", f"SL {sl_pts}pt < {p.sl_min_points}pt")
    if sl_pts > p.sl_max_points:
        return Rejection("rejected_sl_cap", f"SL {sl_pts}pt > {p.sl_max_points}pt")
    return OrderPlan(side, otype, entry, sl, tp, sl_pts, sl_pts * 3)


def spread_gate(spread_points: Decimal, p: StrategyParams = DEFAULT) -> Rejection | None:
    """NEW ENTRY orders only (Doc 2 §4 v5.0 scope). Never call for hard-kill / circuit-breaker closes."""
    if D(spread_points) > p.spread_gate_max_points:
        return Rejection("rejected_spread", f"spread {spread_points} > {p.spread_gate_max_points}")
    return None
