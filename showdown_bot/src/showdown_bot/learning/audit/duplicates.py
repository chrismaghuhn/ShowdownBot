"""Exact, semantic and near-duplicate detection (Phase 3, dataset-reranker-audit
slice, Task 3). Flags decisions whose canonical/semantic hash or mixed
numeric+categorical distance places them too close across a train/val/test
split boundary. Offline/pure: no network, no live battle imports.
"""

from __future__ import annotations

import hashlib
import math
from collections import defaultdict
from itertools import combinations

from showdown_bot.learning.audit.contracts import (
    AuditConfig, AuditCorpus, AuditError, canonical_json, make_finding, quantile, Severity,
)

IDENTITY_METADATA = frozenset({"game_id", "decision_id", "candidate_index"})
NON_INPUT_METADATA = frozenset({
    "game_outcome", "final_turn", "winner", "teacher_trace",
})


def _sha(value) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def full_row_hash(row: dict) -> str:
    return _sha(row)


def full_decision_hash(decision) -> str:
    return _sha(decision.rows)


def semantic_projection(decision) -> dict:
    projected = []
    for row in decision.rows:
        metadata = {
            key: value for key, value in row["metadata"].items()
            if key not in IDENTITY_METADATA | NON_INPUT_METADATA
            and key in {"format_id", "schema_version", "feature_extractor_version"}
        }
        projected.append({"features": row["features"], "metadata": metadata})
    projected.sort(key=canonical_json)
    return {"candidates": projected}


def semantic_decision_hash(decision) -> str:
    return _sha(semantic_projection(decision))


# Labelkonflikte werden in Task 4 auf Basis dieses Hashs und gleicher Teacher-/
# Config-Provenance geprüft.


def block_key(decision) -> tuple:
    first = decision.rows[0]["features"]
    action_multiset = sorted(
        (row["features"]["slot1_action_type"], row["features"]["slot2_action_type"])
        for row in decision.rows
    )
    return (
        decision.rows[0]["metadata"]["format_id"], len(decision.rows),
        first["game_mode"], tuple(action_multiset),
    )


def robust_numeric_reference(train_decisions) -> dict[str, tuple[float, float]]:
    values = defaultdict(list)
    for decision in train_decisions:
        for row in decision.rows:
            for feature, value in row["features"].items():
                if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
                    values[feature].append(float(value))
    out = {}
    for feature, xs in values.items():
        ordered = sorted(xs)
        median = quantile(ordered, 0.5)
        iqr = quantile(ordered, 0.75) - quantile(ordered, 0.25)
        out[feature] = (median, iqr if iqr > 0 else max(abs(median), 1.0))
    return out


def mixed_decision_distance(left, right, reference, config: AuditConfig) -> float:
    lrows = sorted(left.rows, key=lambda row: _sha(row["features"]))
    rrows = sorted(right.rows, key=lambda row: _sha(row["features"]))
    if len(lrows) != len(rrows):
        raise AuditError("near duplicate alignment requires equal candidate counts")
    numeric, categorical = [], []
    for lrow, rrow in zip(lrows, rrows):
        for feature in sorted(set(lrow["features"]) | set(rrow["features"])):
            a, b = lrow["features"].get(feature), rrow["features"].get(feature)
            if feature in reference and isinstance(a, (int, float)) and isinstance(b, (int, float)):
                scale = reference[feature][1]
                numeric.append(min(abs(float(a) - float(b)) / scale, config.near_numeric_cap)
                               / config.near_numeric_cap)
            else:
                categorical.append(0.0 if a == b else 1.0)
    nd = sum(numeric) / len(numeric) if numeric else 0.0
    cd = sum(categorical) / len(categorical) if categorical else 0.0
    return config.near_numeric_weight * nd + config.near_categorical_weight * cd


def cross_split_pairs(members, corpus) -> list[tuple]:
    pairs = []
    for left, right in combinations(sorted(members, key=lambda d: (d.game_id, d.decision_id)), 2):
        if corpus.split_by_game[left.game_id] != corpus.split_by_game[right.game_id]:
            pairs.append((left, right))
    return pairs


def duplicate_finding(code, severity, pairs, corpus, *, evidence=None):
    examples = [
        f"{corpus.split_by_game[left.game_id]}:{left.game_id}/{left.decision_id}|"
        f"{corpus.split_by_game[right.game_id]}:{right.game_id}/{right.decision_id}"
        for left, right in pairs
    ]
    return make_finding(
        code=code, severity=severity, scope="split", message=code,
        count=len(pairs), examples=examples, evidence=evidence or {},
        remediation="remove leakage or rebuild gamewise splits before training",
    )


def audit_duplicates(corpus: AuditCorpus, config: AuditConfig):
    findings = []
    metrics = {"row_duplicate_groups": 0, "full_cross_split_pairs": 0,
               "semantic_cross_split_pairs": 0, "near_cross_split_pairs": 0}
    row_groups = defaultdict(list)
    for decision in corpus.decisions:
        for row in decision.rows:
            row_groups[full_row_hash(row)].append(decision)
    repeated_rows = {key: members for key, members in row_groups.items() if len(members) > 1}
    metrics["row_duplicate_groups"] = len(repeated_rows)
    if repeated_rows:
        findings.append(make_finding(
            code="DUPLICATE_ROWS", severity=Severity.WARN, scope="dataset",
            message="identical rows occur more than once", count=len(repeated_rows),
            examples=sorted(repeated_rows), remediation="inspect repeated exports",
        ))
    for name, hash_fn, code in (
        ("full", full_decision_hash, "FULL_CROSS_SPLIT_DUPLICATE"),
        ("semantic", semantic_decision_hash, "SEMANTIC_CROSS_SPLIT_DUPLICATE"),
    ):
        groups = defaultdict(list)
        for decision in corpus.decisions:
            groups[hash_fn(decision)].append(decision)
        same_split_groups, cross = 0, []
        for members in groups.values():
            if len(members) < 2:
                continue
            pairs = cross_split_pairs(members, corpus)
            cross.extend(pairs)
            if not pairs:
                same_split_groups += 1
        metrics[f"{name}_cross_split_pairs"] = len(cross)
        if cross:
            findings.append(duplicate_finding(code, Severity.FAIL, cross, corpus))
        if same_split_groups:
            findings.append(make_finding(
                code=f"{name.upper()}_SAME_SPLIT_DUPLICATE", severity=Severity.INFO,
                scope="split", message="duplicate decisions remain inside one split",
                count=same_split_groups, remediation="consider deduplication for sample weighting",
            ))
    reference = robust_numeric_reference(corpus.decisions_by_split["train"])
    blocks = defaultdict(list)
    for decision in corpus.decisions:
        blocks[block_key(decision)].append(decision)
    near = []
    for key in sorted(blocks, key=canonical_json):
        for left, right in cross_split_pairs(blocks[key], corpus):
            if semantic_decision_hash(left) == semantic_decision_hash(right):
                continue
            distance = mixed_decision_distance(left, right, reference, config)
            if distance <= config.near_duplicate_threshold:
                near.append((left, right, distance))
    metrics["near_cross_split_pairs"] = len(near)
    if near:
        pairs = [(left, right) for left, right, _distance in near]
        findings.append(duplicate_finding(
            "NEAR_CROSS_SPLIT_DUPLICATE", Severity.WARN, pairs, corpus,
            evidence={"threshold": config.near_duplicate_threshold,
                      "distances": sorted(distance for _left, _right, distance in near)[:20]},
        ))
    return findings, metrics
