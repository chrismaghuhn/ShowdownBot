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
