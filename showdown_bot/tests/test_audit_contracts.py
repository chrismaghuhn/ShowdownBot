from dataclasses import replace

import pytest

from showdown_bot.learning.audit.contracts import (
    AuditConfig,
    AuditError,
    AuditResult,
    Finding,
    Severity,
    make_finding,
)


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
