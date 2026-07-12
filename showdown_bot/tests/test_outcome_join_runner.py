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

def test_runner_matches_results_file_via_gate_when_hero_team_hash_differs_from_team_hash(tmp_path):
    """Real-world regression (phase3-slice2b25a reference smoke): `hero_team_hash`
    (results.jsonl, schedule/eval provenance) and `team_hash` (dataset metadata,
    export provenance) are DIFFERENT hashes over different inputs -- on the real
    reference dataset every group's hero_team_hash mismatched its own team_hash,
    for every group x file pair. The runner must still correctly pair each group
    with its OWN results file purely via the integrity gate (bijective bridge +
    turn-check), never via hero_team_hash equality, and must NOT cross-wire a
    group's labels to the wrong file's battles.

    Two groups, two results files, neither hero_team_hash equal to either
    team_hash. Per-game turn caps are picked asymmetrically so each group's real
    max-turn overshoots the OTHER file's cap on at least one game (mirrors why
    the turn-check disambiguates on the real 75-game-per-hero data) while
    fitting its OWN file's cap exactly.
    """
    TEAM_A, TEAM_B = "teamA", "teamB"
    run_id_a = make_run_id(GIT, True, TEAM_A, CFG, 0)
    run_id_b = make_run_id(GIT, True, TEAM_B, CFG, 0)

    ds = tmp_path / "dataset.jsonl.gz"
    with gzip.open(ds, "wt", encoding="utf-8") as fh:
        for team, run_id, turns_per_game in (
            (TEAM_A, run_id_a, (9, 3)), (TEAM_B, run_id_b, (3, 9)),
        ):
            for gi, turn in enumerate(turns_per_game):
                gid = make_game_id(run_id, gi)
                fh.write(json.dumps({"metadata": {"game_id": gid, "git_sha": GIT,
                    "team_hash": team, "config_hash": CFG, "winner": "__pending__",
                    "game_outcome": "__pending__", "final_turn": -1},
                    "features": {"turn_number": turn}}) + "\n")

    res_a = tmp_path / "results_a.jsonl"
    res_a.write_text("".join(json.dumps({
        "battle_id": f"bA{gi}", "seed_index": gi,
        "winner": "hero" if gi == 0 else "villain", "turns": t,
        "hero_team_hash": "unrelated-hash-1",  # deliberately != TEAM_A
    }) + "\n" for gi, t in enumerate((9, 3))), encoding="utf-8")
    res_b = tmp_path / "results_b.jsonl"
    res_b.write_text("".join(json.dumps({
        "battle_id": f"bB{gi}", "seed_index": gi,
        "winner": "villain" if gi == 0 else "hero", "turns": t,
        "hero_team_hash": "unrelated-hash-2",  # deliberately != TEAM_B
    }) + "\n" for gi, t in enumerate((3, 9))), encoding="utf-8")

    out = tmp_path / "out"
    code = run_outcome_join(dataset_path=ds, results_paths=[res_a, res_b],
                            out_dir=out, mode="label")
    assert code == 0
    sidecar = {r["battle_id"]: r for r in
              (json.loads(l) for l in open(out / "outcome-labels.jsonl", encoding="utf-8"))}
    assert set(sidecar) == {"bA0", "bA1", "bB0", "bB1"}
    assert sidecar["bA0"]["winner"] == "hero" and sidecar["bA1"]["winner"] == "villain"
    assert sidecar["bB0"]["winner"] == "villain" and sidecar["bB1"]["winner"] == "hero"
    assert sidecar["bA0"]["team_hash"] == TEAM_A and sidecar["bB0"]["team_hash"] == TEAM_B
