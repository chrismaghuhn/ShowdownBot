from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


class GeneralisationError(ValueError):
    pass


class SchemaError(GeneralisationError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_id(value: Any, length: int | None = None) -> str:
    digest = hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
    return digest if length is None else digest[:length]


def load_mapping(path: str | Path) -> dict:
    p = Path(path)
    try:
        value = yaml.safe_load(p.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise SchemaError(f"cannot read {p}: {exc}") from exc
    if not isinstance(value, dict):
        raise SchemaError(f"{p} must contain a mapping")
    return value


@dataclass(frozen=True)
class AnalysisPolicy:
    schema_version: str = "generalisation-policy-v1"
    confidence_level: float = 0.95
    alpha: float = 0.05
    descriptive_min_unique_seeds_per_cell: int = 10
    gate_min_unique_seeds_per_cell: int = 30
    required_cell_coverage: float = 1.0
    required_pairing_coverage: float = 1.0
    bootstrap_replicates: int = 10000
    bootstrap_seed: int = 20260712
    regression_margin: float = 0.02
    improvement_margin: float = 0.0
    tie_mode: str = "non_win"
    multiple_testing: str = "holm"
    planner_seed: int = 20260712
    allow_nonreproducible_policies: bool = False

    @property
    def policy_hash(self) -> str:
        return sha256_id(asdict(self))

    def validate(self) -> "AnalysisPolicy":
        if self.schema_version != "generalisation-policy-v1":
            raise SchemaError("unsupported policy schema_version")
        if not 0.0 < self.confidence_level < 1.0 or not 0.0 < self.alpha < 1.0:
            raise SchemaError("confidence_level and alpha must be between zero and one")
        if self.descriptive_min_unique_seeds_per_cell < 1:
            raise SchemaError("descriptive minimum must be positive")
        if self.gate_min_unique_seeds_per_cell < self.descriptive_min_unique_seeds_per_cell:
            raise SchemaError("gate minimum must be at least descriptive minimum")
        if self.required_cell_coverage != 1.0:
            raise SchemaError("required_cell_coverage must equal 1.0 in v1")
        if self.required_pairing_coverage != 1.0:
            raise SchemaError("required_pairing_coverage must equal 1.0 in v1")
        if self.bootstrap_replicates < 1:
            raise SchemaError("bootstrap_replicates must be positive")
        if self.regression_margin < 0.0 or self.improvement_margin < 0.0:
            raise SchemaError("margins must be non-negative")
        if self.tie_mode != "non_win" or self.multiple_testing != "holm":
            raise SchemaError("v1 requires tie_mode=non_win and multiple_testing=holm")
        return self


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str
    scope: str
    message: str
    count: int | None = None
    denominator: int | None = None
    examples: tuple[str, ...] = ()
    evidence: dict[str, Any] = field(default_factory=dict)
    remediation: str = "inspect the referenced inputs"

    def to_dict(self) -> dict:
        return asdict(self)


_POLICY_FIELDS = frozenset(AnalysisPolicy.__dataclass_fields__)


def load_policy(path: str | Path) -> AnalysisPolicy:
    raw = load_mapping(path)
    unknown = set(raw) - _POLICY_FIELDS
    missing = _POLICY_FIELDS - set(raw)
    if unknown:
        raise SchemaError(f"policy unknown fields: {sorted(unknown)}")
    if missing:
        raise SchemaError(f"policy missing fields: {sorted(missing)}")
    try:
        return AnalysisPolicy(**raw).validate()
    except TypeError as exc:
        raise SchemaError(f"invalid policy values: {exc}") from exc
