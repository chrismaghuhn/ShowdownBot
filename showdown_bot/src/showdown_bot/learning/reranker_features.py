"""Slice 2b-2a: model-feature allowlist + groupwise ranking matrix (offline).

INV-6: model input is a subset of schema.FEATURE_COLUMNS only; everything in
LABEL_KEYS / outcome METADATA is forbidden as a feature. value_gap_to_best is
used ONLY to derive the training relevance (the target), never as an input.
No lightgbm import here — this module is pure stdlib so it tests without it.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from showdown_bot.learning.schema import FEATURE_COLUMNS, LABEL_KEYS, METADATA_KEYS

LABEL_DENYLIST = frozenset(LABEL_KEYS)
METADATA_DENYLIST = frozenset(METADATA_KEYS)
UNK = "__unk__"  # reserved categorical code 0 for values unseen at training time


@dataclass
class FeatureMatrix:
    X: list[list[float]]
    group_sizes: list[int]
    relevance: list[int]
    feature_names: list[str]
    categorical_feature_names: list[str]
    categorical_encodings: dict[str, dict[str, int]]
    decision_keys: list[tuple[str, str]]


def relevance_from_gap(gap: float) -> int:
    """Near-equal-safe graded relevance from value_gap_to_best (<= 0)."""
    if gap == 0.0:
        return 4
    a = abs(gap)
    if a <= 0.5:
        return 3
    if a <= 2.0:
        return 2
    if a <= 5.0:
        return 1
    return 0


def _hashable(v):
    if isinstance(v, list):
        return tuple(v)
    if isinstance(v, dict):
        return json.dumps(v, sort_keys=True)
    return v


def _is_categorical(rows: list[dict], col: str) -> bool:
    """Categorical iff any value is a non-numeric string. Bools are numeric (0/1)."""
    for r in rows:
        v = r["features"].get(col)
        if isinstance(v, str):
            try:
                float(v)
            except (ValueError, TypeError):
                return True
    return False


def active_feature_names(decisions) -> list[str]:
    """FEATURE_COLUMNS minus the INV-6 denylists minus columns constant across all
    rows in `decisions` (the 2b-2a dead-column drop). Order = FEATURE_COLUMNS."""
    rows = [r for d in decisions for r in d.rows]
    keep = []
    for c in FEATURE_COLUMNS:
        if c in LABEL_DENYLIST or c in METADATA_DENYLIST:
            continue
        if len({_hashable(r["features"].get(c)) for r in rows}) > 1:
            keep.append(c)
    return keep


def feature_schema_hash(feature_names, categorical_feature_names) -> str:
    payload = json.dumps(
        {"features": list(feature_names), "categorical": list(categorical_feature_names)},
        sort_keys=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _encode(m: dict, val, *, building: bool) -> int:
    # Returns a NON-NEGATIVE integer code (UNK=0, then 1, 2, ...). LightGBM's
    # categorical_feature requires non-negative int codes; later cast to float in
    # the matrix but still discrete categories, not ordinals.
    if UNK not in m:
        m[UNK] = 0
    key = str(val)
    if key in m:
        return m[key]
    if building:
        m[key] = len(m)
        return m[key]
    return m[UNK]


def build_feature_matrix(decisions, *, feature_names=None, encodings=None) -> FeatureMatrix:
    """Build (X, group, relevance) for groupwise ranking. One group per decision,
    rows in candidate_index order. feature_names=None -> active_feature_names.
    encodings=None -> build categorical maps from this data (training); pass the
    training maps for val/test/inference so unseen values map to UNK."""
    rows_all = [r for d in decisions for r in d.rows]
    if feature_names is None:
        feature_names = active_feature_names(decisions)
    unknown = set(feature_names) - set(FEATURE_COLUMNS)
    if unknown:
        raise ValueError(f"non-schema feature columns requested: {sorted(unknown)}")
    denied = set(feature_names) & (LABEL_DENYLIST | METADATA_DENYLIST)
    if denied:
        raise ValueError(f"INV-6 violation: denied columns requested as features: {sorted(denied)}")
    building = encodings is None
    if building:
        cat_names = [c for c in feature_names if _is_categorical(rows_all, c)]
    else:
        cat_names = [c for c in feature_names if c in encodings]
    enc = {c: (dict(encodings[c]) if (not building and c in encodings) else {}) for c in cat_names}

    X: list[list[float]] = []
    group_sizes: list[int] = []
    relevance: list[int] = []
    keys: list[tuple[str, str]] = []
    for d in decisions:
        group_sizes.append(len(d.rows))
        keys.append((d.game_id, d.decision_id))
        for r in d.rows:
            row: list[float] = []
            for c in feature_names:
                v = r["features"].get(c)
                if c in enc:
                    row.append(float(_encode(enc[c], v, building=building)))
                else:
                    row.append(float(v) if v is not None else 0.0)
            X.append(row)
            relevance.append(relevance_from_gap(r["label"]["value_gap_to_best"]))
    return FeatureMatrix(X, group_sizes, relevance, list(feature_names), cat_names, enc, keys)


def vectorize(feature_dicts, *, feature_names, encodings):
    """Build X (list[list[float]]) for scoring, from live feature dicts, using ONLY
    feature_names in order and the persisted categorical encodings (unseen -> UNK).
    No labels, no relevance. Returns (X, missing_feature_names).  Categorical columns
    are those present in `encodings`."""
    missing = sorted({c for c in feature_names for d in feature_dicts if c not in d})
    X = []
    for d in feature_dicts:
        row = []
        for c in feature_names:
            v = d.get(c)
            if c in encodings:
                m = encodings[c]
                row.append(float(m.get(str(v), m.get(UNK, 0))))
            else:
                row.append(float(v) if v is not None else 0.0)
        X.append(row)
    return X, missing
