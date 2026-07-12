from types import SimpleNamespace

from showdown_bot.analysis.generalisation.compare import compare_observation_pairs, holm_adjust
from showdown_bot.analysis.generalisation.contracts import AnalysisPolicy


def _obs(cell, battle, win, config):
    return SimpleNamespace(cell_id=cell, battle_id=battle, seed=battle, hero_win=win,
                           winner="hero" if win else "villain", protected_cell=True,
                           config_hash=config)


def test_holm_adjustment_is_monotone_and_bounded():
    assert holm_adjust([0.01, 0.04, 0.03]) == [0.03, 0.06, 0.06]


def test_paired_delta_and_bootstrap_are_deterministic():
    baseline = [_obs("a", f"b{i}", False, "baseline") for i in range(30)]
    candidate = [_obs("a", f"b{i}", True, "candidate") for i in range(30)]
    policy = AnalysisPolicy(gate_min_unique_seeds_per_cell=30, bootstrap_replicates=1000)
    first = compare_observation_pairs(baseline, candidate, policy)
    second = compare_observation_pairs(baseline, candidate, policy)
    assert first == second
    assert first["cells"][0]["delta"] == 1.0
    assert first["status"] == "IMPROVEMENT"


def test_local_regression_blocks_global_improvement():
    baseline = [_obs("safe", f"a{i}", False, "baseline") for i in range(30)]
    candidate = [_obs("safe", f"a{i}", True, "candidate") for i in range(30)]
    baseline += [_obs("regress", f"r{i}", True, "baseline") for i in range(30)]
    candidate += [_obs("regress", f"r{i}", False, "candidate") for i in range(30)]
    result = compare_observation_pairs(baseline, candidate,
        AnalysisPolicy(gate_min_unique_seeds_per_cell=30, bootstrap_replicates=1000))
    assert result["status"] == "REGRESSION"
