"""F0 binding-document existence/structure guards (spec 2026-07-25-phase3-client-design.md
section 3.3, section 9 gate 1). Each test asserts a required F0 deliverable doc exists and
carries its required section structure -- not full prose review, which is a human gate-9
review task, but enough that a doc silently regressed to an empty stub fails loudly.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from conftest import STUDIO_ROOT  # type: ignore[import-not-found]

_DOCS_SECURITY = STUDIO_ROOT / "docs" / "security"
_DOCS_ARCHITECTURE = STUDIO_ROOT / "docs" / "architecture"


def _assert_doc_has_headings(path: Path, required_headings: list[str]) -> None:
    assert path.is_file(), f"missing required F0 doc: {path}"
    text = path.read_text(encoding="utf-8")
    missing = [h for h in required_headings if h not in text]
    assert not missing, f"{path.name} missing required headings: {missing}"


def test_threat_model_doc_exists_with_required_sections():
    _assert_doc_has_headings(
        _DOCS_SECURITY / "THREAT_MODEL.md",
        [
            "## Purpose and scope",
            "## Assets",
            "## Trust boundaries",
            "## Threat actors",
            "## Threats and mitigations",
            "## Residual risk and non-goals",
        ],
    )


def test_data_classification_doc_exists_with_required_sections():
    _assert_doc_has_headings(
        _DOCS_SECURITY / "DATA_CLASSIFICATION.md",
        [
            "## Purpose",
            "## Classification levels",
            "## Data categories",
            "## Cross-references",
        ],
    )


def test_credential_lifecycle_doc_exists_with_required_sections():
    _assert_doc_has_headings(
        _DOCS_SECURITY / "CREDENTIAL_LIFECYCLE.md",
        [
            "## Purpose",
            "## Lifecycle stages",
            "## Storage",
            "## Never-do list",
            "## Future extension",
        ],
    )


def test_logging_and_redaction_doc_exists_with_required_sections():
    _assert_doc_has_headings(
        _DOCS_SECURITY / "LOGGING_AND_REDACTION.md",
        [
            "## Purpose",
            "## Never-log list",
            "## Diagnostic mode",
            "## Redaction points",
            "## Review checklist",
        ],
    )


def test_untrusted_server_content_doc_exists_with_required_sections():
    _assert_doc_has_headings(
        _DOCS_SECURITY / "UNTRUSTED_SERVER_CONTENT.md",
        [
            "## Purpose",
            "## What counts as untrusted",
            "## Handling rules",
            "## Protocol parsing boundary",
            "## Unknown protocol line handling",
        ],
    )
