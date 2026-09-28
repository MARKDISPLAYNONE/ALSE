"""Sweep + displacement detection, FIFO dual-setup, resting-order invalidation (Doc 2 §4).

Pure state machine — no I/O. The engine feeds it prices and closed 5m candles during 20:30–21:00 NY
and executes the Actions it returns (placing/cancelling orders goes through engine/orders + mt5_client).

ESCALATION #4 (Doc 2 §4 internal contradiction, awaiting owner):
  * "The instant an entry order is placed for the winning side, the opposite side is permanently
     suppressed for the remainder of that day's window."
  * "Resting Order Invalidation Rule: ... opposite-direction sweep+displacement subsequently validates
     before the resting order fills → cancel the resting order before processing the newly validated
     opposite setup."
  These cannot both hold. InvalidationPolicy makes the choice explicit:
    CANCEL_ONLY (default, most conservative): cancel the stale resting order; place NOTHING new.
      Satisfies "stale order never fills" AND "opposite side never gets an order".
    CANCEL_AND_REVERSE: cancel, then place the opposite setup (literal reading of the invalidation rule).
  Changing the default requires owner sign-off + Doc 2 Change Log entry.

Other implementer notes (flagged in handover):
  * One entry order per trading day. After a fill, nothing else is placed that day.
  * A 5m candle is only acted on if it closes strictly before 21:00:00 NY (an order placed at 21:00:00
    would be expired in the same instant by the Doc 2 §5 expiry rule).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from engine.decimal_math import D
from engine.orders.plan import Side
from engine.params import DEFAULT, StrategyParams
from engine.range.levels import Range


class InvalidationPolicy(StrEnum):
    CANCEL_ONLY = "cancel_only"
    CANCEL_AND_REVERSE = "cancel_and_reverse"


@dataclass(frozen=True)
class Candle:
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    close_time: datetime    # tz-aware


@dataclass(frozen=True)
class SignalEvent:
    event: str               # matches signal_events.event check constraint
    side: Side | None
    ts: datetime
    penetration_pts: Decimal | None = None
    body_ratio: Decimal | None = None
    reason: str | None = None


@dataclass(frozen=True)
class PlaceEntry:
    side: Side


@dataclass(frozen=True)
class CancelResting:
    side: Side
    reason: str


Action = PlaceEntry | CancelResting


def body_ratio(c: Candle) -> Decimal | None:
    """abs(C−O)/(H−L). Flat candle (H==L) → None = automatic FAIL (Doc 2 §4)."""
    rng = c.high - c.low
    if rng == 0:
        return None
    return abs(c.close - c.open) / rng


@dataclass
class SignalDetector:
    rng: Range
    exec_end: datetime
    params: StrategyParams = DEFAULT
    policy: InvalidationPolicy = InvalidationPolicy.CANCEL_ONLY
    swept: dict[Side, bool] = field(default_factory=lambda: {Side.BULLISH: False, Side.BEARISH: False})
    resting: Side | None = None
    filled: bool = False
    done_for_day: bool = False
    orders_placed: int = 0
    events: list[SignalEvent] = field(default_factory=list)

    # ---- price feed (ticks or 1m extremes) ---------------------------------
    def on_price(self, high: Decimal, low: Decimal, ts: datetime) -> None:
        if D(low) < self.rng.low and not self.swept[Side.BULLISH]:
            self.swept[Side.BULLISH] = True
            self.events.append(SignalEvent("sweep", Side.BULLISH, ts))
        if D(high) > self.rng.high and not self.swept[Side.BEARISH]:
            self.swept[Side.BEARISH] = True
            self.events.append(SignalEvent("sweep", Side.BEARISH, ts))

    # ---- 5m candle close ---------------------------------------------------
    def on_m5_close(self, c: Candle) -> list[Action]:
        self.on_price(c.high, c.low, c.close_time)       # candle's own extremes count as sweeps
        if self.done_for_day or self.filled or c.close_time >= self.exec_end:
            return []
        validated = [s for s in (Side.BULLISH, Side.BEARISH) if self._validates(s, c)]
        # FIFO by timestamp: candles are processed in time order; within ONE candle only one side can
        # close back inside with ≥10pt penetration unless range < 10pt — prefer the side that isn't resting.
        for side in validated:
            if self.resting is None and self.orders_placed == 0:
                self.orders_placed += 1
                self.resting = side
                self.events.append(SignalEvent("setup_suppressed", side.opposite, c.close_time,
                                               reason=f"{side} setup won FIFO"))
                return [PlaceEntry(side)]
            if self.resting is not None and side is self.resting.opposite:
                stale = self.resting
                self.resting = None
                self.events.append(SignalEvent("resting_order_invalidated", stale, c.close_time,
                                               reason=f"opposite {side} validated before fill"))
                actions: list[Action] = [CancelResting(stale, "opposite setup validated")]
                if self.policy is InvalidationPolicy.CANCEL_AND_REVERSE:
                    self.orders_placed += 1
                    self.resting = side
                    actions.append(PlaceEntry(side))
                else:
                    self.done_for_day = True
                return actions
        return []

    def _validates(self, side: Side, c: Candle) -> bool:
        if not self.swept[side]:
            return False
        if side is Side.BULLISH:
            if c.close <= self.rng.low:
                return False
            pen = c.close - self.rng.low
        else:
            if c.close >= self.rng.high:
                return False
            pen = self.rng.high - c.close
        br = body_ratio(c)
        ok = pen >= self.params.displacement_min_penetration and br is not None and br >= self.params.displacement_body_ratio
        self.events.append(SignalEvent("displacement_valid" if ok else "displacement_rejected", side, c.close_time,
                                       penetration_pts=pen, body_ratio=br,
                                       reason=None if ok else ("flat_candle" if br is None else "threshold")))
        return ok

    # ---- order lifecycle feedback -----------------------------------------
    def on_filled(self) -> None:
        self.filled = True
        self.done_for_day = True
        self.resting = None

    def on_entry_rejected(self) -> None:
        """Order-level rejection (spread/caps/min-lot/margin): no retry within the same setup instance."""
        self.resting = None
        self.done_for_day = True

    def on_window_end(self, ts: datetime) -> list[Action]:
        actions: list[Action] = []
        if self.resting is not None and not self.filled:
            actions.append(CancelResting(self.resting, "21:00 NY expiry"))
            self.resting = None
        if self.orders_placed == 0:
            self.events.append(SignalEvent("setup_aborted", None, ts, reason="no valid setup by 21:00 NY"))
        self.done_for_day = True
        return actions
