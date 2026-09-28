"""Risk state machine (Doc 2 §7 exhaustive transition table) + circuit breaker + win definition."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from engine.decimal_math import D
from engine.params import DEFAULT, StrategyParams


class State(StrEnum):
    A = "A"   # Aggressive
    B = "B"   # Throttle


class Event(StrEnum):
    WIN = "win"
    LOSS = "loss"
    NO_TRADE_DAY = "no_trade_day"


@dataclass(frozen=True)
class RiskState:
    state: State = State.A
    win_streak: int = 0   # only meaningful in State A

    def risk_pct(self, p: StrategyParams = DEFAULT) -> Decimal:
        return p.risk_pct_state_a if self.state is State.A else p.risk_pct_state_b


def classify_trade(net_pnl_usd: Decimal, p: StrategyParams = DEFAULT) -> Event:
    """Win iff net realized PnL (all partials + runner, net of commission) > $0.01. Otherwise Loss."""
    return Event.WIN if D(net_pnl_usd) > p.win_threshold_usd else Event.LOSS


def transition(s: RiskState, e: Event, p: StrategyParams = DEFAULT) -> RiskState:
    if e is Event.NO_TRADE_DAY:
        return s                                          # frozen in both states
    if s.state is State.A:
        if e is Event.LOSS:
            return RiskState(State.A, 0)
        streak = s.win_streak + 1
        if streak >= p.win_streak_throttle_trigger:
            return RiskState(State.B, 0)                  # 5th consecutive win → B immediately
        return RiskState(State.A, streak)
    # State B
    if e is Event.WIN:
        return RiskState(State.A, 0)                      # the restoring win does not count toward A's streak
    return RiskState(State.B, 0)                          # unlimited loss absorption


def circuit_breaker_tripped(realized_today: Decimal, floating: Decimal, sod_equity: Decimal,
                            p: StrategyParams = DEFAULT) -> bool:
    """Trips when Realized_PnL_Today + Floating_PnL drops BELOW −4% of start-of-day equity."""
    return D(realized_today) + D(floating) < -(p.circuit_breaker_pct * D(sod_equity))
