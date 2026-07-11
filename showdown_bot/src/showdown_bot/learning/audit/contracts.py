from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from enum import StrEnum

AUDIT_SCHEMA_VERSION = "dataset-reranker-audit-v1"
REPORT_SCHEMA_VERSION = "dataset-reranker-audit-report-v1"
SPLIT_SCHEMA_VERSION = "dataset-reranker-split-v1"


class AuditError(ValueError):
    pass


class Severity(StrEnum):
    FAIL = "FAIL"
    WARN = "WARN"
    INFO = "INFO"


@dataclass(frozen=True)
class AuditConfig:
    audit_schema_version: str = AUDIT_SCHEMA_VERSION
    split_seed: int = 42
    split_ratios: tuple[float, float, float] = (0.8, 0.1, 0.1)
    example_limit: int = 20
    near_duplicate_threshold: float = 0.05
    near_numeric_weight: float = 0.6
    near_categorical_weight: float = 0.4
    near_numeric_cap: float = 10.0
    near_epsilon: float = 1e-6
    near_constant_rate: float = 0.995
    sentinel_warn_rate: float = 0.95
    unseen_warn_rate: float = 0.05
    out_of_range_warn_rate: float = 0.05
    spearman_warn_abs: float = 0.98
    psi_warn: float = 0.25
    js_warn: float = 0.10
    ood_threshold: float = 0.50
    small_bucket_games: int = 10
    share_shift_warn: float = 0.15
    ece_warn: float = 0.10
    calibration_small_n: int = 100
    require_homogeneous_provenance: bool = False

    def validate(self) -> None:
        if self.audit_schema_version != AUDIT_SCHEMA_VERSION:
            raise AuditError("unsupported audit_schema_version")
        if len(self.split_ratios) != 3 or any(x < 0 for x in self.split_ratios):
            raise AuditError("split_ratios must contain three non-negative values")
        if not math.isclose(sum(self.split_ratios), 1.0, abs_tol=1e-12):
            raise AuditError("split_ratios must sum to 1")
        if not math.isclose(self.near_numeric_weight + self.near_categorical_weight, 1.0, abs_tol=1e-12):
            raise AuditError("near duplicate weights must sum to 1")
        for name, value in vars(self).items():
            if isinstance(value, float) and not math.isfinite(value):
                raise AuditError(f"{name} must be finite")
        if self.example_limit <= 0 or self.small_bucket_games <= 0:
            raise AuditError("limits must be positive")
        unit_interval = (
            "near_duplicate_threshold", "near_numeric_weight", "near_categorical_weight",
            "near_constant_rate", "sentinel_warn_rate", "unseen_warn_rate",
            "out_of_range_warn_rate", "spearman_warn_abs", "psi_warn", "js_warn",
            "ood_threshold", "share_shift_warn", "ece_warn",
        )
        if any(not 0.0 <= getattr(self, name) <= 1.0 for name in unit_interval):
            raise AuditError("rate and divergence thresholds must be in [0, 1]")
        if self.near_numeric_cap <= 0 or self.near_epsilon <= 0:
            raise AuditError("near duplicate cap and epsilon must be positive")
        if self.calibration_small_n <= 0:
            raise AuditError("calibration_small_n must be positive")


@dataclass(frozen=True)
class Finding:
    code: str
    severity: Severity
    scope: str
    message: str
    count: int
    denominator: int | None
    rate: float | None
    split: str | None
    feature: str | None
    examples: tuple[str, ...]
    evidence: dict
    remediation: str


def make_finding(*, code, severity, scope, message, count=0, denominator=None,
                 split=None, feature=None, examples=(), evidence=None,
                 remediation="", example_limit=20) -> Finding:
    if not code or count < 0 or (denominator is not None and denominator < 0):
        raise AuditError("invalid finding identity/count")
    rate = None if denominator in (None, 0) else count / denominator
    if rate is not None and not math.isfinite(rate):
        raise AuditError("finding rate must be finite")
    return Finding(
        code=str(code), severity=Severity(severity), scope=str(scope), message=str(message),
        count=count, denominator=denominator, rate=rate, split=split, feature=feature,
        examples=tuple(sorted(map(str, examples))[:example_limit]),
        evidence=dict(evidence or {}), remediation=str(remediation),
    )


@dataclass(frozen=True)
class AuditCorpus:
    dataset_name: str
    dataset_sha256: str
    rows: tuple[dict, ...]
    decisions: tuple
    split_by_game: dict[str, str]
    decisions_by_split: dict[str, tuple]
    split_manifest: dict


@dataclass
class AuditResult:
    findings: tuple[Finding, ...] = ()
    metrics: dict = field(default_factory=dict)
    provenance: dict = field(default_factory=dict)
    capability: dict = field(default_factory=dict)

    @property
    def status(self) -> str:
        return "AUDIT FAIL" if any(f.severity == Severity.FAIL for f in self.findings) else "AUDIT PASS"

    def sorted_findings(self) -> list[Finding]:
        rank = {Severity.FAIL: 0, Severity.WARN: 1, Severity.INFO: 2}
        return sorted(self.findings, key=lambda f: (
            rank[f.severity], f.code, f.split or "", f.feature or "", f.examples,
        ))


def canonical_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def quantile(ordered: list[float], q: float) -> float:
    if not ordered:
        raise AuditError("quantile requires values")
    position = (len(ordered) - 1) * q
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    fraction = position - lower
    return float(ordered[lower]) * (1 - fraction) + float(ordered[upper]) * fraction
