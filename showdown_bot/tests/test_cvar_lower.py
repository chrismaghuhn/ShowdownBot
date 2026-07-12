from statistics import mean

import pytest

from showdown_bot.battle.policy import cvar_lower


def test_empty_returns_zero():
    assert cvar_lower([], None, 0.25) == 0.0


def test_single_returns_that_value():
    assert cvar_lower([7.0], None, 0.25) == 7.0


def test_alpha_one_is_uniform_mean():
    scores = [1.0, 2.0, 3.0, 4.0]
    assert cvar_lower(scores, None, 1.0) == pytest.approx(mean(scores))


def test_small_alpha_approaches_min():
    scores = [5.0, 1.0, 9.0, 3.0]
    assert cvar_lower(scores, None, 1e-6) == pytest.approx(min(scores))


def test_uniform_worst_quarter_of_four():
    assert cvar_lower([10.0, 2.0, 8.0, 6.0], None, 0.25) == pytest.approx(2.0)


def test_straddle_clipping_exact_alpha_mass():
    assert cvar_lower([1.0, 2.0, 3.0, 4.0, 5.0], None, 0.25) == pytest.approx(1.2)


def test_weighted_tail_uses_weights():
    assert cvar_lower([1.0, 2.0, 3.0], [0.1, 0.1, 0.8], 0.25) == pytest.approx(1.8)


def test_bad_weights_fall_back_to_uniform():
    assert cvar_lower([10.0, 2.0, 8.0, 6.0], [1.0], 0.25) == pytest.approx(2.0)


def test_monotonic_nondecreasing_in_alpha():
    scores = [1.0, 2.0, 3.0, 4.0, 5.0]
    vals = [cvar_lower(scores, None, a) for a in (0.1, 0.25, 0.5, 0.75, 1.0)]
    assert all(vals[i] <= vals[i + 1] + 1e-9 for i in range(len(vals) - 1))


def test_deterministic():
    scores = [3.0, 1.0, 4.0, 1.0, 5.0]
    assert cvar_lower(scores, None, 0.3) == cvar_lower(scores, None, 0.3)
