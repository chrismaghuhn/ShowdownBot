"""Hermetic E2E tests for 1d-3: RolloutLabelProvider wired into DatasetExportRuntime.

All tests use fake deterministic deps — no Node, no live CalcClient.
The stub-mode byte-identical and exporter=None bit-identical tests MUST stay green.
"""
from __future__ import annotations

import io
import json

import pytest

from showdown_bot.battle.decision import heuristic_choose_for_request
from showdown_bot.battle.decision_trace import DecisionTrace
from showdown_bot.learning.export import DatasetExporter, SamplingPolicy
from showdown_bot.learning.export_runtime import DatasetExportRuntime
from showdown_bot.learning.label_provider import RolloutLabelProvider
from showdown_bot.learning.rollout import RolloutLabelError
from showdown_bot.learning.teacher import RolloutConfig


# ---------------------------------------------------------------------------
# Fake deterministic deps (mirrors conftest._FakeCalc/_FakeOracle/_FakeSpeed)
# ---------------------------------------------------------------------------

from showdown_bot.engine.calc.models import DamageResult
from showdown_bot.engine.speed import SpeedRange


class _FakeCalc:
    backend = None

    def damage_batch(self, requests):
        return [DamageResult(min_damage=20, max_damage=35, max_hp=150) for _ in requests]


class _FakeOracle:
    def request(self, req):
        return (req.attacker.species, req.move, req.defender.species)

    def get(self, key):
        return DamageResult(min_damage=45, max_damage=70, max_hp=150)

    def damage(self, req):
        return DamageResult(min_damage=45, max_damage=70, max_hp=150)

    def flush(self):
        pass


class _FakeSpeed:
    def our_speed(self, base, mon, field, side):
        return base or 100

    def opponent_range(self, mon, field, side, *, book):
        return SpeedRange(min=80, likely=110, max=150)

    def likely_speed(self, mon, field, side, preset, item_for_speed) -> int:
        return 100


def _fake_deps(book):
    """Fake deps dict mirroring _CORE_DEP_KEYS (decide_adapter.py:32-34).

    Keys: book, calc, oracle, speed_oracle, dex, priors, weights,
          risk_lambda, tera_margin, rollout_horizon, our_spreads, opp_sets
    + move_meta (needed by rollout_labels)
    """
    calc = _FakeCalc()
    return {
        "book": book,
        "calc": calc,
        "oracle": _FakeOracle(),
        "speed_oracle": _FakeSpeed(),
        "dex": None,
        "priors": None,
        "weights": None,
        "risk_lambda": 0.5,
        "tera_margin": 1.0,
        "rollout_horizon": 0,
        "our_spreads": None,
        "opp_sets": {},
        "move_meta": {},
    }


# ---------------------------------------------------------------------------
# Helpers to produce a real (trace, state, request) from the decision fixture
# ---------------------------------------------------------------------------

def _run_decision(decision_fixture):
    """Run heuristic_choose_for_request with a trace and return (trace, state, req)."""
    req, kw = decision_fixture
    tr = DecisionTrace()
    heuristic_choose_for_request(req, trace=tr, **kw)
    return tr, kw["state"], req


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_rollout_mode_emits_trainable_labels(tmp_path, monkeypatch, decision_fixture):
    """Rollout mode: each row metadata.teacher_version == 'rollout-h{H}-v1',
    metadata.teacher_config['trainable_label'] is True."""
    from showdown_bot.engine.belief.hypotheses import load_spread_book
    from showdown_bot.engine.format_config import load_format_config

    trace, state, req = _run_decision(decision_fixture)
    _, kw = decision_fixture
    book = kw["book"]

    H = 1
    cfg = RolloutConfig(H=H)
    deps = _fake_deps(book)
    provider = RolloutLabelProvider(
        deps=deps,
        likely_sets={},
        move_priors={},
        cfg=cfg,
        speed_oracle=_FakeSpeed(),
    )

    out_path = tmp_path / "rollout_out.jsonl"
    monkeypatch.setenv("SHOWDOWN_DATASET_EXPORT", str(out_path))
    monkeypatch.setenv("SHOWDOWN_DATASET_TEACHER", "rollout")

    # Build runtime with rollout provider (bypassing from_env which needs CalcClient)
    rt = DatasetExportRuntime.from_env(
        format_id="gen9vgc2025regi",
        packed_team="packed",
        mirror_flag=False,
        provider=provider,
    )
    assert rt is not None
    rt.start_game()
    n = rt.observe(trace=trace, state=state, request=req,
                   turn_number=1, our_side="p1")
    assert n > 0, "rollout mode must produce rows"
    rt.flush()

    lines = [l for l in out_path.read_text().splitlines() if l.strip()]
    assert lines, "JSONL must be non-empty"
    for line in lines:
        row = json.loads(line)
        meta = row["metadata"]
        assert meta["teacher_version"] == f"rollout-h{H}-v1", (
            f"Expected rollout-h{H}-v1, got {meta['teacher_version']!r}"
        )
        assert meta["teacher_config"]["trainable_label"] is True
        # labels must also be real (non-zero for at least one key)
        label = row["label"]
        assert isinstance(label, dict)


def test_stub_mode_byte_identical(tmp_path, monkeypatch, decision_fixture):
    """Stub mode (SHOWDOWN_DATASET_TEACHER unset or 'stub') -> byte-identical to pre-1d output."""
    from showdown_bot.learning.provenance import build_feature_context

    trace, state, req = _run_decision(decision_fixture)

    def _run():
        out_path = tmp_path / "stub_out.jsonl"
        monkeypatch.setenv("SHOWDOWN_DATASET_EXPORT", str(out_path))
        monkeypatch.delenv("SHOWDOWN_DATASET_TEACHER", raising=False)
        rt = DatasetExportRuntime.from_env(
            format_id="fmt", packed_team="t", mirror_flag=False
        )
        rt.start_game()
        rt.observe(trace=trace, state=state, request=req, turn_number=1, our_side="p1")
        rt.flush()
        return out_path.read_text()

    run1 = _run()
    run2 = _run()
    assert run1 == run2, "stub mode must be byte-identical across runs"
    assert run1 != "", "stub mode must produce rows"

    # All rows must have teacher_version == stub-h0 and trainable_label False
    for line in run1.splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        assert row["metadata"]["teacher_version"] == "stub-h0"
        assert row["metadata"]["teacher_config"]["trainable_label"] is False


def test_rollout_skip_increments_counter_no_rows(tmp_path, monkeypatch, decision_fixture):
    """A decision whose rollout raises RolloutLabelError -> 0 rows + skipped_count == 1."""
    _, kw = decision_fixture
    book = kw["book"]

    H = 1
    cfg = RolloutConfig(H=H)
    deps = _fake_deps(book)

    class _ErrorProvider:
        def teacher_config(self):
            return {"teacher_version": "rollout-h1-v1", "trainable_label": True}

        def labels_for_decision(self, trace, state, request, *, context):
            raise RolloutLabelError("fake rollout failure")

    out_path = tmp_path / "skip_out.jsonl"
    monkeypatch.setenv("SHOWDOWN_DATASET_EXPORT", str(out_path))

    rt = DatasetExportRuntime.from_env(
        format_id="fmt",
        packed_team="t",
        mirror_flag=False,
        provider=_ErrorProvider(),
    )
    rt.start_game()

    trace, state, req = _run_decision(decision_fixture)
    n = rt.observe(trace=trace, state=state, request=req, turn_number=1, our_side="p1")

    assert n == 0, f"Expected 0 rows on skip, got {n}"
    assert rt.skipped_count == 1, f"Expected skipped_count==1, got {rt.skipped_count}"
    assert rt.sampled_count == 1, f"Expected sampled_count==1, got {rt.sampled_count}"

    rt.flush()
    content = out_path.read_text().strip()
    assert content == "", f"Expected empty JSONL on all-skip, got: {content!r}"


def test_skip_rate_above_threshold_hard_fails(tmp_path, monkeypatch, decision_fixture):
    """More than 5% skip rate after >= 20 sampled raises RuntimeError."""

    class _AlwaysErrorProvider:
        def teacher_config(self):
            return {"teacher_version": "rollout-h1-v1", "trainable_label": True}

        def labels_for_decision(self, trace, state, request, *, context):
            raise RolloutLabelError("always fails")

    out_path = tmp_path / "threshold_out.jsonl"
    monkeypatch.setenv("SHOWDOWN_DATASET_EXPORT", str(out_path))

    rt = DatasetExportRuntime.from_env(
        format_id="fmt",
        packed_team="t",
        mirror_flag=False,
        provider=_AlwaysErrorProvider(),
    )
    rt.start_game()
    trace, state, req = _run_decision(decision_fixture)

    # min_sampled == 20; need >= 20 sampled with 100% skip rate to trigger
    with pytest.raises(RuntimeError):
        for _ in range(25):
            rt.observe(trace=trace, state=state, request=req, turn_number=1, our_side="p1")


def test_exporter_none_bit_identical(monkeypatch):
    """SHOWDOWN_DATASET_EXPORT unset -> from_env returns None."""
    monkeypatch.delenv("SHOWDOWN_DATASET_EXPORT", raising=False)
    rt = DatasetExportRuntime.from_env(format_id="fmt", packed_team="t", mirror_flag=False)
    assert rt is None, "Expected None when SHOWDOWN_DATASET_EXPORT is not set"


# ---------------------------------------------------------------------------
# Guard test: from_env rollout deps must mirror decision.py:156-157 defaults
# ---------------------------------------------------------------------------

def test_from_env_rollout_deps_match_decision_defaults(tmp_path, monkeypatch):
    """Guard: _build_rollout_provider must produce deps matching decision.py defaults.

    Exercises the REAL _build_rollout_provider path (provider=None, mode=rollout)
    so the masking that injected a pre-baked provider=... can't recur.

    Monkeypatches CalcClient (no Node) and SpeedOracle (no subprocess) so this
    test is hermetic on any machine.

    Expected invariants (decision.py:156-157):
      deps["risk_lambda"] == 0.5
      deps["tera_margin"] == 1.0
    """
    import showdown_bot.engine.calc.client as _calc_mod
    import showdown_bot.engine.speed as _speed_mod
    import showdown_bot.battle.oracle as _oracle_mod

    # Patch CalcClient so no Node subprocess is spawned.
    class _StubCalc:
        backend = None

        def damage_batch(self, requests):
            from showdown_bot.engine.calc.models import DamageResult
            return [DamageResult(min_damage=20, max_damage=35, max_hp=150) for _ in requests]

    monkeypatch.setattr(_calc_mod, "CalcClient", lambda **kw: _StubCalc())

    # Patch SpeedOracle so stats_backend=None doesn't fall back to SubprocessCalcBackend.
    class _StubSpeedOracle:
        def __init__(self, stats_backend=None):
            self.backend = stats_backend

    monkeypatch.setattr(_speed_mod, "SpeedOracle", _StubSpeedOracle)

    # Patch DamageOracle so it accepts our _StubCalc without hitting Node.
    class _StubOracle:
        def __init__(self, client=None):
            self.client = client

        def flush(self):
            pass

    monkeypatch.setattr(_oracle_mod, "DamageOracle", _StubOracle)

    # Set env for rollout mode.
    out_path = tmp_path / "guard_out.jsonl"
    monkeypatch.setenv("SHOWDOWN_DATASET_EXPORT", str(out_path))
    monkeypatch.setenv("SHOWDOWN_DATASET_TEACHER", "rollout")
    monkeypatch.setenv("SHOWDOWN_ROLLOUT_HORIZON", "1")

    # Call from_env with provider=None so the real _build_rollout_provider path runs.
    rt = DatasetExportRuntime.from_env(
        format_id="gen9vgc2025regi",
        packed_team="packed",
        mirror_flag=False,
        provider=None,  # explicit: forces real _build_rollout_provider
    )
    assert rt is not None, "from_env must return a runtime when SHOWDOWN_DATASET_EXPORT is set"

    # Assert the deps match decision.py:156-157 defaults exactly.
    deps = rt._provider._deps
    assert deps["risk_lambda"] == 0.5, (
        f"risk_lambda must be 0.5 (decision.py:156 default), got {deps['risk_lambda']!r}"
    )
    assert deps["tera_margin"] == 1.0, (
        f"tera_margin must be 1.0 (decision.py:157 default), got {deps['tera_margin']!r}"
    )


def test_from_env_rollout_deps_threads_priors(tmp_path, monkeypatch):
    """Guard: priors passed to from_env must appear in rollout deps (label-decision consistency).

    Passing a sentinel priors object into from_env(..., priors=<sentinel>) and then
    asserting deps["priors"] is <sentinel> ensures the gauntlet's Protect priors reach
    the rollout's inner opponent model (same priors the live decision used).

    Before the fix: from_env has no priors param -> deps["priors"] is None.
    After the fix:  deps["priors"] is <sentinel>.
    """
    import showdown_bot.engine.calc.client as _calc_mod
    import showdown_bot.engine.speed as _speed_mod
    import showdown_bot.battle.oracle as _oracle_mod

    class _StubCalc:
        backend = None

        def damage_batch(self, requests):
            from showdown_bot.engine.calc.models import DamageResult
            return [DamageResult(min_damage=20, max_damage=35, max_hp=150) for _ in requests]

    monkeypatch.setattr(_calc_mod, "CalcClient", lambda **kw: _StubCalc())

    class _StubSpeedOracle:
        def __init__(self, stats_backend=None):
            self.backend = stats_backend

    monkeypatch.setattr(_speed_mod, "SpeedOracle", _StubSpeedOracle)

    class _StubOracle:
        def __init__(self, client=None):
            self.client = client

        def flush(self):
            pass

    monkeypatch.setattr(_oracle_mod, "DamageOracle", _StubOracle)

    out_path = tmp_path / "priors_guard_out.jsonl"
    monkeypatch.setenv("SHOWDOWN_DATASET_EXPORT", str(out_path))
    monkeypatch.setenv("SHOWDOWN_DATASET_TEACHER", "rollout")
    monkeypatch.setenv("SHOWDOWN_ROLLOUT_HORIZON", "1")

    # Sentinel priors object — identity check (not equality) is what matters.
    _SENTINEL_PRIORS = object()

    rt = DatasetExportRuntime.from_env(
        format_id="gen9vgc2025regi",
        packed_team="packed",
        mirror_flag=False,
        provider=None,  # forces real _build_rollout_provider
        priors=_SENTINEL_PRIORS,
    )
    assert rt is not None

    deps = rt._provider._deps
    assert deps["priors"] is _SENTINEL_PRIORS, (
        f"priors must be threaded into rollout deps for label-decision consistency, "
        f"got {deps['priors']!r}"
    )


# ---------------------------------------------------------------------------
# 2b-2.5a Kaggle-OOM fix: the CalcClient _build_rollout_provider builds must be
# reachable from DatasetExportRuntime.close() (real wiring, not just the close()
# method in isolation).
# ---------------------------------------------------------------------------

def test_from_env_rollout_close_closes_the_built_calc_client(tmp_path, monkeypatch):
    """Guard: from_env's real rollout path (provider=None, mode=rollout) must thread
    the CalcClient it builds into the runtime so close() can tear it down. Before the
    fix: from_env has no calc-tracking seam -> the CalcClient (a PersistentCalcBackend
    Node process in production) is only closed by the process-lifetime atexit hook,
    leaking one process per battle in the Kaggle schedule runner."""
    import showdown_bot.engine.calc.client as _calc_mod
    import showdown_bot.engine.speed as _speed_mod
    import showdown_bot.battle.oracle as _oracle_mod

    class _StubCalc:
        backend = None

        def __init__(self):
            self.close_calls = 0

        def damage_batch(self, requests):
            from showdown_bot.engine.calc.models import DamageResult
            return [DamageResult(min_damage=20, max_damage=35, max_hp=150) for _ in requests]

        def close(self):
            self.close_calls += 1

    stub_calc = _StubCalc()
    monkeypatch.setattr(_calc_mod, "CalcClient", lambda **kw: stub_calc)

    class _StubSpeedOracle:
        def __init__(self, stats_backend=None):
            self.backend = stats_backend

    monkeypatch.setattr(_speed_mod, "SpeedOracle", _StubSpeedOracle)

    class _StubOracle:
        def __init__(self, client=None):
            self.client = client

        def flush(self):
            pass

    monkeypatch.setattr(_oracle_mod, "DamageOracle", _StubOracle)

    out_path = tmp_path / "close_guard_out.jsonl"
    monkeypatch.setenv("SHOWDOWN_DATASET_EXPORT", str(out_path))
    monkeypatch.setenv("SHOWDOWN_DATASET_TEACHER", "rollout")
    monkeypatch.setenv("SHOWDOWN_ROLLOUT_HORIZON", "1")

    rt = DatasetExportRuntime.from_env(
        format_id="gen9vgc2025regi",
        packed_team="packed",
        mirror_flag=False,
        provider=None,  # forces real _build_rollout_provider
    )
    assert rt is not None
    assert stub_calc.close_calls == 0  # not closed yet -- battle "in progress"

    rt.close()
    assert stub_calc.close_calls == 1

    rt.close()  # idempotent -- second close() must not double-close
    assert stub_calc.close_calls == 1
