"""Teacher-, gap-, rank- and tie-consistency auditing (Phase 3, dataset-reranker-audit
slice, Task 4). Checks each decision's counterfactual labels are internally
consistent (gaps to the best, normalization, rank/value ordering, tie flags) and
that semantically-identical inputs under the same teacher provenance never
carry contradictory labels. Offline/pure: no network, no live battle imports.
"""

from __future__ import annotations

import math
from collections import defaultdict

from showdown_bot.learning.audit.contracts import (
    Finding, Severity, canonical_json, make_finding,
)
from showdown_bot.learning.audit.duplicates import semantic_decision_hash

TOL = 1e-9


def _ranks_consistent_with_values(ranks: list[int], values: list[float]) -> bool:
    """teacher.py assigns strict-ordinal ranks (0 = best) with a candidate-id tiebreak the audit
    cannot re-derive, so exact-rank equality is the wrong check. Validate only that the ranks are
    CONSISTENT with the value ordering: sorting candidates by ascending rank yields non-increasing
    values (equal values may be ordered either way)."""
    order = sorted(range(len(ranks)), key=lambda i: ranks[i])
    return all(values[order[k]] >= values[order[k + 1]] - TOL for k in range(len(order) - 1))


def fail(code: str, context: dict) -> Finding:
    return make_finding(
        code=code, severity=Severity.FAIL, scope="label", message=code,
        count=1, examples=[context["decision_id"]], evidence=context,
        remediation="regenerate or correct labels before training",
    )


def audit_decision_labels(decision) -> list[Finding]:
    labels = [row["label"] for row in decision.rows]
    findings = []
    best_flags = [bool(label["teacher_best"]) for label in labels]
    chosen_flags = [bool(label["chosen_by_current_heuristic"]) for label in labels]
    raw = [float(label["counterfactual_value_raw"]) for label in labels]
    normalized = [float(label["counterfactual_value_normalized_within_decision"]) for label in labels]
    gaps = [float(label["value_gap_to_best"]) for label in labels]
    context = {"decision_id": decision.decision_id}
    if not any(best_flags):
        findings.append(fail("NO_TEACHER_BEST", context))
    if not any(chosen_flags):
        findings.append(fail("NO_HEURISTIC_CHOICE", context))
    if any(not math.isfinite(value) for value in raw + normalized + gaps):
        findings.append(fail("NONFINITE_LABEL", context))
        return findings
    maximum = max(raw)
    if any(gap > TOL for gap in gaps):
        findings.append(fail("POSITIVE_VALUE_GAP", context))
    if any(flag and not math.isclose(gap, 0.0, abs_tol=TOL)
           for flag, gap in zip(best_flags, gaps)):
        findings.append(fail("BEST_NONZERO_GAP", context))
    # teacher.py marks exactly ONE best (the tie-broken rank-0), not every tied-max candidate;
    # the spec permits either, so require only that every best-flagged row is a max-value candidate
    # (NO_TEACHER_BEST already covers "at least one").
    if any(flag and not math.isclose(value, maximum, abs_tol=TOL)
           for flag, value in zip(best_flags, raw)):
        findings.append(fail("TEACHER_BEST_RAW_MISMATCH", context))
    if any(not math.isclose(gap, value - maximum, abs_tol=TOL)
           for gap, value in zip(gaps, raw)):
        findings.append(fail("GAP_RAW_MISMATCH", context))
    # spec invariant: the within-decision normalized values have mean ~0 (NOT element-wise
    # raw - mean(raw), which assumes the audit sees the exact labeled candidate set/version).
    if not math.isclose(sum(normalized) / len(normalized), 0.0, abs_tol=TOL):
        findings.append(fail("NORMALIZED_MEAN_MISMATCH", context))
    teacher_ranks = [int(label["teacher_rank"]) for label in labels]
    if not _ranks_consistent_with_values(teacher_ranks, raw):
        findings.append(fail("TEACHER_RANK_MISMATCH", context))
    counterfactual_ranks = [int(label["counterfactual_rank"]) for label in labels]
    if not _ranks_consistent_with_values(counterfactual_ranks, raw):
        findings.append(fail("COUNTERFACTUAL_RANK_MISMATCH", context))
    trainable = {row["metadata"]["teacher_config"]["trainable_label"] for row in decision.rows}
    if len(trainable) != 1:
        findings.append(fail("TRAINABLE_LABEL_MISMATCH", context))
    return findings


def label_signature(decision) -> str:
    return canonical_json([
        {"features": row["features"], "label": row["label"]}
        for row in sorted(decision.rows, key=lambda row: row["metadata"]["candidate_index"])
    ])


def teacher_provenance(decision) -> str:
    row = decision.rows[0]
    return canonical_json({
        "teacher_version": row["metadata"]["teacher_version"],
        "teacher_config": row["metadata"]["teacher_config"],
        "feature_extractor_version": row["metadata"]["feature_extractor_version"],
        "config_hash": row["metadata"]["config_hash"],
    })


def audit_labels(decisions) -> tuple[list[Finding], dict]:
    findings = []
    groups = defaultdict(list)
    for decision in decisions:
        findings.extend(audit_decision_labels(decision))
        groups[(semantic_decision_hash(decision), teacher_provenance(decision))].append(decision)
    contradictions = 0
    provenance_comparisons = defaultdict(set)
    for (semantic_hash, provenance), members in sorted(groups.items()):
        signatures = {label_signature(decision) for decision in members}
        if len(signatures) > 1:
            contradictions += 1
            findings.append(make_finding(
                code="SEMANTIC_LABEL_CONTRADICTION", severity=Severity.FAIL, scope="label",
                message="same semantic input and teacher provenance has contradictory labels",
                count=len(members), examples=[decision.decision_id for decision in members],
                evidence={"semantic_hash": semantic_hash, "teacher_provenance": provenance},
                remediation="regenerate the conflicting decisions from one teacher configuration",
            ))
        provenance_comparisons[semantic_hash].add(provenance)
    changed_provenance = sum(len(values) > 1 for values in provenance_comparisons.values())
    if changed_provenance:
        findings.append(make_finding(
            code="SEMANTIC_INPUT_MULTIPLE_TEACHERS", severity=Severity.INFO, scope="label",
            message="semantic inputs occur under multiple teacher provenance signatures",
            count=changed_provenance,
            remediation="compare teacher versions explicitly; do not treat them as contradictions",
        ))
    metrics = {
        "decisions": len(decisions), "contradiction_groups": contradictions,
        "semantic_inputs_with_multiple_teachers": changed_provenance,
    }
    return findings, metrics
