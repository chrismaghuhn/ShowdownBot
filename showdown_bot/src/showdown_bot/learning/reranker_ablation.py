"""Slice 2b-2b: leave-one-class-out (LOCO) / single-class-only (SCO) feature
ablation harness for the reranker.

This module NEVER forks the model code -- it drives the EXISTING pipeline
(`reranker_features.build_feature_matrix`, `reranker_train.train_lambdarank` /
`attack_strict_decisions`, `reranker_eval.regret_metrics` / `gates_pass`) with
different `feature_names` subsets, using the exact same split (seed=42,
by-game) and LightGBM params as `reranker_train.main`. The FULL-feature
variant therefore reproduces the committed 2b-2.5a offline-eval numbers
exactly (see test_reranker_ablation.py).

See docs/superpowers/specs/2026-07-11-2b2b-feature-ablation-design.md.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from showdown_bot.learning.dataset import group_decisions, load_rows, split_by_game
from showdown_bot.learning.reranker_eval import RerankerMetrics, gates_pass, regret_metrics
from showdown_bot.learning.reranker_features import (
    LABEL_DENYLIST, METADATA_DENYLIST, active_feature_names, build_feature_matrix,
)
from showdown_bot.learning.reranker_train import (
    DEFAULT_CONFIG, _scores_per_decision, attack_strict_decisions, sha256_of_file,
    train_lambdarank,
)

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
