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

    def close(self):
        self.close_calls += 1


class _RaisingCloser:
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
    c._eval_species_dex = fake_dex
    c.close()  # must not raise even though _export.close() raised
    assert fake_dex.close_calls == 1
