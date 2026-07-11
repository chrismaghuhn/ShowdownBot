# Wiederverwendbares Datensatz- und Reranker-Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ein deterministisches Offline-Audit bauen, das beliebige schema-kompatible Reranker-Datensätze, Splits und optionale Modellartefakte auf Integrität, Leakage, Duplikate, Labelqualität, Drift, OOD und Kalibrierung prüft.

**Architecture:** Ein isoliertes `showdown_bot.learning.audit`-Paket enthält kleine pure Prüfer, die standardisierte Findings und Metrikblöcke erzeugen. Der Runner lädt und splittet den Corpus einmal, orchestriert die Prüfer und schreibt auch bei fachlichen FAIL-Findings einen vollständigen JSON-/Markdown-Report. Keine Auditkomponente wird vom Live-, Battle-, Gauntlet-, Teacher- oder Inferenzpfad importiert.

**Tech Stack:** Python 3.11+, stdlib `dataclasses`/`enum`/`hashlib`/`json`/`gzip`/`math`, NumPy, optional LightGBM über den vorhandenen Learning-Extra, bestehende `learning.dataset`, `learning.schema`, `learning.reranker_features` und pytest.

---

## Dateistruktur

Neu:

- `showdown_bot/src/showdown_bot/learning/audit/__init__.py` — öffentliche Paketgrenze.
- `showdown_bot/src/showdown_bot/learning/audit/contracts.py` — Config, Severity, Finding,
  AuditCorpus, AuditResult und kanonische Serialisierung.
- `showdown_bot/src/showdown_bot/learning/audit/integrity.py` — Loader, Dataset-Hash,
  Splitmanifest, Gruppen-/Provenance-/Denylist-Prüfung.
- `showdown_bot/src/showdown_bot/learning/audit/duplicates.py` — Row-, Decision-, semantische und
  blockierte Near-Duplikate.
- `showdown_bot/src/showdown_bot/learning/audit/labels.py` — Gap-, Rank-, Tie- und
  Teacher-Konsistenz.
- `showdown_bot/src/showdown_bot/learning/audit/features.py` — Featuregesundheit, Spearman,
  PSI und Jensen-Shannon.
- `showdown_bot/src/showdown_bot/learning/audit/distribution.py` — Teamkatalog, Coverage und OOD.
- `showdown_bot/src/showdown_bot/learning/audit/model.py` — Manifestprüfung, Scoring,
  Temperaturfit und Kalibrierung.
- `showdown_bot/src/showdown_bot/learning/audit/report.py` — deterministisches JSON/Markdown.
- `showdown_bot/src/showdown_bot/learning/audit/runner.py` — Orchestrierung, Fatal-Report und CLI.
- `showdown_bot/src/showdown_bot/learning/audit/__main__.py` — `python -m ...audit`.

Tests:

- `showdown_bot/tests/test_audit_contracts.py`
- `showdown_bot/tests/test_audit_integrity.py`
- `showdown_bot/tests/test_audit_duplicates.py`
- `showdown_bot/tests/test_audit_labels.py`
- `showdown_bot/tests/test_audit_features.py`
- `showdown_bot/tests/test_audit_distribution.py`
- `showdown_bot/tests/test_audit_model.py`
- `showdown_bot/tests/test_audit_report.py`
- `showdown_bot/tests/test_audit_runner.py`
- `showdown_bot/tests/test_audit_live_path_guard.py`

Dokumentation:

- Modify: `README.md`
- Create: `reports/2026-07-11-dataset-reranker-audit-smoke.md`

---

### Task 1: Auditverträge, Konfiguration und deterministische Findings

**Files:**

- Create: `showdown_bot/src/showdown_bot/learning/audit/__init__.py`
- Create: `showdown_bot/src/showdown_bot/learning/audit/contracts.py`
- Create: `showdown_bot/tests/test_audit_contracts.py`

- [ ] **Step 1: Failing Vertrags- und Sortiertests schreiben**

```python
def test_config_defaults_are_versioned_and_valid():
    cfg = AuditConfig()
    assert cfg.audit_schema_version == "dataset-reranker-audit-v1"
    assert cfg.split_seed == 42
    assert cfg.split_ratios == (0.8, 0.1, 0.1)
    assert cfg.near_duplicate_threshold == 0.05
    assert cfg.near_numeric_weight == 0.6
    assert cfg.near_categorical_weight == 0.4


def test_finding_limits_and_sorts_examples():
    finding = make_finding(
        code="X", severity=Severity.WARN, scope="feature", message="x",
        count=30, denominator=100, examples=[f"d{i:02d}" for i in reversed(range(30))],
        evidence={"threshold": 0.1}, remediation="inspect",
    )
    assert finding.rate == 0.3
    assert finding.examples == tuple(f"d{i:02d}" for i in range(20))


def test_result_status_and_finding_order():
    def finding(code, severity):
        return make_finding(code=code, severity=severity, scope="dataset", message=code,
                            remediation="inspect")
    result = AuditResult(findings=(
        finding("info", Severity.INFO),
        finding("fail", Severity.FAIL),
        finding("warn", Severity.WARN),
    ))
    assert result.status == "AUDIT FAIL"
    assert [f.code for f in result.sorted_findings()] == ["fail", "warn", "info"]
```

```python
@pytest.mark.parametrize("config", [
    replace(AuditConfig(), split_ratios=(0.8, 0.2, 0.2)),
    replace(AuditConfig(), near_duplicate_threshold=-0.1),
    replace(AuditConfig(), near_numeric_weight=0.7, near_categorical_weight=0.4),
])
def test_invalid_config_is_rejected(config):
    with pytest.raises(AuditError):
        config.validate()


def test_invalid_finding_identity_and_severity_are_rejected():
    with pytest.raises(AuditError):
        make_finding(code="", severity=Severity.WARN, scope="x", message="x")
    with pytest.raises(ValueError):
        make_finding(code="X", severity="UNKNOWN", scope="x", message="x")
```

- [ ] **Step 2: Tests rot ausführen**

Run:

```powershell
python -m pytest tests/test_audit_contracts.py -q
```

Expected: FAIL, Paket existiert noch nicht.

- [ ] **Step 3: Config und Grundtypen implementieren**

```python
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
```

- [ ] **Step 4: Finding, Corpus und Result implementieren**

```python
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
```

`__init__.py` exportiert nur `AuditConfig`, `AuditError`, `AuditResult`, `Finding`, `Severity`.

- [ ] **Step 5: Tests grün ausführen und committen**

Run:

```powershell
python -m pytest tests/test_audit_contracts.py -q
```

Expected: PASS.

```powershell
git add showdown_bot/src/showdown_bot/learning/audit/__init__.py showdown_bot/src/showdown_bot/learning/audit/contracts.py showdown_bot/tests/test_audit_contracts.py
git commit -m "feat(audit): define versioned audit contracts"
```

---

### Task 2: Dataset laden, gameweise splitten und Integrität prüfen

**Files:**

- Create: `showdown_bot/src/showdown_bot/learning/audit/integrity.py`
- Create: `showdown_bot/tests/test_audit_integrity.py`

- [ ] **Step 1: Failing Loader-/Split-/Integritätstests schreiben**

Eine lokale Testhilfe schreibt vollständige schema-valide Rows über `schema.to_jsonl_line`.

```python
def _schema_row(game_id, decision_id, candidate_index, *, format_id="gen9vgc2025regi"):
    features = {key: 0.0 for key in FEATURE_COLUMNS}
    features.update({
        "format_id": format_id, "game_mode": "NEUTRAL",
        "slot1_action_type": "move", "slot2_action_type": "move",
        "slot1_move_id": "tackle", "slot2_move_id": "protect",
    })
    best = candidate_index == 0
    raw = 1.0 if best else 0.0
    metadata = {key: None for key in METADATA_KEYS}
    metadata.update({
        "game_id": game_id, "decision_id": decision_id,
        "candidate_index": candidate_index, "format_id": format_id,
        "game_outcome": "win", "final_turn": 5, "winner": "p1", "teacher_trace": {},
        "schema_version": "v1", "feature_extractor_version": "v1",
        "teacher_version": "rollout-h1-v1", "git_sha": "a" * 40,
        "team_hash": "team-a", "config_hash": "config-a",
        "teacher_config": {"teacher_version": "rollout-h1-v1", "trainable_label": True},
    })
    label = {key: 0 for key in LABEL_KEYS}
    label.update({
        "counterfactual_value_raw": raw,
        "counterfactual_value_normalized_within_decision": 0.5 if best else -0.5,
        "value_gap_to_best": 0.0 if best else -1.0,
        "counterfactual_rank": candidate_index, "teacher_rank": candidate_index,
        "teacher_best": best, "chosen_by_current_heuristic": best,
        "heuristic_rank": candidate_index,
    })
    return Row(features=features, metadata=metadata, label=label)


@pytest.fixture
def audit_dataset():
    def write(tmp_path, *, games=3, candidate_indices=(0, 1), mixed_format=False):
        path = tmp_path / "dataset.jsonl"
        lines = []
        for game_index in range(games):
            for candidate_index in candidate_indices:
                format_id = "other-format" if mixed_format and candidate_index == candidate_indices[-1] else "gen9vgc2025regi"
                lines.append(to_jsonl_line(_schema_row(
                    f"g{game_index}", f"g{game_index}-d0", candidate_index,
                    format_id=format_id,
                )))
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path
    return write


def split_manifest_for(path, assignments):
    return build_split_manifest(dataset_sha256(path), assignments)


def test_generated_split_is_complete_disjoint_and_hashed(tmp_path, audit_dataset):
    path = audit_dataset(tmp_path, games=20)
    corpus, findings = load_and_audit_integrity(path, AuditConfig())
    assert findings == []
    assert set(corpus.split_by_game) == {f"g{i}" for i in range(20)}
    assert set(corpus.split_by_game.values()) <= {"train", "validation", "test"}
    assert len(corpus.split_manifest["split_sha256"]) == 64


def test_split_manifest_refuses_missing_game(tmp_path, audit_dataset):
    path = audit_dataset(tmp_path, games=3)
    manifest = split_manifest_for(path, {"g0": "train", "g1": "test"})
    with pytest.raises(AuditError, match="missing games"):
        load_and_audit_integrity(path, AuditConfig(), split_manifest=manifest)


def test_candidate_indices_and_decision_metadata_fail(tmp_path, audit_dataset):
    path = audit_dataset(tmp_path, candidate_indices=[0, 2], mixed_format=True)
    _corpus, findings = load_and_audit_integrity(path, AuditConfig())
    assert {f.code for f in findings} >= {"NONCONTIGUOUS_CANDIDATES", "DECISION_METADATA_MISMATCH"}
    assert all(f.severity == Severity.FAIL for f in findings)
```

```python
def test_empty_dataset_and_wrong_manifest_hash_are_rejected(tmp_path, audit_dataset):
    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(AuditError, match="empty"):
        load_and_audit_integrity(empty, AuditConfig())
    path = audit_dataset(tmp_path, games=3)
    manifest = split_manifest_for(path, {"g0": "train", "g1": "validation", "g2": "test"})
    manifest["dataset_sha256"] = "0" * 64
    with pytest.raises(AuditError, match="dataset hash"):
        load_and_audit_integrity(path, AuditConfig(), split_manifest=manifest)


def test_effective_feature_denylist_is_fail(tmp_path, audit_dataset):
    path = audit_dataset(tmp_path)
    _corpus, findings = load_and_audit_integrity(
        path, AuditConfig(), effective_model_features=["teacher_best"])
    assert any(f.code == "MODEL_FEATURE_DENYLIST_VIOLATION"
               and f.severity == Severity.FAIL for f in findings)


def test_mixed_provenance_is_reported(tmp_path, audit_dataset):
    path = audit_dataset(tmp_path, mixed_format=True)
    _corpus, findings = load_and_audit_integrity(path, AuditConfig())
    assert any(f.code == "MIXED_PROVENANCE" for f in findings)
```

- [ ] **Step 2: Tests rot ausführen**

Run:

```powershell
python -m pytest tests/test_audit_integrity.py -q
```

Expected: FAIL, Modul fehlt.

- [ ] **Step 3: Unkomprimierten Dataset-Hash und Splitmanifest implementieren**

```python
import gzip
import hashlib
import json
from pathlib import Path

from showdown_bot.learning.dataset import group_decisions, load_rows, split_by_game
from showdown_bot.learning.audit.contracts import (
    AuditConfig, AuditCorpus, AuditError, SPLIT_SCHEMA_VERSION, canonical_json, make_finding, Severity,
)


def dataset_sha256(path) -> str:
    p = Path(path)
    data = gzip.open(p, "rb").read() if p.suffix == ".gz" else p.read_bytes()
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
```

Damit prüft `validate_split_manifest` exakte Keys, Schema-Version, Dataset-Hash, erlaubte Splitnamen,
vollständige Game-Menge und den neu berechneten `split_sha256`.

- [ ] **Step 4: Corpus und Integritätsfindings implementieren**

```python
DECISION_WIDE_METADATA = frozenset({
    "game_id", "decision_id", "format_id", "schema_version", "feature_extractor_version",
    "teacher_version", "git_sha", "team_hash", "config_hash", "teacher_config",
})


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
```

```python
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
```

- [ ] **Step 5: Tests grün ausführen und committen**

```powershell
python -m pytest tests/test_audit_integrity.py tests/test_dataset.py tests/test_reranker_features.py -q
```

Expected: PASS.

```powershell
git add showdown_bot/src/showdown_bot/learning/audit/integrity.py showdown_bot/tests/test_audit_integrity.py
git commit -m "feat(audit): validate corpus integrity and game splits"
```

---

### Task 3: Exakte, semantische und Near-Duplikate erkennen

**Files:**

- Create: `showdown_bot/src/showdown_bot/learning/audit/duplicates.py`
- Create: `showdown_bot/tests/test_audit_duplicates.py`

- [ ] **Step 1: Failing Duplikatmatrix schreiben**

```python
def _decision(game_id, *, numeric=0.0, label_gap=-1.0):
    rows = []
    for index in (0, 1):
        best = index == 0
        rows.append({
            "features": {"format_id": "f", "game_mode": "NEUTRAL",
                         "slot1_action_type": "move", "slot2_action_type": "move",
                         "numeric": numeric, "candidate": index},
            "metadata": {"game_id": game_id, "decision_id": f"{game_id}-d",
                         "candidate_index": index, "format_id": "f",
                         "schema_version": "v1", "feature_extractor_version": "v1",
                         "teacher_version": "t", "config_hash": "c"},
            "label": {"teacher_best": best, "value_gap_to_best": 0.0 if best else label_gap},
        })
    return group_decisions(rows)[0]


def _corpus(train, test):
    decisions = tuple(train + test)
    return AuditCorpus(
        dataset_name="fixture", dataset_sha256="a" * 64,
        rows=tuple(row for decision in decisions for row in decision.rows), decisions=decisions,
        split_by_game={d.game_id: ("train" if d in train else "test") for d in decisions},
        decisions_by_split={"train": tuple(train), "validation": (), "test": tuple(test)},
        split_manifest={},
    )


def test_semantic_duplicate_across_splits_is_fail():
    corpus = _corpus([_decision("train-g")], [_decision("test-g")])
    findings, metrics = audit_duplicates(corpus, AuditConfig())
    finding = next(f for f in findings if f.code == "SEMANTIC_CROSS_SPLIT_DUPLICATE")
    assert finding.severity == Severity.FAIL
    assert metrics["semantic_cross_split_pairs"] == 1


def test_label_only_change_keeps_semantic_hash():
    left = _decision("left", label_gap=-1.0)
    right = _decision("right", label_gap=-2.0)
    assert semantic_decision_hash(left) == semantic_decision_hash(right)
    assert full_decision_hash(left) != full_decision_hash(right)


def test_near_duplicate_threshold_is_inclusive():
    left, right = _decision("left", numeric=0.0), _decision("right", numeric=0.5)
    reference = {"numeric": (0.0, 1.0)}
    distance = mixed_decision_distance(left, right, reference, AuditConfig())
    corpus = _corpus([left], [right])
    findings, _metrics = audit_duplicates(
        corpus, replace(AuditConfig(), near_duplicate_threshold=distance))
    assert any(f.code == "NEAR_CROSS_SPLIT_DUPLICATE" for f in findings)
```

```python
def test_same_split_duplicate_is_not_fail():
    left, right = _decision("a"), _decision("b")
    findings, _metrics = audit_duplicates(_corpus([left, right], []), AuditConfig())
    duplicate_findings = [f for f in findings if "DUPLICATE" in f.code]
    assert duplicate_findings
    assert all(f.severity != Severity.FAIL for f in duplicate_findings)


def test_near_distance_above_threshold_and_different_blocks_do_not_warn():
    left, right = _decision("left", numeric=0.0), _decision("right", numeric=1.0)
    right.rows[0]["features"]["game_mode"] = "TRICK_ROOM"
    right.rows[1]["features"]["game_mode"] = "TRICK_ROOM"
    corpus = _corpus([left], [right])
    findings, _metrics = audit_duplicates(corpus, AuditConfig(near_duplicate_threshold=0.05))
    assert not any(f.code == "NEAR_CROSS_SPLIT_DUPLICATE" for f in findings)


def test_zero_iqr_reference_has_positive_scale():
    reference = robust_numeric_reference([_decision("a", numeric=0.0)])
    assert reference["numeric"][1] > 0
```

- [ ] **Step 2: Tests rot ausführen**

```powershell
python -m pytest tests/test_audit_duplicates.py -q
```

Expected: FAIL.

- [ ] **Step 3: Kanonische Hashes implementieren**

```python
import hashlib
import math
from collections import defaultdict

from showdown_bot.learning.audit.contracts import canonical_json, make_finding, Severity

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
```

Labelkonflikte werden in Task 4 auf Basis dieses Hashs und gleicher Teacher-/Config-Provenance
geprüft.

- [ ] **Step 4: Blockierte Near-Distanz implementieren**

```python
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
```

`audit_duplicates` bildet Hashgruppen, meldet exakte/semantische Cross-Split-Paare und vergleicht
nur Decision-Paare innerhalb desselben `block_key`. Jedes ungeordnete Paar erscheint genau einmal.

- [ ] **Step 5: Tests grün ausführen und committen**

```powershell
python -m pytest tests/test_audit_duplicates.py -q
```

Expected: PASS.

```powershell
git add showdown_bot/src/showdown_bot/learning/audit/duplicates.py showdown_bot/tests/test_audit_duplicates.py
git commit -m "feat(audit): detect exact semantic and near duplicates"
```

---

### Task 4: Teacher-, Gap-, Rank- und Tie-Konsistenz auditieren

**Files:**

- Create: `showdown_bot/src/showdown_bot/learning/audit/labels.py`
- Create: `showdown_bot/tests/test_audit_labels.py`

- [ ] **Step 1: Failing Labelinvarianten schreiben**

```python
def _label_decision(*, raw_values=(1.0, 0.0), teacher_best=(True, False),
                    chosen=(True, False), teacher_rank=(0, 1)):
    mean = sum(raw_values) / len(raw_values)
    maximum = max(raw_values)
    rows = []
    for index, raw in enumerate(raw_values):
        rows.append({
            "features": {"candidate": index},
            "metadata": {"game_id": "g", "decision_id": "d", "candidate_index": index,
                         "teacher_version": "t", "feature_extractor_version": "v1",
                         "config_hash": "c",
                         "teacher_config": {"teacher_version": "t", "trainable_label": True}},
            "label": {
                "counterfactual_value_raw": raw,
                "counterfactual_value_normalized_within_decision": raw - mean,
                "value_gap_to_best": raw - maximum,
                "counterfactual_rank": teacher_rank[index], "teacher_rank": teacher_rank[index],
                "teacher_best": teacher_best[index],
                "chosen_by_current_heuristic": chosen[index], "heuristic_rank": index,
            },
        })
    return group_decisions(rows)[0]


def test_valid_tie_and_multiple_equivalent_choices_pass():
    decision = _label_decision(
        raw_values=[2.0, 2.0, 1.0], teacher_best=[True, True, False],
        chosen=[True, True, False], teacher_rank=[0, 0, 2],
    )
    findings, _metrics = audit_labels([decision])
    assert not [f for f in findings if f.severity == Severity.FAIL]


@pytest.mark.parametrize(("mutation", "code"), [
    (lambda row: row["label"].update(value_gap_to_best=0.1), "POSITIVE_VALUE_GAP"),
    (lambda row: row["label"].update(teacher_best=True, value_gap_to_best=-1.0), "BEST_NONZERO_GAP"),
    (lambda row: row["label"].update(counterfactual_value_normalized_within_decision=5.0), "NORMALIZED_MEAN_MISMATCH"),
])
def test_label_failures(mutation, code):
    decision = _label_decision()
    mutation(decision.rows[0])
    findings, _metrics = audit_labels([decision])
    assert any(f.code == code and f.severity == Severity.FAIL for f in findings)
```

```python
@pytest.mark.parametrize(("decision", "code"), [
    (_label_decision(teacher_best=(False, False)), "NO_TEACHER_BEST"),
    (_label_decision(chosen=(False, False)), "NO_HEURISTIC_CHOICE"),
    (_label_decision(teacher_rank=(1, 0)), "TEACHER_RANK_MISMATCH"),
])
def test_structural_label_failures(decision, code):
    findings, _metrics = audit_labels([decision])
    assert any(f.code == code and f.severity == Severity.FAIL for f in findings)


def test_nonfinite_and_trainable_mismatch_fail():
    nonfinite = _label_decision()
    nonfinite.rows[0]["label"]["counterfactual_value_raw"] = float("nan")
    mismatch = _label_decision()
    mismatch.rows[1]["metadata"]["teacher_config"]["trainable_label"] = False
    first, _metrics = audit_labels([nonfinite])
    second, _metrics = audit_labels([mismatch])
    assert any(f.code == "NONFINITE_LABEL" for f in first)
    assert any(f.code == "TRAINABLE_LABEL_MISMATCH" for f in second)
```

- [ ] **Step 2: Tests rot ausführen**

```powershell
python -m pytest tests/test_audit_labels.py -q
```

Expected: FAIL.

- [ ] **Step 3: Per-Decision-Prüfer implementieren**

```python
TOL = 1e-9


def _competition_ranks(values: list[float]) -> list[int]:
    ordered = sorted(values, reverse=True)
    rank = {value: ordered.index(value) for value in set(values)}
    return [rank[value] for value in values]


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
    expected_best = [math.isclose(value, maximum, abs_tol=TOL) for value in raw]
    if best_flags != expected_best:
        findings.append(fail("TEACHER_BEST_RAW_MISMATCH", context))
    if any(not math.isclose(gap, value - maximum, abs_tol=TOL)
           for gap, value in zip(gaps, raw)):
        findings.append(fail("GAP_RAW_MISMATCH", context))
    mean = sum(raw) / len(raw)
    if any(not math.isclose(value, raw_value - mean, abs_tol=TOL)
           for value, raw_value in zip(normalized, raw)):
        findings.append(fail("NORMALIZED_MEAN_MISMATCH", context))
    expected_ranks = _competition_ranks(raw)
    actual_ranks = [int(label["teacher_rank"]) for label in labels]
    if actual_ranks != expected_ranks:
        findings.append(fail("TEACHER_RANK_MISMATCH", context))
    counterfactual_ranks = [int(label["counterfactual_rank"]) for label in labels]
    if counterfactual_ranks != expected_ranks:
        findings.append(fail("COUNTERFACTUAL_RANK_MISMATCH", context))
    trainable = {row["metadata"]["teacher_config"]["trainable_label"] for row in decision.rows}
    if len(trainable) != 1:
        findings.append(fail("TRAINABLE_LABEL_MISMATCH", context))
    return findings
```

```python
def fail(code: str, context: dict) -> Finding:
    return make_finding(
        code=code, severity=Severity.FAIL, scope="label", message=code,
        count=1, examples=[context["decision_id"]], evidence=context,
        remediation="regenerate or correct labels before training",
    )
```

- [ ] **Step 4: Semantische Labelkonflikte implementieren**

```python
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
```

Damit wird nach `(semantic_decision_hash, teacher_provenance)` gruppiert. Verschiedene
Teacher-Provenance wird als INFO-Vergleich gezählt, nicht als Konflikt.

- [ ] **Step 5: Tests grün ausführen und committen**

```powershell
python -m pytest tests/test_audit_labels.py tests/test_dataset.py tests/test_eval_teacher_disagreement.py -q
```

Expected: PASS.

```powershell
git add showdown_bot/src/showdown_bot/learning/audit/labels.py showdown_bot/tests/test_audit_labels.py
git commit -m "feat(audit): enforce reranker label invariants"
```

---

### Task 5: Featuregesundheit, Korrelation und Splitdrift messen

**Files:**

- Create: `showdown_bot/src/showdown_bot/learning/audit/features.py`
- Create: `showdown_bot/tests/test_audit_features.py`

- [ ] **Step 1: Failing Feature-/Drifttests schreiben**

```python
def _feature_corpus(train_rows, test_rows=()):
    def decisions(rows, prefix):
        return tuple(Decision(prefix, f"{prefix}-{i}", [{
            "features": row, "metadata": {"candidate_index": 0}, "label": {}}])
            for i, row in enumerate(rows))
    train, test = decisions(train_rows, "tr"), decisions(test_rows, "te")
    return AuditCorpus(
        dataset_name="fixture", dataset_sha256="a" * 64,
        rows=tuple(row for d in train + test for row in d.rows), decisions=train + test,
        split_by_game={d.game_id: ("train" if d in train else "test") for d in train + test},
        decisions_by_split={"train": train, "validation": (), "test": test}, split_manifest={})


def test_constant_near_constant_and_nonfinite_findings():
    corpus = _feature_corpus([
        {"constant": 1, "near": 0 if i < 199 else 1,
         "bad": 0.0 if i < 199 else float("inf")}
        for i in range(200)
    ])
    findings, metrics = audit_features(corpus, AuditConfig())
    codes = {f.code for f in findings}
    assert {"CONSTANT_FEATURE", "NEAR_CONSTANT_FEATURE", "NONFINITE_FEATURE"} <= codes
    assert metrics["train"]["constant"]["unique"] == 1


def test_psi_and_js_use_train_reference():
    corpus = _feature_corpus(
        [{"numeric": i, "category": "a"} for i in range(100)],
        [{"numeric": i, "category": "b"} for i in range(100, 200)],
    )
    findings, metrics = audit_features(corpus, AuditConfig())
    assert metrics["drift"]["test"]["numeric"]["psi"] >= 0.25
    assert metrics["drift"]["test"]["category"]["js"] >= 0.10
    assert {f.code for f in findings} >= {"PSI_DRIFT", "JS_DRIFT", "UNSEEN_CATEGORY"}
```

```python
def test_feature_threshold_boundaries_are_inclusive():
    rows = [{"near": 0 if i < 199 else 1,
             "sentinel": None if i < 190 else "value"} for i in range(200)]
    findings, _metrics = audit_features(_feature_corpus(rows), AuditConfig())
    assert any(f.code == "NEAR_CONSTANT_FEATURE" and f.feature == "near" for f in findings)
    assert any(f.code == "SENTINEL_DOMINATED_FEATURE" and f.feature == "sentinel"
               for f in findings)


def test_spearman_ties_and_quantile_edges_are_deterministic():
    assert spearman([1, 1, 2, 2], [4, 4, 8, 8]) == pytest.approx(1.0)
    values = list(range(100))
    assert train_quantile_edges(values) == train_quantile_edges(list(reversed(values)))
```

- [ ] **Step 2: Tests rot ausführen**

```powershell
python -m pytest tests/test_audit_features.py -q
```

Expected: FAIL.

- [ ] **Step 3: Featurestatistik und Spearman implementieren**

```python
SENTINEL_STRINGS = frozenset({"__none__", "__untracked__", "__unk__"})


def is_sentinel(value) -> bool:
    return value is None or (isinstance(value, str) and value in SENTINEL_STRINGS)


def feature_rows(decisions):
    return [row["features"] for decision in decisions for row in decision.rows]


def feature_stats(rows: list[dict], feature: str) -> dict:
    values = [row.get(feature) for row in rows]
    counts = Counter(canonical_json(value) for value in values)
    dominant = max(counts.values()) / len(values) if values else 0.0
    sentinel = sum(is_sentinel(value) for value in values)
    numeric = [float(value) for value in values
               if isinstance(value, (int, float)) and not isinstance(value, bool)]
    return {
        "n": len(values), "unique": len(counts), "dominant_rate": dominant,
        "sentinel_rate": sentinel / len(values) if values else 0.0,
        "numeric": bool(numeric) and len(numeric) == len(values),
        "min": min(numeric) if numeric else None, "max": max(numeric) if numeric else None,
    }


def average_ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: (values[index], index))
    ranks = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[end]] == values[order[start]]:
            end += 1
        rank = (start + end - 1) / 2.0
        for position in range(start, end):
            ranks[order[position]] = rank
        start = end
    return ranks


def spearman(left: list[float], right: list[float]) -> float:
    a, b = average_ranks(left), average_ranks(right)
    am, bm = sum(a) / len(a), sum(b) / len(b)
    numerator = sum((x - am) * (y - bm) for x, y in zip(a, b))
    denom = math.sqrt(sum((x - am) ** 2 for x in a) * sum((y - bm) ** 2 for y in b))
    return 0.0 if denom == 0 else numerator / denom
```

`audit_features` erzeugt Findings exakt an den Configschwellen und prüft Denylists/Typen/
Nichtendlichkeit vor Driftberechnung.

- [ ] **Step 4: PSI und Jensen-Shannon implementieren**

```python
def train_quantile_edges(values: list[float], n_bins: int = 10) -> list[float]:
    ordered = sorted(values)
    return sorted(set(quantile(ordered, i / n_bins) for i in range(1, n_bins)))


def histogram(values: list[float], edges: list[float]) -> list[int]:
    counts = [0] * (len(edges) + 1)
    for value in values:
        index = 0
        while index < len(edges) and value > edges[index]:
            index += 1
        counts[index] += 1
    return counts


def psi(reference: list[float], observed: list[float], *, epsilon=1e-6) -> float:
    edges = train_quantile_edges(reference)
    ref = histogram(reference, edges)
    obs = histogram(observed, edges)
    total_ref, total_obs = sum(ref), sum(obs)
    return sum(
        ((r / total_ref + epsilon) - (o / total_obs + epsilon))
        * math.log((r / total_ref + epsilon) / (o / total_obs + epsilon))
        for r, o in zip(ref, obs)
    )


def jensen_shannon(reference, observed, *, epsilon=1e-6) -> float:
    keys = sorted(set(reference) | set(observed), key=str)
    rc, oc = Counter(reference), Counter(observed)
    rp = [(rc[key] + epsilon) / (len(reference) + epsilon * len(keys)) for key in keys]
    op = [(oc[key] + epsilon) / (len(observed) + epsilon * len(keys)) for key in keys]
    mid = [(a + b) / 2 for a, b in zip(rp, op)]
    kl = lambda p, q: sum(a * math.log(a / b, 2) for a, b in zip(p, q))
    return 0.5 * kl(rp, mid) + 0.5 * kl(op, mid)


def feature_warn(code, feature, *, count=1, denominator=None, split=None, evidence=None):
    return make_finding(
        code=code, severity=Severity.WARN, scope="feature", message=code,
        count=count, denominator=denominator, split=split, feature=feature,
        evidence=evidence or {}, remediation="inspect the feature extractor and split distribution",
    )


def audit_features(corpus: AuditCorpus, config: AuditConfig) -> tuple[list[Finding], dict]:
    train_rows = feature_rows(corpus.decisions_by_split["train"])
    features = sorted({name for row in corpus.rows for name in row["features"]})
    findings, metrics = [], {"train": {}, "correlations": [], "drift": {}}
    denied = sorted(set(features) & (LABEL_DENYLIST | METADATA_DENYLIST))
    if denied or not set(features) <= set(FEATURE_COLUMNS):
        findings.append(make_finding(
            code="FEATURE_ALLOWLIST_VIOLATION", severity=Severity.FAIL, scope="feature",
            message="feature payload violates the canonical allowlist", count=len(denied),
            examples=denied, remediation="remove denied or unknown columns before training",
        ))
    numeric_train = {}
    categorical_train = {}
    for feature in features:
        stats = feature_stats(train_rows, feature)
        metrics["train"][feature] = stats
        values = [row.get(feature) for row in train_rows]
        kinds = {"numeric" if isinstance(v, (int, float)) and not isinstance(v, bool)
                 else "categorical" for v in values if not is_sentinel(v)}
        if len(kinds) > 1:
            findings.append(make_finding(
                code="FEATURE_TYPE_MISMATCH", severity=Severity.FAIL, scope="feature",
                message="feature mixes numeric and categorical values", count=len(values),
                feature=feature, remediation="emit one stable type for this feature",
            ))
            continue
        nonfinite = sum(isinstance(v, (int, float)) and not isinstance(v, bool)
                        and not math.isfinite(float(v)) for v in values)
        if nonfinite:
            findings.append(make_finding(
                code="NONFINITE_FEATURE", severity=Severity.FAIL, scope="feature",
                message="feature contains NaN or infinity", count=nonfinite,
                denominator=len(values), feature=feature,
                remediation="fix or reject non-finite extractor output",
            ))
            continue
        if stats["unique"] == 1:
            findings.append(feature_warn("CONSTANT_FEATURE", feature, count=len(values),
                                         denominator=len(values)))
        elif stats["dominant_rate"] >= config.near_constant_rate:
            dominant_count = max(Counter(canonical_json(v) for v in values).values())
            findings.append(feature_warn("NEAR_CONSTANT_FEATURE", feature,
                                         count=dominant_count, denominator=len(values)))
        if stats["sentinel_rate"] >= config.sentinel_warn_rate:
            findings.append(feature_warn("SENTINEL_DOMINATED_FEATURE", feature,
                                         count=sum(is_sentinel(v) for v in values),
                                         denominator=len(values)))
        if kinds == {"numeric"}:
            numeric_train[feature] = [float(v) for v in values
                                      if not is_sentinel(v) and math.isfinite(float(v))]
        else:
            categorical_train[feature] = [canonical_json(v) for v in values]
    for left, right in combinations(sorted(numeric_train), 2):
        pairs = [(float(row[left]), float(row[right])) for row in train_rows
                 if left in row and right in row
                 and not is_sentinel(row[left]) and not is_sentinel(row[right])]
        if len(pairs) < 2:
            continue
        rho = spearman([pair[0] for pair in pairs], [pair[1] for pair in pairs])
        if abs(rho) >= config.spearman_warn_abs:
            findings.append(feature_warn(
                "HIGH_SPEARMAN_CORRELATION", left,
                evidence={"other_feature": right, "rho": rho,
                          "threshold": config.spearman_warn_abs}))
            metrics["correlations"].append({"left": left, "right": right, "rho": rho})
    for split in ("validation", "test"):
        observed_rows = feature_rows(corpus.decisions_by_split[split])
        split_metrics = {}
        metrics["drift"][split] = split_metrics
        if not observed_rows:
            continue
        for feature, reference in sorted(numeric_train.items()):
            observed = [float(row.get(feature)) for row in observed_rows
                        if isinstance(row.get(feature), (int, float))
                        and not isinstance(row.get(feature), bool)
                        and math.isfinite(float(row.get(feature)))]
            if not observed:
                continue
            value_psi = psi(reference, observed, epsilon=config.near_epsilon)
            out_count = sum(v < min(reference) or v > max(reference) for v in observed)
            split_metrics[feature] = {"psi": value_psi,
                                      "out_of_range_rate": out_count / len(observed)}
            if value_psi >= config.psi_warn:
                findings.append(feature_warn("PSI_DRIFT", feature, split=split,
                                             evidence={"psi": value_psi}))
            if out_count / len(observed) > config.out_of_range_warn_rate:
                findings.append(feature_warn("OUT_OF_RANGE_FEATURE", feature, split=split,
                                             count=out_count, denominator=len(observed)))
        for feature, reference in sorted(categorical_train.items()):
            observed = [canonical_json(row.get(feature)) for row in observed_rows]
            value_js = jensen_shannon(reference, observed, epsilon=config.near_epsilon)
            known = set(reference)
            unseen = sum(value not in known for value in observed)
            split_metrics[feature] = {"js": value_js, "unseen_rate": unseen / len(observed)}
            if value_js >= config.js_warn:
                findings.append(feature_warn("JS_DRIFT", feature, split=split,
                                             evidence={"js": value_js}))
            if unseen / len(observed) > config.unseen_warn_rate:
                findings.append(feature_warn("UNSEEN_CATEGORY", feature, split=split,
                                             count=unseen, denominator=len(observed)))
    return findings, metrics
```

Validation/Test liefern keine Bin- oder Kategoriegrenzen. Out-of-range und Unseen-Raten werden gegen
Train berechnet. Die Datei importiert dafür `Counter`/`combinations`, die Verträge und die bestehenden
Feature-Allow-/Denylists explizit.

- [ ] **Step 5: Tests grün ausführen und committen**

```powershell
python -m pytest tests/test_audit_features.py tests/test_reranker_ablation.py -q
```

Expected: PASS.

```powershell
git add showdown_bot/src/showdown_bot/learning/audit/features.py showdown_bot/tests/test_audit_features.py
git commit -m "feat(audit): measure feature health correlation and drift"
```

---

### Task 6: Teamkatalog, Coverage und OOD-Score implementieren

**Files:**

- Create: `showdown_bot/src/showdown_bot/learning/audit/distribution.py`
- Create: `showdown_bot/tests/test_audit_distribution.py`

- [ ] **Step 1: Failing Team-/Coverage-/OOD-Tests schreiben**

```python
def _write_catalog(tmp_path, rows):
    path = tmp_path / "teams.json"
    path.write_text(json.dumps(rows), encoding="utf-8")
    return path


def _distribution_corpus(train_features, test_features=(), team_hashes=None):
    team_hashes = team_hashes or ["known"] * (len(train_features) + len(test_features))
    decisions = []
    for index, features in enumerate(list(train_features) + list(test_features)):
        split = "train" if index < len(train_features) else "test"
        row = {"features": features,
               "metadata": {"candidate_index": 0, "team_hash": team_hashes[index],
                            "game_id": f"g{index}", "decision_id": f"d{index}",
                            "teacher_config": {"trainable_label": True}},
               "label": {"teacher_best": True, "chosen_by_current_heuristic": True}}
        decisions.append((split, Decision(f"g{index}", f"d{index}", [row])))
    return AuditCorpus(
        dataset_name="fixture", dataset_sha256="a" * 64,
        rows=tuple(row for _s, d in decisions for row in d.rows),
        decisions=tuple(d for _s, d in decisions),
        split_by_game={d.game_id: split for split, d in decisions},
        decisions_by_split={
            name: tuple(d for split, d in decisions if split == name)
            for name in ("train", "validation", "test")}, split_manifest={})


def test_team_catalog_is_strict_and_partial_coverage_warns(tmp_path):
    catalog = _write_catalog(tmp_path, [{
        "team_hash": "known", "team_id": "rain-1", "archetype": "rain", "declared_split": "train",
    }])
    corpus = _distribution_corpus([{"x": 0.0}, {"x": 1.0}], team_hashes=["known", "unknown"])
    teams, findings = load_team_catalog(catalog), audit_team_coverage(corpus, load_team_catalog(catalog))
    assert teams["known"].archetype == "rain"
    assert any(f.code == "UNKNOWN_TEAM_HASH" and f.severity == Severity.WARN for f in findings)


def test_ood_score_components_and_threshold():
    corpus = _distribution_corpus(
        [{"numeric": 0.0, "category": "seen", "maybe": 1.0}],
        [{"numeric": 100.0, "category": "unseen", "maybe": None}],
    )
    scores, findings, metrics = audit_ood(corpus, AuditConfig(ood_threshold=0.5))
    assert any(score >= 0.5 for score in scores["test"].values())
    assert any(f.code == "OOD_DECISIONS" for f in findings)
    assert metrics["test"]["ood_rate"] > 0
```

```python
def test_catalog_rejects_unknown_fields_and_conflicting_hash(tmp_path):
    unknown = _write_catalog(tmp_path, [{
        "team_hash": "h", "team_id": "id", "archetype": "rain",
        "declared_split": "train", "extra": True,
    }])
    with pytest.raises(AuditError, match="fields mismatch"):
        load_team_catalog(unknown)
    conflicting = _write_catalog(tmp_path, [
        {"team_hash": "h", "team_id": "a", "archetype": "rain", "declared_split": "train"},
        {"team_hash": "h", "team_id": "b", "archetype": "sun", "declared_split": "train"},
    ])
    with pytest.raises(AuditError, match="conflicting team hash"):
        load_team_catalog(conflicting)


def test_missing_catalog_and_small_action_bucket_are_reported():
    corpus = _distribution_corpus([{"slot1_action_type": "move",
                                    "slot2_action_type": "move"}])
    findings, metrics, _scores = audit_distribution(corpus, AuditConfig(), team_catalog=None)
    assert metrics["coverage"]["train"]["teams"] == "unavailable"
    assert {f.code for f in findings} >= {"TEAM_CATALOG_UNAVAILABLE", "SINGLE_ACTION_CLASS",
                                          "SMALL_ACTION_BUCKET"}
```

- [ ] **Step 2: Tests rot ausführen**

```powershell
python -m pytest tests/test_audit_distribution.py -q
```

Expected: FAIL.

- [ ] **Step 3: Teamkatalog und Coverage implementieren**

```python
@dataclass(frozen=True)
class TeamInfo:
    team_hash: str
    team_id: str
    archetype: str
    declared_split: str


def load_team_catalog(path) -> dict[str, TeamInfo]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise AuditError("team catalog must be a list")
    allowed = {"team_hash", "team_id", "archetype", "declared_split"}
    out = {}
    for index, item in enumerate(data):
        if set(item) != allowed:
            raise AuditError(f"team catalog row {index} fields mismatch")
        info = TeamInfo(**{key: str(item[key]) for key in allowed})
        if info.team_hash in out and out[info.team_hash] != info:
            raise AuditError(f"conflicting team hash {info.team_hash}")
        out[info.team_hash] = info
    return {key: out[key] for key in sorted(out)}


def row_action_class(row) -> str:
    return action_class(row)


def audit_team_coverage(corpus, team_catalog) -> list[Finding]:
    if team_catalog is None:
        return [make_finding(
            code="TEAM_CATALOG_UNAVAILABLE", severity=Severity.INFO, scope="team",
            message="team and archetype coverage is unavailable", remediation="provide --team-catalog",
        )]
    game_team = {}
    for decision in corpus.decisions:
        team_hash = str(decision.rows[0]["metadata"].get("team_hash", ""))
        game_team.setdefault(decision.game_id, team_hash)
        if game_team[decision.game_id] != team_hash:
            raise AuditError(f"game {decision.game_id} has conflicting team hashes")
    unknown = sorted(game for game, team_hash in game_team.items() if team_hash not in team_catalog)
    findings = []
    if unknown:
        findings.append(make_finding(
            code="UNKNOWN_TEAM_HASH", severity=Severity.WARN, scope="team",
            message="games reference hashes absent from the team catalog", count=len(unknown),
            denominator=len(game_team), examples=unknown,
            remediation="extend the catalog or document intentionally unknown teams",
        ))
    return findings
```

Coverage zählt Games, Decisions, Rows, Kandidatenzahl, gewählte `action_class`, Game-Mode,
Turn-Bucket, Format, Config, Teacher-Version, Team und Archetyp pro Split. Gamebasierte Team-/
Archetypcounts deduplizieren über `game_id`.

- [ ] **Step 4: Decision-OOD-Score implementieren**

```python
def train_reference(train_decisions) -> dict:
    rows = feature_rows(train_decisions)
    numeric, categorical = {}, {}
    for feature in sorted({name for row in rows for name in row}):
        values = [row.get(feature) for row in rows]
        present = [value for value in values if not is_sentinel(value)]
        if present and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in present):
            xs = [float(v) for v in present]
            median = quantile(sorted(xs), 0.5)
            q1, q3 = quantile(sorted(xs), 0.25), quantile(sorted(xs), 0.75)
            numeric[feature] = {"min": min(xs), "max": max(xs), "median": median,
                                "scale": q3 - q1 if q3 > q1 else max(abs(median), 1.0)}
        else:
            categorical[feature] = {canonical_json(v) for v in present}
    return {"numeric": numeric, "categorical": categorical}


def decision_ood_score(decision, reference) -> tuple[float, dict]:
    row_components, row_feature_contributions = [], []
    for row in decision.rows:
        unseen, out_range, distance, missing = [], [], [], []
        feature_contributions = defaultdict(float)
        for feature in sorted(set(reference["numeric"]) | set(reference["categorical"])):
            value = row["features"].get(feature)
            if is_sentinel(value):
                is_missing = 1.0
                missing.append(is_missing)
                feature_contributions[feature] += is_missing / 4.0
                continue
            if feature in reference["numeric"] and isinstance(value, (int, float)):
                ref = reference["numeric"][feature]
                outside = float(value < ref["min"] or value > ref["max"])
                numeric_distance = min(abs(float(value) - ref["median"]) / ref["scale"], 10.0) / 10.0
                out_range.append(outside)
                distance.append(numeric_distance)
                feature_contributions[feature] += (outside + numeric_distance) / 4.0
            elif feature in reference["categorical"]:
                is_unseen = float(canonical_json(value) not in reference["categorical"][feature])
                unseen.append(is_unseen)
                feature_contributions[feature] += is_unseen / 4.0
            missing.append(0.0)
        mean = lambda xs: sum(xs) / len(xs) if xs else 0.0
        components = {"unseen": mean(unseen), "out_of_range": mean(out_range),
                      "numeric_distance": mean(distance), "missing": mean(missing)}
        row_components.append(components)
        row_feature_contributions.append(feature_contributions)
    merged = {key: sum(row[key] for row in row_components) / len(row_components)
              for key in ("unseen", "out_of_range", "numeric_distance", "missing")}
    feature_totals = {
        feature: sum(row.get(feature, 0.0) for row in row_feature_contributions)
                 / len(row_feature_contributions)
        for feature in sorted({key for row in row_feature_contributions for key in row})
    }
    top_features = sorted(feature_totals.items(), key=lambda item: (-item[1], item[0]))[:20]
    return sum(merged.values()) / 4.0, {
        "components": merged,
        "top_features": [{"feature": feature, "contribution": value}
                         for feature, value in top_features],
    }


def coverage_metrics(corpus, team_catalog) -> dict:
    result = {}
    for split in ("train", "validation", "test"):
        decisions = corpus.decisions_by_split[split]
        games = sorted({decision.game_id for decision in decisions})
        rows = [row for decision in decisions for row in decision.rows]
        action_games, mode_games, turn_games = defaultdict(set), defaultdict(set), defaultdict(set)
        format_games, config_games, teacher_games = defaultdict(set), defaultdict(set), defaultdict(set)
        for decision in decisions:
            for row in decision.rows:
                action_games[row_action_class(row)].add(decision.game_id)
                mode_games[str(row["features"].get("game_mode", "unknown"))].add(decision.game_id)
                turn = int(row["metadata"].get("turn", 0) or 0)
                turn_games["1-3" if turn <= 3 else "4-6" if turn <= 6 else "7+"].add(decision.game_id)
                format_games[str(row["metadata"].get("format_id", "unknown"))].add(decision.game_id)
                config_games[str(row["metadata"].get("config_hash", "unknown"))].add(decision.game_id)
                teacher_games[str(row["metadata"].get("teacher_version", "unknown"))].add(decision.game_id)
        teams = Counter()
        archetypes = Counter()
        for game_id in games:
            decision = next(d for d in decisions if d.game_id == game_id)
            team_hash = str(decision.rows[0]["metadata"].get("team_hash", ""))
            teams[team_hash] += 1
            if team_catalog and team_hash in team_catalog:
                archetypes[team_catalog[team_hash].archetype] += 1
        result[split] = {
            "games": len(games), "decisions": len(decisions), "rows": len(rows),
            "candidate_count": dict(sorted(Counter(len(d.rows) for d in decisions).items())),
            "action_classes": {key: len(value) for key, value in sorted(action_games.items())},
            "game_modes": {key: len(value) for key, value in sorted(mode_games.items())},
            "turn_buckets": {key: len(value) for key, value in sorted(turn_games.items())},
            "formats": {key: len(value) for key, value in sorted(format_games.items())},
            "config_hashes": {key: len(value) for key, value in sorted(config_games.items())},
            "teacher_versions": {key: len(value) for key, value in sorted(teacher_games.items())},
            "decision_flags": {
                "trainable": sum(bool(d.rows[0]["metadata"]["teacher_config"]["trainable_label"])
                                 for d in decisions),
                "non_trainable": sum(not bool(d.rows[0]["metadata"]["teacher_config"]["trainable_label"])
                                     for d in decisions),
                "strict_unique": sum(
                    len(d.rows) > 1
                    and sum(bool(r["label"]["teacher_best"]) for r in d.rows) == 1
                    and sum(bool(r["label"]["chosen_by_current_heuristic"]) for r in d.rows) == 1
                    for d in decisions),
                "tie": sum(sum(bool(r["label"]["teacher_best"]) for r in d.rows) > 1
                           for d in decisions),
                "forced": sum(len(d.rows) == 1 for d in decisions),
                "multi_candidate": sum(len(d.rows) > 1 for d in decisions),
            },
            "teams": dict(sorted(teams.items())) if team_catalog else "unavailable",
            "archetypes": dict(sorted(archetypes.items())) if team_catalog else "unavailable",
        }
    return result


def audit_ood(corpus, config: AuditConfig):
    train = corpus.decisions_by_split["train"]
    if not train:
        finding = make_finding(
            code="OOD_TRAIN_SPLIT_EMPTY", severity=Severity.FAIL, scope="ood",
            message="OOD reference cannot be fit without train decisions",
            remediation="provide a non-empty gamewise train split",
        )
        return {}, [finding], {"status": "unavailable"}
    reference = train_reference(train)
    scores, findings, metrics = {}, [], {}
    for split in ("validation", "test"):
        split_scores, components = {}, {}
        for decision in corpus.decisions_by_split[split]:
            score, detail = decision_ood_score(decision, reference)
            split_scores[decision.decision_id] = score
            components[decision.decision_id] = detail
        scores[split] = dict(sorted(split_scores.items()))
        ordered = sorted(split_scores.values())
        ood_ids = sorted(key for key, score in split_scores.items()
                         if score >= config.ood_threshold)
        metrics[split] = {
            "n": len(ordered),
            "ood_rate": len(ood_ids) / len(ordered) if ordered else 0.0,
            "quantiles": ({str(q): quantile(ordered, q) for q in (0.5, 0.9, 0.95, 1.0)}
                          if ordered else {}),
            "components": components,
        }
        if ood_ids:
            findings.append(make_finding(
                code="OOD_DECISIONS", severity=Severity.WARN, scope="ood",
                message="decision OOD score meets or exceeds the configured threshold",
                count=len(ood_ids), denominator=len(ordered), split=split, examples=ood_ids,
                evidence={"threshold": config.ood_threshold},
                remediation="inspect the highest component contributions before trusting metrics",
            ))
    return scores, findings, metrics


def audit_distribution(corpus, config, *, team_catalog=None, reference_paths=()):
    findings = audit_team_coverage(corpus, team_catalog)
    coverage = coverage_metrics(corpus, team_catalog)
    scores, ood_findings, ood_metrics = audit_ood(corpus, config)
    findings.extend(ood_findings)
    for split, values in coverage.items():
        if len(values["action_classes"]) < 2 and values["decisions"]:
            findings.append(make_finding(
                code="SINGLE_ACTION_CLASS", severity=Severity.WARN, scope="split",
                message="split contains fewer than two action classes", split=split,
                count=values["decisions"], remediation="expand the game panel",
            ))
        dimensions = {"ACTION": values["action_classes"]}
        if team_catalog:
            dimensions.update({"TEAM": values["teams"], "ARCHETYPE": values["archetypes"]})
        for dimension, buckets in dimensions.items():
            for bucket, games in sorted(buckets.items()):
                if games < config.small_bucket_games:
                    findings.append(make_finding(
                        code=f"SMALL_{dimension}_BUCKET", severity=Severity.WARN, scope="split",
                        message=f"{dimension.lower()} bucket is underpowered", split=split,
                        count=games, examples=[bucket],
                        evidence={"minimum_games": config.small_bucket_games},
                        remediation="add independent games for this bucket",
                    ))
    train_games = max(coverage["train"]["games"], 1)
    for split in ("validation", "test"):
        split_games = max(coverage[split]["games"], 1)
        dimensions = {"action_classes": coverage[split]["action_classes"]}
        if team_catalog:
            dimensions["archetypes"] = coverage[split]["archetypes"]
        for dimension, observed in dimensions.items():
            reference = coverage["train"][dimension]
            for bucket in sorted(set(reference) | set(observed)):
                delta = observed.get(bucket, 0) / split_games - reference.get(bucket, 0) / train_games
                if abs(delta) >= config.share_shift_warn:
                    findings.append(make_finding(
                        code="BUCKET_SHARE_SHIFT", severity=Severity.WARN, scope="split",
                        message="bucket share differs from train by at least the threshold",
                        split=split, examples=[f"{dimension}:{bucket}"],
                        evidence={"delta": delta, "threshold": config.share_shift_warn},
                        remediation="inspect whether the split represents the intended population",
                    ))
    reference_metrics = {}
    for path in sorted(map(Path, reference_paths), key=str):
        external, external_findings = load_and_audit_integrity(path, config)
        findings.extend(external_findings)
        external_scores = []
        reference = train_reference(corpus.decisions_by_split["train"])
        for decision in external.decisions:
            score, _detail = decision_ood_score(decision, reference)
            external_scores.append(score)
        reference_metrics[path.name] = {
            "n": len(external_scores),
            "ood_rate": (sum(score >= config.ood_threshold for score in external_scores)
                         / len(external_scores) if external_scores else 0.0),
        }
    return findings, {"coverage": coverage, "ood": ood_metrics,
                      "references": reference_metrics}, scores
```

`audit_ood` fittet ausschließlich auf Train und bewertet Validation/Test; externe Referenzen werden
mit derselben Trainreferenz bewertet. `score >= config.ood_threshold` zählt als OOD. Alle Coverage-
Buckets werden aus deduplizierten Game-IDs berechnet.

- [ ] **Step 5: Tests grün ausführen und committen**

```powershell
python -m pytest tests/test_audit_distribution.py tests/test_dataset.py -q
```

Expected: PASS.

```powershell
git add showdown_bot/src/showdown_bot/learning/audit/distribution.py showdown_bot/tests/test_audit_distribution.py
git commit -m "feat(audit): report coverage teams and out-of-distribution data"
```

---

### Task 7: Modellmanifest, Predictions und Kalibrierung auditieren

**Files:**

- Create: `showdown_bot/src/showdown_bot/learning/audit/model.py`
- Create: `showdown_bot/tests/test_audit_model.py`

- [ ] **Step 1: Failing Manifest-/Predictiontests schreiben**

```python
class StubModel:
    def __init__(self, feature_names, predictions):
        self._feature_names = list(feature_names)
        self.predictions = list(predictions)

    def feature_name(self):
        return list(self._feature_names)

    def predict(self, matrix):
        return list(self.predictions)


def _model_fixture():
    rows = []
    for index, score in enumerate((1.0, 0.0)):
        features = {key: 0.0 for key in FEATURE_COLUMNS}
        features["heuristic_aggregate_score"] = score
        rows.append({
            "features": features,
            "metadata": {"game_id": "g", "decision_id": "d", "candidate_index": index},
            "label": {"teacher_best": index == 0, "value_gap_to_best": -float(index),
                      "chosen_by_current_heuristic": index == 0},
        })
    decision = Decision("g", "d", rows)
    corpus = AuditCorpus(
        dataset_name="fixture", dataset_sha256="a" * 64,
        rows=tuple(decision.rows), decisions=(decision,),
        split_by_game={"g": "test"},
        decisions_by_split={"train": (decision,), "validation": (decision,), "test": (decision,)},
        split_manifest={})
    features = ["heuristic_aggregate_score"]
    model = StubModel(features, [1.0, 0.0])
    manifest = {
        "dataset_sha256": corpus.dataset_sha256,
        "feature_schema_hash": feature_schema_hash(features, []),
        "training_config_hash": "a" * 16, "model_type": "lightgbm-lambdarank",
        "split_seed": 42, "metrics_summary": {}, "git_sha": "a" * 40,
        "eval_report_path": "reports/test.md", "feature_names": features,
        "categorical_feature_names": [], "categorical_encodings": {},
        "dropped_constant_columns": sorted(
            feature for feature in FEATURE_COLUMNS
            if feature not in features and feature not in (LABEL_DENYLIST | METADATA_DENYLIST)),
        "denied_columns_checked": sorted(LABEL_DENYLIST | METADATA_DENYLIST),
        "training_decision_filter": "fixture",
    }
    return corpus, model, manifest


def test_manifest_mismatches_are_fail():
    corpus, model, manifest = _model_fixture()
    manifest["dataset_sha256"] = "0" * 64
    findings, _metrics = audit_model_artifacts(corpus, model, manifest, AuditConfig())
    assert any(f.code == "MODEL_DATASET_HASH_MISMATCH" and f.severity == Severity.FAIL
               for f in findings)


def test_predictions_must_be_deterministic_and_finite():
    corpus, model, manifest = _model_fixture()
    model.predictions = [float("nan"), 0.0]
    findings, _metrics = audit_model_artifacts(corpus, model, manifest, AuditConfig())
    assert any(f.code == "MODEL_NONFINITE_PREDICTION" for f in findings)
```

```python
@pytest.mark.parametrize(("mutation", "code"), [
    (lambda _model, manifest: manifest.update(feature_schema_hash="bad"),
     "MODEL_FEATURE_SCHEMA_MISMATCH"),
    (lambda model, _manifest: setattr(model, "_feature_names", ["different"]),
     "MODEL_FEATURE_ORDER_MISMATCH"),
    (lambda _model, manifest: manifest.update(categorical_encodings={"x": {"seen": 1}}),
     "MODEL_ENCODING_INVALID"),
    (lambda _model, manifest: manifest.update(dropped_constant_columns=[]),
     "MODEL_DROPPED_CONSTANT_MISMATCH"),
])
def test_manifest_contract_failures(mutation, code):
    corpus, model, manifest = _model_fixture()
    mutation(model, manifest)
    findings, _metrics = audit_model_artifacts(corpus, model, manifest, AuditConfig())
    assert any(f.code == code and f.severity == Severity.FAIL for f in findings)


def test_only_one_model_artifact_is_fail(tmp_path):
    corpus, _model, _manifest = _model_fixture()
    findings, metrics = audit_optional_model(
        corpus, AuditConfig(), tmp_path / "model.txt", None, {})
    assert metrics["status"] == "unavailable"
    assert findings[0].code == "MODEL_ARTIFACT_PAIR_MISSING"
```

- [ ] **Step 2: Failing Kalibrierungstests schreiben**

```python
def test_temperature_uses_validation_only():
    validation = [{"scores": [2.0, 0.0], "teacher_best": [True, False],
                   "game_id": "g", "decision_id": "d"}]
    seen = []
    temperature = fit_temperature(validation, observer=seen.append)
    assert temperature > 0
    assert seen and all(item["split"] == "validation" for item in seen)


def test_calibration_metrics_handle_teacher_ties():
    scored = [{"scores": [2.0, 2.0, 0.0], "teacher_best": [True, True, False],
               "game_id": "g", "decision_id": "d"}]
    metrics = calibration_metrics(scored, temperature=1.0)
    assert metrics["n"] == 1
    assert math.isfinite(metrics["nll"])
    assert math.isfinite(metrics["brier"])
```

ECE-Test mit 10 quantilen Bins, stabilem ID-Tiebreak, `ECE > 0.10`-Warn und Test-N<100-Warn.

- [ ] **Step 3: Tests rot ausführen**

```powershell
python -m pytest tests/test_audit_model.py -q
```

Expected: FAIL.

- [ ] **Step 4: Manifest und Modellprüfung implementieren**

```python
REQUIRED_MANIFEST_KEYS = frozenset({
    "dataset_sha256", "feature_schema_hash", "training_config_hash", "model_type",
    "split_seed", "metrics_summary", "git_sha", "eval_report_path", "feature_names",
    "categorical_feature_names", "categorical_encodings", "dropped_constant_columns",
    "denied_columns_checked", "training_decision_filter",
})


def model_fail(code: str, examples) -> Finding:
    return make_finding(
        code=code, severity=Severity.FAIL, scope="model", message=code,
        count=max(1, len(examples)), examples=examples,
        remediation="rebuild model and manifest from the audited dataset",
    )


def model_warn(code: str, examples, evidence=None) -> Finding:
    return make_finding(
        code=code, severity=Severity.WARN, scope="model", message=code,
        count=max(1, len(examples)), examples=examples, evidence=evidence or {},
        remediation="inspect the historical evaluation provenance",
    )


def validate_manifest(corpus, model, manifest, train_decisions, manifest_base=None) -> list[Finding]:
    findings = []
    missing = REQUIRED_MANIFEST_KEYS - set(manifest)
    if missing:
        findings.append(model_fail("MODEL_MANIFEST_MISSING_KEYS", sorted(missing)))
        return findings
    if manifest["dataset_sha256"] != corpus.dataset_sha256:
        findings.append(model_fail("MODEL_DATASET_HASH_MISMATCH", []))
    if manifest["model_type"] != "lightgbm-lambdarank":
        findings.append(model_fail("MODEL_TYPE_MISMATCH", [manifest["model_type"]]))
    config_hash = str(manifest["training_config_hash"])
    if len(config_hash) < 16 or any(char not in "0123456789abcdef" for char in config_hash.lower()):
        findings.append(model_fail("MODEL_TRAINING_CONFIG_HASH_INVALID", [config_hash]))
    if not isinstance(manifest["metrics_summary"], dict):
        findings.append(model_fail("MODEL_METRICS_SUMMARY_INVALID", []))
    features = list(manifest["feature_names"])
    denied = set(features) & (LABEL_DENYLIST | METADATA_DENYLIST)
    if denied or not set(features) <= set(FEATURE_COLUMNS):
        findings.append(model_fail("MODEL_FEATURE_ALLOWLIST_MISMATCH", sorted(denied)))
    expected_hash = feature_schema_hash(features, manifest["categorical_feature_names"])
    if expected_hash != manifest["feature_schema_hash"]:
        findings.append(model_fail("MODEL_FEATURE_SCHEMA_MISMATCH", []))
    if list(model.feature_name()) != features:
        findings.append(model_fail("MODEL_FEATURE_ORDER_MISMATCH", []))
    encodings = manifest["categorical_encodings"]
    categoricals = list(manifest["categorical_feature_names"])
    train_feature_names = {name for decision in train_decisions
                           for row in decision.rows for name in row["features"]}
    if not set(features) <= train_feature_names:
        findings.append(model_fail("MODEL_FEATURE_MISSING_FROM_TRAIN",
                                   sorted(set(features) - train_feature_names)))
    encoding_invalid = set(encodings) != set(categoricals)
    for mapping in encodings.values():
        codes = list(mapping.values()) if isinstance(mapping, dict) else []
        encoding_invalid |= (
            not isinstance(mapping, dict) or mapping.get("__unk__") != 0
            or any(not isinstance(code, int) or code < 0 for code in codes)
            or len(codes) != len(set(codes))
        )
    if encoding_invalid or not set(categoricals) <= set(features):
        findings.append(model_fail("MODEL_ENCODING_INVALID", []))
    expected_denied = sorted(LABEL_DENYLIST | METADATA_DENYLIST)
    if sorted(manifest["denied_columns_checked"]) != expected_denied:
        findings.append(model_fail("MODEL_DENYLIST_ATTESTATION_MISMATCH", []))
    active = set(active_feature_names(train_decisions))
    actual_dropped = sorted(
        feature for feature in FEATURE_COLUMNS
        if feature not in active and feature not in (LABEL_DENYLIST | METADATA_DENYLIST))
    if sorted(manifest["dropped_constant_columns"]) != actual_dropped:
        findings.append(model_fail("MODEL_DROPPED_CONSTANT_MISMATCH", actual_dropped))
    if manifest_base is not None:
        report_path = Path(manifest_base) / manifest["eval_report_path"]
        if not report_path.exists():
            finding = (model_fail("MODEL_EVAL_REPORT_MISSING_WITH_HASH", [str(report_path)])
                       if "eval_report_sha256" in manifest
                       else model_warn("MODEL_EVAL_REPORT_MISSING", [str(report_path)]))
            findings.append(finding)
        elif "eval_report_sha256" in manifest:
            actual_hash = hashlib.sha256(report_path.read_bytes()).hexdigest()
            if actual_hash != manifest["eval_report_sha256"]:
                findings.append(model_fail("MODEL_EVAL_REPORT_HASH_MISMATCH", [str(report_path)]))
    return findings


def audit_model_artifacts(corpus, model, manifest, config: AuditConfig, manifest_base=None):
    findings = validate_manifest(
        corpus, model, manifest, corpus.decisions_by_split["train"], manifest_base)
    if any(f.severity == Severity.FAIL for f in findings):
        return findings, {"status": "not_scored_due_to_manifest_failure"}
    matrix = build_feature_matrix(
        corpus.decisions, feature_names=manifest["feature_names"],
        encodings=manifest["categorical_encodings"])
    first = list(model.predict(np.asarray(matrix.X, dtype=float)))
    second = list(model.predict(np.asarray(matrix.X, dtype=float)))
    if first != second:
        findings.append(model_fail("MODEL_NONDETERMINISTIC_PREDICTION", []))
    if len(first) != len(matrix.X):
        findings.append(model_fail("MODEL_PREDICTION_COUNT_MISMATCH", []))
    if any(not math.isfinite(float(value)) for value in first):
        findings.append(model_fail("MODEL_NONFINITE_PREDICTION", []))
    return findings, {"prediction_count": len(first), "deterministic": first == second}
```

Scoring nutzt `build_feature_matrix` mit Manifestfeatureliste und Trainingsencodings. Derselbe Matrix-
Input wird zweimal vorhergesagt; Listen müssen exakt gleich, endlich und gruppenlängenkonsistent sein.

- [ ] **Step 5: Softmax, Temperatur und Metriken implementieren**

```python
def softmax(scores: list[float], temperature: float) -> list[float]:
    if temperature <= 0 or not math.isfinite(temperature):
        raise AuditError("temperature must be finite and positive")
    scaled = [score / temperature for score in scores]
    maximum = max(scaled)
    exp = [math.exp(value - maximum) for value in scaled]
    total = sum(exp)
    return [value / total for value in exp]


def decision_nll(item, temperature: float) -> float:
    probs = softmax(item["scores"], temperature)
    best = [i for i, flag in enumerate(item["teacher_best"]) if flag]
    target = 1.0 / len(best)
    return -sum(target * math.log(max(probs[i], 1e-15)) for i in best)


def fit_temperature(validation_items, observer=None) -> float:
    left, right = -5.0, 5.0
    phi = (1 + math.sqrt(5)) / 2
    objective = lambda log_t: sum(decision_nll(item, math.exp(log_t))
                                  for item in validation_items) / len(validation_items)
    for _ in range(80):
        c = right - (right - left) / phi
        d = left + (right - left) / phi
        if observer is not None:
            observer({"split": "validation", "c": c, "d": d})
        if objective(c) <= objective(d):
            right = d
        else:
            left = c
    return math.exp((left + right) / 2)
```

`calibration_metrics` berechnet auf Test: Topset-Accuracy, Mean Regret, NDCG@1/@2, NLL,
multiclass Brier und ECE. Für ECE sortiert es `(confidence, game_id, decision_id)`, teilt mit
`numpy.array_split` in höchstens 10 möglichst gleich häufige Bins und summiert
`len(bin)/N * abs(mean_confidence - mean_accuracy)`. Teacher-Tie-Ziel ist gleichverteilt.

Verbindliche Implementierung der probabilistischen Metriken:

```python
def calibration_metrics(items, temperature: float) -> dict:
    if not items:
        raise AuditError("calibration_metrics requires decisions")
    records, nlls, briers, regrets, ndcg1, ndcg2 = [], [], [], [], [], []
    for item in items:
        probs = softmax(item["scores"], temperature)
        best = [i for i, flag in enumerate(item["teacher_best"]) if flag]
        target = [1.0 / len(best) if i in best else 0.0 for i in range(len(probs))]
        prediction = max(range(len(probs)), key=lambda i: (probs[i], -i))
        correct = float(prediction in best)
        confidence = probs[prediction]
        gaps = [float(value) for value in item.get(
            "value_gap_to_best", [0.0 if flag else -1.0 for flag in item["teacher_best"]])]
        regrets.append(-gaps[prediction])
        relevance = [math.exp(value) for value in gaps]
        ideal = sorted(relevance, reverse=True)
        order = sorted(range(len(probs)), key=lambda i: (-probs[i], i))
        def ndcg_at(k):
            dcg = sum(relevance[index] / math.log2(position + 2)
                      for position, index in enumerate(order[:k]))
            idcg = sum(value / math.log2(position + 2)
                       for position, value in enumerate(ideal[:k]))
            return dcg / idcg if idcg else 1.0
        ndcg1.append(ndcg_at(1))
        ndcg2.append(ndcg_at(2))
        nlls.append(-sum(t * math.log(max(p, 1e-15)) for p, t in zip(probs, target)))
        briers.append(sum((p - t) ** 2 for p, t in zip(probs, target)) / len(probs))
        ordered_probs = sorted(probs, reverse=True)
        margin = ordered_probs[0] - ordered_probs[1] if len(ordered_probs) > 1 else 1.0
        records.append((confidence, item["game_id"], item["decision_id"], correct,
                        -gaps[prediction], margin))
    records.sort(key=lambda row: (row[0], row[1], row[2]))
    bins = [list(chunk) for chunk in np.array_split(np.array(records, dtype=object), min(10, len(records)))
            if len(chunk)]
    ece = 0.0
    bin_rows = []
    for bucket in bins:
        confidence = sum(float(row[0]) for row in bucket) / len(bucket)
        accuracy = sum(float(row[3]) for row in bucket) / len(bucket)
        mean_regret = sum(float(row[4]) for row in bucket) / len(bucket)
        mean_top_margin = sum(float(row[5]) for row in bucket) / len(bucket)
        ece += len(bucket) / len(records) * abs(confidence - accuracy)
        bin_rows.append({"n": len(bucket), "confidence": confidence, "accuracy": accuracy,
                         "mean_regret": mean_regret, "mean_top_margin": mean_top_margin})
    return {
        "n": len(records),
        "topset_accuracy": sum(row[3] for row in records) / len(records),
        "mean_regret": sum(regrets) / len(regrets),
        "ndcg_at_1": sum(ndcg1) / len(ndcg1),
        "ndcg_at_2": sum(ndcg2) / len(ndcg2),
        "nll": sum(nlls) / len(nlls), "brier": sum(briers) / len(briers),
        "ece": ece, "bins": bin_rows,
    }


def score_split(model, manifest, decisions, split: str) -> list[dict]:
    items = []
    for decision in decisions:
        matrix = build_feature_matrix(
            (decision,), feature_names=manifest["feature_names"],
            encodings=manifest["categorical_encodings"])
        scores = [float(value) for value in model.predict(np.asarray(matrix.X, dtype=float))]
        items.append({
            "split": split, "game_id": decision.game_id, "decision_id": decision.decision_id,
            "scores": scores,
            "teacher_best": [bool(row["label"]["teacher_best"]) for row in decision.rows],
            "value_gap_to_best": [float(row["label"]["value_gap_to_best"])
                                  for row in decision.rows],
        })
    return items


def audit_optional_model(corpus, config, model_path, manifest_path, ood_scores):
    if model_path is None and manifest_path is None:
        return [], {"status": "not_requested"}
    if model_path is None or manifest_path is None:
        return [model_fail("MODEL_ARTIFACT_PAIR_MISSING", [])], {"status": "unavailable"}
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    import lightgbm as lgb
    model = lgb.Booster(model_file=str(model_path))
    findings, artifact_metrics = audit_model_artifacts(
        corpus, model, manifest, config, Path(manifest_path).parent)
    if any(f.severity == Severity.FAIL for f in findings):
        return findings, {"artifacts": artifact_metrics, "calibration": "not_run"}
    validation = score_split(model, manifest, corpus.decisions_by_split["validation"], "validation")
    test = score_split(model, manifest, corpus.decisions_by_split["test"], "test")
    if not validation or not test:
        findings.append(model_fail("CALIBRATION_SPLIT_EMPTY", []))
        return findings, {"artifacts": artifact_metrics, "calibration": "not_run"}
    temperature = fit_temperature(validation)
    test_metrics = calibration_metrics(test, temperature)
    if test_metrics["ece"] > config.ece_warn:
        findings.append(make_finding(
            code="ECE_HIGH", severity=Severity.WARN, scope="calibration",
            message="test ECE exceeds the configured threshold", count=len(test),
            evidence={"ece": test_metrics["ece"], "threshold": config.ece_warn},
            remediation="inspect calibration; fit temperature on validation only",
        ))
    if len(test) < config.calibration_small_n:
        findings.append(make_finding(
            code="CALIBRATION_SMALL_N", severity=Severity.WARN, scope="calibration",
            message="test calibration sample is underpowered", count=len(test),
            evidence={"minimum": config.calibration_small_n},
            remediation="collect more independent test decisions",
        ))
    strata = {}
    for name, keep_ood in (("id", False), ("ood", True)):
        subset = [item for item in test
                  if (ood_scores.get("test", {}).get(item["decision_id"], 0.0)
                      >= config.ood_threshold) == keep_ood]
        strata[name] = (calibration_metrics(subset, temperature) if subset
                        else {"n": 0, "underpowered": True})
        if 0 < len(subset) < config.small_bucket_games:
            strata[name]["underpowered"] = True
    performance_effect = None
    if strata["id"].get("n", 0) >= config.small_bucket_games and \
            strata["ood"].get("n", 0) >= config.small_bucket_games:
        performance_effect = {
            "topset_accuracy_delta_ood_minus_id": (
                strata["ood"]["topset_accuracy"] - strata["id"]["topset_accuracy"]),
            "mean_regret_delta_ood_minus_id": (
                strata["ood"]["mean_regret"] - strata["id"]["mean_regret"]),
        }
    return findings, {
        "artifacts": artifact_metrics, "temperature": temperature,
        "test": test_metrics, "test_by_ood": strata,
        "ood_performance_effect": performance_effect,
    }
```

Leere Validation oder Test erzeugt `CALIBRATION_SPLIT_EMPTY`/FAIL statt Division durch null.
`audit_optional_model` berichtet dieselben Leistungsmetriken getrennt für ID/OOD anhand der in Task 6
gelieferten Decision-Scores; Gruppen unter 10 werden als unterpowert markiert.

- [ ] **Step 6: Tests grün ausführen und committen**

```powershell
python -m pytest tests/test_audit_model.py tests/test_reranker_train.py tests/test_reranker_eval.py tests/test_reranker_features.py -q
```

Expected: PASS.

```powershell
git add showdown_bot/src/showdown_bot/learning/audit/model.py showdown_bot/tests/test_audit_model.py
git commit -m "feat(audit): verify reranker artifacts and calibration"
```

---

### Task 8: Report, Runner, Fatal-Pfad und CLI

**Files:**

- Create: `showdown_bot/src/showdown_bot/learning/audit/report.py`
- Create: `showdown_bot/src/showdown_bot/learning/audit/runner.py`
- Create: `showdown_bot/src/showdown_bot/learning/audit/__main__.py`
- Create: `showdown_bot/tests/test_audit_report.py`
- Create: `showdown_bot/tests/test_audit_runner.py`

- [ ] **Step 1: Failing Report- und Exitcodetests schreiben**

```python
def _audit_result():
    fail = make_finding(code="A_FAIL", severity=Severity.FAIL, scope="dataset",
                        message="fail", remediation="fix")
    warn = make_finding(code="B_WARN", severity=Severity.WARN, scope="feature",
                        message="warn", remediation="inspect")
    return AuditResult(findings=(warn, fail), metrics={"x": 1}, provenance={}, capability={})


def reordered(result):
    return AuditResult(findings=tuple(reversed(result.findings)), metrics=result.metrics,
                       provenance=result.provenance, capability=result.capability)


def _runner_row(game, decision, index):
    features = {key: 0.0 for key in FEATURE_COLUMNS}
    features.update({"format_id": "f", "game_mode": "NEUTRAL",
                     "slot1_action_type": "move", "slot2_action_type": "move",
                     "slot1_move_id": "tackle", "slot2_move_id": "protect"})
    best = index == 0
    metadata = {key: None for key in METADATA_KEYS}
    metadata.update({
        "game_id": game, "decision_id": decision, "candidate_index": index,
        "format_id": "f", "game_outcome": "win", "final_turn": 4, "winner": "p1",
        "teacher_trace": {}, "schema_version": "v1", "feature_extractor_version": "v1",
        "teacher_version": "t", "git_sha": "a" * 40, "team_hash": "team",
        "config_hash": "config", "teacher_config": {"teacher_version": "t",
                                                       "trainable_label": True},
    })
    label = {key: 0 for key in LABEL_KEYS}
    label.update({
        "counterfactual_value_raw": 1.0 if best else 0.0,
        "counterfactual_value_normalized_within_decision": 0.5 if best else -0.5,
        "value_gap_to_best": 0.0 if best else -1.0,
        "counterfactual_rank": index, "teacher_rank": index,
        "teacher_best": best, "chosen_by_current_heuristic": best, "heuristic_rank": index,
    })
    return Row(features=features, metadata=metadata, label=label)


def _runner_dataset(tmp_path):
    path = tmp_path / "valid.jsonl"
    rows = [_runner_row("g0", "d0", 0), _runner_row("g0", "d0", 1),
            _runner_row("g1", "d1", 0), _runner_row("g1", "d1", 1)]
    path.write_text("\n".join(to_jsonl_line(row) for row in rows) + "\n", encoding="utf-8")
    return path


def test_report_is_deterministic_and_fail_first():
    audit_result = _audit_result()
    obj = build_report_object(audit_result)
    md = render_markdown(obj)
    assert md.startswith("# AUDIT FAIL\n")
    assert [f["severity"] for f in obj["findings"]][:2] == ["FAIL", "WARN"]
    assert render_markdown(build_report_object(reordered(audit_result))) == md


def test_runner_writes_report_on_findings(tmp_path):
    dataset = _runner_dataset(tmp_path)
    code = run_audit(AuditRunConfig(
        dataset=dataset, out_dir=tmp_path / "out", model_path=tmp_path / "model.txt"))
    assert code == 1
    assert (tmp_path / "out" / "audit.json").exists()
    assert (tmp_path / "out" / "audit.md").exists()
    assert (tmp_path / "out" / "split-manifest.json").exists()


def test_fatal_input_writes_minimal_report(tmp_path):
    code = run_audit(AuditRunConfig(dataset=tmp_path / "missing.jsonl", out_dir=tmp_path))
    obj = json.loads((tmp_path / "audit.json").read_text())
    assert code == 1
    assert obj["status"] == "AUDIT FAIL"
    assert obj["findings"][0]["code"] == "FATAL_INPUT"
    assert obj["metrics"] == {"not_run": True}
```

- [ ] **Step 2: Tests rot ausführen**

```powershell
python -m pytest tests/test_audit_report.py tests/test_audit_runner.py -q
```

Expected: FAIL.

- [ ] **Step 3: JSON- und Markdown-Renderer implementieren**

```python
def finding_dict(finding: Finding) -> dict:
    return {
        "code": finding.code, "severity": finding.severity.value, "scope": finding.scope,
        "message": finding.message, "count": finding.count,
        "denominator": finding.denominator, "rate": finding.rate,
        "split": finding.split, "feature": finding.feature,
        "examples": list(finding.examples), "evidence": finding.evidence,
        "remediation": finding.remediation,
    }


def build_report_object(result: AuditResult) -> dict:
    limitations = sorted(
        f"{name} unavailable" for name, available in result.capability.items() if not available)
    obj = {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "status": result.status,
        "provenance": result.provenance,
        "capability": result.capability,
        "limitations": limitations,
        "findings": [finding_dict(f) for f in result.sorted_findings()],
        "metrics": result.metrics,
    }
    validate_finite(obj)
    return obj


def validate_finite(value, path="$") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise AuditError(f"non-finite report value at {path}")
    if isinstance(value, dict):
        for key in sorted(value, key=str):
            validate_finite(value[key], f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            validate_finite(item, f"{path}[{index}]")


def render_markdown(obj: dict) -> str:
    findings = obj["findings"]
    lines = [f"# {obj['status']}", "",
             f"- FAIL: {sum(f['severity'] == 'FAIL' for f in findings)}",
             f"- WARN: {sum(f['severity'] == 'WARN' for f in findings)}",
             f"- INFO: {sum(f['severity'] == 'INFO' for f in findings)}", "",
             "## Findings", "",
             "| severity | code | scope | count | rate | message |",
             "| --- | --- | --- | ---: | ---: | --- |"]
    for finding in findings:
        rate = "n/a" if finding["rate"] is None else f"{finding['rate']:.6f}"
        lines.append(f"| {finding['severity']} | {finding['code']} | {finding['scope']} | "
                     f"{finding['count']} | {rate} | {finding['message']} |")
    lines += ["", "## Provenance", "", "```json",
              json.dumps(obj["provenance"], sort_keys=True, indent=2), "```", "",
              "## Limitations", "",
              *(obj["limitations"] or ["none"]), "",
              "## Metrics", "", "```json",
              json.dumps(obj["metrics"], sort_keys=True, indent=2), "```", ""]
    return "\n".join(lines)


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")


def write_reports(out_dir: Path, result: AuditResult) -> None:
    obj = build_report_object(result)
    write_json(out_dir / "audit.json", obj)
    (out_dir / "audit.md").write_text(render_markdown(obj), encoding="utf-8")
```

Die Implementierung läuft rekursiv über Dict/List/Tuple und wirft `AuditError` bei NaN/Inf.

- [ ] **Step 4: Runner und CLI implementieren**

```python
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
```

`audit_optional_model` aus Task 7 verlangt Modell und Manifest gemeinsam; keines liefert Capability
false und leere Metrik, nur eines liefert `MODEL_ARTIFACT_PAIR_MISSING`/FAIL. Es lädt LightGBM
ausschließlich in diesem optionalen Pfad.

Verbindliche CLI-Implementierung in `runner.py`:

```python
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
```

`__main__.py` enthält exakt:

```python
from .runner import main

raise SystemExit(main())
```

- [ ] **Step 5: Report-/Runner-Tests grün ausführen und committen**

```powershell
python -m pytest tests/test_audit_report.py tests/test_audit_runner.py -q
```

Expected: PASS.

```powershell
git add showdown_bot/src/showdown_bot/learning/audit/report.py showdown_bot/src/showdown_bot/learning/audit/runner.py showdown_bot/src/showdown_bot/learning/audit/__main__.py showdown_bot/tests/test_audit_report.py showdown_bot/tests/test_audit_runner.py
git commit -m "feat(audit): orchestrate reports and command line audit"
```

---

### Task 9: Live-Path-Isolation, Referenz-Smoke und Gesamtverifikation

**Files:**

- Create: `showdown_bot/tests/test_audit_live_path_guard.py`
- Modify: `README.md`
- Create: `reports/2026-07-11-dataset-reranker-audit-smoke.md`

- [ ] **Step 1: Failing Import-Guard schreiben**

```python
def test_live_paths_do_not_import_learning_audit():
    repo = Path(__file__).resolve().parents[1] / "src" / "showdown_bot"
    forbidden = [
        repo / "battle", repo / "client" / "gauntlet.py",
        repo / "learning" / "teacher.py", repo / "learning" / "rollout.py",
        repo / "learning" / "reranker_shadow.py", repo / "learning" / "reranker_override.py",
    ]
    offenders = []
    for path in forbidden:
        files = path.rglob("*.py") if path.is_dir() else [path]
        for file in files:
            if "showdown_bot.learning.audit" in file.read_text(encoding="utf-8"):
                offenders.append(str(file))
    assert offenders == []
```

- [ ] **Step 2: Real-Dataset-Smoke-Test schreiben**

In `test_audit_runner.py`:

```python
@pytest.mark.integration
def test_phase3_slice2b25a_audit_smoke(tmp_path):
    dataset = REPO_ROOT / "data" / "datasets" / "phase3-slice2b25a" / "dataset.jsonl.gz"
    code = run_audit(AuditRunConfig(dataset=dataset, out_dir=tmp_path))
    obj = json.loads((tmp_path / "audit.json").read_text(encoding="utf-8"))
    assert code in (0, 1)
    assert obj["provenance"]["dataset_sha256"]
    assert obj["metrics"]["features"]
    assert obj["metrics"]["labels"]
    assert obj["metrics"]["duplicates"]
    assert obj["metrics"]["distribution"]
    assert sum(len(obj["provenance"]["split_manifest"]["assignments"]) for _ in [0]) > 0
```

Keine historischen Counts oder erwarteter PASS/FAIL-Status werden festgeschrieben.

- [ ] **Step 3: README und Smoke-Report dokumentieren**

README-Beispiel:

```powershell
python -m showdown_bot.learning.audit `
  ../data/datasets/phase3-slice2b25a/dataset.jsonl.gz `
  --out ../reports/audit-2b25a
```

Hinweis unmittelbar darunter: Datasetvertrauen, kein Strength-Gate; keine Datenmutation, kein
Training, keine Battles und kein Held-out-Zugriff.

`reports/2026-07-11-dataset-reranker-audit-smoke.md` nennt Dataset-/Config-/Split-Hashes, Status,
Finding-Codes und Metrikblocknamen. Es zitiert keine uncommitteten Rohdaten und kennzeichnet sich als
Referenz-Smoke, nicht als Spielstärkebeleg.

- [ ] **Step 4: Betroffene Tests ausführen**

```powershell
python -m pytest tests/test_audit_contracts.py tests/test_audit_integrity.py tests/test_audit_duplicates.py tests/test_audit_labels.py tests/test_audit_features.py tests/test_audit_distribution.py tests/test_audit_model.py tests/test_audit_report.py tests/test_audit_runner.py tests/test_audit_live_path_guard.py tests/test_dataset.py tests/test_reranker_features.py tests/test_reranker_train.py tests/test_reranker_eval.py -q
```

Expected: PASS, 0 failures.

- [ ] **Step 5: Vollständige Suite und statische Prüfungen ausführen**

```powershell
npm ci --prefix tools/calc
python -m pytest -q
git diff --check
rg -n "T[B]D|T[O]DO|F[I]XME|P[L]ACEHOLDER" showdown_bot/src/showdown_bot/learning/audit README.md reports/2026-07-11-dataset-reranker-audit-smoke.md
```

Expected: Suite mit 0 failures; bekannter Strict-Xfail bleibt xfailed. `git diff --check` exit 0;
`rg` exit 1 ohne Treffer.

- [ ] **Step 6: Abschlusscommit und Status**

```powershell
git add README.md reports/2026-07-11-dataset-reranker-audit-smoke.md showdown_bot/tests/test_audit_live_path_guard.py
git commit -m "docs(audit): document reusable dataset audit workflow"
git status --short
```

Expected: leerer Status.

---

## Plan-Selbstprüfung

- Spec §§1–5, Wiederverwendung und Isolation: Tasks 1, 2, 8, 9.
- Spec §6, standardisierte Findings und Severity: Task 1.
- Spec §7, Schema/Provenance/Gruppen/Splits/Denylist: Task 2.
- Spec §8, Row-/Decision-/Semantik-/Near-Duplikate: Task 3.
- Spec §9, Ties/Gaps/Ranks/Teacher-Provenance: Task 4.
- Spec §10, Konstanten/Sentinels/Korrelation/PSI/JS: Task 5.
- Spec §§11–12, Coverage/Teamkatalog/OOD: Task 6.
- Spec §§13–14, Modellmanifest/Predictions/Temperatur/ECE/Brier/NLL: Task 7.
- Spec §§15–17, Reports/Exitcodes/Determinismus/Fatal-Pfad: Task 8.
- Spec §§18–21, Tests/Abnahme/Nicht-Ziele/Referenzcorpus: Task 9.
- Keine Task mutiert Rows, trainiert Modelle, startet Battles oder greift auf Held-out zu.
- LightGBM wird nur im expliziten optionalen Modellpfad importiert.
- Split-, Drift-, OOD- und Kalibrierungsreferenzen werden ausschließlich aus Train/Validation
  abgeleitet; Test beeinflusst keine Parameter.
