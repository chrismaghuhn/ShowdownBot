"""Pinned statistics for the chosen-line cap-hit rate acceptance rule (spec Sec.4).

Bootstrap params are pinned, not chosen after seeing results: B=10,000 resamples, one-sided
95% upper bound (95th percentile, NOT the 97.5th -- a two-sided CI's upper endpoint is a
different, more conservative quantity), RNG seeded 20260713 as its own dedicated stream.

A plain game-clustered bootstrap degenerates to a false [0%, 0%] CI when zero cap-hit events
are observed -- every possible resample can only redraw from all-zero games. The zero-event
branch instead uses the exact one-sided 95% Clopper-Pearson upper bound on a game-level
"did any decision in this game cap-hit" indicator.
"""

from __future__ import annotations

import random
from enum import Enum

BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 20260713
PASS_THRESHOLD = 0.05


class Verdict(Enum):
    PASS = "PASS"
    INCONCLUSIVE = "INCONCLUSIVE"
    FAIL = "FAIL"


def clopper_pearson_zero_upper_bound(g: int) -> float:
    """Exact one-sided 95% Clopper-Pearson upper bound at 0 observed successes out of g trials.
    Closed form: 1 - 0.05^(1/g). Equivalent to the "rule of three" approximation ~3/g for large g."""
    if g <= 0:
        raise ValueError("g must be positive")
    return 1.0 - 0.05 ** (1.0 / g)


def minimum_g_for_zero_event_pass() -> int:
    """Smallest integer G such that clopper_pearson_zero_upper_bound(G) <= 0.05."""
    g = 1
    while clopper_pearson_zero_upper_bound(g) > PASS_THRESHOLD:
        g += 1
    return g


def game_clustered_bootstrap_upper_bound(
    per_game_rate: dict[str, float], *, resamples: int = BOOTSTRAP_RESAMPLES, seed: int = BOOTSTRAP_SEED,
) -> float:
    """One-sided 95% upper bound (95th percentile) of the resampled rate distribution,
    resampling whole games with replacement."""
    games = list(per_game_rate.items())
    if not games:
        raise ValueError("no games to resample")
    rng = random.Random(seed)
    n = len(games)
    resampled_rates = []
    for _ in range(resamples):
        draw = [games[rng.randrange(n)][1] for _ in range(n)]
        resampled_rates.append(sum(draw) / n)
    resampled_rates.sort()
    idx = int(0.95 * (len(resampled_rates) - 1))
    return resampled_rates[idx]


def verdict_for_cap_hit_rate(
    *,
    per_decision_cap_hit: list[tuple[str, bool]] | list[bool],
    per_game_any_cap_hit: dict[str, bool],
    n_decisions: int,
    rng_seed: int = BOOTSTRAP_SEED,
) -> tuple[Verdict, dict]:
    if n_decisions <= 0:
        # No decisions were actually replayed/compared (e.g. every decision raised in
        # `_chosen_candidate`, per Task 10) even though `per_game_any_cap_hit` can still be
        # nonempty (game IDs are pre-seeded before the per-decision try/except). Neither the
        # zero-event Clopper-Pearson branch nor the bootstrap branch below is meaningful with
        # zero measured decisions -- fail closed to INCONCLUSIVE rather than risk a spurious
        # PASS from a run that measured nothing.
        return Verdict.INCONCLUSIVE, {
            "point_estimate": 0.0,
            "numerator": 0,
            "n_decisions": 0,
            "g": len(per_game_any_cap_hit),
            "reason": "no_decisions",
        }

    numerator = sum(
        1 for row in per_decision_cap_hit
        if (row[1] if isinstance(row, tuple) else row)
    )
    point_estimate = (numerator / n_decisions) if n_decisions else 0.0
    g = len(per_game_any_cap_hit)

    if numerator == 0:
        cp_upper = clopper_pearson_zero_upper_bound(g) if g > 0 else 1.0
        detail = {
            "point_estimate": 0.0,
            "numerator": 0,
            "n_decisions": n_decisions,
            "g": g,
            "bootstrap_ci_upper": 0.0,
            "bootstrap_ci_degenerate": True,
            "clopper_pearson_upper_bound": cp_upper,
        }
        verdict = Verdict.PASS if cp_upper <= PASS_THRESHOLD else Verdict.INCONCLUSIVE
        return verdict, detail

    # Nonzero branch: the bootstrap must resample each game's own LOCAL decision-level
    # cap-hit rate (hits_in_game / decisions_in_game), NOT the coarse binary "did this game
    # have any cap-hit at all" indicator from `per_game_any_cap_hit` -- that indicator is
    # scoped to the zero-event Clopper-Pearson branch above only (spec Sec.4, line ~490). Reusing
    # it here conflates "P(a resampled game has >=1 cap-hit decision)" with "P(a decision
    # cap-hits)", which are different quantities and makes the nonzero PASS band effectively
    # unreachable whenever cap-hits are spread one-per-game across many games (the realistic
    # case for a rare event over a corpus with many decisions per game).
    per_game_hits: dict[str, int] = {}
    per_game_total: dict[str, int] = {}
    has_game_ids = False
    for i, row in enumerate(per_decision_cap_hit):
        if isinstance(row, tuple):
            game_id, is_hit = row
            has_game_ids = True
        else:
            # Bare `list[bool]` input carries no per-decision game grouping. No real caller
            # (Task 10's `_diff_row_from_traces` builds the tuple form exclusively) is expected
            # to hit this path for the nonzero case; as a graceful, non-crashing fallback,
            # treat each ungrouped decision as its own singleton "game" so the bootstrap still
            # runs (conservatively -- this just means no within-game clustering correction is
            # possible for this input shape).
            game_id, is_hit = f"__ungrouped_decision_{i}", row
        per_game_total[game_id] = per_game_total.get(game_id, 0) + 1
        per_game_hits[game_id] = per_game_hits.get(game_id, 0) + (1 if is_hit else 0)

    per_game_rate = {
        game: (per_game_hits.get(game, 0) / per_game_total[game])
        for game in per_game_total
    }
    if has_game_ids:
        # Games present in `per_game_any_cap_hit` but with zero recorded decisions (e.g. every
        # decision in that game raised) contribute a 0.0 rate rather than being silently
        # dropped, so the resampled denominator (number of games) still matches `g`.
        for game in per_game_any_cap_hit:
            per_game_rate.setdefault(game, 0.0)

    bootstrap_upper = game_clustered_bootstrap_upper_bound(per_game_rate, seed=rng_seed)
    detail = {
        "point_estimate": point_estimate,
        "numerator": numerator,
        "n_decisions": n_decisions,
        "g": g,
        "bootstrap_ci_upper": bootstrap_upper,
        "bootstrap_ci_degenerate": False,
    }
    if point_estimate > PASS_THRESHOLD:
        verdict = Verdict.FAIL
    elif bootstrap_upper <= PASS_THRESHOLD:
        verdict = Verdict.PASS
    else:
        verdict = Verdict.INCONCLUSIVE
    return verdict, detail
