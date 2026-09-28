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
    assert seen == [{"lots": "0.03"}]   # Decimal serialised as exact string

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
