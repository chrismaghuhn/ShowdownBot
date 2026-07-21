from pathlib import Path

from showdown_bot.client import runner


def test_battle_log_write_closes_the_file_before_return(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "LOG_DIR", tmp_path)
    runner._battle_logs.clear()

    runner._log_battle_line("battle-test-1", "|turn|1")

    path = runner._battle_logs["battle-test-1"]
    assert path.read_text(encoding="utf-8") == "|turn|1\n"
    renamed = path.with_suffix(".moved")
    path.rename(renamed)
    assert renamed.exists()


class _TrackingHandle:
    """A fake file handle recording writes and whether it was closed -- unlike the rename-based
    detection above, this proves close()/__exit__() directly rather than inferring it from
    CPython's refcounting GC (which happens to close an unreferenced handle synchronously for a
    single write even without an explicit `with`, masking the leak on this platform)."""

    def __init__(self):
        self.write_calls: list[str] = []
        self.closed = False

    def write(self, data: str) -> None:
        if self.closed:
            raise ValueError("write to closed handle")
        self.write_calls.append(data)

    def close(self) -> None:
        self.closed = True

    def __enter__(self) -> "_TrackingHandle":
        return self

    def __exit__(self, *exc_info: object) -> bool:
        self.close()
        return False


def test_battle_log_write_calls_close_on_the_handle_directly(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "LOG_DIR", tmp_path)
    runner._battle_logs.clear()

    handle = _TrackingHandle()
    monkeypatch.setattr(Path, "open", lambda self, *a, **k: handle)

    runner._log_battle_line("battle-test-2", "|turn|1")

    assert handle.write_calls == ["|turn|1\n"]
    assert handle.closed is True
