from __future__ import annotations

import atexit
import json
import os
import queue
import subprocess
import threading
from pathlib import Path
from typing import Protocol, runtime_checkable

from showdown_bot.engine.calc.models import DamageRequest, DamageResult

DEFAULT_CALC_DIR = Path(__file__).resolve().parents[4] / "tools" / "calc"


class CalcError(RuntimeError):
    """Raised when the calc backend fails to produce results."""


@runtime_checkable
class CalcBackend(Protocol):
    """Transport-agnostic damage backend.

    Phase 1 uses a one-shot subprocess; Phase 2 can drop in a persistent Node
    process (line protocol / JSON-RPC) without any change to ``CalcClient`` or
    its callers. Batching is part of the contract so a future backend can
    answer many requests in a single round trip.
    """

    def calc_batch(self, requests: list[DamageRequest]) -> list[DamageResult]: ...

    def close(self) -> None: ...


class SubprocessCalcBackend:
    """One-shot ``node calc.mjs`` per batch. Bundles all requests into a single
    stdin array so a batch never pays N x Node startup (~50-100ms each)."""

    def __init__(
        self,
        calc_dir: Path | None = None,
        *,
        node: str = "node",
        script: str = "calc.mjs",
        timeout: float = 20.0,
    ) -> None:
        self.calc_dir = calc_dir or DEFAULT_CALC_DIR
        self.node = node
        self.script = script
        self.timeout = timeout
        # I8-A: cumulative since construction; the profile writer derives per-decision
        # deltas by snapshotting before/after. Under oneshot every batch is its own
        # Node process, so spawn_count tracks transport_attempts exactly.
        self.spawn_count = 0
        self.transport_attempts = 0
        self.damage_batch_calls = 0
        self.stats_batch_calls = 0
        self.types_batch_calls = 0

    def calc_batch(self, requests: list[DamageRequest]) -> list[DamageResult]:
        if not requests:
            return []
        self.damage_batch_calls += 1
        payload = json.dumps([r.to_payload() for r in requests])
        try:
            # Counted BEFORE the call, deliberately: a subprocess that spawns and then
            # times out is a real spawn that paid real latency and must count. The cost
            # is that a FileNotFoundError (no node on PATH) over-counts by one -- but
            # that is a broken environment in which every call fails and the run is void
            # anyway, never a measurement scenario.
            self.spawn_count += 1
            self.transport_attempts += 1
            proc = subprocess.run(
                [self.node, self.script],
                input=payload,
                capture_output=True,
                text=True,
                cwd=str(self.calc_dir),
                timeout=self.timeout,
            )
        except FileNotFoundError as exc:
            raise CalcError(f"node executable not found: {self.node}") from exc
        except subprocess.TimeoutExpired as exc:
            raise CalcError(f"calc subprocess timed out after {self.timeout}s") from exc

        if proc.returncode != 0:
            raise CalcError(
                f"calc subprocess failed (rc={proc.returncode}): {proc.stderr.strip()}"
            )

        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise CalcError(f"calc returned invalid JSON: {proc.stdout[:200]!r}") from exc

        if isinstance(data, dict) and data.get("error"):
            raise CalcError(f"calc error: {data['error']}")

        return [DamageResult.from_json(item) for item in data]

    def _run(self, payload: list[dict]) -> list[dict]:
        # I8-A: the SECOND spawn site. calc_batch has its own subprocess.run above;
        # this helper serves stats_batch and types_batch. Counting only the first
        # would under-report exactly the spawn cost this backend is dominated by.
        try:
            self.spawn_count += 1
            self.transport_attempts += 1
            proc = subprocess.run(
                [self.node, self.script],
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                cwd=str(self.calc_dir),
                timeout=self.timeout,
            )
        except FileNotFoundError as exc:
            raise CalcError(f"node executable not found: {self.node}") from exc
        except subprocess.TimeoutExpired as exc:
            raise CalcError(f"calc subprocess timed out after {self.timeout}s") from exc
        if proc.returncode != 0:
            raise CalcError(
                f"calc subprocess failed (rc={proc.returncode}): {proc.stderr.strip()}"
            )
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise CalcError(f"calc returned invalid JSON: {proc.stdout[:200]!r}") from exc
        if isinstance(data, dict) and data.get("error"):
            raise CalcError(f"calc error: {data['error']}")
        return data

    def stats_batch(self, specs: list, *, gen: int = 9) -> list[dict]:
        """Compute final stats for a batch of CalcMon specs (no in-battle mods)."""
        if not specs:
            return []
        self.stats_batch_calls += 1
        payload = []
        for idx, spec in enumerate(specs):
            payload.append({"id": f"s{idx}", "kind": "stats", "gen": gen, "mon": spec.to_payload()})
        data = self._run(payload)
        return [item["stats"] for item in data]

    def types_batch(self, species: list[str]) -> list[list[str]]:
        """Look up the (base) typing for a batch of species."""
        if not species:
            return []
        self.types_batch_calls += 1
        payload = [
            {"id": f"t{idx}", "kind": "types", "gen": 9, "species": sp}
            for idx, sp in enumerate(species)
        ]
        data = self._run(payload)
        return [item.get("types", []) for item in data]

    def close(self) -> None:
        """No process/handle to release — one-shot ``subprocess.run`` per call.
        No-op, for symmetry with ``PersistentCalcBackend.close`` so callers can
        close any ``CalcBackend`` uniformly."""


class _TransportError(Exception):
    """Process/transport-level failure (crash/EOF/timeout/malformed/desync) -> restart+retry."""


class PersistentCalcBackend:
    """Persistent ``node calc.mjs --server`` backend.

    Keeps one Node process alive across calls, serializes requests with a lock,
    recovers from transport failures (restart + retry-once) using a reader-thread
    queue for cross-platform timeout. Same surface as ``SubprocessCalcBackend``.
    """

    def __init__(
        self,
        calc_dir: Path | None = None,
        *,
        node: str = "node",
        script: str = "calc.mjs",
        timeout_ms: int | None = None,
    ) -> None:
        self.calc_dir = calc_dir or DEFAULT_CALC_DIR
        self.node = node
        self.script = script
        self.timeout = (
            timeout_ms
            if timeout_ms is not None
            else int(os.environ.get("SHOWDOWN_CALC_TIMEOUT_MS", "10000"))
        ) / 1000.0
        self._proc: subprocess.Popen | None = None
        self._reader: threading.Thread | None = None
        self._q: queue.Queue = queue.Queue()
        self._lock = threading.Lock()
        self.spawn_count = 0  # benchmark: confirms persistence
        # I8-A: cumulative since construction, same surface as SubprocessCalcBackend.
        # transport_attempts counts PHYSICAL attempts, so _run's retry path makes one
        # logical call cost two attempts; the *_batch_calls stay logical.
        self.transport_attempts = 0
        self.damage_batch_calls = 0
        self.stats_batch_calls = 0
        self.types_batch_calls = 0
        atexit.register(self.close)

    # --- lifecycle ---

    def _ensure(self) -> subprocess.Popen:
        if self._proc is not None and self._proc.poll() is None:
            return self._proc
        self._spawn()
        return self._proc  # type: ignore[return-value]

    def _spawn(self) -> None:
        # GENERATION ISOLATION: kill old proc, install a FRESH queue, start a
        # reader thread bound to the new (proc, q).  The old reader drains into
        # the now-unreferenced old queue and exits on EOF — so a stale stdout
        # line from a dead generation can never leak into a retry's response.
        self._kill()
        self._q = queue.Queue()  # fresh queue — old one is discarded
        self._proc = subprocess.Popen(
            [self.node, self.script, "--server"],
            cwd=str(self.calc_dir),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            # stderr inherits (NOT piped — avoids undrained buffer deadlock)
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        self.spawn_count += 1
        self._reader = threading.Thread(
            target=self._read_loop,
            args=(self._proc, self._q),
            daemon=True,
        )
        self._reader.start()  # reader writes ONLY to this generation's queue

    def _read_loop(self, proc: subprocess.Popen, q: queue.Queue) -> None:
        try:
            for line in proc.stdout:  # blocking readline in BG thread → cross-platform timeout
                q.put(line)
        except Exception:
            pass
        finally:
            q.put(None)  # sentinel: stream closed (EOF/crash)

    def _kill(self) -> None:
        if self._proc is not None:
            try:
                if self._proc.stdin:
                    self._proc.stdin.close()
            except Exception:
                pass
            try:
                self._proc.kill()
            except Exception:
                pass
            try:
                self._proc.wait(timeout=2)
            except Exception:
                pass
            self._proc = None

    def close(self) -> None:  # idempotent
        self._kill()

    # --- transport core ---

    def _run(self, payload: list) -> list:
        with self._lock:  # serialize: one request fully written+read at a time
            try:
                return self._run_once(payload)
            except _TransportError:
                self._spawn()  # restart
                try:
                    return self._run_once(payload)  # retry ONCE
                except _TransportError as e:
                    raise CalcError(
                        f"persistent calc failed after restart+retry: {e}"
                    ) from e

    def _run_once(self, payload: list) -> list:
        # I8-A: one PHYSICAL attempt. _run calls this up to twice per logical call
        # (:242-243), so transport_attempts > *_batch_calls is the retry signature.
        # Counted here rather than in _run so a retried call reports 2, not 1.
        self.transport_attempts += 1
        proc = self._ensure()
        line = json.dumps(payload, separators=(",", ":")) + "\n"
        try:
            proc.stdin.write(line)
            proc.stdin.flush()
        except (BrokenPipeError, OSError) as e:
            raise _TransportError(f"write failed: {e}") from e
        try:
            resp = self._q.get(timeout=self.timeout)
        except queue.Empty:
            raise _TransportError("response timeout")
        if resp is None:
            raise _TransportError("EOF before response")
        try:
            data = json.loads(resp)
        except json.JSONDecodeError as e:
            raise _TransportError(f"malformed JSON response: {e}") from e
        if isinstance(data, dict) and data.get("error"):
            raise _TransportError(f"server rejected request: {data['error']}")
        if not isinstance(data, list):
            raise _TransportError("response is not a list")
        return data

    # --- surface (same payloads as SubprocessCalcBackend) ---

    def calc_batch(self, requests: list[DamageRequest]) -> list[DamageResult]:
        if not requests:
            return []
        self.damage_batch_calls += 1
        data = self._run([r.to_payload() for r in requests])
        # Per-item {id,error} is SEMANTIC — returned as DamageResult with .error set,
        # same as SubprocessCalcBackend; CalcClient.damage_batch raises CalcError on .error.
        return [DamageResult.from_json(item) for item in data]

    def stats_batch(self, specs: list, *, gen: int = 9) -> list[dict]:
        """Compute final stats for a batch of CalcMon specs (no in-battle mods)."""
        if not specs:
            return []
        self.stats_batch_calls += 1
        payload = [
            {"id": f"s{i}", "kind": "stats", "gen": gen, "mon": s.to_payload()}
            for i, s in enumerate(specs)
        ]
        return [item["stats"] for item in self._run(payload)]

    def types_batch(self, species: list[str]) -> list[list[str]]:
        """Look up the (base) typing for a batch of species."""
        if not species:
            return []
        self.types_batch_calls += 1
        payload = [
            {"id": f"t{i}", "kind": "types", "gen": 9, "species": sp}
            for i, sp in enumerate(species)
        ]
        return [item.get("types", []) for item in self._run(payload)]


def make_calc_backend() -> SubprocessCalcBackend | PersistentCalcBackend:
    """Select a calc backend via ``SHOWDOWN_CALC_BACKEND`` env var.

    - unset / ``""`` / ``"oneshot"`` → :class:`SubprocessCalcBackend` (default)
    - ``"persistent"``               → :class:`PersistentCalcBackend`
    - anything else                  → :exc:`ValueError`
    """
    mode = os.environ.get("SHOWDOWN_CALC_BACKEND", "oneshot")
    if mode in ("", "oneshot"):
        return SubprocessCalcBackend()
    if mode == "persistent":
        return PersistentCalcBackend()
    raise ValueError(
        f"unknown SHOWDOWN_CALC_BACKEND={mode!r} (expected 'oneshot' or 'persistent')"
    )


class CalcClient:
    """Caller-facing API. Does not know whether the backend is a one-shot
    subprocess or a persistent process."""

    def __init__(self, backend: CalcBackend | None = None) -> None:
        self.backend: CalcBackend = backend or make_calc_backend()

    def close(self) -> None:
        """Passthrough to the backend's close (idempotent on both backend types).
        Per-battle teardown seam (2b-2.5a Kaggle-OOM fix) — see PersistentCalcBackend.close."""
        self.backend.close()

    def damage(self, request: DamageRequest) -> DamageResult:
        return self.damage_batch([request])[0]

    def damage_batch(self, requests: list[DamageRequest]) -> list[DamageResult]:
        prepared: list[DamageRequest] = []
        for idx, req in enumerate(requests):
            if req.id is None:
                req.id = f"req{idx}"
            prepared.append(req)

        results = self.backend.calc_batch(prepared)

        by_id = {res.id: res for res in results if res.id is not None}
        if len(by_id) == len(prepared):
            ordered = [by_id[req.id] for req in prepared]
        else:
            # Backend did not echo ids reliably; fall back to positional order.
            ordered = results

        errors = [r for r in ordered if r.error]
        if errors:
            raise CalcError("; ".join(str(e.error) for e in errors))
        return ordered
