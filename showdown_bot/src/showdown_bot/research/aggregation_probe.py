"""Offline 2c aggregation probe (C-path / research; NO live-path changes, NO RNG, NO battles).

Question: would re-aggregating a decision's candidates under a different opponent-response RISK
function change the chosen action and/or its agreement with the rollout teacher — measured ONLY on
already-persisted 2b-2.5a features?

REDUCED FIDELITY (important, stated in the report): the raw per-opponent-response score vectors and
response weights are NOT persisted in the dataset (features.py consumes them into summary stats and
discards them). So the risk "variants" here are proxies built from the persisted per-candidate
summaries — `heuristic_aggregate_score` (already the risk_lambda-weighted baseline), `score_mean_vs_opp`,
`score_worst_response`, `score_var_vs_opp`. They capture the mean/worst/mean-variance axes, NOT an
arbitrary risk_lambda sweep or true CVaR over the full response vector. A null result here rules the
response-risk direction out cheaply; a positive result justifies a full-fidelity re-run that exports
the raw vectors.

Baseline action = argmax(`heuristic_aggregate_score`) (apples-to-apples with the argmax variants; the
live tera/tie-break logic is deliberately not modelled). Teacher = the `teacher_best` candidate set.
Everything is deterministic (candidate-index tie-break, sorted output, no RNG).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from statistics import mean, pvariance

from showdown_bot.engine.belief.game_mode import GameMode
from showdown_bot.learning.dataset import group_decisions, load_rows

PROBE_SCHEMA_VERSION = "2c-aggregation-probe-v1"

# Per-candidate summary features this probe requires (finite) to use a decision.
REQUIRED_FEATURES = (
    "heuristic_aggregate_score",
    "score_mean_vs_opp",
    "score_worst_response",
    "score_var_vs_opp",
)

NEAR_TIE_EPS = 1e-6


def _mean_minus_lambda_std(lam: float):
    def scorer(f: dict) -> float:
        return f["score_mean_vs_opp"] - lam * math.sqrt(max(0.0, float(f["score_var_vs_opp"])))
    return scorer


# name -> scorer(features)->float (higher = better). "baseline_aggregate" is the reference.
VARIANTS: dict = {
    "baseline_aggregate": lambda f: float(f["heuristic_aggregate_score"]),
    "mean": lambda f: float(f["score_mean_vs_opp"]),
    "worst_case": lambda f: float(f["score_worst_response"]),
    "mean_minus_0.5std": _mean_minus_lambda_std(0.5),
    "mean_minus_1.0std": _mean_minus_lambda_std(1.0),
    "mean_minus_2.0std": _mean_minus_lambda_std(2.0),
}
BASELINE = "baseline_aggregate"


def _finite(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _usable(decision) -> bool:
    if len(decision.rows) < 2:
        return False  # single-candidate / forced: nothing can change
    for row in decision.rows:
        f = row["features"]
        if any((k not in f) or not _finite(f[k]) for k in REQUIRED_FEATURES):
            return False
    return True


def _ranked(decision, scorer) -> list[int]:
    """candidate_index order, best first; deterministic tie-break by candidate_index asc."""
    scored = [
        (row["metadata"]["candidate_index"], float(scorer(row["features"])))
        for row in decision.rows
    ]
    scored.sort(key=lambda t: (-t[1], t[0]))
    return [ci for ci, _s in scored]


def _score_of(decision, scorer, candidate_index: int) -> float:
    for row in decision.rows:
        if row["metadata"]["candidate_index"] == candidate_index:
            return float(scorer(row["features"]))
    raise KeyError(candidate_index)


def _teacher_best_set(decision) -> set[int]:
    return {
        row["metadata"]["candidate_index"]
        for row in decision.rows
        if bool(row["label"].get("teacher_best"))
    }


@dataclass
class _VariantAcc:
    changed: int = 0
    agree: int = 0
    fixed_teacher_miss: int = 0
    broke_teacher_hit: int = 0
    top2_flip: int = 0
    margin_delta_sum: float = 0.0
    changed_in_near_tie: int = 0


def run_probe(dataset_path: str, *, variants: dict | None = None) -> dict:
    variants = variants or VARIANTS
    if BASELINE not in variants:
        raise ValueError(f"variants must include the reference {BASELINE!r}")
    rows = load_rows(str(dataset_path), validate=True)
    decisions = group_decisions(rows)

    usable = 0
    skipped_single = 0
    skipped_missing = 0
    near_tie = 0
    baseline_agree = 0
    acc = {name: _VariantAcc() for name in variants if name != BASELINE}

    for d in decisions:
        if len(d.rows) < 2:
            skipped_single += 1
            continue
        if not _usable(d):
            skipped_missing += 1
            continue
        usable += 1
        tb = _teacher_best_set(d)
        base_rank = _ranked(d, variants[BASELINE])
        base_top = base_rank[0]
        base_top1_score = _score_of(d, variants[BASELINE], base_rank[0])
        base_top2_score = _score_of(d, variants[BASELINE], base_rank[1])
        base_margin = base_top1_score - base_top2_score
        is_near_tie = base_margin < NEAR_TIE_EPS
        if is_near_tie:
            near_tie += 1
        base_hits = base_top in tb
        if base_hits:
            baseline_agree += 1

        for name, scorer in variants.items():
            if name == BASELINE:
                continue
            a = acc[name]
            rank = _ranked(d, scorer)
            top = rank[0]
            var_hits = top in tb
            if var_hits:
                a.agree += 1
            if top != base_top:
                a.changed += 1
                if is_near_tie:
                    a.changed_in_near_tie += 1
            if not base_hits and var_hits:
                a.fixed_teacher_miss += 1
            if base_hits and not var_hits:
                a.broke_teacher_hit += 1
            if rank[:2] != base_rank[:2]:
                a.top2_flip += 1
            var_margin = _score_of(d, scorer, rank[0]) - _score_of(d, scorer, rank[1])
            a.margin_delta_sum += (var_margin - base_margin)

    def _rate(n: int) -> float | None:
        return (n / usable) if usable else None

    variant_report = {}
    for name in sorted(acc):
        a = acc[name]
        variant_report[name] = {
            "changed_action_rate": _rate(a.changed),
            "teacher_agreement_delta": (
                (a.agree - baseline_agree) / usable if usable else None
            ),
            "variant_teacher_agreement": _rate(a.agree),
            "variant_fixed_teacher_miss": a.fixed_teacher_miss,
            "variant_fixed_teacher_miss_rate": _rate(a.fixed_teacher_miss),
            "variant_broke_teacher_hit": a.broke_teacher_hit,
            "variant_broke_teacher_hit_rate": _rate(a.broke_teacher_hit),
            "top2_flip_rate": _rate(a.top2_flip),
            "mean_margin_delta": (a.margin_delta_sum / usable) if usable else None,
            "changed_in_near_tie": a.changed_in_near_tie,
        }

    return {
        "probe_schema_version": PROBE_SCHEMA_VERSION,
        "fidelity": "reduced-summary-proxy (raw per-response vectors not persisted)",
        "dataset_decisions_total": len(decisions),
        "usable_decisions": usable,
        "skipped_single_candidate": skipped_single,
        "skipped_missing_data": skipped_missing,
        "near_tie_decisions": near_tie,
        "near_tie_rate": _rate(near_tie),
        "baseline_teacher_agreement": _rate(baseline_agree),
        "variants": variant_report,
    }


def format_md(report: dict) -> str:
    lines = [
        "# 2c Aggregation Probe — reduced-fidelity, offline on 2b-2.5a",
        "",
        f"**Fidelity:** {report['fidelity']}. Baseline = argmax(heuristic_aggregate_score); "
        "teacher = teacher_best set. No live-path changes, no RNG, no battles.",
        "",
        f"- decisions total: {report['dataset_decisions_total']}",
        f"- **usable (multi-candidate, features finite): {report['usable_decisions']}**",
        f"- skipped single-candidate: {report['skipped_single_candidate']}",
        f"- skipped missing-data: {report['skipped_missing_data']}",
        f"- near-tie decisions: {report['near_tie_decisions']} "
        f"(rate {report['near_tie_rate']})",
        f"- baseline teacher-agreement: {report['baseline_teacher_agreement']}",
        "",
        "| variant | changed_action | teacher_agree_Δ | fixed_miss | broke_hit | top2_flip | mean_margin_Δ |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name in sorted(report["variants"]):
        v = report["variants"][name]
        def fmt(x):
            return f"{x:.4f}" if isinstance(x, float) else str(x)
        lines.append(
            f"| {name} | {fmt(v['changed_action_rate'])} | {fmt(v['teacher_agreement_delta'])} "
            f"| {v['variant_fixed_teacher_miss']} | {v['variant_broke_teacher_hit']} "
            f"| {fmt(v['top2_flip_rate'])} | {fmt(v['mean_margin_delta'])} |"
        )
    return "\n".join(lines) + "\n"


def format_json(report: dict) -> str:
    return json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


# =============================================================================
# Full-fidelity probe (2c-Slice-0b, Task 4).
#
# Replays `battle/policy.py::aggregate_scores` against the exact per-candidate
# x per-opponent-response score matrices exported by `research/aggregation_trace.py`
# (Tasks 1-3). Unlike the reduced-fidelity probe above (proxy summary stats from
# the 2b-2.5a dataset), this operates on the raw score vectors, so it can (a)
# self-consistency-check the replay formula against the live-produced
# `exported_aggregate_score` (a fatal pin -- any mismatch means the replay
# formula has drifted from policy.py and every downstream number here is
# meaningless), and (b) sweep mode-appropriate risk/weight variants exactly.
#
# Still offline/research-only: no RNG, no battles, no live-path changes.
# =============================================================================

FULL_FIDELITY_PROBE_SCHEMA_VERSION = "2c-full-fidelity-probe-v1"

NEUTRAL_RISK_LAMBDAS: tuple[float, ...] = (0.0, 0.1, 0.25, 0.5, 0.75, 1.0)
MUST_REACT_LAMBDAS: tuple[float, ...] = (0.0, 0.3, 0.6, 1.0)

# Perturbation used only to PROVE the AHEAD-mode risk-invariance (AHEAD ignores
# risk_lambda/must_react_lambda entirely -- see policy.py::aggregate_scores).
# Any finite, sufficiently-different value works; magnitude is irrelevant since
# the AHEAD branch never reads either knob.
_INVARIANCE_PROBE_DELTA = 137.0


class SelfConsistencyError(RuntimeError):
    """Fatal: a replayed aggregate score did not reproduce the live-policy-produced
    `exported_aggregate_score` (or an internal ordering/invariance check failed).
    This means `replay_aggregate` has drifted from `battle/policy.py::aggregate_scores`
    -- every downstream variant number would be meaningless, so the probe raises
    immediately rather than silently continuing."""


def replay_aggregate(
    scores: list[float],
    mode: GameMode,
    *,
    risk_lambda: float,
    must_react_lambda: float,
    weights: list[float] | None = None,
) -> float:
    """Bit-for-bit mirror of battle/policy.py::aggregate_scores. Unweighted paths
    use statistics.mean/pvariance EXACTLY as policy.py, so replay reproduces the
    live exported_aggregate_score exactly (the self-consistency pin depends on it).
    Weighted paths use the same explicit float sums policy.py uses. `mode` is a
    GameMode enum; `must_react_lambda` is passed in (the probe sweeps it) — for a
    faithful replay of a MUST_REACT row, pass the row's own must_react_lambda."""
    if not scores:
        return 0.0
    use_weights = weights is not None and len(weights) == len(scores) and sum(weights) > 0
    if mode == GameMode.MUST_REACT:
        worst = min(scores)
        if use_weights:
            wsum = sum(weights)
            avg = sum(s * w for s, w in zip(scores, weights)) / wsum
        else:
            avg = mean(scores)
        return avg - must_react_lambda * (avg - worst)
    if use_weights:
        wsum = sum(weights)
        wmean = sum(s * w for s, w in zip(scores, weights)) / wsum
        if mode == GameMode.AHEAD:
            return wmean
        wvar = sum(w * (s - wmean) ** 2 for s, w in zip(scores, weights)) / wsum
        return wmean - risk_lambda * wvar
    if mode == GameMode.AHEAD:
        return mean(scores)
    if len(scores) == 1:
        return scores[0]
    return mean(scores) - risk_lambda * pvariance(scores)


def _mode_from_row(value: str) -> GameMode:
    """`aggregation_mode` is written by battle/decision.py as
    ``mode.value if hasattr(mode, "value") else str(mode)`` -- i.e. always the
    plain ``GameMode.value`` string ("neutral"/"ahead"/"must_react"), never the
    ``GameMode.NAME`` form (that is the separate ``game_mode`` field). GameMode
    is a ``(str, Enum)``, so value-based construction recovers the exact member:
    ``GameMode("ahead") == GameMode.AHEAD``."""
    return GameMode(value)


def _rank_indices(values: list[float]) -> list[int]:
    """Candidate-list indices, best first; ties broken by ascending index (lower
    index / earlier list position wins) -- mirrors decision.py's own
    ``scored.sort(key=lambda t: (-t[2], _label_ja(...)))`` insofar as the exported
    ``candidates`` list is ALREADY rank-sorted, so this reproduces that order."""
    return sorted(range(len(values)), key=lambda i: (-values[i], i))


@dataclass
class _ScopeAcc:
    sample_count: int = 0
    changed: int = 0
    near_tie: int = 0
    changed_in_near_tie: int = 0
    top2_flip: int = 0
    margin_delta_sum: float = 0.0
    teacher_eligible: int = 0
    teacher_skipped_empty: int = 0
    baseline_hits: int = 0
    variant_hits: int = 0
    fixed_miss: int = 0
    broke_hit: int = 0

    def finalize(self) -> dict:
        def rate(n: float, d: int) -> float | None:
            return (n / d) if d else None

        return {
            "sample_count": self.sample_count,
            "changed_action_rate": rate(self.changed, self.sample_count),
            "near_tie_rate": rate(self.near_tie, self.sample_count),
            "changed_in_near_tie": self.changed_in_near_tie,
            "top2_flip_rate": rate(self.top2_flip, self.sample_count),
            "mean_margin_delta": rate(self.margin_delta_sum, self.sample_count),
            "teacher_eligible_count": self.teacher_eligible,
            "teacher_rows_skipped_empty": self.teacher_skipped_empty,
            "baseline_teacher_agreement": rate(self.baseline_hits, self.teacher_eligible),
            "variant_teacher_agreement": rate(self.variant_hits, self.teacher_eligible),
            "teacher_agreement_delta": rate(
                self.variant_hits - self.baseline_hits, self.teacher_eligible
            ),
            "variant_fixed_teacher_miss": self.fixed_miss,
            "variant_fixed_teacher_miss_rate": rate(self.fixed_miss, self.teacher_eligible),
            "variant_broke_teacher_hit": self.broke_hit,
            "variant_broke_teacher_hit_rate": rate(self.broke_hit, self.teacher_eligible),
        }


# ---------------------------------------------------------------------------
# Variant scorers: each maps a "row context" dict (see `_row_context`) to a
# list[float] of per-candidate variant-aggregate scores (parallel to
# row["candidates"]), or None to mean "skip this row for this variant" (only
# `sharpen` does this, when the row has no populated weights to sharpen).
# ---------------------------------------------------------------------------

def _replay_all(rd: dict, *, risk_lambda: float, must_react_lambda: float,
                 weights: list[float] | None) -> list[float]:
    return [
        replay_aggregate(
            c["response_scores"], rd["mode"],
            risk_lambda=risk_lambda, must_react_lambda=must_react_lambda, weights=weights,
        )
        for c in rd["candidates"]
    ]


def _variant_risk_lambda(lam: float):
    def fn(rd: dict) -> list[float]:
        return _replay_all(
            rd, risk_lambda=lam, must_react_lambda=rd["must_react_lambda"], weights=rd["weights"]
        )
    return fn


def _variant_must_react_lambda(mrl: float):
    def fn(rd: dict) -> list[float]:
        return _replay_all(
            rd, risk_lambda=rd["risk_lambda"], must_react_lambda=mrl, weights=rd["weights"]
        )
    return fn


def _variant_unweighted(rd: dict) -> list[float]:
    return _replay_all(
        rd, risk_lambda=rd["risk_lambda"], must_react_lambda=rd["must_react_lambda"], weights=None
    )


def _variant_weighted(rd: dict) -> list[float]:
    """AHEAD-only. Uses the row's own (natural) weights -- identical inputs to
    what produced ``exported_aggregate_score``, so this is expected to always
    reproduce the baseline ranking exactly; it exists as the named counterpart
    to `unweighted` for the AHEAD weighted-vs-unweighted contrast."""
    return _replay_all(
        rd, risk_lambda=rd["risk_lambda"], must_react_lambda=rd["must_react_lambda"],
        weights=rd["weights"],
    )


def _variant_flatten(rd: dict) -> list[float]:
    n = len(rd["response_keys"])
    flat = [1.0 / n] * n if n else []
    return _replay_all(
        rd, risk_lambda=rd["risk_lambda"], must_react_lambda=rd["must_react_lambda"],
        weights=(flat or None),
    )


def _variant_sharpen(rd: dict) -> list[float] | None:
    w = rd["weights"]
    if not w:
        return None  # no populated weights to sharpen -- skip this row
    sq = [x * x for x in w]
    total = sum(sq)
    if total <= 0:
        return None
    sharp = [x / total for x in sq]
    return _replay_all(
        rd, risk_lambda=rd["risk_lambda"], must_react_lambda=rd["must_react_lambda"],
        weights=sharp,
    )


def _variant_table() -> dict[str, dict]:
    table: dict[str, dict] = {}
    for lam in NEUTRAL_RISK_LAMBDAS:
        table[f"risk_lambda_{lam}"] = {"modes": {GameMode.NEUTRAL}, "fn": _variant_risk_lambda(lam)}
    table["flatten"] = {"modes": {GameMode.NEUTRAL}, "fn": _variant_flatten}
    table["sharpen"] = {"modes": {GameMode.NEUTRAL}, "fn": _variant_sharpen}
    for mrl in MUST_REACT_LAMBDAS:
        table[f"must_react_lambda_{mrl}"] = {
            "modes": {GameMode.MUST_REACT}, "fn": _variant_must_react_lambda(mrl)
        }
    table["weighted"] = {"modes": {GameMode.AHEAD}, "fn": _variant_weighted}
    # "unweighted" is the one variant meaningful in every mode -- a single merged
    # entry with a real GLOBAL (pooled across all 3 modes) plus a by_mode split.
    table["unweighted"] = {
        "modes": {GameMode.NEUTRAL, GameMode.MUST_REACT, GameMode.AHEAD},
        "fn": _variant_unweighted,
    }
    return table


def _row_sort_key(row: dict) -> tuple[str, int, str]:
    """Canonical row order, independent of input list order -- makes every float
    accumulation below a pure function of row CONTENT, not of caller-supplied
    order (required for the order-independence guarantee: IEEE754 addition is
    not associative, so summing usable rows in a different order can change the
    last bit of a sum; sorting first removes that dependency entirely)."""
    return (
        str(row.get("battle_id", "")),
        int(row.get("decision_index", 0) or 0),
        str(row.get("our_side", "")),
    )


def _row_context(row: dict) -> dict:
    return {
        "row": row,
        "mode": _mode_from_row(row["aggregation_mode"]),
        "mode_val": row["aggregation_mode"],
        "risk_lambda": row["risk_lambda"],
        "must_react_lambda": row["must_react_lambda"],
        "weights": (row.get("response_weights") or None),
        "response_keys": row.get("response_keys") or [],
        "candidates": row["candidates"],
    }


def _check_self_consistency(rd: dict, stats: dict) -> list[float]:
    """The HARD, fatal pin: replay every candidate and assert it reproduces
    exported_aggregate_score; assert candidates[0] is the true argmax; for
    AHEAD rows additionally assert risk/must-react invariance. Returns the
    list of exported scores (parallel to rd["candidates"]) for reuse."""
    row = rd["row"]
    exported: list[float] = []
    for c in rd["candidates"]:
        replayed = replay_aggregate(
            c["response_scores"], rd["mode"],
            risk_lambda=rd["risk_lambda"], must_react_lambda=rd["must_react_lambda"],
            weights=rd["weights"],
        )
        err = abs(replayed - c["exported_aggregate_score"])
        stats["max_abs_error"] = max(stats["max_abs_error"], err)
        stats["candidates_checked"] += 1
        if err > 1e-9:
            raise SelfConsistencyError(
                f"replay mismatch battle_id={row.get('battle_id')!r} "
                f"decision_index={row.get('decision_index')!r} "
                f"action_key={c['action_key']!r}: replayed={replayed!r} "
                f"exported={c['exported_aggregate_score']!r}"
            )
        if rd["mode"] == GameMode.AHEAD:
            stats["ahead_risk_invariance_checked"] += 1
            perturbed = replay_aggregate(
                c["response_scores"], rd["mode"],
                risk_lambda=rd["risk_lambda"] + _INVARIANCE_PROBE_DELTA,
                must_react_lambda=rd["must_react_lambda"] + _INVARIANCE_PROBE_DELTA,
                weights=rd["weights"],
            )
            if abs(perturbed - replayed) > 1e-9:
                raise SelfConsistencyError(
                    f"AHEAD risk-invariance violated battle_id={row.get('battle_id')!r} "
                    f"decision_index={row.get('decision_index')!r} "
                    f"action_key={c['action_key']!r}: base={replayed!r} "
                    f"perturbed(risk_lambda+must_react_lambda+{_INVARIANCE_PROBE_DELTA})={perturbed!r}"
                )
        exported.append(c["exported_aggregate_score"])

    if exported:
        argmax_rank = _rank_indices(exported)
        if argmax_rank[0] != 0:
            raise SelfConsistencyError(
                f"candidate ordering mismatch battle_id={row.get('battle_id')!r} "
                f"decision_index={row.get('decision_index')!r}: argmax is index "
                f"{argmax_rank[0]} ({rd['candidates'][argmax_rank[0]]['action_key']!r}), "
                f"not candidates[0] ({rd['candidates'][0]['action_key']!r})"
            )
    return exported


def _accumulate(acc: _ScopeAcc, rd: dict, scores: list[float]) -> None:
    acc.sample_count += 1
    variant_rank = _rank_indices(scores)
    var_top_idx = variant_rank[0]
    var_top_key = rd["candidates"][var_top_idx]["action_key"]
    changed = var_top_key != rd["base_top_key"]
    if changed:
        acc.changed += 1
        if rd["is_near_tie"]:
            acc.changed_in_near_tie += 1
    if rd["is_near_tie"]:
        acc.near_tie += 1
    if variant_rank[:2] != rd["baseline_rank"][:2]:
        acc.top2_flip += 1
    var_margin = scores[variant_rank[0]] - scores[variant_rank[1]]
    acc.margin_delta_sum += (var_margin - rd["base_margin"])

    if rd["teacher_ok"]:
        acc.teacher_eligible += 1
        var_hit = var_top_key in rd["teacher_set"]
        base_hit = rd["base_hit"]
        if base_hit:
            acc.baseline_hits += 1
        if var_hit:
            acc.variant_hits += 1
        if not base_hit and var_hit:
            acc.fixed_miss += 1
        if base_hit and not var_hit:
            acc.broke_hit += 1
    else:
        acc.teacher_skipped_empty += 1


def run_full_fidelity_probe(rows: list[dict]) -> dict:
    """Mode-aware, full-fidelity aggregation probe (2c-Slice-0b, Task 4).

    ``rows`` are full-fidelity agg-trace rows as produced by
    ``research.aggregation_trace.build_agg_row`` / loaded via
    ``research.aggregation_trace.load_agg_trace`` (one row per DECISION, not
    per-candidate). Deterministic, pure, no RNG: rows are processed in a
    canonical sort order (see ``_row_sort_key``) so the result is independent
    of the input list's order, including in float-accumulation edge cases.

    Raises ``SelfConsistencyError`` (fatal) if any row's replayed aggregate
    does not reproduce its exported_aggregate_score, if the exported
    ``candidates`` order does not match the argmax, or if an AHEAD-mode row's
    aggregate is (incorrectly) sensitive to risk_lambda/must_react_lambda.
    """
    rows = sorted(rows, key=_row_sort_key)

    rows_total = len(rows)
    skipped_degenerate = 0
    skipped_single = 0
    mode_counts: dict[str, int] = {}
    usable: list[dict] = []
    stats = {"candidates_checked": 0, "max_abs_error": 0.0, "ahead_risk_invariance_checked": 0}

    for row in rows:
        if row.get("aggregation_mode") is None:
            skipped_degenerate += 1
            continue
        rd = _row_context(row)
        exported = _check_self_consistency(rd, stats)

        if len(rd["candidates"]) < 2:
            skipped_single += 1
            continue

        baseline_rank = _rank_indices(exported)
        base_top_idx = baseline_rank[0]
        base_top_key = rd["candidates"][base_top_idx]["action_key"]
        base_margin = exported[baseline_rank[0]] - exported[baseline_rank[1]]
        teacher_set = set(row.get("teacher_best_action_keys") or [])
        teacher_ok = bool(teacher_set)

        rd.update(
            baseline_rank=baseline_rank,
            base_top_key=base_top_key,
            base_margin=base_margin,
            is_near_tie=base_margin < NEAR_TIE_EPS,
            teacher_set=teacher_set,
            teacher_ok=teacher_ok,
            base_hit=(base_top_key in teacher_set) if teacher_ok else False,
        )
        usable.append(rd)
        mode_counts[rd["mode_val"]] = mode_counts.get(rd["mode_val"], 0) + 1

    variants_report: dict[str, dict] = {}
    table = _variant_table()
    for name in sorted(table):
        spec = table[name]
        modes_allowed = spec["modes"]
        fn = spec["fn"]
        acc_global = _ScopeAcc()
        acc_by_mode: dict[str, _ScopeAcc] = {}
        skipped_no_weights = 0
        for rd in usable:
            if rd["mode"] not in modes_allowed:
                continue
            scores = fn(rd)
            if scores is None:
                skipped_no_weights += 1
                continue
            _accumulate(acc_global, rd, scores)
            acc_mode = acc_by_mode.setdefault(rd["mode_val"], _ScopeAcc())
            _accumulate(acc_mode, rd, scores)
        variants_report[name] = {
            "global": acc_global.finalize(),
            "by_mode": {m: acc_by_mode[m].finalize() for m in sorted(acc_by_mode)},
            "skipped_no_weights": skipped_no_weights,
        }

    return {
        "probe_schema_version": FULL_FIDELITY_PROBE_SCHEMA_VERSION,
        "rows_total": rows_total,
        "rows_skipped_degenerate_mode": skipped_degenerate,
        "rows_skipped_single_candidate": skipped_single,
        "usable_rows": len(usable),
        "mode_counts": mode_counts,
        "self_consistency": {
            "rows_checked": rows_total - skipped_degenerate,
            "candidates_checked": stats["candidates_checked"],
            "ahead_risk_invariance_checked": stats["ahead_risk_invariance_checked"],
            "max_abs_error": stats["max_abs_error"],
        },
        "variants": variants_report,
    }


def format_full_fidelity_json(result: dict) -> str:
    return json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def format_full_fidelity_md(result: dict) -> str:
    sc = result["self_consistency"]
    lines = [
        "# 2c Aggregation Probe — full-fidelity, mode-aware replay",
        "",
        f"**Schema:** {result['probe_schema_version']}. Self-consistency pin: "
        f"{sc['candidates_checked']} candidates across {sc['rows_checked']} rows "
        f"replayed exactly (max abs error {sc['max_abs_error']:.3g}); "
        f"{sc['ahead_risk_invariance_checked']} AHEAD candidates confirmed "
        "risk-invariant.",
        "",
        f"- rows total: {result['rows_total']}",
        f"- skipped (degenerate mode): {result['rows_skipped_degenerate_mode']}",
        f"- skipped (single candidate): {result['rows_skipped_single_candidate']}",
        f"- **usable: {result['usable_rows']}**",
        f"- mode counts: {json.dumps(result['mode_counts'], sort_keys=True)}",
        "",
        "| variant | scope | n | changed | teacher_Δ | fixed | broke | top2_flip | near_tie |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]

    def fmt(x):
        return f"{x:.4f}" if isinstance(x, float) else ("" if x is None else str(x))

    for name in sorted(result["variants"]):
        v = result["variants"][name]
        g = v["global"]
        lines.append(
            f"| {name} | global | {g['sample_count']} | {fmt(g['changed_action_rate'])} "
            f"| {fmt(g['teacher_agreement_delta'])} | {g['variant_fixed_teacher_miss']} "
            f"| {g['variant_broke_teacher_hit']} | {fmt(g['top2_flip_rate'])} "
            f"| {fmt(g['near_tie_rate'])} |"
        )
        for mode_val in sorted(v["by_mode"]):
            m = v["by_mode"][mode_val]
            lines.append(
                f"| {name} | {mode_val} | {m['sample_count']} | {fmt(m['changed_action_rate'])} "
                f"| {fmt(m['teacher_agreement_delta'])} | {m['variant_fixed_teacher_miss']} "
                f"| {m['variant_broke_teacher_hit']} | {fmt(m['top2_flip_rate'])} "
                f"| {fmt(m['near_tie_rate'])} |"
            )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(description="Offline 2c aggregation probe (reduced fidelity).")
    p.add_argument("dataset", help="path to a 2b-2.5a-style dataset .jsonl(.gz)")
    p.add_argument("--out-json", required=True)
    p.add_argument("--out-md", required=True)
    args = p.parse_args(argv)
    report = run_probe(args.dataset)
    from pathlib import Path

    Path(args.out_json).write_text(format_json(report), encoding="utf-8")
    Path(args.out_md).write_text(format_md(report), encoding="utf-8")
    v = report["variants"]
    best_delta = max((vv["teacher_agreement_delta"] or 0.0) for vv in v.values()) if v else 0.0
    max_changed = max((vv["changed_action_rate"] or 0.0) for vv in v.values()) if v else 0.0
    print(f"PROBE: usable={report['usable_decisions']} max_changed_action={max_changed:.4f} "
          f"best_teacher_agree_delta={best_delta:+.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
