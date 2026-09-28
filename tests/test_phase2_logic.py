from datetime import datetime, timedelta
from decimal import Decimal

from engine.decimal_math import D
from engine.management.partial import be_plus_5, partial_triggered, plan_partial
from engine.orders.plan import OrderPlan, Rejection, Side, plan_order, spread_gate
from engine.params import StrategyParams
from engine.range.levels import Range, mark_range
from engine.risk.sizing import margin_check, size_position
from engine.risk.state_machine import Event, RiskState, State, circuit_breaker_tripped, classify_trade, transition
from engine.session.clock import NY
from engine.signal.detector import CancelResting, Candle, InvalidationPolicy, PlaceEntry, SignalDetector, body_ratio


# ---------------- range / levels ----------------
def test_mark_range_and_levels():
    r = mark_range([(D("28600"), D("28534.1")), (D("28684.7"), D("28550"))])
    assert (r.high, r.low, r.size) == (D("28684.7"), D("28534.1"), D("150.6"))
    assert D(r.levels_json()["2.0"]) == D("28835.3")

# ---------------- order plan / caps ----------------
R40 = Range(D("20040"), D("20000"))   # size 40 → SL 50pt

def test_bull_plan():
    p = plan_order(Side.BULLISH, R40)
    assert isinstance(p, OrderPlan)
    assert (p.entry, p.sl, p.sl_points, p.tp) == (D("20010"), D("19960"), D("50"), D("20160"))
    assert p.order_type == "ORDER_TYPE_BUY_LIMIT"

def test_bear_plan():
    p = plan_order(Side.BEARISH, R40)
    assert (p.entry, p.sl, p.sl_points, p.tp) == (D("20030"), D("20080"), D("50"), D("19880"))

def test_sl_caps():
    assert plan_order(Side.BULLISH, Range(D("20011.9"), D("20000"))).reason == "rejected_sl_too_shallow"  # 14.875
    assert isinstance(plan_order(Side.BULLISH, Range(D("20012"), D("20000"))), OrderPlan)              # 15.00
    assert isinstance(plan_order(Side.BULLISH, Range(D("20080"), D("20000"))), OrderPlan)              # 100
    assert plan_order(Side.BULLISH, Range(D("20080.01"), D("20000"))).reason == "rejected_sl_cap"

def test_tick_rounding_conservative_and_tp_exact_3x():
    p = plan_order(Side.BULLISH, Range(D("20033.33"), D("20000")))
    assert p.tp - p.entry == 3 * (p.entry - p.sl)
    assert p.entry == D("20008.33")      # 20008.3325 floored

def test_spread_gate():
    assert spread_gate(D("5")) is None
    assert spread_gate(D("5.01")).reason == "rejected_spread"

# ---------------- sizing ----------------
def test_lot_formula():
    s = size_position(D("10000"), D("0.02"), D("50"))   # 200 / (1000+10) = 0.198 → 0.19
    assert s.lots == D("0.19")

def test_min_lot_skip_not_force():
    r = size_position(D("100"), D("0.005"), D("100"))
    assert isinstance(r, Rejection) and r.reason == "rejected_min_lot"

def test_margin_and_max_lot():
    assert margin_check(D("25.01"), D("1"), D("100")).reason == "rejected_margin_max_lot"
    assert margin_check(D("1"), D("101"), D("100")).reason == "rejected_margin_max_lot"
    assert margin_check(D("25.00"), D("100"), D("100")) is None

# ---------------- risk state machine (full table) ----------------
def test_state_table():
    s = RiskState()
    for i in range(1, 5):
        s = transition(s, Event.WIN)
        assert s == RiskState(State.A, i)
    s = transition(s, Event.NO_TRADE_DAY); assert s == RiskState(State.A, 4)       # frozen
    s = transition(s, Event.WIN); assert s == RiskState(State.B, 0)                # 5th → B
    for _ in range(7):
        s = transition(s, Event.LOSS); assert s.state is State.B                    # unlimited absorption
    s = transition(s, Event.NO_TRADE_DAY); assert s.state is State.B
    s = transition(s, Event.WIN); assert s == RiskState(State.A, 0)                # restore, streak 0
    s = transition(transition(s, Event.WIN), Event.LOSS); assert s == RiskState(State.A, 0)  # loss resets

def test_risk_pct_by_state():
    assert RiskState(State.A).risk_pct() == D("0.02")
    assert RiskState(State.B).risk_pct() == D("0.005")

def test_win_definition():
    assert classify_trade(D("0.02")) is Event.WIN
    assert classify_trade(D("0.01")) is Event.LOSS
    assert classify_trade(D("-5")) is Event.LOSS

def test_circuit_breaker():
    assert not circuit_breaker_tripped(D("-300"), D("-100"), D("10000"))   # exactly -4% → not below
    assert circuit_breaker_tripped(D("-300"), D("-100.01"), D("10000"))

def test_params_from_config():
    p = StrategyParams.from_config({"sl_max_points": "90", "win_streak_throttle_trigger": "4"})
    assert p.sl_max_points == D("90") and p.win_streak_throttle_trigger == 4

# ---------------- partial close ----------------
def test_partial_close_cases():
    assert plan_partial(Side.BULLISH, D("0.01"), D("100")).close_lots == 0              # zero target → skip
    assert plan_partial(Side.BULLISH, D("0.01"), D("100")).move_sl_to == D("105")       # BE+5 on full
    p = plan_partial(Side.BULLISH, D("0.19"), D("100"))
    assert (p.close_lots, p.remaining_lots) == (D("0.14"), D("0.05"))
    p = plan_partial(Side.BEARISH, D("0.02"), D("100"))
    assert (p.close_lots, p.remaining_lots, p.move_sl_to) == (D("0.01"), D("0.01"), D("95"))

def test_partial_trigger_and_be():
    assert partial_triggered(Side.BULLISH, D("175.01"), D("100"), D("50"))
    assert not partial_triggered(Side.BULLISH, D("175"), D("100"), D("50"))
    assert partial_triggered(Side.BEARISH, D("24.99"), D("100"), D("50"))
    assert be_plus_5(Side.BEARISH, D("100")) == D("95")

# ---------------- signal detector ----------------
T0 = datetime(2026, 9, 28, 20, 35, tzinfo=NY)
END = datetime(2026, 9, 28, 21, 0, tzinfo=NY)
R = Range(D("20040"), D("20000"))

def c(o, h, lo, cl, minutes=0):
    return Candle(D(o), D(h), D(lo), D(cl), T0 + timedelta(minutes=minutes))

def test_body_ratio_flat_candle_fails():
    assert body_ratio(c("1", "1", "1", "1")) is None
    d = SignalDetector(R, END)
    d.on_price(D("20001"), D("19990"), T0)
    assert d.on_m5_close(Candle(D("20012"), D("20012"), D("20012"), D("20012"), T0)) == []

def test_bullish_valid():
    d = SignalDetector(R, END)
    acts = d.on_m5_close(c("19995", "20013", "19990", "20012"))   # sweep inside same candle, pen 12, br 17/23
    assert acts == [PlaceEntry(Side.BULLISH)]

def test_penetration_below_10_rejected():
    d = SignalDetector(R, END)
    assert d.on_m5_close(c("19992", "20010", "19990", "20009.99")) == []
    assert d.events[-1].event == "displacement_rejected"

def test_no_sweep_no_setup():
    d = SignalDetector(R, END)
    assert d.on_m5_close(c("20001", "20020", "20000", "20019")) == []   # low == range low → not a sweep

def test_fifo_high_swept_first_then_low_valid():
    d = SignalDetector(R, END)
    d.on_m5_close(c("20035", "20045", "20034", "20036"))               # high swept, no valid displacement
    assert d.on_m5_close(c("19995", "20013", "19990", "20012", 5)) == [PlaceEntry(Side.BULLISH)]

def test_invalidation_cancel_only_default():
    d = SignalDetector(R, END)
    d.on_m5_close(c("19995", "20013", "19990", "20012"))
    acts = d.on_m5_close(c("20045", "20046", "20028", "20029", 5))       # bear valid: pen 11, br 16/18
    assert acts == [CancelResting(Side.BULLISH, "opposite setup validated")]
    assert d.on_m5_close(c("19995", "20013", "19990", "20012", 10)) == []  # done for the day

def test_invalidation_cancel_and_reverse_policy():
    d = SignalDetector(R, END, policy=InvalidationPolicy.CANCEL_AND_REVERSE)
    d.on_m5_close(c("19995", "20013", "19990", "20012"))
    acts = d.on_m5_close(c("20045", "20046", "20028", "20029", 5))
    assert acts == [CancelResting(Side.BULLISH, "opposite setup validated"), PlaceEntry(Side.BEARISH)]

def test_after_fill_nothing_more():
    d = SignalDetector(R, END)
    d.on_m5_close(c("19995", "20013", "19990", "20012"))
    d.on_filled()
    assert d.on_m5_close(c("20045", "20046", "20028", "20029", 5)) == []

def test_candle_closing_at_2100_ignored_and_expiry():
    d = SignalDetector(R, END)
    late = Candle(D("19995"), D("20013"), D("19990"), D("20012"), END)
    assert d.on_m5_close(late) == []
    d.on_window_end(END)
    assert d.events[-1].event == "setup_aborted"

def test_window_end_cancels_resting():
    d = SignalDetector(R, END)
    d.on_m5_close(c("19995", "20013", "19990", "20012"))
    assert d.on_window_end(END) == [CancelResting(Side.BULLISH, "21:00 NY expiry")]

def test_decimal_types():
    assert isinstance(plan_order(Side.BULLISH, R40).tp, Decimal)
