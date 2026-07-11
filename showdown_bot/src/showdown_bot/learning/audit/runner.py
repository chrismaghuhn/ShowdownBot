"""Orchestration, fatal-input path and CLI for the dataset/reranker audit
(Phase 3, dataset-reranker-audit slice, Task 8). Wires the integrity,
duplicates, labels, features, distribution and optional-model checkers into
one AuditResult, writes deterministic JSON/Markdown reports plus the
resolved split manifest, and exposes a command-line entrypoint. Offline/pure
except for the checkers' own documented exceptions (file I/O, optional
lightgbm load in audit_optional_model). No network, no live battle imports.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from showdown_bot.learning.audit.contracts import (
    AuditConfig, AuditError, AuditResult, Severity, make_finding,
)
from showdown_bot.learning.audit.distribution import audit_distribution, load_team_catalog
from showdown_bot.learning.audit.duplicates import audit_duplicates
from showdown_bot.learning.audit.features import audit_features
from showdown_bot.learning.audit.integrity import load_and_audit_integrity
from showdown_bot.learning.audit.labels import audit_labels
from showdown_bot.learning.audit.model import audit_optional_model
from showdown_bot.learning.audit.report import write_json, write_reports


@dataclass(frozen=True)
class AuditRunConfig:
    dataset: Path
    out_dir: Path
    audit_config: AuditConfig = field(default_factory=AuditConfig)
    split_manifest_path: Path | None = None
    team_catalog_path: Path | None = None
    model_path: Path | None = None
    model_manifest_path: Path | None = None
    reference_datasets: tuple[Path, ...] = ()


def fatal_result(run: AuditRunConfig, exc: Exception) -> AuditResult:
    finding = make_finding(
        code="FATAL_INPUT", severity=Severity.FAIL, scope="dataset",
        message="audit input or contract prevented the full audit",
        count=1, examples=[type(exc).__name__],
        evidence={"error_type": type(exc).__name__, "error": str(exc)},
        remediation="correct the input path or violated contract and rerun the audit",
    )
    return AuditResult(
        findings=(finding,), metrics={"not_run": True},
        provenance={"dataset_name": run.dataset.name,
                    "audit_schema_version": run.audit_config.audit_schema_version},
        capability={"full_audit": False},
    )


def run_audit(run: AuditRunConfig) -> int:
    run.out_dir.mkdir(parents=True, exist_ok=True)
    try:
        split_manifest = (json.loads(run.split_manifest_path.read_text(encoding="utf-8"))
                          if run.split_manifest_path else None)
        corpus, findings = load_and_audit_integrity(
            run.dataset, run.audit_config, split_manifest=split_manifest)
        duplicate_findings, duplicate_metrics = audit_duplicates(corpus, run.audit_config)
        label_findings, label_metrics = audit_labels(corpus.decisions)
        feature_findings, feature_metrics = audit_features(corpus, run.audit_config)
        catalog = load_team_catalog(run.team_catalog_path) if run.team_catalog_path else None
        distribution_findings, distribution_metrics, ood_scores = audit_distribution(
            corpus, run.audit_config, team_catalog=catalog,
            reference_paths=run.reference_datasets)
        model_findings, model_metrics = audit_optional_model(
            corpus, run.audit_config, run.model_path, run.model_manifest_path, ood_scores)
        result = AuditResult(
            findings=tuple(findings + duplicate_findings + label_findings + feature_findings
                           + distribution_findings + model_findings),
            metrics={"duplicates": duplicate_metrics, "labels": label_metrics,
                     "features": feature_metrics, "distribution": distribution_metrics,
                     "model": model_metrics},
            provenance={"dataset_name": corpus.dataset_name,
                        "dataset_sha256": corpus.dataset_sha256,
                        "audit_config": asdict(run.audit_config),
                        "split_manifest": corpus.split_manifest},
            capability={"team_catalog": catalog is not None,
                        "model": (run.model_path is not None
                                  and run.model_manifest_path is not None),
                        "references": bool(run.reference_datasets)},
        )
    except (AuditError, OSError, json.JSONDecodeError, ValueError) as exc:
        result = fatal_result(run, exc)
    write_reports(run.out_dir, result)
    if "split_manifest" in result.provenance:
        write_json(run.out_dir / "split-manifest.json", result.provenance["split_manifest"])
    return 1 if result.status == "AUDIT FAIL" else 0


def load_config(path: Path | None) -> AuditConfig:
    if path is None:
        config = AuditConfig()
    else:
        data = json.loads(path.read_text(encoding="utf-8"))
        allowed = {item.name for item in fields(AuditConfig)}
        unknown = sorted(set(data) - allowed)
        if unknown:
            raise AuditError(f"unknown audit config keys: {unknown}")
        if "split_ratios" in data:
            data["split_ratios"] = tuple(float(value) for value in data["split_ratios"])
        config = AuditConfig(**data)
    config.validate()
    return config


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="audit a Showdown reranker dataset")
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--config-json", type=Path)
    parser.add_argument("--split-manifest", type=Path)
    parser.add_argument("--team-catalog", type=Path)
    parser.add_argument("--model", type=Path)
    parser.add_argument("--model-manifest", type=Path)
    parser.add_argument("--reference", action="append", default=[], type=Path)
    args = parser.parse_args(argv)
    run = AuditRunConfig(
        dataset=args.dataset, out_dir=args.out, audit_config=load_config(args.config_json),
        split_manifest_path=args.split_manifest, team_catalog_path=args.team_catalog,
        model_path=args.model, model_manifest_path=args.model_manifest,
        reference_datasets=tuple(args.reference),
    )
    return run_audit(run)
