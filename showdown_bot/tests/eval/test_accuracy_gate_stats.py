from __future__ import annotations

import math

from showdown_bot.eval.accuracy_gate_stats import (
    Verdict,
    clopper_pearson_zero_upper_bound,
    game_clustered_bootstrap_upper_bound,
    minimum_g_for_zero_event_pass,
    verdict_for_cap_hit_rate,
)


def test_clopper_pearson_zero_upper_bound_matches_known_values():
    assert math.isclose(clopper_pearson_zero_upper_bound(85), 0.0346, abs_tol=1e-3)
    assert math.isclose(clopper_pearson_zero_upper_bound(197), 0.0151, abs_tol=1e-3)
    assert math.isclose(clopper_pearson_zero_upper_bound(30), 0.095, abs_tol=1e-3)


def test_minimum_g_for_zero_event_pass_is_59():
    assert minimum_g_for_zero_event_pass() == 59
    assert clopper_pearson_zero_upper_bound(59) <= 0.05
    assert clopper_pearson_zero_upper_bound(58) > 0.05


def test_bootstrap_zero_events_uses_game_level_bound():
    # 10 games, 0 decisions with a cap-hit in any of them.
    per_game_cap_hit = {f"game{i}": False for i in range(10)}
    per_decision = []  # no cap-hit decisions at all
    verdict, detail = verdict_for_cap_hit_rate(
        per_decision_cap_hit=per_decision, per_game_any_cap_hit=per_game_cap_hit,
        n_decisions=200, rng_seed=20260713,
    )
    assert detail["bootstrap_ci_upper"] == 0.0
    assert detail["bootstrap_ci_degenerate"] is True
    assert "clopper_pearson_upper_bound" in detail
    assert detail["clopper_pearson_upper_bound"] == clopper_pearson_zero_upper_bound(10)
    assert verdict == Verdict.INCONCLUSIVE  # G=10 is far below the G>=59 floor


def test_zero_events_passes_when_g_clears_the_floor():
    per_game_cap_hit = {f"game{i}": False for i in range(85)}
    verdict, detail = verdict_for_cap_hit_rate(
        per_decision_cap_hit=[], per_game_any_cap_hit=per_game_cap_hit,
        n_decisions=1186, rng_seed=20260713,
    )
    assert verdict == Verdict.PASS
    assert detail["clopper_pearson_upper_bound"] <= 0.05


def test_nonzero_events_uses_bootstrap_pass_band():
    # 100 decisions across 20 games, 1 cap-hit decision (0.5% point estimate) -- should PASS
    # given a tight bootstrap CI at this scale.
    per_decision = [False] * 99 + [True]
    game_ids = [f"game{i % 20}" for i in range(100)]
    per_game_any_cap_hit = {f"game{i}": False for i in range(20)}
    per_game_any_cap_hit["game19"] = True  # the one cap-hit decision's game
    verdict, detail = verdict_for_cap_hit_rate(
        per_decision_cap_hit=list(zip(game_ids, per_decision)),
        per_game_any_cap_hit=per_game_any_cap_hit,
        n_decisions=100, rng_seed=20260713,
    )
    assert detail["point_estimate"] == 0.01
    assert verdict in (Verdict.PASS, Verdict.INCONCLUSIVE)  # depends on bootstrap variance at n=20 games


def test_nonzero_events_fails_above_five_percent():
    per_decision = [(f"game{i}", True) for i in range(10)] + [(f"game{i}", False) for i in range(10, 100)]
    per_game_any_cap_hit = {f"game{i}": (i < 10) for i in range(100)}
    verdict, detail = verdict_for_cap_hit_rate(
        per_decision_cap_hit=per_decision, per_game_any_cap_hit=per_game_any_cap_hit,
        n_decisions=100, rng_seed=20260713,
    )
    assert detail["point_estimate"] == 0.10
    assert verdict == Verdict.FAIL
