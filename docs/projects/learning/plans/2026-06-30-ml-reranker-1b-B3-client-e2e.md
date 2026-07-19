# Phase 3 Slice 1b-B3: client hook + provenance + hermetic E2E — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the real decision pipeline to the dataset export — build a
`FeatureContext` with deterministic provenance, sample per decision, bridge
trace→rows→exporter, and prove the whole path with a hermetic E2E — while keeping the
client hook thin and `exporter=None` bit-identical.

**Architecture:** Three thin layers, each testable in isolation. `learning/provenance.py`
gathers run provenance + mints `FeatureContext` (via the B2 ID helpers).
`learning/export_driver.py::maybe_observe_decision` is the sampling-gated trace→rows
bridge (the dumb `DatasetExporter` still sees only finished Rows; `battle/` still
knows no export). A thin hook in `client/gauntlet.py` enables it via an env knob.

**Tech Stack:** Python stdlib (`subprocess`, `hashlib`, `json`). Spec:
`docs/projects/learning/specs/2026-06-30-ml-reranker-1b-feature-extraction-export-design.md`.
Reuses B1 (`features.py`) + B2 (`export.py`). Run tests from `showdown_bot/`. The
hermetic E2E uses `tests/conftest.py`'s `decision_fixture` — no Node.

## Dependency rule (unchanged): `battle/` no learning dep · `learning/` reads battle DTOs · `client/` optionally wires the exporter.

---

## The 7 gates (acceptance criteria — each is a test below)
1. `exporter=None` produces exactly the same chosen action as before.
2. `exporter` enabled produces the same chosen action **plus** rows.
3. `FeatureContext` carries deterministic IDs / provenance.
4. `SamplingPolicy.should_sample` is respected per decision.
5. `extract_features` is called **only** for sampled decisions.
6. `exporter.add` validates rows (via B2).
7. `flush_sorted` produces byte-identical JSONL in the hermetic E2E.

## Out of scope (hard): no model, training, reranker, simulator, new features, new heuristic terms. No feature logic in the client; no export logic in `battle/`.

## File Structure
- Create: `src/showdown_bot/learning/provenance.py`, `src/showdown_bot/learning/export_driver.py`,
  `src/showdown_bot/learning/export_runtime.py` (the **testable seam**: env setup +
  per-decision observe + counters + flush; the client just holds one).
- Modify (thin): `src/showdown_bot/client/gauntlet.py` — only `DatasetExportRuntime.from_env(...)`
  + `.start_game()` / `.observe(...)` / `.flush()` calls, no export logic.
- Test: `tests/test_provenance.py`, `tests/test_export_driver.py`,
  `tests/test_export_runtime.py` (the hermetic hook seam), `tests/test_export_e2e.py`.

## Counter semantics (pinned)
- `game_index` — run-level, increments once per battle (first game = 0).
- `decision_local_index` — **per-game**, resets to 0 at battle start, increments per
  our decision; feeds `decision_id` (locally stable, so re-runs of the same game
  reproduce the same decision_ids).
- `sampling_decision_index` — **global run-level**, increments per our decision across
  ALL games, never resets; the ONLY counter passed to `SamplingPolicy.should_sample`
  (sampling spans the whole run; it must not restart each game).

## Env knobs (concrete)
- `SHOWDOWN_DATASET_EXPORT=/path/out.jsonl` — enable + output path. **Excluded from
  `config_hash`** (the path is not dataset semantics).
- `SHOWDOWN_DATASET_RUN_SEED=0`, `SHOWDOWN_DATASET_SAMPLE_POLICY=all`,
  `SHOWDOWN_DATASET_SAMPLE_RATE=1`.
- `config_hash` covers **dataset-semantic** config only: `{sample_policy, sample_rate,
  top_k, team_hash, + the relevant heuristic knobs (SHOWDOWN_PROTECT_PENALTY,
  SHOWDOWN_REAL_SPREADS, SHOWDOWN_OPP_SETS, SHOWDOWN_OPP_SPEED,
  SHOWDOWN_MUST_REACT_LAMBDA, SHOWDOWN_ROLLOUT_HORIZON)}` — NOT the output path.

---

## Task 1: `provenance.py` — deterministic FeatureContext minting

**Files:** Create `src/showdown_bot/learning/provenance.py`; Test `tests/test_provenance.py`.

- [ ] **Step 1: failing tests**

```python
# tests/test_provenance.py
from showdown_bot.learning.provenance import team_hash, config_hash, build_feature_context
from showdown_bot.learning.export import make_run_id, make_game_id, make_decision_id


def test_hashes_are_deterministic_16hex():
    assert team_hash("packed|team|str") == team_hash("packed|team|str")
    assert team_hash("a") != team_hash("b")
    assert len(team_hash("x")) == 16
    assert config_hash({"a": 1, "b": 2}) == config_hash({"b": 2, "a": 1})   # order-independent
    assert config_hash({"a": 1}) != config_hash({"a": 2})


def test_build_feature_context_mints_chained_ids():
    ctx = build_feature_context(
        git_sha="sha", dirty_flag=False, team_hash_="t", config_hash_="c", run_seed=7,
        game_index=0, decision_local_index=2, turn_number=3, our_side="p1",
        format_id="fmt", mirror_flag=True,
        teacher_config={"teacher_version": "stub-h0", "trainable_label": False},
        sampling_policy="all",
    )
    run_id = make_run_id("sha", False, "t", "c", 7)
    assert ctx.run_id == run_id
    assert ctx.game_id == make_game_id(run_id, 0)
    assert ctx.decision_id == make_decision_id(ctx.game_id, 2, 3, "p1")
    assert ctx.format_id == "fmt" and ctx.mirror_flag is True
    # rebuild with same inputs -> identical ids (deterministic)
    ctx2 = build_feature_context(
        git_sha="sha", dirty_flag=False, team_hash_="t", config_hash_="c", run_seed=7,
        game_index=0, decision_local_index=2, turn_number=3, our_side="p1",
        format_id="fmt", mirror_flag=True,
        teacher_config={"teacher_version": "stub-h0", "trainable_label": False},
        sampling_policy="all",
    )
    assert (ctx2.run_id, ctx2.game_id, ctx2.decision_id) == (ctx.run_id, ctx.game_id, ctx.decision_id)
```

- [ ] **Step 2: run → FAIL.** `cd showdown_bot && python -m pytest tests/test_provenance.py -q`

- [ ] **Step 3: implement `src/showdown_bot/learning/provenance.py`**

```python
"""Run provenance + FeatureContext minting for dataset export (Phase 3 slice 1b-B3).

Gathers the code/team/config fingerprint ONCE per run; mints a per-decision
FeatureContext with deterministic IDs (via the B2 ID helpers). No per-decision
git/subprocess calls.
"""

from __future__ import annotations

import hashlib
import json
import subprocess

from showdown_bot.learning.export import make_run_id, make_game_id, make_decision_id
from showdown_bot.learning.features import FeatureContext


def git_sha_and_dirty() -> tuple[str, bool]:
    """Current commit + dirty flag; ('unknown', False) if git is unavailable.
    Call ONCE at run start (not per decision)."""
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                             check=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain"], capture_output=True,
                                    text=True).stdout.strip())
        return sha or "unknown", dirty
    except Exception:  # noqa: BLE001
        return "unknown", False


def _sha16(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]


def team_hash(packed_team: str) -> str:
    return _sha16(packed_team or "")


def config_hash(config: dict) -> str:
    return _sha16(json.dumps(config, sort_keys=True, separators=(",", ":"), default=str))


def build_feature_context(
    *, git_sha: str, dirty_flag: bool, team_hash_: str, config_hash_: str, run_seed,
    game_index: int, decision_local_index: int, turn_number: int, our_side: str,
    format_id: str, mirror_flag: bool, teacher_config: dict, sampling_policy: str,
    dex=None, move_meta=None, speed_oracle=None, protect_priors_by_opp_slot=None,
) -> FeatureContext:
    run_id = make_run_id(git_sha, dirty_flag, team_hash_, config_hash_, run_seed)
    game_id = make_game_id(run_id, game_index)
    decision_id = make_decision_id(game_id, decision_local_index, turn_number, our_side)
    return FeatureContext(
        run_id=run_id, game_id=game_id, decision_id=decision_id,
        decision_local_index=decision_local_index, turn_number=turn_number, our_side=our_side,
        format_id=format_id, team_hash=team_hash_, config_hash=config_hash_, git_sha=git_sha,
        dirty_flag=dirty_flag, teacher_config=teacher_config, sampling_policy=sampling_policy,
        mirror_flag=mirror_flag, dex=dex, move_meta=move_meta, speed_oracle=speed_oracle,
        protect_priors_by_opp_slot=protect_priors_by_opp_slot,
    )
```

- [ ] **Step 4: run → PASS** + full suite (+2). **Step 5: commit** `feat(learning): provenance + deterministic FeatureContext minting`.

---

## Task 2: `export_driver.py` — sampling-gated trace→rows bridge

**Files:** Create `src/showdown_bot/learning/export_driver.py`; Test `tests/test_export_driver.py`.

- [ ] **Step 1: failing tests** (gates 4, 5, 6 — hermetic, reuse `decision_fixture` to populate a real trace)

```python
# tests/test_export_driver.py
import pytest
from showdown_bot.learning.export import DatasetExporter, SamplingPolicy
from showdown_bot.learning.export_driver import maybe_observe_decision


def _ctx_and_trace(decision_fixture):
    from showdown_bot.battle.decision import heuristic_choose_for_request
    from showdown_bot.battle.decision_trace import DecisionTrace
    from showdown_bot.learning.provenance import build_feature_context
    req, kw = decision_fixture
    tr = DecisionTrace()
    heuristic_choose_for_request(req, trace=tr, **kw)
    ctx = build_feature_context(
        git_sha="s", dirty_flag=False, team_hash_="t", config_hash_="c", run_seed=0,
        game_index=0, decision_local_index=0, turn_number=1, our_side=kw.get("our_side", "p1"),
        format_id="fmt", mirror_flag=False, teacher_config={"teacher_version": "stub-h0", "trainable_label": False},
        sampling_policy="all",
    )
    return tr, kw["state"], req, ctx


def test_sampled_decision_adds_rows(decision_fixture):
    tr, state, req, ctx = _ctx_and_trace(decision_fixture)
    exp = DatasetExporter(SamplingPolicy(policy="all"))
    n = maybe_observe_decision(exp, 0, ctx=ctx, trace=tr, state=state, request=req)
    assert n == len(tr.candidates) and len(exp.rows_for_test()) == n


def test_unsampled_decision_adds_nothing_and_skips_extract(decision_fixture, monkeypatch):
    tr, state, req, ctx = _ctx_and_trace(decision_fixture)
    import showdown_bot.learning.export_driver as drv
    called = {"n": 0}
    real = drv.extract_features
    monkeypatch.setattr(drv, "extract_features", lambda *a, **k: called.__setitem__("n", called["n"] + 1) or real(*a, **k))
    exp = DatasetExporter(SamplingPolicy(policy="every_nth", rate=2))
    assert maybe_observe_decision(exp, 1, ctx=ctx, trace=tr, state=state, request=req) == 0  # odd -> not sampled
    assert exp.rows_for_test() == [] and called["n"] == 0                                     # extract NOT called
    assert maybe_observe_decision(exp, 0, ctx=ctx, trace=tr, state=state, request=req) > 0     # even -> sampled
    assert called["n"] == 1


def test_added_rows_are_validated(decision_fixture):
    tr, state, req, ctx = _ctx_and_trace(decision_fixture)
    from showdown_bot.learning.schema import validate_row
    exp = DatasetExporter(SamplingPolicy(policy="all"))
    maybe_observe_decision(exp, 0, ctx=ctx, trace=tr, state=state, request=req)
    for row in exp.rows_for_test():
        validate_row(row)   # B2 add() already validated; re-assert
```

- [ ] **Step 2: run → FAIL.**

- [ ] **Step 3: implement `src/showdown_bot/learning/export_driver.py`**

```python
"""Sampling-gated bridge: a populated DecisionTrace -> schema Rows -> exporter.add.

Keeps the DatasetExporter dumb (it only ever sees finished Rows) and battle/ free of
export logic. The client calls this once per decision.
"""

from __future__ import annotations

from showdown_bot.learning.features import extract_features


def maybe_observe_decision(exporter, decision_index: int, *, ctx, trace, state, request) -> int:
    """If the exporter's SamplingPolicy includes ``decision_index``, extract one Row
    per candidate and add them (each validated by ``exporter.add``). Returns the row
    count (0 if the decision is not sampled — ``extract_features`` is then NOT called)."""
    if not exporter.sampling_policy.should_sample(decision_index):
        return 0
    rows = extract_features(trace, state, request, ctx)
    for row in rows:
        exporter.add(row)
    return len(rows)
```

- [ ] **Step 4: run → PASS** + full suite (+3). **Step 5: commit** `feat(learning): export_driver (sampling-gated trace->rows->exporter bridge)`.

---

## Task 3: `DatasetExportRuntime` seam + thin gauntlet hook + hermetic E2E

The gauntlet's live `_Client`/WebSocket loop is not hermetically testable, so the
hook logic lives in a small **seam** — `DatasetExportRuntime` — that is fully tested
without Node. `_Client` just holds one (or `None`) and calls `start_game` / `observe`
/ `flush`. No export logic in the client; no feature logic either.

**Files:** Create `src/showdown_bot/learning/export_runtime.py`; Test
`tests/test_export_runtime.py` + `tests/test_export_e2e.py`; Modify
`src/showdown_bot/client/gauntlet.py` (thin).

- [ ] **Step 1: seam tests** — `tests/test_export_runtime.py` (the 4th gate: the
  env-gated wiring is real-tested, not hand-smoked).

```python
# tests/test_export_runtime.py
import io
from showdown_bot.learning.export_runtime import DatasetExportRuntime


def test_runtime_from_env_off_is_none(monkeypatch):
    monkeypatch.delenv("SHOWDOWN_DATASET_EXPORT", raising=False)
    assert DatasetExportRuntime.from_env(format_id="fmt", packed_team="t", mirror_flag=False) is None


def test_runtime_from_env_on_initializes(monkeypatch, tmp_path):
    monkeypatch.setenv("SHOWDOWN_DATASET_EXPORT", str(tmp_path / "o.jsonl"))
    rt = DatasetExportRuntime.from_env(format_id="fmt", packed_team="packed", mirror_flag=True)
    assert rt is not None and rt.exporter is not None
    assert len(rt.config_hash_) == 16 and "/" not in rt.config_hash_   # path not in config_hash


def test_runtime_observe_calls_driver_once_and_increments(monkeypatch, tmp_path):
    monkeypatch.setenv("SHOWDOWN_DATASET_EXPORT", str(tmp_path / "o.jsonl"))
    import showdown_bot.learning.export_runtime as rtmod
    calls = []
    monkeypatch.setattr(rtmod, "maybe_observe_decision",
                        lambda exp, idx, **kw: calls.append(idx) or 1)
    rt = DatasetExportRuntime.from_env(format_id="fmt", packed_team="t", mirror_flag=False)
    rt.start_game(); rt.observe(trace=object(), state=object(), request=object(), turn_number=1, our_side="p1")
    rt.observe(trace=object(), state=object(), request=object(), turn_number=2, our_side="p1")
    assert calls == [0, 1]                       # GLOBAL sampling index, increments per decision
    assert rt._decision_local_index == 2         # per-game counter advanced
    rt.start_game()
    assert rt._decision_local_index == 0          # resets per game; sampling index does NOT
    rt.observe(trace=object(), state=object(), request=object(), turn_number=1, our_side="p1")
    assert calls == [0, 1, 2]                      # sampling index kept counting across games


def test_runtime_flush_writes(monkeypatch, tmp_path):
    p = tmp_path / "o.jsonl"
    monkeypatch.setenv("SHOWDOWN_DATASET_EXPORT", str(p))
    rt = DatasetExportRuntime.from_env(format_id="fmt", packed_team="t", mirror_flag=False)
    rt.flush()                                     # empty exporter -> writes an (empty) file, no crash
    assert p.exists()
```

- [ ] **Step 2: run → FAIL.** `cd showdown_bot && python -m pytest tests/test_export_runtime.py -q`

- [ ] **Step 3: implement `src/showdown_bot/learning/export_runtime.py`**

```python
"""The testable seam between the live client and the export pipeline (slice 1b-B3).

`_Client` holds one `DatasetExportRuntime` (or None) and calls start_game/observe/
flush. All env setup, provenance, counters, and the driver call live here so they can
be tested without Node/WebSocket.
"""

from __future__ import annotations

import os

from showdown_bot.learning.export import DatasetExporter, SamplingPolicy
from showdown_bot.learning.export_driver import maybe_observe_decision
from showdown_bot.learning.provenance import (
    build_feature_context, config_hash, git_sha_and_dirty, team_hash,
)

_HEURISTIC_KNOBS = (
    "SHOWDOWN_PROTECT_PENALTY", "SHOWDOWN_REAL_SPREADS", "SHOWDOWN_OPP_SETS",
    "SHOWDOWN_OPP_SPEED", "SHOWDOWN_MUST_REACT_LAMBDA", "SHOWDOWN_ROLLOUT_HORIZON",
)


class DatasetExportRuntime:
    def __init__(self, exporter, export_path, *, git_sha, dirty_flag, team_hash_,
                 config_hash_, run_seed, format_id, mirror_flag, sampling_policy_name,
                 dex=None, move_meta=None, protect_priors_by_opp_slot=None):
        self.exporter = exporter
        self.export_path = export_path
        self.git_sha = git_sha; self.dirty_flag = dirty_flag
        self.team_hash_ = team_hash_; self.config_hash_ = config_hash_
        self.run_seed = run_seed; self.format_id = format_id; self.mirror_flag = mirror_flag
        self.sampling_policy_name = sampling_policy_name
        self.teacher_config = {"teacher_version": "stub-h0", "trainable_label": False}
        self.dex = dex; self.move_meta = move_meta
        self.protect_priors_by_opp_slot = protect_priors_by_opp_slot
        self._game_index = -1            # first start_game -> 0
        self._decision_local_index = 0   # per-game (decision_id)
        self._sampling_decision_index = 0  # global run-level (SamplingPolicy)

    @classmethod
    def from_env(cls, *, format_id, packed_team, mirror_flag, dex=None, move_meta=None,
                 protect_priors_by_opp_slot=None):
        path = os.environ.get("SHOWDOWN_DATASET_EXPORT")
        if not path:
            return None                  # env off -> exporter stays None (gate: bit-identical)
        seed = int(os.environ.get("SHOWDOWN_DATASET_RUN_SEED", "0"))
        policy = os.environ.get("SHOWDOWN_DATASET_SAMPLE_POLICY", "all")
        rate = int(os.environ.get("SHOWDOWN_DATASET_SAMPLE_RATE", "1"))
        git_sha, dirty = git_sha_and_dirty()
        th = team_hash(packed_team)
        # config_hash = dataset-semantic config ONLY (NOT the output path)
        cfg = {"sample_policy": policy, "sample_rate": rate, "top_k": 6, "team_hash": th}
        cfg.update({k: os.environ.get(k) for k in _HEURISTIC_KNOBS})
        ch = config_hash(cfg)
        exp = DatasetExporter(SamplingPolicy(policy=policy, rate=rate, seed=seed))
        return cls(exp, path, git_sha=git_sha, dirty_flag=dirty, team_hash_=th, config_hash_=ch,
                   run_seed=seed, format_id=format_id, mirror_flag=mirror_flag,
                   sampling_policy_name=policy, dex=dex, move_meta=move_meta,
                   protect_priors_by_opp_slot=protect_priors_by_opp_slot)

    def start_game(self) -> None:
        self._game_index += 1
        self._decision_local_index = 0          # reset per game; sampling index does NOT reset

    def observe(self, *, trace, state, request, turn_number, our_side) -> int:
        ctx = build_feature_context(
            git_sha=self.git_sha, dirty_flag=self.dirty_flag, team_hash_=self.team_hash_,
            config_hash_=self.config_hash_, run_seed=self.run_seed, game_index=self._game_index,
            decision_local_index=self._decision_local_index, turn_number=turn_number, our_side=our_side,
            format_id=self.format_id, mirror_flag=self.mirror_flag, teacher_config=self.teacher_config,
            sampling_policy=self.sampling_policy_name, dex=self.dex, move_meta=self.move_meta,
            protect_priors_by_opp_slot=self.protect_priors_by_opp_slot)
        n = maybe_observe_decision(self.exporter, self._sampling_decision_index,
                                   ctx=ctx, trace=trace, state=state, request=request)
        self._decision_local_index += 1
        self._sampling_decision_index += 1       # GLOBAL: counts across all games
        return n

    def flush(self) -> None:
        self.exporter.flush_sorted(self.export_path)
```

- [ ] **Step 4: run seam tests → PASS** + full suite. **Commit** `feat(learning): DatasetExportRuntime (testable env-gated export seam, pinned counters)`.

- [ ] **Step 5: the hermetic learning E2E (gates 1, 2, 7)** — `tests/test_export_e2e.py`. No client, no Node: reuse `decision_fixture`, run the decision twice (trace=None and trace+export), assert identical choice + byte-identical JSONL.

```python
# tests/test_export_e2e.py
import io
from showdown_bot.battle.decision import heuristic_choose_for_request
from showdown_bot.battle.decision_trace import DecisionTrace
from showdown_bot.learning.export import DatasetExporter, SamplingPolicy
from showdown_bot.learning.export_driver import maybe_observe_decision
from showdown_bot.learning.provenance import build_feature_context


def _ctx(our_side):
    return build_feature_context(
        git_sha="s", dirty_flag=False, team_hash_="t", config_hash_="c", run_seed=0,
        game_index=0, decision_local_index=0, turn_number=1, our_side=our_side,
        format_id="fmt", mirror_flag=False, teacher_config={"teacher_version": "stub-h0", "trainable_label": False},
        sampling_policy="all")


def test_e2e_choice_identical_and_jsonl_byte_identical(decision_fixture):
    req, kw = decision_fixture
    our_side = kw.get("our_side", "p1")
    # gate 1: trace=None choice
    base = heuristic_choose_for_request(req, trace=None, **kw)

    def _run():
        tr = DecisionTrace()
        choice = heuristic_choose_for_request(req, trace=tr, **kw)
        exp = DatasetExporter(SamplingPolicy(policy="all"))
        maybe_observe_decision(exp, 0, ctx=_ctx(our_side), trace=tr, state=kw["state"], request=req)
        buf = io.StringIO(); exp.flush_sorted(buf)
        return choice, buf.getvalue()

    c1, j1 = _run()
    c2, j2 = _run()
    assert c1 == base          # gate 2: enabled choice == trace=None choice
    assert j1 != ""            # rows were produced
    assert j1 == j2            # gate 7: byte-identical across runs (same inputs)
```

- [ ] **Step 6: run the E2E** → green (proves the learning-side export path). `cd showdown_bot && python -m pytest tests/test_export_e2e.py -q`. Then commit `test(learning): hermetic trace->rows->JSONL export E2E`.

- [ ] **Step 7: thin gauntlet wiring (uses the seam — no logic here).** In `client/gauntlet.py`:
  - In `_Client.__init__`: `self._export = DatasetExportRuntime.from_env(format_id=self.format_id, packed_team=self.packed_team, mirror_flag=<mirror?>, dex=<self.dex if available else None>, move_meta=<MoveMeta map if available else None>)`. `from_env` returns `None` when the env knob is unset (so `self._export is None` = today's path).
  - Find where THIS client starts a battle (room init) → call `self._export.start_game()` if `self._export is not None`.
  - At the heuristic-decision call site (the `_choose` heuristic branch for this client): if `self._export is not None`, build `trace = DecisionTrace()`, pass `trace=trace` into `choose_with_fallback`, then `self._export.observe(trace=trace, state=state, request=req, turn_number=<state.turn or req-derived>, our_side=<our_side>)`. If `self._export is None`, pass `trace=None` (unchanged path).
  - On battle end / client shutdown: `if self._export is not None: self._export.flush()`.
  - **Guard:** with the env knob unset, `self._export is None` ⇒ every branch is skipped ⇒ runtime bit-identical to today. (Adapt the exact call site + the `dex`/`move_meta` handles to what `_Client`/`_choose` already build; pass `None` where a handle isn't in scope — `features.py` sentinels those, and speed is in the trace.)

- [ ] **Step 8: run full suite** `cd showdown_bot && python -m pytest -q`. The seam is hermetically tested (Step 1); the gauntlet wiring is thin + behind `self._export is not None`.

- [ ] **Step 9: commit** `feat(client): optional dataset-export hook in gauntlet via DatasetExportRuntime (env-gated, bit-identical when off)`.

---

## Optional manual smoke (NOT CI, NOT a gate)
With a local `node pokemon-showdown start --no-security` on :8000:
`SHOWDOWN_DATASET_EXPORT=/tmp/ds.jsonl python -m ... gauntlet --format gen9vgc2024regg` →
assert `/tmp/ds.jsonl` is written and every line passes `schema.validate_row`.

## Self-Review notes
- **7 gates + the seam gate mapped:** trace=None choice (E2E gate 1), enabled choice==base + rows (E2E gate 2), deterministic IDs/provenance (T1), should_sample per decision (T2), extract only when sampled (T2 monkeypatch), validate-on-add (T2 + B2), byte-identical JSONL (E2E gate 7), **+ the env-gated wiring (seam tests: env off→None, env on→init, observe→driver-once+increment, flush writes)**.
- **Counter semantics pinned:** `decision_local_index` per-game (decision_id), `sampling_decision_index` global run-level (the only one passed to `should_sample`), `game_index` per battle. Seam test asserts the global index keeps counting across `start_game` while the local one resets.
- **`config_hash` excludes the output path** (path ≠ dataset semantics); includes sampling + the relevant heuristic knobs + team_hash + top_k.
- **Layering held:** bridge = `export_driver`; seam = `export_runtime` (testable without Node); the client only holds the runtime + calls start_game/observe/flush; `battle/` unchanged; `DatasetExporter` stays dumb (Rows only).
- **`exporter=None` ⇒ bit-identical:** `from_env` returns `None` when the knob is unset ⇒ every hook branch is `if self._export is not None`-guarded ⇒ today's path.
- **This completes slice 1b** — `learning/` produces a real, validated, byte-identical dataset from real self-play decisions (stub label; the deeper teacher is slice 1c).
