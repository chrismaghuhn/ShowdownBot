import gzip, json
from showdown_bot.learning.export import make_run_id, make_game_id
from showdown_bot.learning.outcome_join.runner import run_outcome_join

GIT, TEAM, CFG = "gitsha", "teamA", "cfgA"

def _write(tmp_path):
    run_id = make_run_id(GIT, True, TEAM, CFG, 0)
    ds = tmp_path / "dataset.jsonl.gz"
    with gzip.open(ds, "wt", encoding="utf-8") as fh:
        for gi in range(2):
            gid = make_game_id(run_id, gi)
            for turn in (1, 4):
                fh.write(json.dumps({"metadata": {"game_id": gid, "git_sha": GIT,
                    "team_hash": TEAM, "config_hash": CFG, "winner": "__pending__",
                    "game_outcome": "__pending__", "final_turn": -1},
                    "features": {"turn_number": turn}}) + "\n")
    res = tmp_path / "results.jsonl"
    res.write_text("".join(json.dumps({"battle_id": f"b{gi}", "seed_index": gi,
        "winner": "hero" if gi == 0 else "villain", "turns": 9,
        "hero_team_hash": TEAM}) + "\n" for gi in range(2)), encoding="utf-8")
    return ds, res

def test_runner_labels_and_exits_zero(tmp_path):
    ds, res = _write(tmp_path)
    out = tmp_path / "out"
    code = run_outcome_join(dataset_path=ds, results_paths=[res],
                            out_dir=out, mode="label")
    assert code == 0
    sidecar = [json.loads(l) for l in open(out / "outcome-labels.jsonl", encoding="utf-8")]
    assert {r["game_outcome"] for r in sidecar} == {1.0, -1.0}
    assert (out / "outcome-join-report.json").exists()

def test_runner_exit_one_when_a_group_cannot_be_bridged(tmp_path):
    ds, res = _write(tmp_path)
    # corrupt results turns so the turn-gate fails -> group skipped
    rows = [json.loads(l) for l in open(res, encoding="utf-8")]
    rows[0]["turns"] = 0
    res.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    code = run_outcome_join(dataset_path=ds, results_paths=[res],
                            out_dir=tmp_path / "o2", mode="label")
    assert code == 1
