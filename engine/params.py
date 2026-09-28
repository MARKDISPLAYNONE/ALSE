"""Strategy parameters (Doc 2). Defaults = Doc 2 v5.0 values; at runtime they are loaded from the
Supabase `config_current` view (Doc 3 §3.3) so provisional values can be recalibrated without deploys."""
from __future__ import annotations

from dataclasses import dataclass, fields
from decimal import Decimal

from engine.decimal_math import D


@dataclass(frozen=True)
class StrategyParams:
    # Provisional (Doc 2 §9)
    sl_min_points: Decimal = D("15")
    sl_max_points: Decimal = D("100")
    displacement_min_penetration: Decimal = D("10")
    displacement_body_ratio: Decimal = D("0.60")
    circuit_breaker_pct: Decimal = D("0.04")
    risk_pct_state_a: Decimal = D("0.02")
    risk_pct_state_b: Decimal = D("0.005")
    win_streak_throttle_trigger: int = 5
    # Hard rules (Doc 2 §1, §4–§8)
    spread_gate_max_points: Decimal = D("5")
    max_lot: Decimal = D("25.00")
    min_lot: Decimal = D("0.01")
    point_value_usd: Decimal = D("20")
    commission_per_lot_usd: Decimal = D("10")
    win_threshold_usd: Decimal = D("0.01")

    @classmethod
    def from_config(cls, rows: dict[str, str]) -> StrategyParams:
        """Build from {param_key: value} (config_current). Unknown keys ignored; missing keys keep defaults."""
        kwargs = {}
        for f in fields(cls):
            if f.name in rows:
                kwargs[f.name] = int(rows[f.name]) if f.type in (int, "int") else D(rows[f.name])
        return cls(**kwargs)


DEFAULT = StrategyParams()
