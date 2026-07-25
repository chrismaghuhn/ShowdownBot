"""Bundle contract §15 gate 3, extended to the decision-trace input path.

**Read this before adding more "the audit says MISSING" tests.** The Plan F coverage audit
lists gate 3 as MISSING. That is stale: it ran at `main @ 5feaa7c`, which `git merge-base`
confirms predates commit `1980174` ("close gate-coverage gaps the Plan F audit verified").
Gate 3 already has a test -- `test_a8_fixtures.py::test_one_byte_source_mutation_changes_bundle_digest`
-- and so does gate 7, which is why no gate-7 test lives here: the existing
`test_a1_canonicalize.py::test_jsonl_files_end_with_exactly_one_newline_and_no_cr` covers it
and was verified to go red on both a CRLF break and a double-newline break. Do not trust the
audit's table without checking the current tests first.

What is genuinely uncovered is the **second input path**. The existing gate-3 test mutates
`battle.log` and asserts `battle.jsonl`'s digest moved -- exercising `export_battle_jsonl`.
Nothing mutates the *decision trace* and confirms the change reaches `decisions.jsonl`, and
that is a different producer (`export_decisions_jsonl`).

Measured, not assumed: replacing `decision_latency_ms` with `int(...)` in the exporter --
real data loss, 1.5 ms rendered as 1 ms in the UI -- leaves the entire rest of the suite
green (109 passed, 0 failed), including the existing gate-3, gate-7 and gate-9 tests. This
file's one test is the thing that goes red.
"""

# ruff: noqa: S101 -- pytest assertion rewriting needs bare `assert`, matches every
# sibling file under tests/python/.
from __future__ import annotations

import hashlib
import shutil

from conftest import STUDIO_ROOT  # type: ignore[import-not-found]

from showdownbot_studio_exporter.export_bundle import export_bundle  # type: ignore[import-not-found]


FIX01_SRC = STUDIO_ROOT / "fixtures" / "viewer-v0" / "sources" / "fixture-01"

# Located by search rather than by byte offset, so a fixture edit relocates the site instead
# of silently mutating some unrelated field. `1.0` -> `1.5` keeps the value a finite float
# (the export must not refuse for an unrelated reason) and `decision_latency_ms` is carried
# through to decisions.jsonl, so the edit is content-bearing rather than only echoed by the
# manifest's recorded source hash.
_MUTATION_SITE = b'"decision_latency_ms":1.0'
_MUTATED_SITE = b'"decision_latency_ms":1.5'


def _sha(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _export_kwargs(src_dir):
    return {
        "battle_log": src_dir / "battle.log",
        "decision_trace": src_dir / "decision_trace.jsonl",
        "results": src_dir / "results.jsonl",
        "run_manifest": src_dir / "results.manifest.json",
        "config_manifest": src_dir / "results.config-manifest.json",
    }


def _digest_map(bundle_dir) -> dict[str, str]:
    return {p.name: _sha(p) for p in sorted(bundle_dir.iterdir())}


def test_one_byte_decision_trace_mutation_reaches_the_decisions_payload(tmp_path):
    """Gate 3 on the decision-trace path, through the real `export_bundle`.

    Asserts that `decisions.jsonl` itself moved, not merely that *some* digest changed:
    `manifest.json` records the source file's own sha256, so a mutation the exporter
    silently dropped from the payload would still change the bundle and a weaker test would
    pass while the content was in fact insensitive. Verified -- with the exporter truncating
    the field, the differing set is exactly `{"manifest.json"}` and this test is what fails.
    """
    src_a = tmp_path / "src_a"
    src_b = tmp_path / "src_b"
    shutil.copytree(FIX01_SRC, src_a)
    shutil.copytree(FIX01_SRC, src_b)

    trace_b = src_b / "decision_trace.jsonl"
    original = trace_b.read_bytes()
    assert original.count(_MUTATION_SITE) >= 1, "mutation site vanished from fixture-01"
    mutated = original.replace(_MUTATION_SITE, _MUTATED_SITE, 1)

    # The gate says ONE byte. Prove it rather than trusting the replacement's shape.
    assert len(mutated) == len(original)
    assert sum(x != y for x, y in zip(mutated, original, strict=True)) == 1

    trace_b.write_bytes(mutated)

    out_a = tmp_path / "out_a"
    out_b = tmp_path / "out_b"
    export_bundle(out=out_a, **_export_kwargs(src_a))
    export_bundle(out=out_b, **_export_kwargs(src_b))

    digests_a = _digest_map(out_a)
    digests_b = _digest_map(out_b)

    assert set(digests_a) == set(digests_b), "one-byte edit must not change the file list"
    differing = {name for name in digests_a if digests_a[name] != digests_b[name]}
    assert "decisions.jsonl" in differing, "the mutation never reached the payload"
    assert "manifest.json" in differing, "the manifest did not record the changed source"
