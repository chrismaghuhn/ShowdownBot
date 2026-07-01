"""Slice 2b-2a: regret-vs-teacher evaluation + report. The GATE is regret, not
NDCG, not exact-match. Pure stdlib for the math (no lightgbm needed to test it);
the CLI (Task 4) loads a booster to produce per-candidate scores."""
from __future__ import annotations

from dataclasses import dataclass, field

from showdown_bot.learning.dataset import action_class

NEAR_EQUAL = 0.5
LOWER_BOUND_LINE = ("2b-2a uses feature-limited 45-live-feature input; this is a lower-bound "
                    "experiment, not a final judgment on reranker viability.")
NOWIN_LINE = ("NO-GO for this feature-limited model, NOT NO-GO for the reranker architecture. "
              "Next hypothesis: feature-extractor quality (-> slice 2b-2.5).")


@dataclass
class RerankerMetrics:
    n_decisions: int = 0
    heuristic_regret: float = 0.0
    model_regret: float = 0.0
    attack_heuristic_regret: float = 0.0
    attack_model_regret: float = 0.0
    heuristic_wrong_near_equal: int = 0
    model_wrong_near_equal: int = 0
    contestable_heuristic_regret: float = 0.0
    contestable_model_regret: float = 0.0
    n_attack: int = 0
    n_contestable: int = 0
    extra: dict = field(default_factory=dict)


def _gap(row) -> float:
    return abs(row["label"]["value_gap_to_best"])


def regret_metrics(scored_decisions) -> RerankerMetrics:
    """scored_decisions: iterable of (Decision, scores) where scores[i] is the
    model score for candidate i (same order as Decision.rows)."""
    m = RerankerMetrics()
    h_reg, mo_reg = [], []
    a_h, a_mo = [], []
    c_h, c_mo = [], []
    for d, scores in scored_decisions:
        m.n_decisions += 1
        chosen = d.chosen_rows()[0]
        model_idx = max(range(len(d.rows)), key=lambda i: scores[i])
        model_row = d.rows[model_idx]
        hr, mr = _gap(chosen), _gap(model_row)
        h_reg.append(hr); mo_reg.append(mr)
        if 0 < hr <= NEAR_EQUAL:
            m.heuristic_wrong_near_equal += 1
        if 0 < mr <= NEAR_EQUAL:
            m.model_wrong_near_equal += 1
        if action_class(chosen) == "attack":
            m.n_attack += 1; a_h.append(hr); a_mo.append(mr)
        contestable = any(0 < _gap(r) <= NEAR_EQUAL and not r["label"]["teacher_best"] for r in d.rows)
        if contestable:
            m.n_contestable += 1; c_h.append(hr); c_mo.append(mr)
    mean = lambda xs: round(sum(xs) / len(xs), 4) if xs else 0.0
    m.heuristic_regret, m.model_regret = mean(h_reg), mean(mo_reg)
    m.attack_heuristic_regret, m.attack_model_regret = mean(a_h), mean(a_mo)
    m.contestable_heuristic_regret, m.contestable_model_regret = mean(c_h), mean(c_mo)
    return m


def gates_pass(gate_m: RerankerMetrics) -> bool:
    """PRIMARY gate, evaluated on the ATTACK-strict test set (the trained domain):
    model regret beats heuristic regret AND no extra damage on equivalent swaps.
    (On an attack-only set, model_regret IS the attack regret.) all-strict and
    contestable are diagnostics, not gates."""
    return (gate_m.model_regret < gate_m.heuristic_regret
            and gate_m.model_wrong_near_equal <= gate_m.heuristic_wrong_near_equal)


def format_report(gate_m: RerankerMetrics, *, all_strict_m: RerankerMetrics | None = None) -> str:
    win = gates_pass(gate_m)
    lines = ["# 2b-2a Reranker Offline Eval", "", LOWER_BOUND_LINE, "",
             "## A) ATTACK-strict (PRIMARY GATE)",
             f"- decisions {gate_m.n_decisions}",
             f"- mean regret: heuristic {gate_m.heuristic_regret}  vs  model {gate_m.model_regret}",
             f"- wrong-but-near-equal: heuristic {gate_m.heuristic_wrong_near_equal}  vs  "
             f"model {gate_m.model_wrong_near_equal}"]
    if all_strict_m is not None:
        lines += ["", "## B) all-strict (diagnostic)",
                  f"- decisions {all_strict_m.n_decisions}",
                  f"- mean regret: heuristic {all_strict_m.heuristic_regret}  vs  "
                  f"model {all_strict_m.model_regret}",
                  "", "## C) contestable-only (diagnostic)",
                  f"- decisions {all_strict_m.n_contestable}",
                  f"- mean regret: heuristic {all_strict_m.contestable_heuristic_regret}  vs  "
                  f"model {all_strict_m.contestable_model_regret}"]
    lines += ["", f"## Verdict: {'GO (gate passes)' if win else 'NO-GO'}"]
    if not win:
        lines += ["", NOWIN_LINE]
    return "\n".join(lines) + "\n"
