# Phase 3 Slice 2a: Persistent CalcClient backend — Design

**Goal:** Replace the one-shot `node calc.mjs` subprocess-per-batch with an opt-in **persistent**
Node process speaking a newline-framed line protocol, so the rollout export (and any calc-heavy
path) stops paying Node startup + `Generations.get(9)` per batch. Same `CalcClient` API, same
results — transport optimization only.

**Status:** brainstorming, 2026-06-30, on `main` (Phase 3 Slice 1 complete, suite 405). New branch
for 2a. Motivation: the 1d real probe measured **~146s/sampled-decision** (H=1, top_k=6), dominated
by ~120 one-shot `node` spawns each re-loading the gen-9 dex. A persistent process amortizes that.

## Non-goals (hard)
No ML, no reranker, no dataset-schema change, **no calc-mechanics change** (transport only). Don't
touch the direct `SubprocessCalcBackend()` construction sites (speed.py/opponent.py/hypotheses.py)
beyond what selection requires. `SubprocessCalcBackend` stays the default behavior.

## Architecture — swappable backend transport
```
calc.mjs              + a SERVER mode (flag, e.g. `node calc.mjs --server`): read stdin LINE BY
                        LINE in a loop; per line parse ONE JSON batch (array, same shape as today)
                        -> dispatch each item by `kind` (runOne/runStats/runTypes — SHARED with the
                        one-shot path) -> write ONE JSON result-array line; the `gens` Map (and the
                        loaded Generation) STAYS ALIVE across lines. One-shot mode unchanged.
PersistentCalcBackend  Python, in engine/calc/client.py: spawns ONE node server process (lazy, on
                        first request); implements the FULL surface SubprocessCalcBackend exposes —
                        `calc_batch`, `stats_batch`, `types_batch`, `_run` — byte-for-byte
                        compatible. Synchronous write-line / read-line per batch.
make_calc_backend()    factory reading env SHOWDOWN_CALC_BACKEND = "oneshot" | "persistent"
                        (default "oneshot"). CalcClient's default backend uses it, so a single env
                        switch makes ALL CalcClient() persistent (incl. the rollout via
                        decision.py:182 `calc = calc or CalcClient()`). Live default = oneshot,
                        current behavior bit-for-bit preserved.
```
The rollout benefits automatically: it builds `calc = CalcClient()` and derives
`SpeedOracle(stats_backend=calc.backend)`, so one persistent backend serves damage + stats; types
lookups elsewhere are cached and rare.

## Line protocol (newline-framed, compact JSON)
- One request = one line = `json.dumps(batch, separators=(",",":"))` (compact → no embedded
  newlines) + `\n`. One response = one line = the JSON result array + `\n`.
- Correlation: synchronous (write a line, read a line) + by `id` within the batch (as today). No
  pipelining (callers are synchronous).
- **stdout is PROTOCOL ONLY** (pin 1): in server mode `calc.mjs` writes ONLY JSON result lines to
  stdout. All logs / debug / errors go to **stderr**. (A stray stdout log would desync the protocol.)

## Backend surface (identical to SubprocessCalcBackend)
`calc_batch(requests: list[DamageRequest]) -> list[DamageResult]`,
`stats_batch(specs) -> list[dict]`, `types_batch(species) -> list[list[str]]`, plus the internal
`_run(payload) -> list[dict]`. The persistent backend frames each of these the same way the
one-shot backend builds its payload, but over the live process instead of a fresh subprocess.

## Recovery — restart-and-retry-once, transport failures only (pinned)
Distinguish **semantic** from **transport** failures (pin 2):
- **Semantic calc error** — `calc.mjs` returns a per-item `{id, error}` (bad input / unsupported
  case): Python raises `CalcError`. **No restart, no retry.** (Same as today's one-shot behavior.)
- **Transport failure** — process crash / EOF / timeout-hang / malformed-JSON / protocol desync:
  **kill the process → restart → retry the SAME request exactly once.** If the retry also fails →
  `CalcError` (the export run hard-fails). **Never silently fabricate a result.**
- **Per-request timeout** (pin 3): `SHOWDOWN_CALC_TIMEOUT_MS` (default 10000ms). A request that
  doesn't return a line in time is a transport failure → kill + restart + retry once.

## Lifecycle + Windows Popen (pinned)
- Lazy spawn on first request; **`close()` is idempotent** (pin 4) — safe to call multiple times,
  never crashes; registered via `atexit` so no orphan node process survives the run. Optional
  context-manager sugar.
- `Popen` config: `text=True, encoding="utf-8", bufsize=1`, stdin/stdout pipes. **stderr: inherit
  or `DEVNULL`** — NOT a pipe left undrained (a chatty node could block on a full stderr pipe).
  v1: inherit (so debug logs are visible); the protocol only reads stdout.

## Determinism + batch-order golden (pin 5)
Persistent == one-shot is asserted not just on values but on the full shape:
**same request ids, same ordering, same number of results, same per-item errors, same normalized
payload shape.** (A faster backend that subtly reorders or drops would otherwise corrupt labels.)

## Decomposition (the plan will cut it)
- **2a-1 — `calc.mjs` server mode:** the stdin line-loop + shared `runOne`/`runStats`/`runTypes` +
  stdout-protocol-only / stderr-logs; a Node-level smoke (feed two batch lines, get two result
  lines, process stays up). One-shot mode untouched.
- **2a-2 — `PersistentCalcBackend`:** spawn + line protocol + the full surface
  (calc_batch/stats_batch/types_batch/_run) + restart-and-retry-once recovery + per-request timeout
  + idempotent `close()`/atexit. Golden tests vs one-shot + the recovery tests.
- **2a-3 — selection + benchmark:** `make_calc_backend()` factory + `SHOWDOWN_CALC_BACKEND` env +
  `CalcClient` default wiring; re-run the rollout-export probe (H=1, top_k=6) and record the speedup.

## Tests (acceptance)
- one-shot and persistent produce **identical** `damage_batch` results (ids/order/count/errors/shape).
- identical `stats_batch` results.
- identical `types_batch` results.
- crash before response → process restarted → same request retried once → success.
- timeout/hang → process killed + restarted → same request retried once.
- malformed JSON / protocol desync → restart + retry once.
- retry also fails → `CalcError`.
- semantic `{id, error}` → `CalcError`, **no** restart, **no** retry.
- `close()` is idempotent (call twice + atexit, no crash).
- `SHOWDOWN_CALC_BACKEND=persistent` → `CalcClient()` uses `PersistentCalcBackend`.
- default env → one-shot, current behavior preserved (existing calc tests stay green).

## Benchmark gate (goal, not a hard number)
Re-run the rollout-export probe (H=1, top_k=6). **Expected: materially faster than 145.9s/decision**
(target ~order-of-magnitude from amortizing the gen load, but not pinned as an exact multiple).
Record: sampled decisions, calc requests, total seconds, seconds/decision. If it is not clearly
faster, 2a is not met.
