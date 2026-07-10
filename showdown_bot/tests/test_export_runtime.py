# tests/test_export_runtime.py
import io
from showdown_bot.learning.export import DatasetExporter, SamplingPolicy
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

    observe_count = [0]
    # Stub both the driver (no-op) and the provider (return fake labels), so we
    # can pass raw object() as trace/state/request without hitting real logic.
    monkeypatch.setattr(rtmod, "maybe_observe_decision",
                        lambda exp, **kw: observe_count.__setitem__(0, observe_count[0] + 1) or 1)

    class _FakeProvider:
        def teacher_config(self):
            return {"teacher_version": "stub-h0", "trainable_label": False}
        def labels_for_decision(self, trace, state, request, *, context):
            return {}  # no candidates -> no rows (fine for index-tracking test)

    rt = DatasetExportRuntime.from_env(format_id="fmt", packed_team="t", mirror_flag=False,
                                       provider=_FakeProvider())
    rt.start_game(); rt.observe(trace=object(), state=object(), request=object(), turn_number=1, our_side="p1")
    rt.observe(trace=object(), state=object(), request=object(), turn_number=2, our_side="p1")
    assert observe_count[0] == 2                  # driver called twice (both sampled by "all" policy)
    assert rt._decision_local_index == 2          # per-game counter advanced
    rt.start_game()
    assert rt._decision_local_index == 0          # resets per game; sampling index does NOT
    rt.observe(trace=object(), state=object(), request=object(), turn_number=1, our_side="p1")
    assert observe_count[0] == 3                  # driver called a third time


def test_runtime_flush_writes(monkeypatch, tmp_path):
    p = tmp_path / "o.jsonl"
    monkeypatch.setenv("SHOWDOWN_DATASET_EXPORT", str(p))
    rt = DatasetExportRuntime.from_env(format_id="fmt", packed_team="t", mirror_flag=False)
    rt.flush()                                     # empty exporter -> writes an (empty) file, no crash
    assert p.exists()


# ---------------------------------------------------------------------------
# 2b-2.5a Kaggle-OOM fix: DatasetExportRuntime.close() must tear down the
# rollout-mode CalcClient (PersistentCalcBackend -> leaked Node process
# otherwise, one per battle since the schedule runner builds a fresh runtime
# per run_local_gauntlet(games=1) call).
# ---------------------------------------------------------------------------

class _FakeCalcClient:
    """Minimal CalcClient stand-in: only close() matters for these tests."""

    def __init__(self):
        self.close_calls = 0

    def close(self):
        self.close_calls += 1


def test_runtime_close_closes_injected_calc_client():
    fake_calc = _FakeCalcClient()
    rt = DatasetExportRuntime(
        DatasetExporter(SamplingPolicy(policy="all", rate=1, seed=0)),
        "unused.jsonl",
        git_sha="gs", dirty_flag=False, team_hash_="th", config_hash_="ch",
        run_seed=0, format_id="fmt", mirror_flag=False, sampling_policy_name="all",
        calc=fake_calc,
    )
    rt.close()
    assert fake_calc.close_calls == 1


def test_runtime_close_is_idempotent():
    fake_calc = _FakeCalcClient()
    rt = DatasetExportRuntime(
        DatasetExporter(SamplingPolicy(policy="all", rate=1, seed=0)),
        "unused.jsonl",
        git_sha="gs", dirty_flag=False, team_hash_="th", config_hash_="ch",
        run_seed=0, format_id="fmt", mirror_flag=False, sampling_policy_name="all",
        calc=fake_calc,
    )
    rt.close()
    rt.close()  # second call must not close the backend again
    assert fake_calc.close_calls == 1


def test_runtime_close_noop_in_stub_mode(monkeypatch, tmp_path):
    """Stub mode (the default, no SHOWDOWN_DATASET_TEACHER=rollout) never builds a
    calc client -> close() is a safe no-op (does not raise, no calc to close)."""
    monkeypatch.setenv("SHOWDOWN_DATASET_EXPORT", str(tmp_path / "o.jsonl"))
    monkeypatch.delenv("SHOWDOWN_DATASET_TEACHER", raising=False)
    rt = DatasetExportRuntime.from_env(format_id="fmt", packed_team="t", mirror_flag=False)
    assert rt is not None
    rt.close()  # must not raise
    rt.close()  # idempotent


# ---------------------------------------------------------------------------
# 2b-2.5a run-scoped fix: `build_schedule_export_runtime` builds ONE runtime for
# cli.run_schedule to thread through every row (instead of each row's
# run_local_gauntlet(games=1) call building+closing its own, which overwrote the
# export file every battle).
# ---------------------------------------------------------------------------


def test_build_schedule_export_runtime_returns_none_when_env_unset(monkeypatch):
    monkeypatch.delenv("SHOWDOWN_DATASET_EXPORT", raising=False)
    from showdown_bot.client.gauntlet import build_schedule_export_runtime

    assert build_schedule_export_runtime("gen9vgc2025regi", "teams/fixed_team.txt") is None


def test_build_schedule_export_runtime_builds_with_hero_team_and_format(monkeypatch, tmp_path):
    monkeypatch.setenv("SHOWDOWN_DATASET_EXPORT", str(tmp_path / "o.jsonl"))
    from showdown_bot.client.gauntlet import build_schedule_export_runtime

    rt = build_schedule_export_runtime("gen9vgc2025regi", "teams/fixed_team.txt")
    assert rt is not None
    assert rt.format_id == "gen9vgc2025regi"
    assert rt.mirror_flag is False  # schedules are always non-mirror (distinct opp teams)
    assert len(rt.team_hash_) == 16  # a real (non-empty) packed team was loaded and hashed


def test_build_schedule_export_runtime_degrades_gracefully_on_bad_team_path(monkeypatch, tmp_path):
    """A missing/bad hero_team_path must not raise -- mirrors _resolve_side_teams' existing
    ""-on-load-failure tolerance (the schedule loop itself would fail loudly elsewhere on a
    bad team path; this seam just must not crash the export-runtime build specifically)."""
    monkeypatch.setenv("SHOWDOWN_DATASET_EXPORT", str(tmp_path / "o.jsonl"))
    from showdown_bot.client.gauntlet import build_schedule_export_runtime

    rt = build_schedule_export_runtime("gen9vgc2025regi", "no/such/team/file.txt")
    assert rt is not None  # still built -- degrades to an empty packed_team, not a crash
