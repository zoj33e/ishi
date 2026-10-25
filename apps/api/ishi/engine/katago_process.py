"""Long-lived KataGo analysis process manager.

One process per backend. Queries are JSON lines on stdin; responses come back on stdout
(possibly out of order) and are dispatched by `id` to awaiting futures.

Uses plain `subprocess` + reader threads instead of asyncio subprocesses so it works on any
Windows event loop (uvicorn's reloader uses a selector loop, which can't spawn subprocesses).
"""

from __future__ import annotations

import asyncio
import contextlib
import itertools
import json
import logging
import subprocess
import threading
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from ishi.engine.models import AnalysisQuery, AnalysisResponse

log = logging.getLogger(__name__)

RESTART_DELAYS_S = (0.5, 1, 2, 5, 10)


class EngineError(Exception):
    """Base class for engine failures."""


class EngineUnavailableError(EngineError):
    """The engine is not running (yet, or anymore). Retryable."""


class EngineRestartedError(EngineUnavailableError):
    """The engine died while this query was in flight. Retryable."""


class KataGoQueryError(EngineError):
    """KataGo rejected the query (`{"error": ..., "field": ..., "id": ...}`)."""


@dataclass
class _Pending:
    future: asyncio.Future[list[dict[str, Any]]]
    expected: int
    results: list[dict[str, Any]] = field(default_factory=list)


class KataGoProcess:
    def __init__(self, command: Sequence[str], *, auto_restart: bool = True) -> None:
        self._command = list(command)
        self._auto_restart = auto_restart
        self._proc: subprocess.Popen[str] | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._pending: dict[str, _Pending] = {}
        self._write_lock = threading.Lock()
        self._ids = itertools.count(1)
        self._ready = False
        self._stopping = False
        self._restart_attempt = 0
        self._restart_task: asyncio.Task[None] | None = None
        self.version: str | None = None

    # -- lifecycle -------------------------------------------------------

    @property
    def ready(self) -> bool:
        return self._ready and self._proc is not None and self._proc.poll() is None

    async def start(self, ready_timeout: float = 120.0) -> None:
        """Spawn KataGo and wait until it answers `query_version`.

        The first OpenCL launch tunes kernels and can take a while, hence the long timeout.
        """
        self._loop = asyncio.get_running_loop()
        self._stopping = False
        log.info("starting katago: %s", " ".join(self._command))
        self._proc = subprocess.Popen(
            self._command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        proc = self._proc
        threading.Thread(target=self._read_stdout, args=(proc,), daemon=True).start()
        threading.Thread(target=self._read_stderr, args=(proc,), daemon=True).start()

        reply = await self._send(
            {"action": "query_version"}, expected=1, timeout=ready_timeout, require_ready=False
        )
        self.version = reply[0].get("version")
        self._ready = True
        self._restart_attempt = 0
        log.info("katago ready, version %s", self.version)

    async def stop(self) -> None:
        self._stopping = True
        self._ready = False
        if self._restart_task is not None:
            self._restart_task.cancel()
        proc, self._proc = self._proc, None
        if proc is None:
            return
        with contextlib.suppress(OSError):
            if proc.stdin:
                proc.stdin.close()
        try:
            await asyncio.to_thread(proc.wait, 5)
        except subprocess.TimeoutExpired:
            proc.kill()
        self._fail_all(EngineUnavailableError("engine stopped"))

    # -- queries ---------------------------------------------------------

    async def analyze(self, query: AnalysisQuery, timeout: float = 30.0) -> list[AnalysisResponse]:
        """Run an analysis query. Returns one response per analyzed turn, sorted by turn."""
        payload = query.model_dump(exclude_none=True)
        raw = await self._send(payload, expected=query.expected_responses(), timeout=timeout)
        return sorted((AnalysisResponse.model_validate(r) for r in raw), key=lambda r: r.turnNumber)

    async def ping(self, timeout: float = 2.0) -> bool:
        if not self.ready:
            return False
        try:
            await self._send({"action": "query_version"}, expected=1, timeout=timeout)
        except EngineError:
            return False
        return True

    async def _send(
        self,
        payload: dict[str, Any],
        *,
        expected: int,
        timeout: float,
        require_ready: bool = True,
    ) -> list[dict[str, Any]]:
        proc = self._proc
        if proc is None or proc.poll() is not None or (require_ready and not self._ready):
            raise EngineUnavailableError("engine not running")
        assert self._loop is not None
        qid = str(payload.get("id") or f"q{next(self._ids)}")
        if qid in self._pending:
            raise ValueError(f"duplicate query id {qid}")
        payload = {**payload, "id": qid}
        pending = _Pending(self._loop.create_future(), expected)
        self._pending[qid] = pending
        line = json.dumps(payload, separators=(",", ":"))
        log.debug("katago query %s", qid)
        try:
            await asyncio.to_thread(self._write_line, proc, line)
            return await asyncio.wait_for(pending.future, timeout)
        except TimeoutError:
            self._terminate_query(qid)
            raise
        except OSError as e:
            raise EngineUnavailableError(f"write failed: {e}") from e
        finally:
            self._pending.pop(qid, None)

    def _write_line(self, proc: subprocess.Popen[str], line: str) -> None:
        assert proc.stdin is not None
        with self._write_lock:
            proc.stdin.write(line + "\n")
            proc.stdin.flush()

    def _terminate_query(self, qid: str) -> None:
        proc = self._proc
        if proc is None or proc.poll() is not None:
            return
        line = json.dumps({"id": f"terminate-{qid}", "action": "terminate", "terminateId": qid})
        with contextlib.suppress(OSError):
            self._write_line(proc, line)

    # -- reader threads (never touch futures directly; hop to the loop) ---

    def _read_stdout(self, proc: subprocess.Popen[str]) -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                log.warning("katago non-json stdout: %s", line[:200])
                continue
            self._call_in_loop(self._dispatch, msg)
        self._call_in_loop(self._on_exit, proc)

    def _read_stderr(self, proc: subprocess.Popen[str]) -> None:
        assert proc.stderr is not None
        for line in proc.stderr:
            log.debug("katago stderr: %s", line.rstrip())

    def _call_in_loop(self, fn: Any, *args: Any) -> None:
        loop = self._loop
        if loop is not None and not loop.is_closed():
            with contextlib.suppress(RuntimeError):
                loop.call_soon_threadsafe(fn, *args)

    def _dispatch(self, msg: dict[str, Any]) -> None:
        qid = msg.get("id")
        if "warning" in msg:
            log.warning("katago warning for %s (%s): %s", qid, msg.get("field"), msg["warning"])
            return
        if "error" in msg:
            log.error("katago error for %s (%s): %s", qid, msg.get("field"), msg["error"])
            pending = self._pending.get(qid) if qid else None
            if pending and not pending.future.done():
                pending.future.set_exception(KataGoQueryError(msg["error"]))
            return
        if msg.get("action") == "terminate":
            return
        pending = self._pending.get(qid) if qid else None
        if pending is None or pending.future.done():
            log.debug("katago response for unknown/finished id %s", qid)
            return
        if msg.get("isDuringSearch"):
            return
        log.debug("katago response %s turn %s", qid, msg.get("turnNumber"))
        pending.results.append(msg)
        if len(pending.results) >= pending.expected:
            pending.future.set_result(pending.results)

    def _on_exit(self, proc: subprocess.Popen[str]) -> None:
        if proc is not self._proc:
            return
        self._ready = False
        code = proc.poll()
        self._fail_all(EngineRestartedError(f"katago exited (code {code})"))
        if self._stopping or not self._auto_restart:
            return
        if self._restart_task is not None and not self._restart_task.done():
            return  # a restart loop is already running (this exit was a failed restart)
        log.error("katago exited unexpectedly (code %s); restarting", code)
        self._restart_task = asyncio.ensure_future(self._restart())

    async def _restart(self) -> None:
        while not self._stopping:
            delay = RESTART_DELAYS_S[min(self._restart_attempt, len(RESTART_DELAYS_S) - 1)]
            self._restart_attempt += 1
            await asyncio.sleep(delay)
            try:
                await self.start()
                return
            except (EngineError, OSError, TimeoutError) as e:
                log.error("katago restart failed: %s", e)

    def _fail_all(self, exc: EngineError) -> None:
        for pending in list(self._pending.values()):
            if not pending.future.done():
                pending.future.set_exception(exc)
