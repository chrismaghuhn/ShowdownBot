# Phase 3 Slice 1d: Export-Swap (stub-h0 → real rollout teacher) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Swap the 1b export's `stub-h0` labels for REAL trainable counterfactual labels from
the 1c H-loop teacher, behind a `LabelProvider` seam — stub mode stays byte-identical, rollout
mode emits `trainable_label=true`.

**Architecture:** A `LabelProvider` Protocol (`StubLabelProvider` = today; `RolloutLabelProvider`
= 1c `rollout_labels`). `features.py` becomes label-agnostic (consumes a `labels` dict). The
`DatasetExportRuntime` owns the provider + one `calc` + the rollout deps + the skip counters.
`battle/` untouched; the `DatasetExporter` stays dumb.

**Tech Stack:** Python stdlib. Spec: `docs/superpowers/specs/2026-06-30-1d-export-swap-design.md`.
Reuses: `learning/rollout.py` (`rollout_labels`, `RolloutConfig`), `learning/belief_builder.py`
(`build_belief_for_side`/`build_opponent_belief`/`build_known_side`), `engine/belief/`
(`load_opp_sets_for_format`, `move_priors.load_move_priors_for_format`), and — for the deps
mirror — `engine.calc.client.CalcClient`, `battle.oracle.DamageOracle`, `engine.speed.SpeedOracle`
(exactly as `battle/decision.py:11/18/20,182-186`). Run tests from `showdown_bot/`.

**Grounded facts:** `LABEL_KEYS` (schema.py:55) == the 8 `label_decision` keys → 1:1; `validate_row`
enforces the exact set. `extract_features` (features.py:598) iterates `trace.candidates`, builds
`Row(features, _metadata(ctx,i), _stub_label())`; `_metadata` hardcodes `"stub-h0"` (581).
`rollout_labels` recoverable raises: rollout.py **250** (no opponent response), **237** (all-switch
R), **336** (chosen_candidate_id not in set); the weights raises **254/260** are integrity bugs →
stay `ValueError` (hard-fail). `config_hash(dict)` (provenance.py:39) = canonical-JSON sha1; extend
the `cfg` dict in `from_env`. `observe` already gets `our_side`(=root) + `request`(=known_team).

---

## File Structure
- Create: `learning/label_provider.py` — `LabelProvider` Protocol, `StubLabelProvider`,
  `RolloutLabelProvider`.
- Modify: `learning/features.py` — `extract_features(..., *, labels)` label-agnostic +
  `_validate_label_prefix`; `_metadata` reads `teacher_version` from `ctx.teacher_config`.
- Modify: `learning/rollout.py` — define `RolloutLabelError`; classify the 3 recoverable raises.
- Modify: `learning/export_driver.py` — `maybe_observe_decision` takes precomputed `labels`.
- Modify: `learning/export_runtime.py` — owns provider + calc/deps + skip counters + threshold +
  `config_hash` extension; `from_env(mode)`.
- Modify: `client/gauntlet.py` — thread `calc/book/our_spreads/opp_sets/dex/move_meta` into `from_env`.
- Tests: `tests/test_label_provider.py`, `tests/test_export_rollout_e2e.py`, plus additions to the
  existing export tests.

---

## Task 1d-1: LabelProvider seam + StubLabelProvider + label-agnostic extract_features

**Files:** Create `learning/label_provider.py`; Modify `learning/features.py`; Test
`tests/test_label_provider.py` + the existing `tests/test_features*.py`/export tests.

- [ ] **Step 1: failing tests**

```python
# tests/test_label_provider.py
from showdown_bot.learning.label_provider import StubLabelProvider, _validate_label_prefix
from showdown_bot.learning.schema import LABEL_KEYS


def test_stub_provider_teacher_config():
    p = StubLabelProvider()
    assert p.teacher_config() == {"teacher_version": "stub-h0", "trainable_label": False}


def test_stub_provider_labels_all_candidates(trace_fixture):
    p = StubLabelProvider()
    labels = p.labels_for_decision(trace_fixture, None, None, context=None)
    assert set(labels) == {c.candidate_id for c in trace_fixture.candidates}
    for lab in labels.values():
        assert set(lab) == set(LABEL_KEYS)        # exact key set
        assert all(v == 0 for v in lab.values())  # zeroed (byte-identical to today)


def test_validate_label_prefix_rejects_holey_set(trace_fixture):
    # labels for candidate 0 and 2 but not 1 -> a holey ranking -> reject
    ids = [c.candidate_id for c in trace_fixture.candidates]
    holey = {ids[0]: {}, ids[2]: {}} if len(ids) >= 3 else {}
    import pytest
    with pytest.raises(ValueError):
        _validate_label_prefix(trace_fixture, holey)


def test_validate_label_prefix_rejects_empty_for_nonempty_trace(trace_fixture):
    import pytest
    with pytest.raises(ValueError):
        _validate_label_prefix(trace_fixture, {})   # empty labels for a non-empty trace -> reject


def test_stub_row_metadata_teacher_version(trace_fixture, stub_ctx):
    # PIN: row metadata teacher_version comes from ctx.teacher_config (NOT hardcoded), and
    # ctx.teacher_config is the provider's. Stub -> "stub-h0" / trainable_label False.
    from showdown_bot.learning.features import extract_features
    from showdown_bot.learning.label_provider import StubLabelProvider
    p = StubLabelProvider()
    labels = p.labels_for_decision(trace_fixture, None, None, context=stub_ctx)
    rows = extract_features(trace_fixture, <state>, <request>, stub_ctx, labels=labels)
    assert all(r.metadata["teacher_version"] == "stub-h0" for r in rows)
    assert all(r.metadata["teacher_config"]["trainable_label"] is False for r in rows)
```
(`stub_ctx` is a FeatureContext whose `teacher_config == StubLabelProvider().teacher_config()`,
mirroring how the runtime sets `ctx.teacher_config = provider.teacher_config()`.)
Plus a gate in the export tests: the existing byte-identical-JSONL / stub-export test must stay
green when `extract_features` is called through the new `labels=` path with a `StubLabelProvider`.

- [ ] **Step 2: run → FAIL.** `cd showdown_bot && python -m pytest tests/test_label_provider.py -q`

- [ ] **Step 3: implement**
  - `learning/label_provider.py`:
```python
from __future__ import annotations
from typing import Protocol
from showdown_bot.learning.schema import LABEL_KEYS


class LabelProvider(Protocol):
    def teacher_config(self) -> dict: ...
    def labels_for_decision(self, trace, state, request, *, context) -> dict: ...


def _validate_label_prefix(trace, labels: dict) -> None:
    """The labeled set must be exactly the first len(labels) candidates, in trace order.
    An EMPTY label dict for a non-empty trace is invalid — a 'no labels possible' situation
    must surface as RolloutLabelError on the rollout path, never as a silent 0-row export."""
    if trace.candidates and not labels:
        raise ValueError("labels must not be empty for a non-empty trace")
    expected = [c.candidate_id for c in trace.candidates[: len(labels)]]
    if list(labels.keys()) != expected:
        raise ValueError("labels must be a candidate prefix in trace order")


class StubLabelProvider:
    def teacher_config(self) -> dict:
        return {"teacher_version": "stub-h0", "trainable_label": False}

    def labels_for_decision(self, trace, state, request, *, context) -> dict:
        zero = {k: 0 for k in LABEL_KEYS}
        return {c.candidate_id: dict(zero) for c in trace.candidates}
```
  - `features.py`: change `extract_features(trace, state, request, context)` →
    `extract_features(trace, state, request, context, *, labels)`. Call `_validate_label_prefix(
    trace, labels)`. Emit one Row per `cand in trace.candidates` **whose `candidate_id in labels`**
    (in trace order), `label=labels[cand.candidate_id]`, `candidate_index=i`. In `_metadata`,
    replace the hardcoded `"teacher_version": "stub-h0"` with `ctx.teacher_config["teacher_version"]`
    (the run-level teacher_config already flows via ctx). Remove `_stub_label()` usage from
    `extract_features` (the provider owns labels now; keep the helper only if a test needs it).
  - Update the one current caller `export_driver.maybe_observe_decision` to pass
    `labels=StubLabelProvider().labels_for_decision(trace, state, request, context=ctx)` FOR NOW
    (1d-3 swaps in the real provider + the runtime path).

- [ ] **Step 4: run → PASS** + full suite. **GATE: stub mode byte-identical** — the existing
  export E2E (byte-identical JSONL, `exporter=None` bit-identical) MUST stay green. `LABEL_KEYS`
  exactly validated by `validate_row`. **Step 5: commit** `feat(learning): LabelProvider seam + StubLabelProvider; extract_features label-agnostic + prefix validation`.

---

## Task 1d-2: RolloutLabelProvider + RolloutLabelError + deps mirror

**Files:** Modify `learning/rollout.py` (define `RolloutLabelError` + classify raises),
`learning/label_provider.py` (add `RolloutLabelProvider`); Test `tests/test_label_provider.py`.

- [ ] **Step 1: explore** — read `learning/rollout.py` raises at lines 237/250/336 (recoverable)
  vs 254/260 (integrity); `rollout_labels`' signature (`*, root_our_side, roster_by_side,
  movesets_by_side, stats_by_side, move_meta, deps, cfg`); `learning/decide_adapter.py`
  `_CORE_DEP_KEYS`/`_core_deps` (what the rollout's `decide` needs in `deps`); and
  `battle/decision.py:182-186` for the EXACT deps construction to mirror.

- [ ] **Step 2: failing tests**

```python
def test_rollout_provider_teacher_config():
    from showdown_bot.learning.label_provider import RolloutLabelProvider
    from showdown_bot.learning.rollout import RolloutConfig
    p = RolloutLabelProvider(deps=<deps>, likely_sets={}, move_priors={}, cfg=RolloutConfig(H=4))
    tc = p.teacher_config()
    assert tc["teacher_version"] == "rollout-h4-v1" and tc["trainable_label"] is True
    assert "rollout_config" in tc


def test_rollout_provider_labels_topk(rollout_decision_fixture):
    # belief built internally; labels keyed by candidate_id for the top-K prefix; exact LABEL_KEYS
    p = RolloutLabelProvider(...)
    labels = p.labels_for_decision(trace, state, request, context=ctx)
    assert labels and all(set(v) == set(LABEL_KEYS) for v in labels.values())


def test_no_opponent_responses_raises_rollout_label_error(empty_R_fixture):
    from showdown_bot.learning.rollout import RolloutLabelError
    import pytest
    with pytest.raises(RolloutLabelError):
        RolloutLabelProvider(...).labels_for_decision(trace_no_responses, state, request, context=ctx)


def test_weights_integrity_stays_hard_fail():
    # a malformed-weights trace raises plain ValueError (NOT RolloutLabelError) -> hard-fail
    ...
```

- [ ] **Step 3: implement**
  - `rollout.py`: add `class RolloutLabelError(Exception): ...`. Change the recoverable raises
    (line 250 no-response, 237 all-switch, 336 chosen-not-in-set) to `raise RolloutLabelError(...)`.
    LEAVE 254/260 (weights length/sum) as `ValueError` (integrity bug → hard-fail). Existing 1c
    rollout tests that asserted `ValueError` on the recoverable cases must be updated to
    `RolloutLabelError` (it subclasses nothing special; update those asserts).
  - `label_provider.py` `RolloutLabelProvider`:
```python
class RolloutLabelProvider:
    def __init__(self, *, deps, likely_sets, move_priors, cfg, speed_oracle=None):
        self._deps = deps; self._likely_sets = likely_sets
        self._move_priors = move_priors; self._cfg = cfg; self._speed_oracle = speed_oracle

    def teacher_config(self) -> dict:
        return {"teacher_version": f"rollout-h{self._cfg.H}-v1", "trainable_label": True,
                "rollout_config": {"H": self._cfg.H, "gamma": self._cfg.gamma,
                                   "top_k": self._cfg.top_k, "use_leaf": self._cfg.use_leaf}}

    def labels_for_decision(self, trace, state, request, *, context) -> dict:
        from showdown_bot.learning.rollout import rollout_labels
        from showdown_bot.learning.belief_builder import build_known_side, build_opponent_belief
        root = context.our_side
        opp = "p2" if root == "p1" else "p1"
        us = build_known_side(request.side.pokemon)
        them = build_opponent_belief(state, opp, likely_sets=self._likely_sets,
                                     move_priors=self._move_priors, speed_oracle=self._speed_oracle)
        roster = {root: us.roster, opp: them.roster}
        movesets = {root: us.movesets, opp: them.movesets}
        stats = {root: us.stats, opp: them.stats}
        return rollout_labels(trace, state, root_our_side=root, roster_by_side=roster,
                              movesets_by_side=movesets, stats_by_side=stats,
                              move_meta=self._deps["move_meta"], deps=self._deps, cfg=self._cfg)
        # rollout_labels raises RolloutLabelError on recoverable failure -> caller (runtime) skips.
```
  Ground `request.side.pokemon`, `context.our_side`, and the exact `deps` keys against
  `_core_deps`/`make_resolve`. The `deps` are assembled by the runtime (1d-3) mirroring
  `decision.py`; here the provider just consumes them.

- [ ] **Step 4: run + full suite** (update the 1c rollout tests' recoverable asserts to
  `RolloutLabelError`). **Step 5: commit** `feat(learning): RolloutLabelProvider + RolloutLabelError (narrow recoverable taxonomy)`.

---

## Task 1d-3: Runtime / gauntlet wiring + config_hash + hermetic E2E

**Files:** Modify `learning/export_driver.py`, `learning/export_runtime.py`,
`client/gauntlet.py`; Test `tests/test_export_rollout_e2e.py` + existing runtime tests.

- [ ] **Step 1: failing E2E test** (`tests/test_export_rollout_e2e.py`)

```python
def test_rollout_mode_emits_trainable_labels(tmp_path, monkeypatch, gauntlet_decision_fixture):
    # env: SHOWDOWN_DATASET_EXPORT + SHOWDOWN_DATASET_TEACHER=rollout
    # build a DatasetExportRuntime.from_env in rollout mode with a fake calc/book deps bundle;
    # observe a real (trace,state,request); flush; read JSONL.
    # ASSERT: each row metadata teacher_version == "rollout-h{H}-v1", teacher_config.trainable_label True.
    ...


def test_stub_mode_byte_identical(tmp_path, monkeypatch):
    # SHOWDOWN_DATASET_TEACHER unset/stub -> identical bytes to the pre-1d stub export golden.
    ...


def test_rollout_skip_increments_counter_no_rows(...):
    # a decision whose rollout raises RolloutLabelError -> 0 rows + runtime.skipped_count == 1.


def test_skip_rate_above_threshold_hard_fails(...):
    # >5% skips after >=20 sampled -> flush() (or observe) raises RuntimeError.


def test_exporter_none_bit_identical(...):
    # SHOWDOWN_DATASET_EXPORT unset -> from_env None -> choice path unchanged.
```

- [ ] **Step 2: implement**
  - `export_driver.maybe_observe_decision(exporter, *, ctx, trace, state, request, labels) -> int`:
    drop the internal sampling check (moves to the runtime), `_validate`-and-`extract_features(
    trace, state, request, ctx, labels=labels)`, add rows, return count.
  - `export_runtime.py`:
    - `__init__` takes `provider` + the rollout deps bundle (`calc`, `book`, `our_spreads`,
      `opp_sets`, `likely_sets`, `move_priors`, `cfg`); `self.teacher_config = provider.teacher_config()`;
      counters `self.sampled_count = 0`, `self.skipped_count = 0`; thresholds
      `self.max_skip_rate = 0.05`, `self.min_sampled = 20`.
    - `from_env(..., mode=os.environ.get("SHOWDOWN_DATASET_TEACHER","stub"))`: if `"rollout"`,
      build ONE `calc=CalcClient()`, `deps={"book":book,"oracle":DamageOracle(calc),
      "speed_oracle":SpeedOracle(stats_backend=calc.backend),"our_spreads":our_spreads,
      "opp_sets":opp_sets,"dex":dex,"move_meta":move_meta, ...full _core_deps...}` (MIRROR
      decision.py:182-186 — pin with a review note), `cfg=RolloutConfig(H=<env>)`, load
      `likely_sets`/`move_priors` for the format; `provider=RolloutLabelProvider(deps=deps,
      likely_sets=..., move_priors=..., cfg=cfg, speed_oracle=deps["speed_oracle"])`. Else
      `provider=StubLabelProvider()`. **Extend the `cfg` dict** that feeds `config_hash` with
      `rollout_config` (H/γ/top_k/use_leaf) + a `move_priors` hash + a `likely_sets` hash. PIN the
      hash method = **canonical loaded dict** (semantic, normalized belief-config), matching the
      existing `config_hash(dict)` principle — NOT file path / YAML whitespace / key order:
      `_sha16(json.dumps(loaded_dict, sort_keys=True, separators=(",",":"), default=str))` (reuse
      provenance's `_sha16`); so `cfg["move_priors_hash"]`, `cfg["likely_sets_hash"]`,
      `cfg["rollout_config"]`.
    - `observe`: build ctx with `teacher_config=self.teacher_config`; if sampled
      (`should_sample`), `self.sampled_count += 1`, then
      `try: labels = self.provider.labels_for_decision(trace, state, request, context=ctx)`
      `except RolloutLabelError: self.skipped_count += 1; log; self._check_threshold(); return 0`;
      else `maybe_observe_decision(..., labels=labels)`. **Only `RolloutLabelError` is caught** —
      every other exception propagates (hard-fail). `_check_threshold`: if
      `sampled_count >= min_sampled and skipped_count/sampled_count > max_skip_rate: raise RuntimeError`.
  - `gauntlet.py`: pass `calc/book/our_spreads/opp_sets/dex/move_meta` into `from_env` (today
    `dex=None, move_meta=None`; `self.book/our_spreads/opp_sets` exist on the client).

- [ ] **Step 3: run → PASS** + full suite. **Hard gates:** stub byte-identical · rollout
  `trainable_label=true`+`rollout-h{H}-v1` · skip→0 rows+counter · no silent stub fallback ·
  over-threshold hard-fail · wrong LABEL_KEYS hard-fail (validate_row) · `exporter=None`
  bit-identical · `battle/` still no `learning/` import (grep gate). **Step 4: commit**
  `feat(learning,client): wire RolloutLabelProvider into runtime (mode env, calc/deps, config_hash, skip threshold) + E2E`.

---

## Self-Review notes
- **Spec coverage:** seam+StubProvider+label-agnostic (1d-1); RolloutProvider+RolloutLabelError+
  deps mirror (1d-2); runtime mode/threading/config_hash/threshold + E2E (1d-3). The 3 review pins
  (prefix validation, `ctx.teacher_config==provider.teacher_config()`, skip-state in runtime) land
  in 1d-1 / 1d-3 / 1d-3.
- **Byte-identical stub:** `StubLabelProvider` reproduces today's all-zero labels + `stub-h0`
  exactly; the prefix rule emits ALL candidates in stub mode.
- **No silent stub fallback:** the runtime catches ONLY `RolloutLabelError` and emits zero rows;
  it never substitutes a stub label in rollout mode.
- **Deps mirror is explicit** (decision.py:182-186), pinned by a review note + the E2E using the
  same construction.
- **Non-goals:** no model/training/reranker/push; no `battle/→learning/` import; exporter dumb;
  stub mode valid; teacher only in runtime/provider layer.
- **Ground in execution:** exact `_core_deps` key set for the rollout `deps`; the `move_priors`/
  `likely_sets` hash = canonical loaded dict (`_sha16(json.dumps(...,sort_keys=True,default=str))`);
  `CalcClient` cost under SamplingPolicy (one-build-reuse; measure, not correctness).
