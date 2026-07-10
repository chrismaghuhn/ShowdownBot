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
