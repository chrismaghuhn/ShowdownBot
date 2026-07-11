"""2b-2.5a run-scoped dataset export fix.

`cli.run_schedule` plays each schedule row as its own `run_local_gauntlet(games=1)` call.
Before this fix, each call's hero client built its OWN `DatasetExportRuntime` pointed at the
same `SHOWDOWN_DATASET_EXPORT` path; `DatasetExporter.flush_sorted` opens that path in "w"
mode, so every battle's flush overwrote the previous battle's rows -- only the LAST battle in
a 75-row schedule ever survived to disk.

These tests exercise the fix at the seam level (start_game/add/flush, called directly -- no
live battles, no Node, matching this repo's "no local battles/servers" constraint) and prove:
  (a) the fix -- ONE shared runtime, threaded through N sequential simulated battles (mirroring
      `_run_client`'s per-battle start_game()-on-init / flush()-on-win-tie lifecycle), ends up
      with all N games' rows in one file, and N distinct game_ids (game_index increments once
      per `start_game()` call on the shared runtime -- 2b-0 did exactly this over 100 games).
  (b) the contrasting OLD bug shape -- a FRESH runtime per battle -- overwrites the file every
      flush, so only the last battle's row (and its game_id, always game_index 0) survives.
"""
from __future__ import annotations

import json

from showdown_bot.learning.export_runtime import DatasetExportRuntime
from showdown_bot.learning.schema import FEATURE_COLUMNS, LABEL_KEYS, METADATA_KEYS, Row


def _row(game_id, decision_id, cand_idx=0):
    features = {c: 0 for c in FEATURE_COLUMNS}
    metadata = {k: "x" for k in METADATA_KEYS}
    metadata.update(game_id=game_id, decision_id=decision_id, candidate_index=cand_idx)
    label = {k: 0 for k in LABEL_KEYS}
    return Row(features=features, metadata=metadata, label=label)


def _play_one_simulated_battle(rt: DatasetExportRuntime) -> str:
    """Mirrors client/gauntlet.py's `_run_client`: `start_game()` fires on the |init|battle
    frame, one (stand-in) row is added per decision (standing in for the real observe() ->
    maybe_observe_decision -> exporter.add() chain), and `flush()` fires on win/tie."""
    rt.start_game()
    game_id = f"g{rt._game_index}"  # stand-in for make_game_id(run_id, game_index)
    rt.exporter.add(_row(game_id, f"{game_id}-d0"))
    rt.flush()
    return game_id


def _read_jsonl(path):
    text = path.read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line]


def test_shared_runtime_accumulates_all_games_rows_into_one_file(tmp_path, monkeypatch):
    monkeypatch.setenv("SHOWDOWN_DATASET_EXPORT", str(tmp_path / "dataset.jsonl"))
    rt = DatasetExportRuntime.from_env(format_id="fmt", packed_team="t", mirror_flag=False)

    game_ids = [_play_one_simulated_battle(rt) for _ in range(5)]

    rows = _read_jsonl(tmp_path / "dataset.jsonl")
    assert len(rows) == 5  # all 5 games' rows survive -- not just the last
    seen_game_ids = {r["metadata"]["game_id"] for r in rows}
    assert seen_game_ids == set(game_ids)
    assert len(seen_game_ids) == 5  # every game_id distinct (game_index incremented per game)


def test_shared_runtime_saw_n_start_game_calls(tmp_path, monkeypatch):
    monkeypatch.setenv("SHOWDOWN_DATASET_EXPORT", str(tmp_path / "dataset.jsonl"))
    rt = DatasetExportRuntime.from_env(format_id="fmt", packed_team="t", mirror_flag=False)

    for _ in range(5):
        _play_one_simulated_battle(rt)

    assert rt._game_index == 4  # 0-indexed: the 5th start_game() call lands on index 4


def test_old_bug_shape_fresh_runtime_per_battle_overwrites_the_file(tmp_path, monkeypatch):
    """Contrast test documenting the PRE-FIX shape: a fresh DatasetExportRuntime per battle
    (the old `run_local_gauntlet(games=1)`-per-row pattern, one runtime built+closed inside
    each call) overwrites the file on every flush -- only the LAST battle's row survives, and
    since every fresh runtime's `_game_index` restarts at 0, that surviving row's game_id is
    always the SAME one a real multi-battle run would have produced for battle #1."""
    path = tmp_path / "dataset.jsonl"
    monkeypatch.setenv("SHOWDOWN_DATASET_EXPORT", str(path))

    game_ids = []
    for i in range(5):
        rt = DatasetExportRuntime.from_env(format_id="fmt", packed_team="t", mirror_flag=False)
        game_ids.append(_play_one_simulated_battle(rt))  # fresh runtime -> start_game() -> index 0 every time

    assert game_ids == ["g0"] * 5  # the bug: every "battle" looks like game_index 0
    rows = _read_jsonl(path)
    assert len(rows) == 1  # only the LAST battle's row survived the repeated overwrite
    assert rows[0]["metadata"]["game_id"] == "g0"
