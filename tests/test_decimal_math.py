from decimal import Decimal

import pytest

from engine.decimal_math import D, floor_step, from_broker


def test_float_rejected():
    with pytest.raises(TypeError):
        D(0.1)

def test_floor_never_rounds_up():
    assert floor_step(D("0.0199")) == D("0.01")
    assert floor_step(D("1.999")) == D("1.99")
    assert floor_step(D("0.009")) == D("0")

def test_partial_close_example():  # Doc 2 §6 floor(L*0.75)
    assert floor_step(D("0.03") * D("0.75")) == D("0.02")

def test_from_broker_float_is_exact_repr():
    assert from_broker(28571.75) == Decimal("28571.75")
    assert from_broker(0.1) == Decimal("0.1")

def test_fib_worked_example():  # Doc 2 §3 — programmatic verification
    lo, hi = D("28534.1"), D("28684.7")
    size = hi - lo
    def lvl(r):
        return lo + size * D(r)
    assert (lvl("-1.0"), lvl("0.25"), lvl("0.75"), lvl("2.0")) == (
        D("28383.5"), D("28571.75"), D("28647.05"), D("28835.3"))
