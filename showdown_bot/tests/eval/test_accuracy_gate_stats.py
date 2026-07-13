from __future__ import annotations

import math

from showdown_bot.eval.accuracy_gate_stats import (
    PASS_THRESHOLD,
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


def test_nonzero_events_spread_across_games_uses_local_rate_not_binary_indicator():
    # 30 games x 20 decisions each = 600 decisions. 10 cap-hit decisions, exactly one per game,
    # spread across the first 10 games -- the realistic "rare event spread across many games"
    # shape. point_estimate = 10/600 ~= 1.67%, safely under 5%. The bootstrap must use each
    # game's own LOCAL decision-level rate (1/20 = 5% for a hit game, 0% otherwise), not the
    # coarse "did this game have ANY cap-hit" binary indicator (which would make every hit game
    # contribute 1.0 instead of 0.05 and inflate the CI far past 5%, making PASS unreachable).
    per_decision: list[tuple[str, bool]] = []
    per_game_any_cap_hit: dict[str, bool] = {}
    per_game_binary_rate: dict[str, float] = {}
    for g in range(30):
        game_id = f"game{g}"
        is_hit_game = g < 10
        per_game_any_cap_hit[game_id] = is_hit_game
        per_game_binary_rate[game_id] = 1.0 if is_hit_game else 0.0
        for d in range(20):
            per_decision.append((game_id, is_hit_game and d == 0))

    verdict, detail = verdict_for_cap_hit_rate(
        per_decision_cap_hit=per_decision, per_game_any_cap_hit=per_game_any_cap_hit,
        n_decisions=600, rng_seed=20260713,
    )
    assert math.isclose(detail["point_estimate"], 10 / 600, rel_tol=1e-9)
    assert verdict == Verdict.PASS
    assert detail["bootstrap_ci_upper"] < 0.10

    # Local sanity check: the OLD (buggy) binary-indicator computation on this same fixture
    # produces a much larger, practically-unreachable-for-PASS upper bound -- proving the fix
    # changed the actual quantity being bootstrapped, not just tightened a constant.
    old_style_upper = game_clustered_bootstrap_upper_bound(per_game_binary_rate, seed=20260713)
    assert old_style_upper > detail["bootstrap_ci_upper"]
    assert old_style_upper > PASS_THRESHOLD


def test_zero_decisions_is_inconclusive_even_with_seeded_games():
    # Every decision raised/failed (e.g. `_chosen_candidate`'s RuntimeError, per Task 10) --
    # n_decisions=0 but per_game_any_cap_hit can still be nonempty since game IDs are
    # pre-seeded before the per-decision try/except. Must fail closed to INCONCLUSIVE, never PASS.
    per_game_any_cap_hit = {f"game{i}": False for i in range(85)}
    verdict, detail = verdict_for_cap_hit_rate(
        per_decision_cap_hit=[], per_game_any_cap_hit=per_game_any_cap_hit,
        n_decisions=0, rng_seed=20260713,
    )
    assert verdict == Verdict.INCONCLUSIVE
    assert detail["n_decisions"] == 0
    assert detail["numerator"] == 0
    assert detail["reason"] == "no_decisions"
