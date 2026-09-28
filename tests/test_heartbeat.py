from datetime import datetime

from engine.session.clock import NY
from ops.heartbeat import HeartbeatService


class W:
    def __init__(self): self.rows = []
    def insert(self, t, r): self.rows.append((t, r))
    def backlog(self): return 0
    def try_flush(self): return 0

def test_active_window_every_5_min():
    w = W(); s = HeartbeatService(w)
    s._next_daily = datetime(2099, 1, 1, tzinfo=NY)
    for minute in range(0, 16):
        s.tick(datetime(2026, 9, 28, 20, minute, tzinfo=NY))
    kinds = [r["kind"] for t, r in w.rows if t == "heartbeats"]
    assert kinds == ["active_window"] * 4   # 20:00, :05, :10, :15

def test_daily_ping_fires_once():
    w = W(); s = HeartbeatService(w)
    s._next_daily = datetime(2026, 9, 26, 9, 0, tzinfo=NY)   # Saturday — still pings
    s.tick(datetime(2026, 9, 26, 9, 0, 1, tzinfo=NY))
    s.tick(datetime(2026, 9, 26, 9, 3, tzinfo=NY))
    assert [r["kind"] for _, r in w.rows] == ["daily_coarse"]
