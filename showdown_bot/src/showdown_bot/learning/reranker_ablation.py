"""Slice 2b-2b: leave-one-class-out (LOCO) / single-class-only (SCO) feature
ablation harness for the reranker.

This module NEVER forks the model code -- it drives the EXISTING pipeline
(`reranker_features.build_feature_matrix`, `reranker_train.train_lambdarank` /
`attack_strict_decisions`, `reranker_eval.regret_metrics` / `gates_pass`) with
different `feature_names` subsets, using the exact same split (seed=42,
by-game) and LightGBM params as `reranker_train.main`. The FULL-feature
variant therefore reproduces the committed 2b-2.5a offline-eval numbers
exactly (see test_reranker_ablation.py).

See docs/projects/learning/specs/2026-07-11-2b2b-feature-ablation-design.md.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from showdown_bot.learning.dataset import group_decisions, load_rows, split_by_game
from showdown_bot.learning.reranker_eval import RerankerMetrics, gates_pass, regret_metrics
from showdown_bot.learning.reranker_features import (
    LABEL_DENYLIST, METADATA_DENYLIST, active_feature_names, build_feature_matrix,
)
from showdown_bot.learning.reranker_train import (
    DEFAULT_CONFIG, _scores_per_decision, attack_strict_decisions, sha256_of_file,
    train_lambdarank,
)
from showdown_bot.learning.schema import FEATURE_COLUMNS

MISC = "misc"

# ---------------------------------------------------------------------------
# Feature classes. Order matters: a live feature is assigned to the FIRST
# class whose matcher fires (checked in this dict's insertion order), so the
# explicit/known column lists (straight from the spec's R4 named-feature
# groups) claim their members before the prefix/substring-matched classes
# get a chance -- e.g. slot{1,2}_is_protect stays in move_desc (explicit),
# NOT protect (substring "protect" would otherwise also match it).
#
# A class value is either:
#   - a tuple[str, ...]  -> exact-name membership (small/known sets)
#   - a callable(name) -> bool -> prefix/substring matcher, evaluated against
#     whatever is actually LIVE (no hardcoded, possibly-stale column list) --
#     damage/speed/board/protect per the spec.
# ---------------------------------------------------------------------------
FEATURE_CLASSES = {
    "weather_terrain": ("field_weather", "trick_room_active", "tailwind_ours", "tailwind_opp"),
    "move_desc": tuple(
        f"slot{s}_{suffix}"
        for s in (1, 2)
        for suffix in ("move_type", "move_category", "priority", "is_damaging", "is_protect")
    ),
    "species_id": tuple(
        f"slot{s}_{suffix}"
        for s in (1, 2)
        for suffix in ("actor_species_id", "switch_target_species_id", "target_species_id_if_known")
    ),
    "mirror": ("mirror_flag",),
    # predicted-damage / KO-threat features
    "damage": lambda name: (
        "damage" in name or "kos_for" in name or "kos_against" in name
        or name.startswith("ko_") or name == "out_in_ratio" or "survives_for_sure" in name
    ),
    # who-acts-first / speed-order features
    "speed": lambda name: "speed" in name,
    # HP / fainted / board-state counters
    "board": lambda name: "alive_count" in name or "hp_frac" in name or "endgame" in name,
    # protect-related live features
    "protect": lambda name: "protect" in name,
}


def _classify(name: str) -> str:
    for cls, matcher in FEATURE_CLASSES.items():
        if isinstance(matcher, tuple):
            if name in matcher:
                return cls
        elif matcher(name):
            return cls
    return MISC


def _validate_partition(partition: dict[str, list[str]], live_features: list[str]) -> None:
    """Assert `partition` is exhaustive (union == live_features) and disjoint
    (no name assigned to two classes) -- raise ValueError on violation. Split
    out from partition_features so both the real build path AND a
    deliberately-broken partition (unit test) can be checked without needing
    to defeat `_classify`'s first-match-wins guarantee (which, by
    construction, can never itself produce an overlapping assignment)."""
    union: list[str] = [n for members in partition.values() for n in members]
    if len(union) != len(set(union)):
        seen: set[str] = set()
        dupes: set[str] = set()
        for n in union:
            (dupes if n in seen else seen).add(n)
        raise ValueError(f"partition not disjoint: {sorted(dupes)} assigned to multiple classes")
    if set(union) != set(live_features):
        missing = set(live_features) - set(union)
        extra = set(union) - set(live_features)
        raise ValueError(f"partition not exhaustive: missing={sorted(missing)} extra={sorted(extra)}")


def partition_features(live_features: list[str]) -> dict[str, list[str]]:
    """Partition `live_features` into FEATURE_CLASSES + a `misc` catch-all.
    Each class's member order follows `live_features` order. Raises via
    `_validate_partition` on a non-exhaustive or non-disjoint result --
    defensive: `_classify` is a total function assigning each name to exactly
    one bucket, so in practice this can only fire if FEATURE_CLASSES itself is
    edited into an inconsistent state, but the plan requires the check
    regardless."""
    partition: dict[str, list[str]] = {cls: [] for cls in FEATURE_CLASSES}
    partition[MISC] = []
    for name in live_features:
        partition[_classify(name)].append(name)
    _validate_partition(partition, live_features)
    return partition


def _loco_subset(live_features: list[str], removed_members: list[str]) -> list[str]:
    removed = set(removed_members)
    return [f for f in live_features if f not in removed]


def _sco_subset(live_features: list[str], kept_members: list[str]) -> list[str]:
    keep = set(kept_members)
    return [f for f in live_features if f in keep]


@dataclass
class VariantMetrics:
    variant: str             # "FULL" | "LOCO" | "SCO"
    class_name: str | None   # None for FULL
    feature_names: list[str]
    n_features: int
    model_regret: float
    heuristic_regret: float
    model_wrong_near_equal: int
    heuristic_wrong_near_equal: int
    gate_pass: bool
    delta_vs_full: float      # model_regret - FULL.model_regret (0.0 for FULL itself)


@dataclass
class AblationResult:
    dataset_path: str
    dataset_sha256: str
    split_seed: int
    live_features: list[str]
    partition: dict[str, list[str]]
    full: VariantMetrics
    loco: dict[str, VariantMetrics | None]
    sco: dict[str, VariantMetrics | None]


def _train_and_eval(tr, va, te, feature_names: list[str]) -> RerankerMetrics:
    """Train + score via the REAL pipeline pieces, on the given feature subset.
    INV-6: subsets are built from active_feature_names so they're clean by
    construction, but assert it here too (defense in depth; build_feature_matrix
    also raises on this)."""
    denied = set(feature_names) & (LABEL_DENYLIST | METADATA_DENYLIST)
    if denied:
        raise ValueError(f"INV-6 violation: denied columns in feature subset: {sorted(denied)}")
    train_m = build_feature_matrix(tr, feature_names=feature_names)
    enc = train_m.categorical_encodings
    val_m = build_feature_matrix(va, feature_names=feature_names, encodings=enc)
    booster = train_lambdarank(train_m, config=DEFAULT_CONFIG, val_matrix=val_m)
    scored = _scores_per_decision(booster, te, feature_names=feature_names, encodings=enc)
    return regret_metrics(scored)


def _to_variant(m: RerankerMetrics, *, variant: str, class_name: str | None,
                feature_names: list[str], full_model_regret: float) -> VariantMetrics:
    return VariantMetrics(
        variant=variant, class_name=class_name, feature_names=list(feature_names),
        n_features=len(feature_names), model_regret=m.model_regret,
        heuristic_regret=m.heuristic_regret, model_wrong_near_equal=m.model_wrong_near_equal,
        heuristic_wrong_near_equal=m.heuristic_wrong_near_equal, gate_pass=gates_pass(m),
        delta_vs_full=m.model_regret - full_model_regret,
    )


def _ablate_decisions(tr, va, te, live_features: list[str], *, dataset_path: str = "",
                      dataset_sha256: str = "", split_seed: int = 42) -> AblationResult:
    """Core LOCO/SCO loop, operating on already-built decision lists + a live
    feature set. Split out from run_ablation so tests can drive it with a
    small synthetic (or sliced-real) decisions fixture without re-parsing a
    dataset file."""
    partition = partition_features(live_features)

    full_metrics = _train_and_eval(tr, va, te, live_features)
    full = _to_variant(full_metrics, variant="FULL", class_name=None,
                       feature_names=live_features, full_model_regret=full_metrics.model_regret)

    loco: dict[str, VariantMetrics | None] = {}
    sco: dict[str, VariantMetrics | None] = {}
    for cls, members in partition.items():
        if not members:
            # Empty class: "removing nothing" is IDENTICAL to FULL by
            # construction (same feature set) -- reuse FULL's result instead
            # of re-training, which also makes the identity exact (not just
            # approximately reproduced by LightGBM determinism).
            loco[cls] = replace(full, variant="LOCO", class_name=cls, delta_vs_full=0.0)
            sco[cls] = None  # SCO on zero features is undefined -- nothing to train
            continue

        loco_subset = _loco_subset(live_features, members)
        if loco_subset:
            m = _train_and_eval(tr, va, te, loco_subset)
            loco[cls] = _to_variant(m, variant="LOCO", class_name=cls, feature_names=loco_subset,
                                    full_model_regret=full.model_regret)
        else:
            loco[cls] = None  # degenerate: class == the entire live feature set

        sco_subset = _sco_subset(live_features, members)
        m2 = _train_and_eval(tr, va, te, sco_subset)
        sco[cls] = _to_variant(m2, variant="SCO", class_name=cls, feature_names=sco_subset,
                               full_model_regret=full.model_regret)

    return AblationResult(dataset_path=dataset_path, dataset_sha256=dataset_sha256,
                          split_seed=split_seed, live_features=list(live_features),
                          partition=partition, full=full, loco=loco, sco=sco)


def run_ablation(dataset_path: str, *, split_seed: int = 42) -> AblationResult:
    """Build decisions once from `dataset_path`, split by game (seed=split_seed,
    same as reranker_train.main), compute the live feature set + partition,
    then train+eval the FULL model and every LOCO/SCO variant via the real
    pipeline. ATTACK-strict throughout (train/val/test filtered to
    attack_strict_decisions), matching reranker_train.main exactly so the
    FULL row reproduces the committed offline-eval numbers."""
    ds_sha = sha256_of_file(dataset_path)
    decisions = group_decisions(load_rows(dataset_path))
    sp = split_by_game(decisions, seed=split_seed)
    tr = attack_strict_decisions(sp.train)
    va = attack_strict_decisions(sp.val)
    te = attack_strict_decisions(sp.test)
    live = active_feature_names(tr)
    return _ablate_decisions(tr, va, te, live, dataset_path=dataset_path,
                             dataset_sha256=ds_sha, split_seed=split_seed)


# ---------------------------------------------------------------------------
# Task 2: dropped-constant count, determinism self-check, ranked report + JSON
# sidecar, CLI entry (`python -m showdown_bot.learning.reranker_ablation`).
# ---------------------------------------------------------------------------

def dropped_constant_columns(live_features: list[str]) -> list[str]:
    """FEATURE_COLUMNS not in the live set and not already INV-6-denylisted --
    the SAME computation reranker_train.main uses to build its manifest's
    `dropped_constant_columns` (schema order, not alphabetical)."""
    live = set(live_features)
    denylist = LABEL_DENYLIST | METADATA_DENYLIST
    return [c for c in FEATURE_COLUMNS if c not in live and c not in denylist]


# Committed 2b-2.5a offline-eval numbers (reports/2026-07-11-2b25a-offline-eval.md,
# "Final offline eval" table) -- the FULL-model ablation row must reproduce these
# exactly (same code paths, same split) or the harness has silently diverged.
_EXPECTED_DROPPED_CONSTANT_COUNT = 7
_EXPECTED_ATTACK_MODEL_REGRET = 0.6172
_EXPECTED_ATTACK_HEURISTIC_REGRET = 2.2286
_EXPECTED_MODEL_WRONG_NEAR_EQUAL = 8
_FLOAT_TOL = 1e-6


class SelfCheckError(RuntimeError):
    """Raised when the FULL-model ablation row does not reproduce the committed
    2b-2.5a offline-eval numbers -- fail loud rather than publish a misleading
    report (plan requirement, Task 2)."""


def self_check(result: AblationResult, dropped: list[str]) -> None:
    """Abort (raise SelfCheckError) unless the FULL row exactly matches the
    committed 2b-2.5a numbers within float tolerance and dropped_constant_columns
    == 7. Called by `main()` before any artifact is written."""
    full = result.full
    errors = []
    if len(dropped) != _EXPECTED_DROPPED_CONSTANT_COUNT:
        errors.append(
            f"dropped_constant_columns count {len(dropped)} != expected "
            f"{_EXPECTED_DROPPED_CONSTANT_COUNT} (dropped={sorted(dropped)})"
        )
    if abs(full.model_regret - _EXPECTED_ATTACK_MODEL_REGRET) > _FLOAT_TOL:
        errors.append(
            f"FULL model_regret {full.model_regret} != expected {_EXPECTED_ATTACK_MODEL_REGRET}"
        )
    if abs(full.heuristic_regret - _EXPECTED_ATTACK_HEURISTIC_REGRET) > _FLOAT_TOL:
        errors.append(
            f"FULL heuristic_regret {full.heuristic_regret} != expected "
            f"{_EXPECTED_ATTACK_HEURISTIC_REGRET}"
        )
    if full.model_wrong_near_equal != _EXPECTED_MODEL_WRONG_NEAR_EQUAL:
        errors.append(
            f"FULL model_wrong_near_equal {full.model_wrong_near_equal} != expected "
            f"{_EXPECTED_MODEL_WRONG_NEAR_EQUAL}"
        )
    if not full.gate_pass:
        errors.append("FULL gate_pass is False, expected True")
    if errors:
        raise SelfCheckError(
            "2b-2b ablation self-check FAILED -- the harness/split has diverged from the "
            "committed 2b-2.5a offline-eval numbers (reports/2026-07-11-2b25a-offline-eval.md). "
            "Aborting WITHOUT writing a report:\n  " + "\n  ".join(errors)
        )


# Verdict thresholds (documented, not tuned to any particular dataset): a class
# is "load-bearing" if its LOCO removal breaks the gate outright, or worsens
# mean model_regret by >= _MATERIAL_ABS_DELTA (absolute) or >= _MATERIAL_REL_DELTA
# (relative to FULL's model_regret) -- either is "material" on this scale.
# "prunable" requires BOTH a near-zero LOCO delta (|delta| <= _NOISE_ABS_DELTA,
# i.e. within noise on a small test split) AND weak/no SCO standalone signal
# (the class alone can't approach FULL's regret, or fails the gate by itself).
# Anything else is "inconclusive" -- explicitly not forced into a bucket.
_MATERIAL_ABS_DELTA = 0.10
_MATERIAL_REL_DELTA = 0.15
_NOISE_ABS_DELTA = 0.03

LOAD_BEARING = "load-bearing"
PRUNABLE = "prunable"
INCONCLUSIVE = "inconclusive"
NOT_APPLICABLE = "n/a"


def classify_verdict(loco: VariantMetrics | None, sco: VariantMetrics | None,
                      full: VariantMetrics) -> str:
    """Pure classification from already-computed LOCO/SCO metrics -- see the
    threshold constants above for the exact rule. `loco is None` only occurs
    in the degenerate case where a class equals the ENTIRE live feature set
    (not expected on the committed dataset, but handled defensively)."""
    if loco is None:
        return NOT_APPLICABLE
    if not loco.gate_pass:
        return LOAD_BEARING
    delta = loco.delta_vs_full
    rel = (delta / full.model_regret) if full.model_regret else (0.0 if delta == 0.0 else float("inf"))
    if delta >= _MATERIAL_ABS_DELTA or rel >= _MATERIAL_REL_DELTA:
        return LOAD_BEARING
    if abs(delta) <= _NOISE_ABS_DELTA:
        if sco is None:
            # empty class: SCO is undefined (nothing to train standalone on) --
            # zero features removed means zero features to prune either.
            return PRUNABLE
        sco_gap = sco.model_regret - full.model_regret
        if sco_gap >= _MATERIAL_ABS_DELTA or not sco.gate_pass:
            return PRUNABLE
    return INCONCLUSIVE


def _variant_to_dict(v: VariantMetrics | None) -> dict | None:
    return asdict(v) if v is not None else None


def ablation_result_to_json(result: AblationResult, dropped: list[str]) -> dict:
    """Raw-numbers JSON sidecar. Pretty-printed + key-sorted by the caller
    (json.dumps(..., indent=2, sort_keys=True)) so it is byte-deterministic
    given identical input metrics."""
    verdicts = {
        cls: classify_verdict(result.loco.get(cls), result.sco.get(cls), result.full)
        for cls in result.partition
    }
    return {
        "dataset_path": result.dataset_path,
        "dataset_sha256": result.dataset_sha256,
        "split_seed": result.split_seed,
        "live_feature_count": len(result.live_features),
        "live_features": list(result.live_features),
        "dropped_constant_columns": sorted(dropped),
        "dropped_constant_count": len(dropped),
        "partition": {cls: list(members) for cls, members in result.partition.items()},
        "full": _variant_to_dict(result.full),
        "loco": {cls: _variant_to_dict(v) for cls, v in result.loco.items()},
        "sco": {cls: _variant_to_dict(v) for cls, v in result.sco.items()},
        "verdicts": verdicts,
        "verdict_thresholds": {
            "material_abs_delta": _MATERIAL_ABS_DELTA,
            "material_rel_delta": _MATERIAL_REL_DELTA,
            "noise_abs_delta": _NOISE_ABS_DELTA,
        },
    }


def _fmt(x: float) -> str:
    return f"{x:.4f}"


def format_ablation_report(result: AblationResult, dropped: list[str]) -> str:
    """Render the markdown report: partition, LOCO table (Δ-descending), SCO
    table, per-class verdicts, and the caveats section (plan Task 2)."""
    full = result.full
    lines = [
        "# 2b-2b Feature Ablation — LOCO/SCO Report",
        "",
        "Slice 2b-2b. Leave-one-class-out (LOCO) and single-class-only (SCO) retraining over "
        "the committed 2b-2.5a dataset, ATTACK-strict gate throughout -- same split (seed="
        f"{result.split_seed}, by-game), same LightGBM params, same code paths as "
        "`reranker_train.main` (see "
        "docs/projects/learning/specs/2026-07-11-2b2b-feature-ablation-design.md). This ranks which "
        "feature classes actually drive the gate metric (regret-vs-teacher), which LightGBM's "
        "own gain/split importance does not measure.",
        "",
        f"Dataset: `{result.dataset_path}` (sha256 `{result.dataset_sha256}`)",
        f"Live features: {len(result.live_features)}  |  dropped constant: {len(dropped)}",
        "",
        "## Self-check",
        "",
        "FULL row reproduces the committed 2b-2.5a offline-eval numbers "
        "(`reports/2026-07-11-2b25a-offline-eval.md`): "
        f"model_regret={_fmt(full.model_regret)}, heuristic_regret={_fmt(full.heuristic_regret)}, "
        f"model_wrong_near_equal={full.model_wrong_near_equal}, gate_pass={full.gate_pass}, "
        f"dropped_constant_columns={len(dropped)}. **PASS** (self-check ran before this report "
        "was written -- see `self_check()`; a mismatch aborts with no report written at all).",
        "",
        "## Feature-class partition",
        "",
        "Every live feature is assigned to exactly one class (exhaustive + disjoint, enforced by "
        "`partition_features`); `misc` is the explicit catch-all so nothing is silently "
        "unclassified.",
        "",
        "| class | n | members |",
        "|---|---|---|",
    ]
    for cls, members in result.partition.items():
        lines.append(f"| {cls} | {len(members)} | {', '.join(members) if members else '_(empty)_'} |")

    lines += [
        "",
        "## LOCO — leave-one-class-out (sorted by Δ descending: most load-bearing first)",
        "",
        f"Baseline (FULL, all {len(result.live_features)} features): "
        f"model_regret={_fmt(full.model_regret)}, heuristic_regret={_fmt(full.heuristic_regret)}, "
        f"model_wrong_near_equal={full.model_wrong_near_equal}, gate_pass={full.gate_pass}.",
        "",
        "| class | features removed | model_regret | Δ vs FULL | gate still passes? |",
        "|---|---|---|---|---|",
    ]
    loco_items = [(cls, v) for cls, v in result.loco.items() if v is not None]
    loco_items.sort(key=lambda kv: kv[1].delta_vs_full, reverse=True)
    for cls, v in loco_items:
        n_removed = len(result.partition[cls])
        lines.append(
            f"| {cls} | {n_removed} | {_fmt(v.model_regret)} | {v.delta_vs_full:+.4f} | {v.gate_pass} |"
        )

    lines += [
        "",
        "## SCO — single-class-only (standalone signal; diagnostic, not a gate)",
        "",
        "| class | n features | model_regret | gate_pass |",
        "|---|---|---|---|",
    ]
    for cls, members in result.partition.items():
        v = result.sco.get(cls)
        if v is None:
            lines.append(f"| {cls} | {len(members)} | _n/a (empty class)_ | _n/a_ |")
        else:
            lines.append(f"| {cls} | {len(members)} | {_fmt(v.model_regret)} | {v.gate_pass} |")

    lines += [
        "",
        "## Verdicts",
        "",
        f"load-bearing: LOCO breaks the gate, or Δ >= {_MATERIAL_ABS_DELTA} (absolute) or "
        f">= {_MATERIAL_REL_DELTA*100:.0f}% (relative to FULL). prunable: |Δ| <= "
        f"{_NOISE_ABS_DELTA} (noise-level) AND SCO shows no material standalone signal. "
        "inconclusive: neither condition is met cleanly.",
        "",
        "| class | n | Δ vs FULL | gate_pass (LOCO) | verdict |",
        "|---|---|---|---|---|",
    ]
    for cls, members in result.partition.items():
        loco_v = result.loco.get(cls)
        sco_v = result.sco.get(cls)
        verdict = classify_verdict(loco_v, sco_v, full)
        delta_str = f"{loco_v.delta_vs_full:+.4f}" if loco_v is not None else "n/a"
        gate_str = str(loco_v.gate_pass) if loco_v is not None else "n/a"
        lines.append(f"| {cls} | {len(members)} | {delta_str} | {gate_str} | {verdict} |")

    negative_delta_classes = [
        cls for cls, v in result.loco.items() if v is not None and v.delta_vs_full < -_NOISE_ABS_DELTA
    ]
    single_col_classes = [cls for cls, members in result.partition.items() if len(members) == 1]
    lines += ["", "### Interpretation notes"]
    if negative_delta_classes:
        joined = ", ".join(f"`{c}` ({result.loco[c].delta_vs_full:+.4f})" for c in negative_delta_classes)
        lines += [
            "",
            f"- **Negative-delta classes** ({joined}): removing these classes made mean model_regret "
            "*lower* (better) than FULL on this test split. That is counterintuitive for a "
            "genuinely load-bearing class -- most likely redundancy/collinearity with other live "
            "features (the same signal is recoverable elsewhere) or plain refit noise on a small "
            "held-out split, not evidence the class is actively harmful. Classified `inconclusive` "
            "rather than `prunable`: under this rule a negative Δ is a *weaker*, not stronger, "
            "prunability signal than Δ≈0 -- a confident prune call needs more than one refit.",
        ]
    if single_col_classes:
        joined = ", ".join(f"`{c}`" for c in single_col_classes)
        lines += [
            "",
            f"- **Single-column classes** ({joined}): only one feature each, so their LOCO Δ and "
            "SCO regret each reflect a single dropped/kept column's effect on one refit -- the "
            "lowest statistical power in this report. Their verdict is reported as-is but should "
            "not be treated as confidently settled.",
        ]
    misc_sco = result.sco.get(MISC)
    if misc_sco is not None and MISC in result.partition and result.partition[MISC]:
        lines += [
            "",
            f"- **`misc` dominance:** `misc` alone (SCO, {len(result.partition[MISC])} features) "
            f"reaches model_regret={_fmt(misc_sco.model_regret)} vs FULL's {_fmt(full.model_regret)} "
            "-- most of the gate signal lives in this catch-all class, which includes the "
            "heuristic's own aggregate score/gap features (`heuristic_aggregate_score`, "
            "`score_gap_to_top`, ...). Unsurprising: the reranker leans heavily on the heuristic's "
            "own scoring as a feature, on top of which it improves.",
        ]

    lines += [
        "",
        "## Caveats",
        "",
        "- **Offline optimistic metric.** Regret-vs-teacher is measured against the rollout "
        "teacher's own value estimates on teacher-labeled offline data -- the same caveat as "
        "2b-2.5a's offline eval applies here unchanged; this ranks feature classes relative to "
        "each other, it does not establish live playing strength.",
        "- **Small test split.** The ATTACK-strict test set is a few hundred decisions from a "
        "held-back 30-game partition; small Δ values (roughly within `noise_abs_delta` of each "
        "other) are within the noise of a single LightGBM refit on this split, not a confident "
        "ranking. Single-column classes (`mirror`, `protect` on this dataset) have especially "
        "low statistical power -- report their Δ but do not over-read a small movement either "
        "way as proof of (ir)relevance.",
        "- **LightGBM importance ≠ gate contribution.** Built-in gain/split importance ranks "
        "features for the model's own internal fit; it is not the same as marginal contribution "
        "to the ATTACK-strict gate metric on held-back data. This LOCO table **is** the gate "
        "contribution (the actual quantity we care about), not a proxy for it.",
        "",
        "## Reproduction",
        "",
        "```bash",
        "python -m showdown_bot.learning.reranker_ablation "
        "data/datasets/phase3-slice2b25a/dataset.jsonl.gz \\",
        "  --out-report reports/2026-07-11-2b2b-feature-ablation.md \\",
        "  --out-json reports/2026-07-11-2b2b-feature-ablation.json",
        "```",
    ]
    return "\n".join(lines) + "\n"


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(
        description="2b-2b: leave-one-class-out / single-class-only feature ablation for the "
        "reranker -- ranked report + JSON sidecar."
    )
    ap.add_argument("dataset")  # path to .jsonl(.gz)
    ap.add_argument("--out-report", default="reports/2026-07-11-2b2b-feature-ablation.md")
    ap.add_argument("--out-json", default="reports/2026-07-11-2b2b-feature-ablation.json")
    ap.add_argument("--split-seed", type=int, default=42)
    args = ap.parse_args(argv)

    result = run_ablation(args.dataset, split_seed=args.split_seed)
    dropped = dropped_constant_columns(result.live_features)

    self_check(result, dropped)  # raises SelfCheckError (fail loud) on any mismatch

    report = format_ablation_report(result, dropped)
    obj = ablation_result_to_json(result, dropped)

    out_report = Path(args.out_report)
    out_json = Path(args.out_json)
    out_report.parent.mkdir(parents=True, exist_ok=True)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_report.write_text(report, encoding="utf-8", newline="\n")
    out_json.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {out_report} and {out_json}")
    print(f"self-check PASS: dropped_constant_columns={len(dropped)}, "
          f"FULL model_regret={_fmt(result.full.model_regret)}, gate_pass={result.full.gate_pass}")


if __name__ == "__main__":
    main()
