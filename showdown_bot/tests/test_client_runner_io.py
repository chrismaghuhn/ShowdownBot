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
