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
