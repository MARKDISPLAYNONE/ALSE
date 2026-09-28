"""Supabase write/read wrapper (Doc 3 §3.2, §6).

Guarantees:
  * Every synchronous write has a HARD 2-second timeout.
  * On timeout / error / outage -> append to a local durable JSONL buffer and return
    immediately. A slow DB never delays a safety action.
  * Buffered rows are flushed in order once the write path is healthy again.
  * Writes go through PostgREST with JSON bodies (parameterized by construction — Doc 4 §1.4).
  * INSERT only. This client exposes no update/delete method on purpose.
  * Idempotent: every row gets a client-side row_uuid; inserts use ON CONFLICT (row_uuid)
    DO NOTHING. A write that lands at the DB *after* the 2s deadline (and was therefore also
    buffered) can never produce a duplicate audit row when the buffer is flushed.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx

log = logging.getLogger("alse.supabase")

WRITE_TIMEOUT_S = 2.0


def _json_default(o: Any) -> Any:
    if isinstance(o, Decimal):
        return str(o)          # Decimal -> string; Postgres numeric parses exactly
    if hasattr(o, "isoformat"):
        return o.isoformat()
    if isinstance(o, UUID):
        return str(o)
    raise TypeError(f"not JSON serialisable: {type(o)!r}")


@dataclass
class WriteResult:
    ok: bool
    buffered: bool
    error: str | None = None


class SupabaseWriter:
    def __init__(self, url: str, service_key: str, buffer_dir: Path, transport: httpx.BaseTransport | None = None):
        self._base = f"{url}/rest/v1"
        self._headers = {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal,resolution=ignore-duplicates",
        }
        self._http = httpx.Client(timeout=httpx.Timeout(WRITE_TIMEOUT_S), transport=transport)
        # Worker pool enforces a strict wall-clock deadline (httpx timeouts are per-phase, not total).
        self._pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="sb-write")
        buffer_dir.mkdir(parents=True, exist_ok=True)
        self._buffer = buffer_dir / "supabase_buffer.jsonl"
        self._lock = threading.Lock()
        self.on_fallback = None  # optional callback(table, error) for alerting/metrics (F7)

    # ---------- public ---------------------------------------------------
    def insert(self, table: str, row: dict[str, Any]) -> WriteResult:
        """Synchronous insert. If anything is already buffered, append behind it to preserve order."""
        row = {**row, "row_uuid": str(row.get("row_uuid") or uuid.uuid4())}
        if self.backlog() > 0:
            self._append_buffer(table, row)
            self.try_flush()
            return WriteResult(ok=self.backlog() == 0, buffered=True)
        err = self._post(table, row)
        if err is None:
            return WriteResult(ok=True, buffered=False)
        self._append_buffer(table, row)
        log.warning("supabase write fell back to local buffer: %s (%s)", table, err)
        if self.on_fallback:
            try:
                self.on_fallback(table, err)
            except Exception:  # never let an alert hook break the trading path
                log.exception("on_fallback hook failed")
        return WriteResult(ok=False, buffered=True, error=err)

    def select(self, table: str, params: dict[str, str]) -> list[dict[str, Any]]:
        r = self._http.get(f"{self._base}/{table}", headers=self._headers, params=params)
        r.raise_for_status()
        return r.json()

    def backlog(self) -> int:
        if not self._buffer.exists():
            return 0
        with self._buffer.open("r", encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())

    def try_flush(self) -> int:
        """Flush buffered rows in order. Stops at first failure. Returns rows flushed."""
        with self._lock:
            if not self._buffer.exists():
                return 0
            lines = [ln for ln in self._buffer.read_text(encoding="utf-8").splitlines() if ln.strip()]
            flushed = 0
            for ln in lines:
                item = json.loads(ln)
                if self._post(item["table"], item["row"]) is not None:
                    break
                flushed += 1
            remaining = lines[flushed:]
            tmp = self._buffer.with_suffix(".tmp")
            tmp.write_text("".join(x + "\n" for x in remaining), encoding="utf-8")
            os.replace(tmp, self._buffer)
            if flushed:
                log.info("flushed %d buffered rows, %d remaining", flushed, len(remaining))
            return flushed

    def close(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)
        self._http.close()

    # ---------- internals -----------------------------------------------
    def _post(self, table: str, row: dict[str, Any]) -> str | None:
        """Return None on success, else an error string. Hard 2s wall-clock deadline."""
        fut = self._pool.submit(self._do_post, table, row)
        try:
            return fut.result(timeout=WRITE_TIMEOUT_S)
        except FutureTimeout:
            # The request may still land later — harmless: row_uuid makes the flush idempotent.
            return f"timeout>{WRITE_TIMEOUT_S}s"

    def _do_post(self, table: str, row: dict[str, Any]) -> str | None:
        body = json.dumps(row, default=_json_default)
        try:
            r = self._http.post(f"{self._base}/{table}", headers=self._headers,
                                params={"on_conflict": "row_uuid"}, content=body)
        except httpx.TimeoutException:
            return f"timeout>{WRITE_TIMEOUT_S}s"
        except httpx.HTTPError as e:
            return f"http_error:{e.__class__.__name__}"
        if r.status_code >= 300:
            return f"status_{r.status_code}:{r.text[:200]}"
        return None

    def _append_buffer(self, table: str, row: dict[str, Any]) -> None:
        with self._lock, self._buffer.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"table": table, "row": row}, default=_json_default) + "\n")
            f.flush()
            os.fsync(f.fileno())
