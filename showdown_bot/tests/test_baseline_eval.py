# tests/test_baseline_eval.py
from collections import Counter
from pathlib import Path

from showdown_bot.learning.dataset import group_decisions, load_rows, split_by_game
from showdown_bot.learning.baseline_eval import evaluate_baseline, BaselineMetrics

# Committed 100-game dataset artifact (660 KB .gz at the repo root). The raw
# .jsonl is gitignored; this .gz is the reproducible source of the pinned numbers.
_DS = (Path(__file__).resolve().parents[2] / "data" / "datasets" / "phase3-slice2b"
       / "rollout_labels_100g_gen9vgc2025regi_h1_v1.jsonl.gz")


def _r(game, dec, idx, **lbl):
    base = {"teacher_best": False, "chosen_by_current_heuristic": False,
            "value_gap_to_best": -1.0}
    base.update(lbl)
    return {"features": {"slot1_move_id": "tackle", "slot1_action_type": "move"},
            "metadata": {"game_id": game, "decision_id": dec, "candidate_index": idx},
            "label": base}


def test_agreement_counts_topset_and_strict():
    # A: heuristic-chosen IS teacher_best (agree)
    A = [_r("g", "A", 0, teacher_best=True, chosen_by_current_heuristic=True, value_gap_to_best=0.0),
         _r("g", "A", 1, value_gap_to_best=-2.0)]
    # B: heuristic-chosen is NOT teacher_best, gap -0.3 -> near-equal-safe miss
    B = [_r("g", "B", 0, teacher_best=True, value_gap_to_best=0.0),
         _r("g", "B", 1, chosen_by_current_heuristic=True, value_gap_to_best=-0.3)]
    m = evaluate_baseline(group_decisions(A + B))
    assert m.multi_decisions == 2
    assert m.agree_topset == 1 and m.agree_topset_total == 2          # 50%
    assert m.wrong_but_near_equal == 1                               # B is a cheap miss
    assert m.mean_regret == 0.15                                     # (0.0 + 0.3)/2
    assert m.override_opportunity == 1                               # B: chosen != best


def test_tie_decision_excluded_from_strict_but_in_topset():
    T = [_r("g", "T", 0, teacher_best=True, chosen_by_current_heuristic=True, value_gap_to_best=0.0),
         _r("g", "T", 1, teacher_best=True, value_gap_to_best=0.0),
         _r("g", "T", 2, value_gap_to_best=-1.0)]
    m = evaluate_baseline(group_decisions(T))
    assert m.ties == 1
    assert m.agree_topset == 1                  # chosen in teacher-best set
    assert m.strict_total == 0                  # tie excluded from unique-strict


def test_zero_gap_nonbest_flagged():
    Z = [_r("g", "Z", 0, teacher_best=True, chosen_by_current_heuristic=True, value_gap_to_best=0.0),
         _r("g", "Z", 1, value_gap_to_best=0.0),   # equal value, not marked best
         _r("g", "Z", 2, value_gap_to_best=-5.0)]
    m = evaluate_baseline(group_decisions(Z))
    assert m.zero_gap_nonbest_decisions == 1


def test_format_report_runs():
    A = [_r("g", "A", 0, teacher_best=True, chosen_by_current_heuristic=True, value_gap_to_best=0.0),
         _r("g", "A", 1, value_gap_to_best=-2.0)]
    from showdown_bot.learning.baseline_eval import format_report
    text = format_report(evaluate_baseline(group_decisions(A)))
    assert "Baseline Evaluation Report" in text and "joint-action class" in text


def test_multi_chosen_tie_does_not_crash_and_counts_as_topset_agree():
    # Real-data case: a forced switch/pass decision whose two candidates are
    # equivalent (the switch target lives in a dead feature column), so the
    # export marks BOTH as chosen AND both as teacher_best. These multi-chosen
    # decisions coincide exactly with the teacher ties. The evaluator must not
    # crash, must count topset agreement (any chosen is best), and must exclude
    # the decision from the unique-strict set.
    M = [_r("g", "M", 0, teacher_best=True, chosen_by_current_heuristic=True, value_gap_to_best=0.0),
         _r("g", "M", 1, teacher_best=True, chosen_by_current_heuristic=True, value_gap_to_best=0.0)]
    m = evaluate_baseline(group_decisions(M))
    assert m.multi_decisions == 1
    assert m.ties == 1
    assert m.agree_topset == 1          # any chosen row is teacher_best
    assert m.strict_total == 0          # excluded from strict (tie + multi-chosen)
    assert m.override_opportunity == 0  # heuristic chose a teacher-best option


def test_baseline_reproduces_2b0_qa_numbers():
    # HARD REQUIREMENT (slice 2b-1): the evaluator must reproduce the 2b-0 QA
    # numbers exactly on the committed dataset. Never skip — a silently-skipped
    # green test would hide metric drift.
    assert _DS.exists(), f"missing committed dataset artifact: {_DS}"
    decs = group_decisions(load_rows(str(_DS)))  # validate=True by default
    # candidate grouping must be exactly right, not coincidentally counted
    assert Counter(len(d.rows) for d in decs) == {1: 100, 2: 101, 5: 144, 6: 606}
    m = evaluate_baseline(decs)
    assert (m.rows, m.games, m.decisions) == (4658, 100, 951)
    assert (m.multi_decisions, m.forced_decisions, m.ties) == (851, 100, 100)
    assert (m.agree_topset, m.agree_topset_total) == (524, 851)        # 61.6%
    assert (m.agree_strict, m.strict_total) == (424, 751)             # 56.5%
    assert m.zero_gap_nonbest_decisions == 348                        # 36.6%
    assert m.contestable_decisions == 529                             # 55.6%
    assert m.nonzero_near_equal_decisions == 279                      # 29.3%
    assert m.trainable_decisions == 951
    # joint-action classes must cover the WHOLE unique-strict set (no stray bucket)
    assert sum(t for _, t in m.by_action.values()) == m.strict_total  # 751
    assert m.by_action["attack"] == (317, 643)                       # ATTACK 49.3%
    assert m.by_action["protect"] == (107, 108)                      # protect 99.1%


def test_seed42_split_shapes_match_report():
    assert _DS.exists(), f"missing committed dataset artifact: {_DS}"
    decs = group_decisions(load_rows(str(_DS)))
    sp = split_by_game(decs, seed=42, ratios=(0.8, 0.1, 0.1))
    shape = lambda p: (len({d.game_id for d in p}), len(p), sum(len(d.rows) for d in p))
    assert shape(sp.train) == (80, 762, 3729)
    assert shape(sp.val) == (10, 95, 467)
    assert shape(sp.test) == (10, 94, 462)
