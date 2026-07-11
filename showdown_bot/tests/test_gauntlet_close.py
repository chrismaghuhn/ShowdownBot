"""2b-2.5a Kaggle-OOM fix: per-battle resource teardown.

`_Client.close()` must close every calc-owning resource the client created
(the DatasetExportRuntime's rollout CalcClient, and the eval-species-dex
backend) -- idempotently, best-effort, never raising -- so
`run_local_gauntlet`'s finally block can call it unconditionally on both the
success and failure paths.

No live connection is needed for these tests: `_Client.__init__` only stores
`conn` (never touches it -- see gauntlet.py), so a plain sentinel object is a
valid `conn`. A full run_local_gauntlet fake-run (fake ShowdownConnection
driving a whole battle through the async loop) is not covered here -- no
fake-connection test infrastructure exists in this suite (see
test_gauntlet_shadow.py's docstring: constructing a real `_Client` for a full
run requires a live websocket + running Showdown server). Coverage is via
these unit seams instead: `_Client.close()` directly, plus the underlying
`DatasetExportRuntime.close()` / `CalcClient.close()` / `SpeciesDex.close()`
tests in test_export_runtime.py, test_export_rollout_e2e.py, and
test_calc_client.py.
"""
from __future__ import annotations

from showdown_bot.client.gauntlet import _Client


class _FakeCloser:
    def __init__(self):
        self.close_calls = 0
        # Duck-type the attrs _Client.__init__ reads for the shadow-mode provenance dict
        # (self._export.git_sha etc, slice 2b-3a, lines right after export construction) --
        # only exercised when export_runtime is threaded THROUGH the constructor (as the new
        # borrowed-runtime tests below do); the pre-existing tests set c._export post-hoc and
        # never hit that code path, so they didn't need these.
        self.git_sha = "fakesha"
        self.dirty_flag = False
        self.team_hash_ = "faketeam"
        self.config_hash_ = "fakecfg"
        self.run_seed = 0

    def close(self):
        self.close_calls += 1


class _RaisingCloser:
    git_sha = "fakesha"
    dirty_flag = False
    team_hash_ = "faketeam"
    config_hash_ = "fakecfg"
    run_seed = 0

    def close(self):
        raise RuntimeError("boom")


def _client(**kw):
    defaults = dict(
        conn=object(), name="T", agent="max_damage", book=None, priors=None,
        format_id="fmt", packed_team="", opp_sets={},
    )
    defaults.update(kw)
    return _Client(**defaults)


def test_close_is_noop_when_no_calc_owning_resources_were_built():
    # SHOWDOWN_DATASET_EXPORT is unset by default -> _export is None; the
    # max_damage agent never builds _eval_species_dex -> both are None.
    c = _client()
    assert c._export is None
    assert c._eval_species_dex is None
    c.close()  # must not raise


def test_close_closes_export_runtime():
    c = _client()
    fake_export = _FakeCloser()
    c._export = fake_export
    c.owns_export = True  # 2b-2.5a: close() now gates on ownership, not just presence
    c.close()
    assert fake_export.close_calls == 1


def test_close_closes_eval_species_dex():
    c = _client()
    fake_dex = _FakeCloser()
    c._eval_species_dex = fake_dex
    c.close()
    assert fake_dex.close_calls == 1


def test_close_closes_both_resources():
    c = _client()
    fake_export = _FakeCloser()
    fake_dex = _FakeCloser()
    c._export = fake_export
    c.owns_export = True
    c._eval_species_dex = fake_dex
    c.close()
    assert fake_export.close_calls == 1
    assert fake_dex.close_calls == 1


def test_close_survives_one_resource_raising():
    # A single resource's close() failure must not prevent the other's, and must
    # not propagate out of close() (best-effort teardown).
    c = _client()
    fake_dex = _FakeCloser()
    c._export = _RaisingCloser()
    c.owns_export = True
    c._eval_species_dex = fake_dex
    c.close()  # must not raise even though _export.close() raised
    assert fake_dex.close_calls == 1


# ---------------------------------------------------------------------------
# 2b-2.5a run-scoped fix: dataset export is battle-scoped and each battle
# OVERWROTE the export file (cli.run_schedule looped run_local_gauntlet(games=1)
# per row, and each call's hero built+closed its OWN runtime pointed at the same
# path). A BORROWED runtime (passed via export_runtime=) spans multiple battles
# and must survive any single _Client.close() call; the VILLAIN must never build
# one at all (hero-only contract), even when villain_agent == "heuristic" (a
# valid, trace-producing opponent policy that would otherwise export its own
# decisions to the same file and race the hero's flushes).
# ---------------------------------------------------------------------------


def test_close_does_not_close_borrowed_export_runtime():
    fake_export = _FakeCloser()
    c = _client(export_runtime=fake_export)
    assert c._export is fake_export
    assert c.owns_export is False
    c.close()
    assert fake_export.close_calls == 0  # borrowed -- outlives this client


def test_close_does_not_close_borrowed_export_runtime_even_if_it_raises():
    # Never called here (borrowed), so a raising close() must not even fire.
    c = _client(export_runtime=_RaisingCloser())
    c.close()  # must not raise


def test_allow_own_export_false_never_builds_a_runtime(monkeypatch, tmp_path):
    """The villain construction shape: allow_own_export=False keeps _export None even
    when the env gate is set (hero-only contract)."""
    monkeypatch.setenv("SHOWDOWN_DATASET_EXPORT", str(tmp_path / "o.jsonl"))
    c = _client(agent="heuristic", allow_own_export=False)
    assert c._export is None
    assert c.owns_export is False
    c.close()  # must not raise


def test_allow_own_export_false_skips_from_env_call_entirely(monkeypatch, tmp_path):
    monkeypatch.setenv("SHOWDOWN_DATASET_EXPORT", str(tmp_path / "o.jsonl"))
    import showdown_bot.client.gauntlet as gauntlet_mod

    calls = []

    def _counting_from_env(**kw):
        calls.append(kw)
        return None

    monkeypatch.setattr(gauntlet_mod.DatasetExportRuntime, "from_env", _counting_from_env)
    _client(allow_own_export=False)
    assert calls == []  # villain: from_env is never even called


def test_allow_own_export_true_calls_from_env_once_and_owns_the_result(monkeypatch, tmp_path):
    """The hero (plain --games N path, export_runtime=None) still builds+owns its own
    runtime exactly as before this fix -- bit-identical behavior when nothing is borrowed."""
    monkeypatch.setenv("SHOWDOWN_DATASET_EXPORT", str(tmp_path / "o.jsonl"))
    import showdown_bot.client.gauntlet as gauntlet_mod

    calls = []
    real_from_env = gauntlet_mod.DatasetExportRuntime.from_env  # bound classmethod (cls already set)

    def _counting_from_env(**kw):
        calls.append(kw)
        return real_from_env(**kw)

    monkeypatch.setattr(gauntlet_mod.DatasetExportRuntime, "from_env", _counting_from_env)
    c = _client(allow_own_export=True)
    assert len(calls) == 1
    assert c._export is not None
    assert c.owns_export is True
    c.close()
    assert c._export._closed is True  # DatasetExportRuntime.close() flips this flag


def test_export_runtime_param_takes_precedence_over_allow_own_export(monkeypatch, tmp_path):
    """export_runtime=<given> always wins: even with allow_own_export=True, a borrowed
    runtime is used as-is (never rebuilt) and never owned/closed by this client."""
    monkeypatch.setenv("SHOWDOWN_DATASET_EXPORT", str(tmp_path / "o.jsonl"))
    fake_export = _FakeCloser()
    c = _client(export_runtime=fake_export, allow_own_export=True)
    assert c._export is fake_export
    assert c.owns_export is False
    c.close()
    assert fake_export.close_calls == 0


# ---------------------------------------------------------------------------
# 2b-2.5a wiring fix: gauntlet.py hardcoded mirror_flag=False and move_meta=None/dex=None at
# BOTH DatasetExportRuntime construction sites (reports/2026-07-11-2b25a-offline-eval.md root
# causes (A)/(B)). These tests pin the real values now threaded through: an OWNED runtime gets
# the caller's `is_mirror` + a real move_meta table at construction; a BORROWED (run-scoped)
# runtime gets its mirror_flag REFRESHED per battle (per fresh _Client), since a schedule's
# villain can differ row to row while sharing one runtime instance across the whole run.
# ---------------------------------------------------------------------------


def test_allow_own_export_threads_real_mirror_flag_and_move_meta(monkeypatch, tmp_path):
    monkeypatch.setenv("SHOWDOWN_DATASET_EXPORT", str(tmp_path / "o.jsonl"))

    c_mirror = _client(allow_own_export=True, is_mirror=True)
    assert c_mirror._export.mirror_flag is True
    assert c_mirror._export.move_meta is not None
    assert "protect" in c_mirror._export.move_meta  # real _move_table(), not None

    c_nonmirror = _client(allow_own_export=True, is_mirror=False)
    assert c_nonmirror._export.mirror_flag is False


def test_borrowed_export_runtime_mirror_flag_refreshed_per_client(tmp_path):
    fake_export = _FakeCloser()
    fake_export.mirror_flag = "unset"  # stand-in initial value, overwritten by each client below

    c1 = _client(export_runtime=fake_export, is_mirror=True)
    assert fake_export.mirror_flag is True
    assert c1._export is fake_export  # still the SAME borrowed instance, not rebuilt

    # A second client (= the schedule's next battle) borrowing the SAME runtime with a
    # different villain refreshes mirror_flag to that battle's own value.
    c2 = _client(export_runtime=fake_export, is_mirror=False)
    assert fake_export.mirror_flag is False
    assert c2._export is fake_export


# ---------------------------------------------------------------------------
# 2b-2.5a Kaggle-OOM ROOT CAUSE: the client now owns ONE calc/oracle/speed_oracle/
# dex bundle per battle (built lazily on the first live decision, threaded into
# every decision, closed once in the per-battle teardown seam). Before this,
# agent_choose never passed a calc down, so the decision core spawned a fresh
# `node calc.mjs --server` PER DECISION. Only agents that actually use calc
# (heuristic, max_damage) build the bundle; the request-only eval policies
# (greedy_protect/simple_heuristic/scripted_vgc) and random never do.
# ---------------------------------------------------------------------------


class _FakeCalcClient:
    """Stand-in for CalcClient: counts constructions, exposes a `backend` for the
    oracle/speed-oracle/dex to bind to (none of which spawn Node at construction)."""

    def __init__(self):
        _FakeCalcClient.instances += 1
        self.backend = object()
        self.close_calls = 0

    def close(self):
        self.close_calls += 1


_FakeCalcClient.instances = 0


def _patch_calc(monkeypatch):
    import showdown_bot.client.gauntlet as gauntlet_mod

    _FakeCalcClient.instances = 0
    monkeypatch.setattr(gauntlet_mod, "CalcClient", _FakeCalcClient)


def test_decision_deps_built_once_and_cached_for_heuristic(monkeypatch):
    _patch_calc(monkeypatch)
    c = _client(agent="heuristic")
    calc, oracle, speed_oracle, dex = c._decision_deps()
    assert calc is c._decision_calc
    assert isinstance(calc, _FakeCalcClient)
    assert oracle is not None and speed_oracle is not None and dex is not None
    # Second call is cached -- ONE calc per battle, not per decision.
    again = c._decision_deps()
    assert again == (calc, oracle, speed_oracle, dex)
    assert _FakeCalcClient.instances == 1


def test_decision_deps_built_for_max_damage(monkeypatch):
    _patch_calc(monkeypatch)
    c = _client(agent="max_damage")
    calc, oracle, speed_oracle, dex = c._decision_deps()
    assert isinstance(calc, _FakeCalcClient)
    assert _FakeCalcClient.instances == 1


def test_decision_deps_threads_client_scoped_dex_into_owned_export_runtime(monkeypatch, tmp_path):
    """2b-2.5a wiring fix: an OWNED export runtime's `.dex` starts None at construction (dex is
    client/per-battle-scoped, built lazily off the live-decision calc backend -- AFTER the
    constructor returns) and gets set to the SAME client-scoped SpeciesDex the live decision
    path uses, the first time `_decision_deps()` builds it -- i.e. before the first
    `observe()` call of the battle (handle_request calls `_decision_deps()` first)."""
    _patch_calc(monkeypatch)
    monkeypatch.setenv("SHOWDOWN_DATASET_EXPORT", str(tmp_path / "o.jsonl"))

    c = _client(agent="heuristic", allow_own_export=True)
    assert c._export.dex is None  # not yet built -- no decision has been made
    calc, oracle, speed_oracle, dex = c._decision_deps()
    assert dex is not None
    assert c._export.dex is dex  # threaded into the export runtime by _decision_deps()
    assert c._export.dex is c._decision_dex


def test_decision_deps_leaves_borrowed_export_runtime_dex_untouched(monkeypatch):
    """2b-2.5a wiring fix: a BORROWED (run-scoped) runtime keeps its own independent,
    run-invariant SpeciesDex (built once by build_schedule_export_runtime, spanning the whole
    schedule) -- _decision_deps() must NOT overwrite it with the per-battle client-scoped dex."""
    _patch_calc(monkeypatch)
    fake_export = _FakeCloser()
    sentinel_dex = object()
    fake_export.dex = sentinel_dex

    c = _client(agent="heuristic", export_runtime=fake_export)
    calc, oracle, speed_oracle, dex = c._decision_deps()
    assert dex is not None  # the client still built its own per-battle dex...
    assert c._export.dex is sentinel_dex  # ...but the borrowed runtime's dex is untouched


def test_decision_deps_never_built_for_request_only_agent(monkeypatch):
    """Eval-policy guard: a request-only opponent (greedy_protect) never uses calc,
    so it must never construct one."""
    _patch_calc(monkeypatch)
    c = _client(agent="greedy_protect")
    assert c._decision_deps() == (None, None, None, None)
    assert c._decision_calc is None
    assert _FakeCalcClient.instances == 0
    c.close()  # must not raise


def test_decision_deps_never_built_for_random(monkeypatch):
    _patch_calc(monkeypatch)
    c = _client(agent="random")
    assert c._decision_deps() == (None, None, None, None)
    assert _FakeCalcClient.instances == 0


def test_close_closes_decision_calc():
    c = _client(agent="heuristic")
    fake_calc = _FakeCloser()
    c._decision_calc = fake_calc
    c.close()
    assert fake_calc.close_calls == 1


def test_close_survives_decision_calc_raising():
    # A raising decision-calc close() must not skip the other resources' closes.
    c = _client(agent="heuristic")
    fake_dex = _FakeCloser()
    c._decision_calc = _RaisingCloser()
    c._eval_species_dex = fake_dex
    c.close()  # must not raise
    assert fake_dex.close_calls == 1


def test_close_noop_when_no_decision_calc_built():
    # Never took a decision (or a request-only agent) -> _decision_calc stays None.
    c = _client(agent="greedy_protect")
    assert c._decision_calc is None
    c.close()  # must not raise
