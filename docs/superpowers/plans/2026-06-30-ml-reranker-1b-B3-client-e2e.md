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
`docs/superpowers/specs/2026-06-30-ml-reranker-1b-feature-extraction-export-design.md`.
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
- Create: `src/showdown_bot/learning/provenance.py`, `src/showdown_bot/learning/export_driver.py`.
- Modify (thin): `src/showdown_bot/client/gauntlet.py` (optional exporter hook).
- Test: `tests/test_provenance.py`, `tests/test_export_driver.py`, `tests/test_export_e2e.py`.

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
        format_id="fmt", mirror_flag=False, teacher_config={"teacher_version": "stub-h0"},
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

## Task 3: thin client hook (gauntlet) + the hermetic E2E

**Files:** Modify `src/showdown_bot/client/gauntlet.py` (thin); Test `tests/test_export_e2e.py`.

- [ ] **Step 1: the hermetic E2E test (gates 1, 2, 7)** — `tests/test_export_e2e.py`. No client, no Node: reuse `decision_fixture`, run the decision twice (trace=None and trace+export), assert identical choice + byte-identical JSONL.

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
        format_id="fmt", mirror_flag=False, teacher_config={"teacher_version": "stub-h0"},
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

- [ ] **Step 2: run → FAIL** (until the imports resolve — they exist after Tasks 1-2, so this mostly passes once written; confirm it runs green, which proves the learning-side E2E).

- [ ] **Step 3: thin gauntlet hook.** In `client/gauntlet.py`, add an OPTIONAL exporter, enabled by env knob `SHOWDOWN_DATASET_EXPORT` (a file path). Keep it thin — no feature/export logic here, only wiring:
  - In `_Client.__init__`: if `os.environ.get("SHOWDOWN_DATASET_EXPORT")`, gather provenance ONCE (`git_sha_and_dirty()`, `team_hash(self.packed_team)`, `config_hash(<env knob snapshot>)`), create `self._exporter = DatasetExporter(SamplingPolicy(...))`, set `self._export_path`, `self._game_index`, `self._decision_index = 0`; else `self._exporter = None`.
  - At the heuristic-decision call site (the `_choose` heuristic branch / where `choose_with_fallback` is invoked for this client): if `self._exporter is not None`, build `trace = DecisionTrace()`, pass `trace=trace`, then `ctx = build_feature_context(...; game_index=self._game_index, decision_local_index=self._decision_index, turn_number=<from state/req>, our_side=...; dex/move_meta/speed_oracle/protect_priors from the client's existing handles)` and `maybe_observe_decision(self._exporter, self._decision_index, ctx=ctx, trace=trace, state=state, request=req)`; `self._decision_index += 1`. If `self._exporter is None`, pass `trace=None` (unchanged path).
  - On battle end / client shutdown: `self._exporter.flush_sorted(self._export_path)` (append-safe: write once at end).
  - **Guard:** when `SHOWDOWN_DATASET_EXPORT` is unset, the code path is exactly today's (trace=None, no driver, no flush) → runtime bit-identical. (Adapt the exact call site + the `dex`/`move_meta`/`speed_oracle` handles to what `_Client`/`_choose` already build; if a handle isn't readily in scope, pass `None` — features.py already sentinels those, except speed which is now in the trace.)

- [ ] **Step 4: run the E2E + full suite.** `cd showdown_bot && python -m pytest tests/test_export_e2e.py -q` then `cd showdown_bot && python -m pytest -q`. The gauntlet hook is covered structurally (no Node test); the optional live smoke is below.

- [ ] **Step 5: commit** `feat(client): optional dataset-export hook in gauntlet (env-gated, exporter=None bit-identical) + E2E`.

---

## Optional manual smoke (NOT CI, NOT a gate)
With a local `node pokemon-showdown start --no-security` on :8000:
`SHOWDOWN_DATASET_EXPORT=/tmp/ds.jsonl python -m ... gauntlet --format gen9vgc2024regg` →
assert `/tmp/ds.jsonl` is written and every line passes `schema.validate_row`.

## Self-Review notes
- **7 gates mapped:** trace=None choice (E2E gate 1), enabled choice==base + rows (E2E gate 2), deterministic IDs/provenance (T1), should_sample per decision (T2), extract only when sampled (T2 monkeypatch), validate-on-add (T2 + B2), byte-identical JSONL (E2E gate 7).
- **Thin client, dumb exporter, export-free battle:** the bridge is `export_driver`; the client only wires; `battle/` unchanged.
- **`exporter=None` ⇒ bit-identical:** the hook is fully behind `if self._exporter is not None`; unset env knob = today's path.
- **This completes slice 1b** — `learning/` produces a real, validated, byte-identical dataset from real self-play decisions (stub label; the deeper teacher is slice 1c).
