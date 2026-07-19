# Phase 3 Slice 2a: Persistent CalcClient backend — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in persistent Node calc backend (one long-lived `node calc.mjs --server`
process + newline line-protocol) so calc-heavy paths stop paying Node startup + gen-9 dex load per
batch. Same `CalcClient` API, identical results.

**Architecture:** `calc.mjs` gains a `--server` line-loop mode (shared compute logic). A new
`PersistentCalcBackend` (Python) keeps one process alive, serializes requests with a lock, frames
each batch as one JSON line, and recovers from transport failures (restart + retry-once) with a
cross-platform reader-thread timeout. A `make_calc_backend()` factory + `SHOWDOWN_CALC_BACKEND` env
selects the backend (default one-shot → behavior-preserving).

**Tech Stack:** Python stdlib (`subprocess`, `threading`, `queue`, `atexit`), Node + `@smogon/calc`.
Spec: `docs/projects/core-bot/specs/2026-06-30-2a-persistent-calc-design.md`. Touch: `tools/calc/calc.mjs`,
`engine/calc/client.py`. Run tests from `showdown_bot/`. NB: `node` is available (v24); the real
calc works.

**Grounded facts:** `SubprocessCalcBackend` (client.py): `calc_batch` builds
`[r.to_payload() for r in requests]` → subprocess → `[DamageResult.from_json(item)]`; `_run(payload)`
→ subprocess → `json.loads(stdout)`; `stats_batch(specs)` builds `{"id":f"s{i}","kind":"stats",
"gen":9,"mon":spec.to_payload()}` → `_run` → `[item["stats"]]`; `types_batch(species)` builds
`{"id":f"t{i}","kind":"types","gen":9,"species":sp}` → `_run` → `[item.get("types",[])]`.
`DEFAULT_CALC_DIR = parents[4]/tools/calc`. `calc.mjs` reads ALL stdin, dispatches per `req.kind`
(stats/types/else=damage), caches `gens` per batch, writes a JSON array. **Do NOT touch
`SubprocessCalcBackend`'s behavior** — `PersistentCalcBackend` is a parallel class with the same
surface; the golden test asserts identical output.

---

## File Structure
- Modify: `tools/calc/calc.mjs` — add a `--server` line-loop mode; refactor compute into shared
  `runOne`/`runStats`/`runTypes` + a `dispatch(gens, req)` reused by both modes. One-shot path
  unchanged.
- Modify: `engine/calc/client.py` — add `PersistentCalcBackend`, `make_calc_backend()`,
  `CalcError` reuse, a private `_TransportError`. `CalcClient.__init__` default backend → factory.
- Tests: `tests/test_calc_persistent.py` (server smoke, golden vs one-shot, recovery, lock, factory).

---

## Task 2a-1: `calc.mjs` server mode

**Files:** Modify `tools/calc/calc.mjs`; Test `tests/test_calc_persistent.py`.

- [ ] **Step 1: failing test** — a Python test that spawns the server and round-trips two lines:

```python
# tests/test_calc_persistent.py
import json, subprocess
from showdown_bot.engine.calc.client import DEFAULT_CALC_DIR


def _types_line(species):
    return json.dumps([{"id": "t0", "kind": "types", "gen": 9, "species": species}],
                      separators=(",", ":")) + "\n"


def test_calc_mjs_server_mode_roundtrips_two_lines():
    proc = subprocess.Popen(["node", "calc.mjs", "--server"], cwd=str(DEFAULT_CALC_DIR),
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8", bufsize=1)
    try:
        proc.stdin.write(_types_line("Incineroar")); proc.stdin.flush()
        line1 = proc.stdout.readline()
        proc.stdin.write(_types_line("Flutter Mane")); proc.stdin.flush()
        line2 = proc.stdout.readline()
        r1, r2 = json.loads(line1), json.loads(line2)
        assert isinstance(r1, list) and isinstance(r2, list)     # each line is a JSON array
        assert r1[0]["types"] == ["Fire", "Dark"]
        assert set(r2[0]["types"]) == {"Ghost", "Fairy"}
        assert proc.poll() is None                               # alive after 2 requests
    finally:
        proc.stdin.close()
        rest = proc.stdout.read()                                # everything after line2
        assert rest == "", f"unexpected extra stdout (banner/log breaks the protocol): {rest!r}"
        assert proc.wait(timeout=5) == 0                         # clean EOF exit, code 0
```
(The `rest == ""` + the JSON-array asserts together pin **stdout = protocol only**: no startup
banner before line1, no extra/log line after line2 — exactly one response line per request.)

- [ ] **Step 2: run → FAIL** (no `--server` mode yet). `cd showdown_bot && python -m pytest tests/test_calc_persistent.py::test_calc_mjs_server_mode_roundtrips_two_lines -q`

- [ ] **Step 3: implement** in `calc.mjs`: extract the per-request dispatch into a shared
  `dispatch(gens, req)` (the existing `req.kind` switch → runStats/runTypes/runOne, with the
  per-request try/catch returning `{id, error}`). Keep `main()` (one-shot) using it. Add a server
  entry: if `process.argv.includes("--server")`, run a `readline` loop over stdin —

```js
import { createInterface } from 'node:readline';

function processBatch(gens, raw) {
  let parsed;
  try { parsed = JSON.parse(raw); }
  catch (e) { return JSON.stringify({ error: `invalid JSON: ${e.message}` }); }
  const requests = Array.isArray(parsed) ? parsed : [parsed];
  return JSON.stringify(requests.map((req) => dispatch(gens, req)));
}

function serve() {
  const gens = new Map();                              // SHARED across all lines (the win)
  const rl = createInterface({ input: process.stdin, crlfDelay: Infinity });
  rl.on('line', (raw) => {
    if (raw.trim() === '') return;
    process.stdout.write(processBatch(gens, raw) + '\n');  // stdout = protocol ONLY
  });
  rl.on('close', () => process.exit(0));               // stdin EOF -> clean exit 0
}

if (process.argv.includes('--server')) serve();
else main();                                            // one-shot path unchanged
```
Any logging/errors → `console.error` (stderr), never stdout. `dispatch` must keep the per-request
`try/catch → {id, error}` so a bad ITEM doesn't kill the loop.

- [ ] **Step 4: run → PASS** + full suite (`cd showdown_bot && python -m pytest -q`, baseline 405 —
  one-shot tests must stay green). **Step 5: commit** `feat(calc): calc.mjs --server line-loop mode (shared dispatch, stdout protocol-only, clean EOF)`.

---

## Task 2a-2: `PersistentCalcBackend`

**Files:** Modify `engine/calc/client.py`; Test `tests/test_calc_persistent.py`.

- [ ] **Step 1: failing golden + lifecycle tests**

```python
from showdown_bot.engine.calc.client import (
    CalcClient, SubprocessCalcBackend, PersistentCalcBackend, CalcError)
from showdown_bot.engine.calc.models import DamageRequest


def test_persistent_matches_oneshot_types_and_stats():
    one, persistent = SubprocessCalcBackend(), PersistentCalcBackend()
    try:
        assert persistent.types_batch(["Incineroar", "Flutter Mane"]) == one.types_batch(["Incineroar", "Flutter Mane"])
        # stats: build a couple of CalcMon specs as the speed code does; assert equal lists (ids/order/count)
        ...
    finally:
        persistent.close()


def test_persistent_matches_oneshot_damage_batch(sample_damage_requests):
    one, persistent = SubprocessCalcBackend(), PersistentCalcBackend()
    try:
        a = one.calc_batch(sample_damage_requests)
        b = persistent.calc_batch(sample_damage_requests)
        assert [r.id for r in a] == [r.id for r in b]       # same ids + order + count
        assert [(r.min_damage, r.max_damage, r.max_hp) for r in a] == [(r.min_damage, r.max_damage, r.max_hp) for r in b]
    finally:
        persistent.close()


def test_close_is_idempotent():
    b = PersistentCalcBackend(); b.types_batch(["Incineroar"])
    b.close(); b.close()        # no crash on double close
```

- [ ] **Step 2: run → FAIL. Step 3: implement** `PersistentCalcBackend` in `client.py`:

```python
import atexit, queue, threading


class _TransportError(Exception):
    """Process/transport-level failure (crash/EOF/timeout/malformed/desync) -> restart+retry."""


class PersistentCalcBackend:
    def __init__(self, calc_dir=None, *, node="node", script="calc.mjs", timeout_ms=None):
        self.calc_dir = calc_dir or DEFAULT_CALC_DIR
        self.node, self.script = node, script
        self.timeout = (timeout_ms or int(os.environ.get("SHOWDOWN_CALC_TIMEOUT_MS", "10000"))) / 1000.0
        self._proc = None
        self._reader = None
        self._q: queue.Queue = queue.Queue()
        self._lock = threading.Lock()
        self.spawn_count = 0           # benchmark: confirms it stays persistent
        atexit.register(self.close)

    # --- lifecycle ---
    def _ensure(self):
        if self._proc is not None and self._proc.poll() is None:
            return self._proc
        self._spawn()
        return self._proc

    def _spawn(self):
        # GENERATION ISOLATION (pin): each process generation owns its OWN queue + reader thread.
        # On restart we kill the old proc, install a FRESH self._q, and start a reader bound to the
        # new (proc, q). The old reader drains into the now-unreferenced old queue and exits on EOF —
        # so no stale stdout line from a dead generation can ever leak into the retry's response.
        self._kill()
        self._q = queue.Queue()                                # fresh queue — old one is discarded
        self._proc = subprocess.Popen(
            [self.node, self.script, "--server"], cwd=str(self.calc_dir),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,    # stderr inherits (NOT piped/undrained)
            text=True, encoding="utf-8", bufsize=1)
        self.spawn_count += 1
        self._reader = threading.Thread(target=self._read_loop, args=(self._proc, self._q), daemon=True)
        self._reader.start()                                   # reader writes ONLY to this generation's q

    def _read_loop(self, proc, q):
        try:
            for line in proc.stdout:          # blocking readline in a BG thread -> cross-platform timeout
                q.put(line)
        except Exception:
            pass
        finally:
            q.put(None)                       # sentinel: stream closed (EOF/crash)

    def _kill(self):
        if self._proc is not None:
            try:
                if self._proc.stdin: self._proc.stdin.close()
            except Exception: pass
            try: self._proc.kill()
            except Exception: pass
            try: self._proc.wait(timeout=2)
            except Exception: pass
            self._proc = None

    def close(self):                          # idempotent
        self._kill()

    # --- transport core ---
    def _run(self, payload):
        with self._lock:                      # serialize: one request fully written+read at a time
            try:
                return self._run_once(payload)
            except _TransportError:
                self._spawn()                 # restart
                try:
                    return self._run_once(payload)   # retry ONCE
                except _TransportError as e:
                    raise CalcError(f"persistent calc failed after restart+retry: {e}") from e

    def _run_once(self, payload):
        proc = self._ensure()
        line = json.dumps(payload, separators=(",", ":")) + "\n"
        try:
            proc.stdin.write(line); proc.stdin.flush()
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
            raise _TransportError(f"server rejected request: {data['error']}")   # whole-line reject = transport
        if not isinstance(data, list):
            raise _TransportError("response is not a list")
        return data

    # --- surface (same payloads as SubprocessCalcBackend; per-item {id,error} is SEMANTIC) ---
    def calc_batch(self, requests):
        if not requests: return []
        data = self._run([r.to_payload() for r in requests])
        results = [DamageResult.from_json(item) for item in data]
        # CalcClient.damage_batch raises CalcError on per-item .error (semantic) — same as one-shot.
        return results

    def stats_batch(self, specs):
        if not specs: return []
        payload = [{"id": f"s{i}", "kind": "stats", "gen": 9, "mon": s.to_payload()} for i, s in enumerate(specs)]
        return [item["stats"] for item in self._run(payload)]

    def types_batch(self, species):
        if not species: return []
        payload = [{"id": f"t{i}", "kind": "types", "gen": 9, "species": sp} for i, sp in enumerate(species)]
        return [item.get("types", []) for item in self._run(payload)]
```
Ground `DamageResult.from_json` / `to_payload` against the real models. The per-item semantic
`{id,error}` handling must match `SubprocessCalcBackend` exactly (so `calc_batch` golden-matches) —
check how the one-shot `calc_batch`/`CalcClient.damage_batch` surfaces item errors and mirror it.

- [ ] **Step 4: run golden + idempotent-close → PASS.**

- [ ] **Step 5: recovery tests** (the 6 from the spec) — use a FAKE/controllable server so failures
  are deterministic (e.g. a tiny `fake_server.mjs` or monkeypatch `_spawn` to launch a stub script
  that: crashes after 1 response / hangs / emits malformed JSON / emits a non-list). Tests:
  crash-before-response → restart+retry→success; timeout/hang → kill+restart+retry-once; malformed
  → restart+retry; retry-fails → `CalcError`; semantic per-item `{id,error}` → `CalcError` with NO
  restart (assert `spawn_count` unchanged); concurrent `_run` from two threads → both correct +
  non-swapped (assert via distinct `types_batch` species per thread). Implement until green.
  **Step 6: commit** `feat(calc): PersistentCalcBackend (line protocol, lock, restart+retry-once, reader-thread timeout, idempotent close)`.

---

## Task 2a-3: factory + env selection + benchmark

**Files:** Modify `engine/calc/client.py`; Test `tests/test_calc_persistent.py`; benchmark via the
scratchpad probe.

- [ ] **Step 1: failing tests**

```python
def test_factory_default_is_oneshot(monkeypatch):
    monkeypatch.delenv("SHOWDOWN_CALC_BACKEND", raising=False)
    from showdown_bot.engine.calc.client import make_calc_backend, SubprocessCalcBackend
    assert isinstance(make_calc_backend(), SubprocessCalcBackend)


def test_factory_persistent(monkeypatch):
    monkeypatch.setenv("SHOWDOWN_CALC_BACKEND", "persistent")
    from showdown_bot.engine.calc.client import make_calc_backend, PersistentCalcBackend
    b = make_calc_backend()
    try: assert isinstance(b, PersistentCalcBackend)
    finally: b.close()


def test_factory_unknown_raises(monkeypatch):
    monkeypatch.setenv("SHOWDOWN_CALC_BACKEND", "persitent")    # typo
    from showdown_bot.engine.calc.client import make_calc_backend
    import pytest
    with pytest.raises(ValueError):
        make_calc_backend()


def test_calcclient_default_uses_factory(monkeypatch):
    monkeypatch.setenv("SHOWDOWN_CALC_BACKEND", "persistent")
    from showdown_bot.engine.calc.client import CalcClient, PersistentCalcBackend
    c = CalcClient()
    try: assert isinstance(c.backend, PersistentCalcBackend)
    finally: c.backend.close()
```

- [ ] **Step 2: fail. Step 3: implement** in `client.py`:

```python
def make_calc_backend():
    mode = os.environ.get("SHOWDOWN_CALC_BACKEND", "oneshot")
    if mode in ("", "oneshot"):
        return SubprocessCalcBackend()
    if mode == "persistent":
        return PersistentCalcBackend()
    raise ValueError(f"unknown SHOWDOWN_CALC_BACKEND={mode!r} (expected 'oneshot' or 'persistent')")
```
Change `CalcClient.__init__`: `self.backend = backend or make_calc_backend()` (was
`or SubprocessCalcBackend()`). Default env → one-shot → existing behavior preserved.

- [ ] **Step 4: run → PASS** + full suite. **Step 5: benchmark (measurement, not a test):** re-run
  the scratchpad probe with `SHOWDOWN_CALC_BACKEND=persistent SHOWDOWN_ROLLOUT_HORIZON=1`. Record:
  `spawn_count` (expect ~1, confirming persistence), calc batches, total seconds, **seconds/decision
  vs the 145.9s one-shot baseline**. Note the result in the probe report doc. **Step 6: commit**
  `feat(calc): make_calc_backend factory + SHOWDOWN_CALC_BACKEND env; CalcClient default wiring`.

---

## Self-Review notes
- **Spec coverage:** server-mode + stdout-protocol-only + clean-EOF (2a-1); PersistentCalcBackend
  surface + lock + restart+retry-once + cross-platform reader-thread timeout + idempotent close +
  the recovery/golden/concurrency tests (2a-2); factory + env + ValueError + CalcClient default +
  benchmark spawn-count (2a-3).
- **Pins:** stdout protocol-only (`console.error` for logs); semantic per-item `{id,error}` →
  `CalcError` no-retry (whole-line `{error}` = transport); `threading.Lock` serialization;
  cross-platform timeout via reader-thread+queue (NO `select()`); idempotent `close()`/atexit;
  golden asserts ids/order/count/values; factory `ValueError` on unknown env; Windows Popen
  (`text/utf-8/bufsize=1`, stderr inherit).
- **Behaviour-preserving:** `SubprocessCalcBackend` untouched; default env → one-shot; existing
  calc tests stay green.
- **Ground in execution:** the exact `DamageResult.from_json`/`to_payload`, how the one-shot
  `calc_batch` surfaces per-item errors (mirror it), the recovery-test stub-server mechanism.
- **Non-goals:** no calc-mechanics change, no ML/reranker/dataset change.
