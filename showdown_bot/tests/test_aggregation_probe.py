import copy
import json as _json
import random

import pytest

from showdown_bot.battle.policy import aggregate_scores as live_aggregate_scores
from showdown_bot.engine.belief.game_mode import GameMode
from showdown_bot.research.aggregation_probe import (
    SelfConsistencyError,
    format_full_fidelity_json,
    format_full_fidelity_md,
    format_json,
    replay_aggregate,
    run_full_fidelity_probe,
    run_probe,
)


def _row(game, dec, ci, *, agg, mean, worst, var, teacher_best):
    return {
        "features": {
            "heuristic_aggregate_score": agg,
            "score_mean_vs_opp": mean,
            "score_worst_response": worst,
            "score_var_vs_opp": var,
        },
        "metadata": {"game_id": game, "decision_id": dec, "candidate_index": ci},
        "label": {"teacher_best": teacher_best},
    }


def _fixture_rows():
    rows = [
        # d1: baseline(aggregate) picks c0 (10>9) = MISS; worst_case + mean-Xstd pick c1 = teacher -> FIX
        _row("g", "d1", 0, agg=10.0, mean=10.0, worst=2.0, var=16.0, teacher_best=False),
        _row("g", "d1", 1, agg=9.0, mean=9.0, worst=8.0, var=1.0, teacher_best=True),
        # d2: baseline picks c0 = HIT; worst_case picks c1 (9.95>9.0) = MISS -> BREAK
        _row("g", "d2", 0, agg=10.0, mean=10.0, worst=9.0, var=0.0, teacher_best=True),
        _row("g", "d2", 1, agg=9.9, mean=9.9, worst=9.95, var=0.0, teacher_best=False),
        # d3: single candidate -> skipped
        _row("g", "d3", 0, agg=5.0, mean=5.0, worst=5.0, var=0.0, teacher_best=True),
    ]
    return rows


def test_probe_metrics_and_teacher_semantics(monkeypatch):
    from showdown_bot.research import aggregation_probe as ap
    monkeypatch.setattr(ap, "load_rows", lambda *_a, **_k: _fixture_rows())
    r = run_probe("ignored")
    assert r["usable_decisions"] == 2
    assert r["skipped_single_candidate"] == 1
    # baseline hits teacher on d2 only -> 1/2
    assert r["baseline_teacher_agreement"] == 0.5
    wc = r["variants"]["worst_case"]
    # worst_case: changed on both (d1 c0->c1, d2 c0->c1) = 1.0
    assert wc["changed_action_rate"] == 1.0
    # worst_case fixes d1 (+1) and breaks d2 (-1) -> net teacher_agreement_delta 0
    assert wc["variant_fixed_teacher_miss"] == 1
    assert wc["variant_broke_teacher_hit"] == 1
    assert wc["teacher_agreement_delta"] == 0.0
    # mean matches baseline argmax on both -> no change
    mean = r["variants"]["mean"]
    assert mean["changed_action_rate"] == 0.0
    assert mean["teacher_agreement_delta"] == 0.0


def test_probe_is_order_independent(monkeypatch):
    from showdown_bot.research import aggregation_probe as ap
    base = _fixture_rows()
    shuffled = list(base)
    random.Random(1).shuffle(shuffled)
    monkeypatch.setattr(ap, "load_rows", lambda *_a, **_k: base)
    r1 = format_json(run_probe("x"))
    monkeypatch.setattr(ap, "load_rows", lambda *_a, **_k: shuffled)
    r2 = format_json(run_probe("x"))
    assert r1 == r2


# =============================================================================
# Full-fidelity probe (2c-Slice-0b, Task 4)
# =============================================================================

# -----------------------------------------------------------------------
# Step 1: replay_aggregate -- bit-for-bit mirror of policy.aggregate_scores
# -----------------------------------------------------------------------

@pytest.mark.parametrize("mode", [GameMode.AHEAD, GameMode.NEUTRAL, GameMode.MUST_REACT])
@pytest.mark.parametrize("weighted", [False, True])
def test_replay_aggregate_matches_live_policy(monkeypatch, mode, weighted):
    monkeypatch.setenv("SHOWDOWN_MUST_REACT_LAMBDA", "0.6")
    scores = [3.0, 7.0, -2.0, 5.5]
    weights = [0.4, 0.1, 0.2, 0.3] if weighted else None
    live = live_aggregate_scores(scores, mode, risk_lambda=0.35, weights=weights)
    replayed = replay_aggregate(
        scores, mode, risk_lambda=0.35, must_react_lambda=0.6, weights=weights
    )
    assert replayed == live  # same ops -> exact equality holds


@pytest.mark.parametrize("mode", [GameMode.AHEAD, GameMode.NEUTRAL, GameMode.MUST_REACT])
def test_replay_aggregate_empty_scores_returns_zero(mode):
    assert replay_aggregate([], mode, risk_lambda=0.5, must_react_lambda=0.6) == 0.0


def test_replay_aggregate_single_score_neutral_unweighted_returns_the_score():
    # `if len(scores) == 1: return scores[0]` edge (unweighted NEUTRAL path).
    assert replay_aggregate(
        [4.25], GameMode.NEUTRAL, risk_lambda=0.5, must_react_lambda=0.6
    ) == 4.25


@pytest.mark.parametrize("mode", [GameMode.AHEAD, GameMode.NEUTRAL, GameMode.MUST_REACT])
def test_replay_aggregate_single_score_matches_live_for_all_modes(monkeypatch, mode):
    monkeypatch.setenv("SHOWDOWN_MUST_REACT_LAMBDA", "0.6")
    live = live_aggregate_scores([4.25], mode, risk_lambda=0.5)
    assert replay_aggregate([4.25], mode, risk_lambda=0.5, must_react_lambda=0.6) == live


def test_replay_aggregate_must_react_uses_passed_lambda_not_current_env(monkeypatch):
    """must_react_lambda is passed in explicitly (the row's recorded value at
    export time) -- replay must NOT re-read the (possibly since-changed) env."""
    scores = [10.0, 2.0]
    monkeypatch.setenv("SHOWDOWN_MUST_REACT_LAMBDA", "0.6")
    exported = live_aggregate_scores(scores, GameMode.MUST_REACT)  # uses env=0.6
    monkeypatch.setenv("SHOWDOWN_MUST_REACT_LAMBDA", "0.9")  # env changes after "export"
    replayed = replay_aggregate(
        scores, GameMode.MUST_REACT, risk_lambda=0.5, must_react_lambda=0.6
    )
    assert replayed == exported


def test_replay_aggregate_ahead_ignores_risk_and_must_react_lambda():
    scores = [3.0, 9.0, -1.0]
    lo = replay_aggregate(scores, GameMode.AHEAD, risk_lambda=0.0, must_react_lambda=0.0)
    hi = replay_aggregate(scores, GameMode.AHEAD, risk_lambda=5.0, must_react_lambda=1.0)
    assert lo == hi
    weights = [0.5, 0.3, 0.2]
    lo_w = replay_aggregate(
        scores, GameMode.AHEAD, risk_lambda=0.0, must_react_lambda=0.0, weights=weights
    )
    hi_w = replay_aggregate(
        scores, GameMode.AHEAD, risk_lambda=9.0, must_react_lambda=1.0, weights=weights
    )
    assert lo_w == hi_w


def test_replay_aggregate_must_react_ignores_risk_lambda():
    scores = [3.0, 9.0, -1.0]
    v1 = replay_aggregate(scores, GameMode.MUST_REACT, risk_lambda=0.0, must_react_lambda=0.4)
    v2 = replay_aggregate(scores, GameMode.MUST_REACT, risk_lambda=99.0, must_react_lambda=0.4)
    assert v1 == v2


def test_replay_aggregate_neutral_ignores_must_react_lambda():
    scores = [3.0, 9.0, -1.0]
    v1 = replay_aggregate(scores, GameMode.NEUTRAL, risk_lambda=0.5, must_react_lambda=0.0)
    v2 = replay_aggregate(scores, GameMode.NEUTRAL, risk_lambda=0.5, must_react_lambda=1.0)
    assert v1 == v2


def test_gamemode_value_round_trips_from_aggregation_mode_string():
    # aggregation_mode is written by decision.py as `mode.value` (never `.name`)
    # -- confirm the inverse mapping run_full_fidelity_probe relies on holds.
    for mode in (GameMode.AHEAD, GameMode.NEUTRAL, GameMode.MUST_REACT):
        assert GameMode(mode.value) == mode


# -----------------------------------------------------------------------
# Step 2 + 3 fixtures: hand-computed agg-trace rows (schema per
# research/aggregation_trace.py::build_agg_row). Numbers below were verified
# against the REAL `battle.policy.aggregate_scores` (not hand arithmetic).
# -----------------------------------------------------------------------

def _cand(action_key, exported, response_scores):
    return {
        "action_key": action_key,
        "exported_aggregate_score": exported,
        "response_scores": list(response_scores),
    }


def _ff_row(battle_id, decision_index, *, mode, candidates, response_keys=("r0", "r1"),
            response_weights=(), risk_lambda=0.5, must_react_lambda=0.6, teacher_best=()):
    return {
        "battle_id": battle_id,
        "decision_index": decision_index,
        "our_side": "p1",
        "aggregation_mode": mode,
        "risk_lambda": risk_lambda,
        "must_react_lambda": must_react_lambda,
        "response_keys": list(response_keys),
        "response_weights": list(response_weights),
        "teacher_best_action_keys": list(teacher_best),
        "candidates": list(candidates),
    }


def _row_a_neutral_fix():
    """NEUTRAL, unweighted. Baseline (risk_lambda=0.5) picks c0 -- MISS (teacher
    is c1). The risk_lambda_0.0 variant (and only that swept value) flips to
    c1 -- FIX."""
    return _ff_row(
        "battle-A", 0, mode="neutral", teacher_best=["c1"],
        candidates=[_cand("c0", 9.0, [9.0, 9.0]), _cand("c1", 2.0, [14.0, 6.0])],
    )


def _row_b_neutral_break():
    """NEUTRAL, unweighted. Baseline picks c0 -- HIT (teacher is c0). The
    risk_lambda_0.0 variant (and only that swept value) flips to c1 -- BREAK."""
    return _ff_row(
        "battle-B", 0, mode="neutral", teacher_best=["c0"],
        candidates=[_cand("c0", 9.0, [9.0, 9.0]), _cand("c1", -22.0, [2.0, 18.0])],
    )


def _row_c_must_react_change():
    """MUST_REACT, unweighted. Baseline (must_react_lambda=0.6) picks c0 -- MISS
    (teacher is c1). The must_react_lambda_0.0 variant flips to c1 -- FIX."""
    return _ff_row(
        "battle-C", 0, mode="must_react", teacher_best=["c1"],
        candidates=[
            _cand("c0", 10.0, [10.0, 10.0]),
            _cand("c1", 5.6000000000000005, [20.0, 2.0]),
        ],
    )


def _row_d_ahead_weighted_vs_unweighted():
    """AHEAD, weighted [0.9, 0.1]. Baseline/`weighted` picks c0 -- MISS (teacher
    is c1). `unweighted` (plain mean) flips to c1 -- FIX."""
    return _ff_row(
        "battle-D", 0, mode="ahead", response_weights=[0.9, 0.1], teacher_best=["c1"],
        candidates=[_cand("c0", 10.0, [10.0, 10.0]), _cand("c1", 6.5, [5.0, 20.0])],
    )


def _row_e_single_candidate():
    """Single candidate: nothing can change by re-ranking -- excluded from
    variant/mode sample counts, but still self-consistency-pinned."""
    return _ff_row(
        "battle-E", 0, mode="neutral", teacher_best=["only"],
        candidates=[_cand("only", 5.0, [5.0, 5.0])],
    )


def _row_f_empty_teacher():
    """NEUTRAL, unweighted, no flips anywhere in the sweep (both candidates are
    constant across responses) -- isolates the teacher-set-empty skip
    bookkeeping from any ranking-change signal."""
    return _ff_row(
        "battle-F", 0, mode="neutral", teacher_best=[],
        candidates=[_cand("c0", 9.0, [9.0, 9.0]), _cand("c1", 5.0, [5.0, 5.0])],
    )


def _row_h_neutral_weighted():
    """NEUTRAL, weighted [0.8, 0.2] -- exercises sharpen (needs populated
    weights) and the weighted axis of the risk_lambda sweep. Baseline picks c0
    -- HIT (teacher is c0); no swept variant flips it."""
    return _ff_row(
        "battle-H", 0, mode="neutral", response_weights=[0.8, 0.2], teacher_best=["c0"],
        candidates=[
            _cand("c0", 10.0, [10.0, 10.0]),
            _cand("c1", 2.4800000000000013, [6.0, 14.0]),
        ],
    )


def _row_degenerate():
    return _ff_row(
        "battle-G", 0, mode=None, risk_lambda=None, must_react_lambda=None, candidates=[]
    )


def _ff_fixture_rows():
    return [
        _row_a_neutral_fix(), _row_b_neutral_break(), _row_c_must_react_change(),
        _row_d_ahead_weighted_vs_unweighted(), _row_e_single_candidate(),
        _row_f_empty_teacher(), _row_h_neutral_weighted(), _row_degenerate(),
    ]


# -----------------------------------------------------------------------
# Step 2: run_full_fidelity_probe -- row/mode counts, self-consistency pin
# -----------------------------------------------------------------------

def test_full_fidelity_probe_passes_on_well_formed_rows():
    run_full_fidelity_probe(_ff_fixture_rows())  # must not raise


def test_full_fidelity_probe_row_and_mode_counts():
    r = run_full_fidelity_probe(_ff_fixture_rows())
    assert r["rows_total"] == 8
    assert r["rows_skipped_degenerate_mode"] == 1
    assert r["rows_skipped_single_candidate"] == 1
    assert r["usable_rows"] == 6
    assert r["mode_counts"] == {"neutral": 4, "must_react": 1, "ahead": 1}


def test_full_fidelity_probe_self_consistency_counts():
    r = run_full_fidelity_probe(_ff_fixture_rows())
    sc = r["self_consistency"]
    assert sc["rows_checked"] == 7  # all but the degenerate row
    assert sc["candidates_checked"] == 13  # 2+2+2+2+1+2+2
    assert sc["ahead_risk_invariance_checked"] == 2  # row D's 2 candidates
    assert sc["max_abs_error"] < 1e-9


def test_full_fidelity_probe_self_consistency_pin_raises_on_perturbed_export():
    bad = copy.deepcopy(_row_a_neutral_fix())
    bad["candidates"][0]["exported_aggregate_score"] += 0.5
    with pytest.raises(SelfConsistencyError, match="battle-A"):
        run_full_fidelity_probe([bad])


def test_full_fidelity_probe_ordering_pin_raises_when_candidates_not_rank_sorted():
    bad = copy.deepcopy(_row_a_neutral_fix())
    bad["candidates"] = list(reversed(bad["candidates"]))  # candidates[0] no longer the argmax
    with pytest.raises(SelfConsistencyError, match=r"not candidates\[0\]"):
        run_full_fidelity_probe([bad])


def test_ahead_risk_invariance_guard_fires_on_a_broken_formula(monkeypatch):
    """Proves the AHEAD risk/must-react-invariance guard is wired up (not dead
    code): a deliberately-broken replay (risk-sensitive only far outside the
    normal parameter range) must trip the fatal guard."""
    from showdown_bot.research import aggregation_probe as ap

    real = ap.replay_aggregate

    def broken(scores, mode, *, risk_lambda, must_react_lambda, weights=None):
        result = real(
            scores, mode, risk_lambda=risk_lambda, must_react_lambda=must_react_lambda,
            weights=weights,
        )
        if mode == GameMode.AHEAD and scores and risk_lambda > 50:
            return result - 1.0  # only manifests for the invariance-probe's perturbed lambda
        return result

    monkeypatch.setattr(ap, "replay_aggregate", broken)
    with pytest.raises(SelfConsistencyError, match="risk-invariance"):
        run_full_fidelity_probe([_row_d_ahead_weighted_vs_unweighted()])


# -----------------------------------------------------------------------
# Step 2: NEUTRAL risk_lambda sweep -- fix + break
# -----------------------------------------------------------------------

def test_neutral_risk_lambda_0_fixes_a_teacher_miss_and_breaks_a_teacher_hit():
    r = run_full_fidelity_probe(_ff_fixture_rows())
    v = r["variants"]["risk_lambda_0.0"]
    neutral = v["by_mode"]["neutral"]
    assert neutral["sample_count"] == 4  # a, b, f, h
    assert neutral["changed_action_rate"] == pytest.approx(2 / 4)  # a, b flip; f, h don't
    assert neutral["teacher_eligible_count"] == 3  # a, b, h (f excluded: empty teacher set)
    assert neutral["teacher_rows_skipped_empty"] == 1
    assert neutral["baseline_teacher_agreement"] == pytest.approx(2 / 3)  # b, h hit; a misses
    assert neutral["variant_teacher_agreement"] == pytest.approx(2 / 3)  # a now hits, b now misses
    assert neutral["teacher_agreement_delta"] == pytest.approx(0.0)
    assert neutral["variant_fixed_teacher_miss"] == 1  # a
    assert neutral["variant_broke_teacher_hit"] == 1  # b

    # This variant is NEUTRAL-only -> global == neutral exactly, no other modes present.
    assert v["global"] == neutral
    assert set(v["by_mode"]) == {"neutral"}


@pytest.mark.parametrize("lam", [0.1, 0.25, 0.5, 0.75, 1.0])
def test_neutral_risk_lambda_other_swept_values_do_not_flip_a_or_b(lam):
    r = run_full_fidelity_probe(_ff_fixture_rows())
    v = r["variants"][f"risk_lambda_{lam}"]["by_mode"]["neutral"]
    assert v["changed_action_rate"] == pytest.approx(0.0)
    assert v["variant_fixed_teacher_miss"] == 0
    assert v["variant_broke_teacher_hit"] == 0


def test_neutral_risk_lambda_0_5_reproduces_baseline_exactly_for_unweighted_rows():
    # a, b, f all recorded risk_lambda=0.5 (the default) and are natively
    # unweighted, so sweeping to exactly 0.5 must reproduce baseline bit-for-bit.
    r = run_full_fidelity_probe(_ff_fixture_rows())
    v = r["variants"]["risk_lambda_0.5"]["by_mode"]["neutral"]
    assert v["changed_action_rate"] == 0.0
    assert v["teacher_agreement_delta"] == 0.0


# -----------------------------------------------------------------------
# Step 2: MUST_REACT must_react_lambda sweep -- change
# -----------------------------------------------------------------------

def test_must_react_lambda_0_fixes_a_teacher_miss():
    r = run_full_fidelity_probe(_ff_fixture_rows())
    v = r["variants"]["must_react_lambda_0.0"]
    must_react = v["by_mode"]["must_react"]
    assert must_react["sample_count"] == 1
    assert must_react["changed_action_rate"] == 1.0
    assert must_react["baseline_teacher_agreement"] == 0.0
    assert must_react["variant_teacher_agreement"] == 1.0
    assert must_react["variant_fixed_teacher_miss"] == 1
    assert must_react["variant_broke_teacher_hit"] == 0
    # MUST_REACT-only variant -> global == must_react exactly.
    assert v["global"] == must_react


@pytest.mark.parametrize("mrl", [0.3, 0.6, 1.0])
def test_must_react_lambda_other_swept_values_do_not_flip(mrl):
    r = run_full_fidelity_probe(_ff_fixture_rows())
    v = r["variants"][f"must_react_lambda_{mrl}"]["by_mode"]["must_react"]
    assert v["changed_action_rate"] == 0.0


def test_must_react_lambda_0_6_reproduces_baseline_exactly():
    # row C recorded must_react_lambda=0.6 (the default) and is unweighted, so
    # sweeping to exactly 0.6 must reproduce baseline bit-for-bit.
    r = run_full_fidelity_probe(_ff_fixture_rows())
    v = r["variants"]["must_react_lambda_0.6"]["by_mode"]["must_react"]
    assert v["changed_action_rate"] == 0.0
    assert v["teacher_agreement_delta"] == 0.0


# -----------------------------------------------------------------------
# Step 2: AHEAD weighted vs unweighted
# -----------------------------------------------------------------------

def test_ahead_weighted_reproduces_baseline_exactly():
    r = run_full_fidelity_probe(_ff_fixture_rows())
    weighted = r["variants"]["weighted"]["by_mode"]["ahead"]
    assert weighted["sample_count"] == 1
    assert weighted["changed_action_rate"] == 0.0  # identical inputs to baseline by construction
    assert weighted["teacher_agreement_delta"] == 0.0
    assert weighted["variant_fixed_teacher_miss"] == 0


def test_ahead_unweighted_flips_and_fixes_a_teacher_miss():
    r = run_full_fidelity_probe(_ff_fixture_rows())
    unweighted = r["variants"]["unweighted"]["by_mode"]["ahead"]
    assert unweighted["sample_count"] == 1
    assert unweighted["changed_action_rate"] == 1.0  # d flips
    assert unweighted["variant_fixed_teacher_miss"] == 1
    assert unweighted["teacher_agreement_delta"] == pytest.approx(1.0)


# -----------------------------------------------------------------------
# Step 2: unweighted merges across all three modes (the one variant name
# meaningful everywhere) -- a real pooled GLOBAL, not a degenerate single-mode
# echo like the sweep variants above.
# -----------------------------------------------------------------------

def test_unweighted_variant_merges_across_all_three_modes():
    r = run_full_fidelity_probe(_ff_fixture_rows())
    v = r["variants"]["unweighted"]
    assert set(v["by_mode"]) == {"neutral", "must_react", "ahead"}

    g = v["global"]
    assert g["sample_count"] == 6  # a,b,f,h (neutral) + c (must_react) + d (ahead)
    assert g["changed_action_rate"] == pytest.approx(1 / 6)  # only d flips
    assert g["teacher_eligible_count"] == 5  # f excluded (empty teacher set)
    assert g["baseline_teacher_agreement"] == pytest.approx(2 / 5)  # b, h hit
    assert g["variant_teacher_agreement"] == pytest.approx(3 / 5)  # b, h, d(fixed)
    assert g["teacher_agreement_delta"] == pytest.approx(0.2)
    assert g["variant_fixed_teacher_miss"] == 1
    assert g["variant_broke_teacher_hit"] == 0

    assert v["by_mode"]["neutral"]["sample_count"] == 4
    assert v["by_mode"]["neutral"]["changed_action_rate"] == 0.0
    assert v["by_mode"]["must_react"]["sample_count"] == 1
    assert v["by_mode"]["must_react"]["changed_action_rate"] == 0.0
    assert v["by_mode"]["ahead"]["sample_count"] == 1
    assert v["by_mode"]["ahead"]["changed_action_rate"] == 1.0


# -----------------------------------------------------------------------
# Step 2: flatten / sharpen (NEUTRAL only; sharpen skips unweighted rows)
# -----------------------------------------------------------------------

def test_flatten_applies_to_all_neutral_rows_regardless_of_native_weights():
    r = run_full_fidelity_probe(_ff_fixture_rows())
    v = r["variants"]["flatten"]
    assert v["global"]["sample_count"] == 4  # a, b, f, h
    assert v["skipped_no_weights"] == 0


def test_sharpen_skips_rows_without_populated_weights():
    r = run_full_fidelity_probe(_ff_fixture_rows())
    v = r["variants"]["sharpen"]
    assert v["global"]["sample_count"] == 1  # only h has populated weights
    assert v["skipped_no_weights"] == 3  # a, b, f skipped
    assert v["by_mode"]["neutral"]["sample_count"] == 1


# -----------------------------------------------------------------------
# Step 3: formatters
# -----------------------------------------------------------------------

def test_format_full_fidelity_json_is_order_independent():
    base = _ff_fixture_rows()
    shuffled = list(base)
    random.Random(7).shuffle(shuffled)
    r1 = format_full_fidelity_json(run_full_fidelity_probe(base))
    r2 = format_full_fidelity_json(run_full_fidelity_probe(shuffled))
    assert r1 == r2


def test_format_full_fidelity_json_is_valid_sorted_and_finite():
    result = run_full_fidelity_probe(_ff_fixture_rows())
    text = format_full_fidelity_json(result)
    assert text.endswith("\n")
    assert _json.loads(text) == result
    assert "NaN" not in text
    assert "Infinity" not in text


def test_format_full_fidelity_md_contains_key_sections():
    result = run_full_fidelity_probe(_ff_fixture_rows())
    text = format_full_fidelity_md(result)
    assert text.startswith("# 2c Aggregation Probe")
    assert "risk_lambda_0.0" in text
    assert "must_react_lambda_0.0" in text
    assert "weighted" in text
    assert "neutral" in text
    assert "ahead" in text
    assert "must_react" in text


def test_format_full_fidelity_md_is_order_independent():
    base = _ff_fixture_rows()
    shuffled = list(base)
    random.Random(3).shuffle(shuffled)
    m1 = format_full_fidelity_md(run_full_fidelity_probe(base))
    m2 = format_full_fidelity_md(run_full_fidelity_probe(shuffled))
    assert m1 == m2


# -----------------------------------------------------------------------
# Zero-denominator edge cases: none of the fixtures above ever put a whole
# SCOPE at teacher_eligible_count==0 or sample_count==0, so the `rate()`
# None-guards (and the by_mode-omits-empty-modes behavior) need their own
# direct coverage.
# -----------------------------------------------------------------------

def test_full_fidelity_probe_handles_empty_rows_list():
    r = run_full_fidelity_probe([])
    assert r["rows_total"] == 0
    assert r["usable_rows"] == 0
    assert r["mode_counts"] == {}
    assert r["self_consistency"]["candidates_checked"] == 0
    assert r["self_consistency"]["max_abs_error"] == 0.0
    assert r["variants"]  # the variant table itself is still fully populated
    for v in r["variants"].values():
        assert v["global"]["sample_count"] == 0
        assert v["global"]["changed_action_rate"] is None
        assert v["global"]["baseline_teacher_agreement"] is None
        assert v["by_mode"] == {}


def test_teacher_metrics_are_none_when_every_row_in_scope_has_empty_teacher_set():
    row1 = _ff_row(
        "battle-X", 0, mode="neutral", teacher_best=[],
        candidates=[_cand("c0", 9.0, [9.0, 9.0]), _cand("c1", 5.0, [5.0, 5.0])],
    )
    row2 = _ff_row(
        "battle-Y", 0, mode="neutral", teacher_best=[],
        candidates=[_cand("c0", 4.0, [4.0, 4.0]), _cand("c1", 1.0, [1.0, 1.0])],
    )
    r = run_full_fidelity_probe([row1, row2])
    v = r["variants"]["unweighted"]["by_mode"]["neutral"]
    assert v["sample_count"] == 2
    assert v["teacher_eligible_count"] == 0
    assert v["teacher_rows_skipped_empty"] == 2
    assert v["baseline_teacher_agreement"] is None
    assert v["variant_teacher_agreement"] is None
    assert v["teacher_agreement_delta"] is None
    assert v["variant_fixed_teacher_miss_rate"] is None
    assert v["variant_broke_teacher_hit_rate"] is None
    # non-teacher metrics are still computed normally regardless of teacher data.
    assert v["changed_action_rate"] == 0.0


def test_variant_scope_absent_from_by_mode_when_no_rows_of_that_mode_present():
    # Only NEUTRAL rows in the input -> the AHEAD-only "weighted" variant must
    # show global sample_count 0 and no "ahead" key in by_mode at all.
    r = run_full_fidelity_probe([_row_a_neutral_fix(), _row_b_neutral_break()])
    weighted = r["variants"]["weighted"]
    assert weighted["global"]["sample_count"] == 0
    assert weighted["global"]["changed_action_rate"] is None
    assert weighted["by_mode"] == {}
