"""Lot sizing + pre-trade validation (Doc 2 §8). Closed-form, commission-inclusive, round DOWN."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from engine.decimal_math import D, floor_step
from engine.orders.plan import Rejection
from engine.params import DEFAULT, StrategyParams


@dataclass(frozen=True)
class Sizing:
    risk_budget: Decimal
    lots: Decimal


def size_position(sod_equity: Decimal, risk_pct: Decimal, sl_points: Decimal,
                  p: StrategyParams = DEFAULT) -> Sizing | Rejection:
    budget = D(sod_equity) * D(risk_pct)
    raw = budget / (D(sl_points) * p.point_value_usd + p.commission_per_lot_usd)
    lots = floor_step(raw, p.min_lot)
    if lots < p.min_lot:
        return Rejection("rejected_min_lot", f"lots {raw} < {p.min_lot} (Insufficient Equity for Min Lot)")
    return Sizing(budget, lots)


def margin_check(lots: Decimal, margin_required: Decimal, margin_free: Decimal,
                 p: StrategyParams = DEFAULT) -> Rejection | None:
    """margin_required from mt5.order_calc_margin(); margin_free from mt5.account_info()."""
    if D(lots) > p.max_lot or D(margin_required) > D(margin_free):
        return Rejection("rejected_margin_max_lot",
                         f"lots={lots} max={p.max_lot} margin_req={margin_required} free={margin_free}")
    return None
