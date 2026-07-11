import random

from showdown_bot.research.aggregation_probe import format_json, run_probe


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
