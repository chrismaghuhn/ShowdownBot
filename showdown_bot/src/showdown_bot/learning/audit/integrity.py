"""Dataset/split integrity audit (Phase 3, dataset-reranker-audit slice, Task 2).

Loads a rollout-label JSONL corpus (schema.py contract), derives or validates a
game-level train/validation/test split, and reports structural integrity
findings (duplicate rows, non-contiguous candidates, decision-metadata
consistency, provenance homogeneity, and the model-feature allowlist).
Offline/pure: no network, no live battle imports.
"""

from __future__ import annotations

import gzip
import hashlib
from pathlib import Path

from showdown_bot.learning.audit.contracts import (
    AuditConfig, AuditCorpus, AuditError, Finding, SPLIT_SCHEMA_VERSION, Severity,
    canonical_json, make_finding,
)
from showdown_bot.learning.dataset import group_decisions, load_rows, split_by_game
from showdown_bot.learning.reranker_features import LABEL_DENYLIST, METADATA_DENYLIST
from showdown_bot.learning.schema import FEATURE_COLUMNS

DECISION_WIDE_METADATA = frozenset({
    "game_id", "decision_id", "format_id", "schema_version", "feature_extractor_version",
    "teacher_version", "git_sha", "team_hash", "config_hash", "teacher_config",
})


def dataset_sha256(path) -> str:
    p = Path(path)
    raw = p.read_bytes()
    data = gzip.decompress(raw) if p.suffix == ".gz" else raw
    return hashlib.sha256(data).hexdigest()


def _generated_assignments(decisions, config: AuditConfig) -> dict[str, str]:
    split = split_by_game(list(decisions), seed=config.split_seed, ratios=config.split_ratios)
    out = {}
    for name, part in (("train", split.train), ("validation", split.val), ("test", split.test)):
        for decision in part:
            previous = out.setdefault(decision.game_id, name)
            if previous != name:
                raise AuditError(f"game {decision.game_id} assigned twice")
    return out


def build_split_manifest(dataset_hash: str, assignments: dict[str, str]) -> dict:
    canonical_assignments = {game: assignments[game] for game in sorted(assignments)}
    payload = {
        "split_schema_version": SPLIT_SCHEMA_VERSION,
        "dataset_sha256": dataset_hash,
        "assignments": canonical_assignments,
    }
    payload["split_sha256"] = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
    return payload


def validate_split_manifest(manifest, dataset_hash: str, game_ids: set[str]) -> dict[str, str]:
    required = {"split_schema_version", "dataset_sha256", "assignments", "split_sha256"}
    if set(manifest) != required:
        raise AuditError("split manifest fields mismatch")
    if manifest["split_schema_version"] != SPLIT_SCHEMA_VERSION:
        raise AuditError("unsupported split schema version")
    if manifest["dataset_sha256"] != dataset_hash:
        raise AuditError("split manifest dataset hash mismatch")
    assignments = {str(key): str(value) for key, value in manifest["assignments"].items()}
    if set(assignments) != game_ids:
        missing, extra = sorted(game_ids - set(assignments)), sorted(set(assignments) - game_ids)
        raise AuditError(f"split manifest missing games={missing} extra games={extra}")
    if set(assignments.values()) - {"train", "validation", "test"}:
        raise AuditError("split manifest contains unknown split")
    expected = build_split_manifest(dataset_hash, assignments)
    if manifest["split_sha256"] != expected["split_sha256"]:
        raise AuditError("split manifest hash mismatch")
    return expected["assignments"]


def load_and_audit_integrity(path, config: AuditConfig, *, split_manifest=None,
                             effective_model_features=None):
    config.validate()
    rows = load_rows(str(path), validate=True)
    if not rows:
        raise AuditError("dataset is empty")
    decisions = group_decisions(rows)
    ds_hash = dataset_sha256(path)
    assignments = (_generated_assignments(decisions, config) if split_manifest is None else
                   validate_split_manifest(split_manifest, ds_hash, {d.game_id for d in decisions}))
    manifest = build_split_manifest(ds_hash, assignments)
    by_split = {"train": [], "validation": [], "test": []}
    for decision in decisions:
        by_split[assignments[decision.game_id]].append(decision)
    corpus = AuditCorpus(
        dataset_name=Path(path).name, dataset_sha256=ds_hash, rows=tuple(rows),
        decisions=tuple(decisions), split_by_game=assignments,
        decisions_by_split={key: tuple(value) for key, value in by_split.items()},
        split_manifest=manifest,
    )
    findings = []
    seen = set()
    identity_by_decision_id = {}
    for decision in decisions:
        indices = [row["metadata"]["candidate_index"] for row in decision.rows]
        keys = [(decision.game_id, decision.decision_id, index) for index in indices]
        duplicates = []
        for key in keys:
            if key in seen:
                duplicates.append(key)
            seen.add(key)
        if duplicates:
            findings.append(make_finding(
                code="DUPLICATE_ROW_KEY", severity=Severity.FAIL, scope="decision",
                message="duplicate (game, decision, candidate) key", count=len(duplicates),
                examples=[repr(key) for key in duplicates], remediation="regenerate the dataset"))
        split = assignments[decision.game_id]
        identity = (decision.game_id, split)
        previous_identity = identity_by_decision_id.setdefault(decision.decision_id, identity)
        if previous_identity != identity:
            findings.append(make_finding(
                code="DUPLICATE_DECISION_ID", severity=Severity.FAIL, scope="split",
                message="decision_id occurs under more than one game or split", count=1,
                examples=[decision.decision_id],
                evidence={"identities": sorted({previous_identity, identity})},
                remediation="make decision IDs globally unique or repair split assignment"))
        if indices != list(range(len(indices))):
            findings.append(make_finding(
                code="NONCONTIGUOUS_CANDIDATES", severity=Severity.FAIL, scope="decision",
                message="candidate_index is not contiguous from zero", count=1,
                examples=[decision.decision_id], evidence={"indices": indices},
                remediation="fix grouping/export before training"))
        for field in DECISION_WIDE_METADATA:
            values = {canonical_json(row["metadata"][field]) for row in decision.rows}
            if len(values) != 1:
                findings.append(make_finding(
                    code="DECISION_METADATA_MISMATCH", severity=Severity.FAIL, scope="decision",
                    message=f"decision-wide metadata differs: {field}", count=1,
                    examples=[decision.decision_id], evidence={"field": field},
                    remediation="fix exporter consistency"))
    findings.extend(audit_provenance(corpus, config))
    findings.extend(audit_feature_allowlist(effective_model_features))
    return corpus, findings


def audit_provenance(corpus: AuditCorpus, config: AuditConfig) -> list[Finding]:
    signatures = {}
    for decision in corpus.decisions:
        metadata = decision.rows[0]["metadata"]
        signature = canonical_json({
            key: metadata[key] for key in (
                "schema_version", "feature_extractor_version", "teacher_version",
                "format_id", "config_hash", "teacher_config",
            )
        })
        signatures.setdefault(signature, []).append(decision.decision_id)
    if len(signatures) <= 1:
        return []
    schema_teacher_pairs = {
        (decision.rows[0]["metadata"]["schema_version"],
         decision.rows[0]["metadata"]["teacher_version"])
        for decision in corpus.decisions
    }
    severity = (Severity.FAIL if config.require_homogeneous_provenance
                or len(schema_teacher_pairs) > 1 else Severity.INFO)
    return [make_finding(
        code="MIXED_PROVENANCE", severity=severity, scope="dataset",
        message="dataset contains multiple provenance signatures",
        count=len(signatures), denominator=len(corpus.decisions),
        examples=signatures.keys(), evidence={"signatures": len(signatures)},
        remediation="split incompatible corpora or explicitly allow compatible configs",
    )]


def audit_feature_allowlist(effective_model_features) -> list[Finding]:
    if effective_model_features is None:
        return []
    requested = set(effective_model_features)
    denied = requested & (LABEL_DENYLIST | METADATA_DENYLIST)
    unknown = requested - set(FEATURE_COLUMNS)
    if not denied and not unknown:
        return []
    return [make_finding(
        code="MODEL_FEATURE_DENYLIST_VIOLATION", severity=Severity.FAIL, scope="feature",
        message="effective model features contain denied or unknown columns",
        count=len(denied | unknown), examples=sorted(denied | unknown),
        evidence={"denied": sorted(denied), "unknown": sorted(unknown)},
        remediation="restrict model input to schema.FEATURE_COLUMNS",
    )]
