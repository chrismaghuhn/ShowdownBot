from showdown_bot.learning.audit.contracts import AuditResult, Severity, make_finding
from showdown_bot.learning.audit.report import build_report_object, render_markdown


def _audit_result():
    fail = make_finding(code="A_FAIL", severity=Severity.FAIL, scope="dataset",
                        message="fail", remediation="fix")
    warn = make_finding(code="B_WARN", severity=Severity.WARN, scope="feature",
                        message="warn", remediation="inspect")
    return AuditResult(findings=(warn, fail), metrics={"x": 1}, provenance={}, capability={})


def reordered(result):
    return AuditResult(findings=tuple(reversed(result.findings)), metrics=result.metrics,
                       provenance=result.provenance, capability=result.capability)


def test_report_is_deterministic_and_fail_first():
    audit_result = _audit_result()
    obj = build_report_object(audit_result)
    md = render_markdown(obj)
    assert md.startswith("# AUDIT FAIL\n")
    assert [f["severity"] for f in obj["findings"]][:2] == ["FAIL", "WARN"]
    assert render_markdown(build_report_object(reordered(audit_result))) == md
