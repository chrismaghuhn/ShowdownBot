"""T5 stats: exact values pinned so the verdict gates rest on verified math."""
import math

import pytest

from showdown_bot.eval.stats import (
    LOSING_CELL_WILSON_UPPER,
    N_DISCORDANT_CLAIM_MIN,
    N_DISCORDANT_MATH_FLOOR,
    TIE_FLAG_RATE,
    McnemarCounts,
    exact_binom_two_sided_p,
    mcnemar_counts,
    wilson_interval,
)


def test_constants_pinned():
    assert N_DISCORDANT_MATH_FLOOR == 6
    assert N_DISCORDANT_CLAIM_MIN == 10
    assert LOSING_CELL_WILSON_UPPER == 0.5
    assert TIE_FLAG_RATE == 0.02


def test_exact_binom_pinned_values():
    assert exact_binom_two_sided_p(6, 6) == pytest.approx(0.03125)
    assert exact_binom_two_sided_p(0, 6) == pytest.approx(0.03125)   # symmetric
    assert exact_binom_two_sided_p(5, 6) == pytest.approx(0.21875)
    assert exact_binom_two_sided_p(3, 6) == pytest.approx(1.0)       # dead center
    assert exact_binom_two_sided_p(0, 0) == 1.0                      # no data -> no evidence
    assert exact_binom_two_sided_p(9, 10) == pytest.approx(22 / 1024)  # 2*(1+10)/1024


def test_wilson_known_values():
    lo, hi = wilson_interval(0, 0)
    assert (lo, hi) == (0.0, 1.0)                                    # no data -> maximal interval
    lo, hi = wilson_interval(5, 10)
    assert lo == pytest.approx(0.2366, abs=1e-3)                     # published Wilson 95% values
    assert hi == pytest.approx(0.7634, abs=1e-3)
    lo, hi = wilson_interval(10, 10)
    assert lo == pytest.approx(0.7225, abs=1e-3)
    assert hi == 1.0
    lo, hi = wilson_interval(0, 5)
    assert lo == 0.0
    assert hi == pytest.approx(0.4345, abs=1e-3)


def test_mcnemar_counts_and_delta():
    # pairs as (hero_win_a, hero_win_b); ties were already mapped to False upstream
    pairs = [(True, True)] * 3 + [(False, False)] * 2 + [(True, False)] * 4 + [(False, True)] * 1
    c = mcnemar_counts(pairs)
    assert (c.n11, c.n00, c.n10, c.n01) == (3, 2, 4, 1)
    assert c.n_discordant == 5
    assert c.delta == pytest.approx((4 - 1) / 10)
    assert McnemarCounts(0, 0, 0, 0).delta == 0.0                    # empty-safe
