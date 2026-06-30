"""Baseline evaluator for the Phase-3 reranker dataset (slice 2b-1).

Reproduces the 2b-0 QA metrics on any rollout-label JSONL: heuristic vs teacher
agreement (topset + unique-strict), per joint-action class (ATTACK!), contest-
ability, and explicit near-equal / zero-gap handling. Offline only — no model,
no live behavior.
"""
from __future__ import annotations

import argparse
import statistics
from dataclasses import dataclass

from showdown_bot.learning.dataset import (
    Decision, action_class, group_decisions, load_rows, split_by_game,
)

NEAR_EQUAL = 0.5  # |value_gap| <= 0.5 is "near-equal"


@dataclass
class BaselineMetrics:
    rows: int = 0
    games: int = 0
    decisions: int = 0
    multi_decisions: int = 0
    forced_decisions: int = 0
    trainable_decisions: int = 0
    ties: int = 0
    # agreement
    agree_topset: int = 0          # chosen in teacher-best set (multi)
    agree_topset_total: int = 0
    agree_strict: int = 0          # unique chosen == unique teacher_best (multi, non-tie)
    strict_total: int = 0
    # near-equal / zero-gap (the 2b-2 training-safety signal)
    wrong_but_near_equal: int = 0      # disagree but |chosen gap| <= 0.5
    mean_regret: float = 0.0           # mean |chosen value_gap| over multi
    override_opportunity: int = 0      # multi decisions where chosen is not teacher_best
    contestable_decisions: int = 0     # >=1 non-best alt with |gap| <= 0.5
    zero_gap_nonbest_decisions: int = 0
    nonzero_near_equal_decisions: int = 0
    # value_gap distribution over non-best rows (reporting)
    nonbest_gap_median: float = 0.0
    nonbest_gap_mean: float = 0.0
    nonbest_gap_min: float = 0.0
    # per joint-action class (chosen row), unique-strict multi only
    by_action: dict | None = None      # cls -> (agree, total)


def _pct(a: int, b: int) -> str:
    return f"{a}/{b} = {100*a/b:.1f}%" if b else f"{a}/0 = n/a"


def evaluate_baseline(decisions: list[Decision]) -> BaselineMetrics:
    m = BaselineMetrics(by_action={})
    m.decisions = len(decisions)
    m.games = len({d.game_id for d in decisions})
    m.rows = sum(len(d.rows) for d in decisions)
    regrets: list[float] = []
    nonbest_gaps: list[float] = []
    for d in decisions:
        if all(r["metadata"].get("teacher_config", {}).get("trainable_label") is True
               for r in d.rows):
            m.trainable_decisions += 1
        if d.is_tie:
            m.ties += 1
        for r in d.rows:
            if not r["label"]["teacher_best"] and r["label"]["value_gap_to_best"] is not None:
                nonbest_gaps.append(r["label"]["value_gap_to_best"])
        near = [r for r in d.rows
                if not r["label"]["teacher_best"]
                and r["label"]["value_gap_to_best"] is not None
                and abs(r["label"]["value_gap_to_best"]) <= NEAR_EQUAL]
        if near:
            m.contestable_decisions += 1
        if d.zero_gap_nonbest_count() > 0:
            m.zero_gap_nonbest_decisions += 1
        if any(0.0 < abs(r["label"]["value_gap_to_best"]) <= NEAR_EQUAL for r in near):
            m.nonzero_near_equal_decisions += 1
        if not d.is_multi_candidate:
            m.forced_decisions += 1
            continue
        m.multi_decisions += 1
        chosen = d.chosen_row()  # fail-fast: raises on != 1 heuristic choice
        gap = chosen["label"]["value_gap_to_best"]
        regrets.append(abs(gap) if gap is not None else 0.0)
        in_best = chosen["label"]["teacher_best"]
        m.agree_topset_total += 1
        if in_best:
            m.agree_topset += 1
        else:
            m.override_opportunity += 1
            if gap is not None and abs(gap) <= NEAR_EQUAL:
                m.wrong_but_near_equal += 1
        # strict + per-action-class on the SAME unique-strict set so by_action
        # denominators match the 2b-0 QA (attack 643 + protect 108 == 751).
        if not d.is_tie:
            m.strict_total += 1
            if in_best:
                m.agree_strict += 1
            cls = action_class(chosen)
            agree, total = m.by_action.get(cls, (0, 0))
            m.by_action[cls] = (agree + (1 if in_best else 0), total + 1)
    m.mean_regret = round(sum(regrets) / len(regrets), 4) if regrets else 0.0
    if nonbest_gaps:
        m.nonbest_gap_median = round(statistics.median(nonbest_gaps), 4)
        m.nonbest_gap_mean = round(statistics.mean(nonbest_gaps), 4)
        m.nonbest_gap_min = round(min(nonbest_gaps), 4)
    return m


def format_report(m: BaselineMetrics) -> str:
    lines = ["# Baseline Evaluation Report", "",
             f"- rows {m.rows} · games {m.games} · decisions {m.decisions} "
             f"(multi {m.multi_decisions}, forced {m.forced_decisions}, "
             f"trainable {m.trainable_decisions}, ties {m.ties})",
             "",
             "## Heuristic vs Teacher",
             f"- topset agreement (multi): {_pct(m.agree_topset, m.agree_topset_total)}",
             f"- unique-strict agreement: {_pct(m.agree_strict, m.strict_total)}",
             f"- mean regret (|value_gap| of chosen, multi): {m.mean_regret}",
             f"- override opportunity (multi, chosen != teacher_best): "
             f"{_pct(m.override_opportunity, m.multi_decisions)}",
             "",
             "## Near-equal / zero-gap (training-safety)",
             f"- wrong-but-near-equal (disagree, |gap| <= {NEAR_EQUAL}): {m.wrong_but_near_equal}",
             f"- contestable decisions (>=1 non-best |gap| <= {NEAR_EQUAL}): "
             f"{_pct(m.contestable_decisions, m.decisions)}",
             f"- zero-gap non-best alternative: {_pct(m.zero_gap_nonbest_decisions, m.decisions)}",
             f"- nonzero near-equal (0 < |gap| <= {NEAR_EQUAL}): "
             f"{_pct(m.nonzero_near_equal_decisions, m.decisions)}",
             f"- non-best value_gap: median {m.nonbest_gap_median}, mean {m.nonbest_gap_mean}, "
             f"min {m.nonbest_gap_min}",
             "",
             "## By chosen joint-action class (unique-strict multi only)"]
    for cls in sorted(m.by_action or {}):
        a, t = m.by_action[cls]
        lines.append(f"- {cls}: {_pct(a, t)}")
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Baseline eval for rollout-label JSONL")
    ap.add_argument("path", help="path to .jsonl or .jsonl.gz")
    ap.add_argument("--split-seed", type=int, default=None,
                    help="if set, also print per-split (train/val/test) headline metrics")
    ap.add_argument("--out", default=None, help="write the markdown report to this path")
    args = ap.parse_args(argv)
    decisions = group_decisions(load_rows(args.path))
    m = evaluate_baseline(decisions)
    report = format_report(m)
    if args.split_seed is not None:
        sp = split_by_game(decisions, seed=args.split_seed)
        report += "\n## Per-split (seed %d)\n" % args.split_seed
        for name, part in (("train", sp.train), ("val", sp.val), ("test", sp.test)):
            pm = evaluate_baseline(part)
            report += (f"- {name}: {pm.games}g/{pm.decisions}d/{pm.rows}r · "
                       f"strict {_pct(pm.agree_strict, pm.strict_total)} · "
                       f"ATTACK {_pct(*(pm.by_action or {}).get('attack', (0, 0)))}\n")
    print(report)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(report)
    return m


if __name__ == "__main__":
    main()
