import json
from decimal import Decimal

import httpx

from data.supabase_client.client import SupabaseWriter


def make(tmp_path, handler):
    return SupabaseWriter("https://x.supabase.co", "k", tmp_path, transport=httpx.MockTransport(handler))

def test_ok_write(tmp_path):
    seen = []
    w = make(tmp_path, lambda r: (seen.append(json.loads(r.content)), httpx.Response(201))[1])
    assert w.insert("t", {"lots": Decimal("0.03")}).ok
    assert seen[0]["lots"] == "0.03" and "row_uuid" in seen[0]   # Decimal as exact string

def test_timeout_buffers_then_flushes_in_order(tmp_path):
    state = {"down": True}; got = []
    def h(r):
        if state["down"]:
            raise httpx.ReadTimeout("slow")
        got.append(json.loads(r.content)["n"]); return httpx.Response(201)
    w = make(tmp_path, h)
    fired = []; w.on_fallback = lambda t, e: fired.append(e)
    r = w.insert("t", {"n": 1}); assert r.buffered and not r.ok
    w.insert("t", {"n": 2})
    assert w.backlog() == 2 and fired
    state["down"] = False
    w.insert("t", {"n": 3})     # queues behind backlog, then flushes all
    assert got == [1, 2, 3] and w.backlog() == 0

def test_http_error_buffers(tmp_path):
    w = make(tmp_path, lambda r: httpx.Response(503))
    assert w.insert("t", {"a": 1}).buffered

def test_row_uuid_added_and_stable_across_flush(tmp_path):
    state = {"down": True}; bodies = []
    def h(r):
        if state["down"]:
            raise httpx.ReadTimeout("slow")
        assert r.url.params["on_conflict"] == "row_uuid"
        assert "resolution=ignore-duplicates" in r.headers["prefer"]
        bodies.append(json.loads(r.content)); return httpx.Response(201)
    w = make(tmp_path, h)
    w.insert("t", {"n": 1})
    state["down"] = False
    w.try_flush()
    assert len(bodies) == 1 and len(bodies[0]["row_uuid"]) == 36

def test_strict_deadline_even_if_server_hangs(tmp_path, monkeypatch):
    import time as _t

    import data.supabase_client.client as c
    monkeypatch.setattr(c, "WRITE_TIMEOUT_S", 0.3)
    def h(r):
        _t.sleep(1.0); return httpx.Response(201)
    w = make(tmp_path, h)
    t0 = _t.monotonic(); res = w.insert("t", {"n": 1})
    assert res.buffered and _t.monotonic() - t0 < 0.8
