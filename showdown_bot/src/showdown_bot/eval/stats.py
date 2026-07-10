"""T5 statistics primitives (stdlib only) + the pinned verdict constants.

The thresholds are CODE, not prose (review §3): the exact binomial test cannot reach
p < 0.05 below 6 discordant pairs (a 6/6 split gives p = 2/64 = 0.03125), and no claim
may appear in a verdict line below 10. A cell whose Wilson upper bound is below 0.5 is
a "losing cell" and must surface in the verdict. Tie shares above 2% get flagged
(degeneracy suspicion). Rationale: docs/superpowers/reviews/2026-07-01-fable-t5-t6-
eval-architecture-review.md §3-4.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

N_DISCORDANT_MATH_FLOOR = 6    # below: p<0.05 mathematically unreachable
N_DISCORDANT_CLAIM_MIN = 10    # below: no claim in any verdict line (UNDERPOWERED)
LOSING_CELL_WILSON_UPPER = 0.5
TIE_FLAG_RATE = 0.02


def wilson_interval(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score 95% interval on a win proportion (ties counted as losses upstream)."""
    if n == 0:
        return (0.0, 1.0)
    phat = wins / n
    denom = 1 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    margin = (z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n))) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))


def exact_binom_two_sided_p(k: int, n: int) -> float:
    """Exact two-sided binomial test at p=0.5 ("small p-values" method): the sum of
    P(X=i) over all outcomes no more likely than the observed one. Chi-square is
    invalid at this N — this is exact by construction (math.comb)."""
    if n == 0:
        return 1.0
    total = 2 ** n
    pk = math.comb(n, k)
    return min(1.0, sum(math.comb(n, i) for i in range(n + 1) if math.comb(n, i) <= pk) / total)


@dataclass(frozen=True)
class McnemarCounts:
    n11: int  # both won
    n00: int  # both lost (ties land here — tie = not-a-win)
    n10: int  # A won, B lost
    n01: int  # B won, A lost

    @property
    def n_discordant(self) -> int:
        return self.n10 + self.n01

    @property
    def total(self) -> int:
        return self.n11 + self.n00 + self.n10 + self.n01

    @property
    def delta(self) -> float:
        """(n10 - n01) / N == winrate_A - winrate_B; 0.0 on empty input."""
        return 0.0 if self.total == 0 else (self.n10 - self.n01) / self.total


def mcnemar_counts(pairs) -> McnemarCounts:
    """pairs: iterable of (hero_win_a: bool, hero_win_b: bool)."""
    n11 = n00 = n10 = n01 = 0
    for a, b in pairs:
        if a and b:
            n11 += 1
        elif a and not b:
            n10 += 1
        elif b and not a:
            n01 += 1
        else:
            n00 += 1
    return McnemarCounts(n11, n00, n10, n01)
