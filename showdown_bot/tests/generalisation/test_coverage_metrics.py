# tests/generalisation/test_coverage_metrics.py
from types import SimpleNamespace

from showdown_bot.analysis.generalisation.contracts import AnalysisPolicy
from showdown_bot.analysis.generalisation.coverage import coverage_matrix
from showdown_bot.analysis.generalisation.metrics import single_run_summary


def _obs(cell, seed, win, archetype):
    return SimpleNamespace(cell_id=cell, seed=seed, hero_win=win,
        winner="hero" if win else "villain", end_reason="normal", end_hp_diff=1.0,
        turns=7, opponent_archetype=archetype, hero_lead=("a", "b"),
        opponent_lead=("c", "d"), hero_side="p1",
        hero_static_speed_control="none", opponent_static_speed_control="none",
        hero_activated_speed_control=(), opponent_activated_speed_control=())


def test_missing_cell_stays_visible():
    manifest = SimpleNamespace(cells=(
        SimpleNamespace(cell_id="a", protected=True, required_unique_seeds=2),
        SimpleNamespace(cell_id="b", protected=True, required_unique_seeds=2)))
    rows = coverage_matrix(manifest, [_obs("a", "s1", True, "rain")], AnalysisPolicy())
    assert [row["cell_id"] for row in rows] == ["a", "b"]
    assert rows[1]["n"] == 0 and rows[1]["complete"] is False


def test_macro_is_not_row_weighted_and_worst_is_stable():
    observations = [_obs("large", f"l{i}", i < 90, "rain") for i in range(100)]
    observations += [_obs("small", f"x{i}", False, "sun") for i in range(10)]
    manifest = SimpleNamespace(cells=(
        SimpleNamespace(cell_id="large", protected=True, required_unique_seeds=10),
        SimpleNamespace(cell_id="small", protected=True, required_unique_seeds=10)))
    policy = AnalysisPolicy(gate_min_unique_seeds_per_cell=10)
    result = single_run_summary(manifest, observations, policy)
    assert round(result["micro"]["win_rate"], 6) == round(90 / 110, 6)
    assert result["macro"]["win_rate"] == 0.45
    assert result["worst_cell"]["cell_id"] == "small"
    assert result["robustness_gap"] == 0.45
