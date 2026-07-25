from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from conftest import STUDIO_ROOT, SMOKE

from showdownbot_studio_exporter.errors import ExportRefuse
from showdownbot_studio_exporter.export_bundle import export_bundle
from showdownbot_studio_exporter.provenance import ProvenanceSources, resolve_provenance
from showdownbot_studio_exporter.validate_bundle import validate_bundle_dir

FIX01 = STUDIO_ROOT / "fixtures" / "viewer-v0" / "sources" / "fixture-01"
FIX01_BUNDLE = STUDIO_ROOT / "fixtures" / "viewer-v0" / "bundles" / "fixture-01"
FIX04_BUNDLE = STUDIO_ROOT / "fixtures" / "viewer-v0" / "bundles" / "fixture-04"
FIX04_SRC = STUDIO_ROOT / "fixtures" / "viewer-v0" / "sources" / "fixture-04"
FIX05_BUNDLE = STUDIO_ROOT / "fixtures" / "viewer-v0" / "bundles" / "fixture-05"


def test_unknown_git_sha_dirty_null():
    rows = json.loads((FIX01 / "decision_trace.jsonl").read_text(encoding="utf-8").splitlines()[0])
    prov = resolve_provenance(ProvenanceSources(trace_rows=[json.loads((FIX01 / "decision_trace.jsonl").read_text(encoding="utf-8").splitlines()[0])], result_row=json.loads((FIX01 / "results.jsonl").read_text(encoding="utf-8").splitlines()[0])))
    assert prov.git_sha == "unknown"
    assert prov.dirty is None


def test_provenance_disagreement_refuses(tmp_path):
    row = json.loads((FIX01 / "decision_trace.jsonl").read_text(encoding="utf-8").splitlines()[0])
    result = json.loads((FIX01 / "results.jsonl").read_text(encoding="utf-8").splitlines()[0])
    result["config_hash"] = "deadbeefdeadbeef"
    with pytest.raises(ExportRefuse) as exc:
        resolve_provenance(ProvenanceSources(trace_rows=[row], result_row=result))
    assert exc.value.reason == "provenance_disagreement"


def test_trace_rows_disagreeing_config_hash_refuses():
    lines = (FIX01 / "decision_trace.jsonl").read_text(encoding="utf-8").splitlines()
    rows = [json.loads(line) for line in lines if line.strip()]
    assert len(rows) >= 2
    rows[1] = dict(rows[1])
    rows[1]["config_hash"] = "aaaaaaaaaaaaaaaa"
    result = json.loads((FIX01 / "results.jsonl").read_text(encoding="utf-8").splitlines()[0])
    with pytest.raises(ExportRefuse) as exc:
        resolve_provenance(ProvenanceSources(trace_rows=rows, result_row=result))
    assert exc.value.reason == "provenance_disagreement"
    assert "config_hash" in exc.value.message


def test_export_modes_replay_trace_replay_only_trace_only(tmp_path):
    out1 = tmp_path / "rt"
    export_bundle(out=out1, battle_log=FIX01 / "battle.log", decision_trace=FIX01 / "decision_trace.jsonl", results=FIX01 / "results.jsonl")
    m1 = validate_bundle_dir(out1)
    assert m1["files"]["battle_log"]["present"] and m1["files"]["decision_trace"]["present"]

    out2 = tmp_path / "ro"
    export_bundle(out=out2, battle_log=FIX01 / "battle.log", results=FIX01 / "results.jsonl")
    m2 = validate_bundle_dir(out2)
    assert m2["files"]["battle_log"]["present"] and not m2["files"]["decision_trace"]["present"]
    assert m2["trace_schema_version"] is None

    out3 = tmp_path / "to"
    export_bundle(out=out3, decision_trace=SMOKE / "decision_trace.jsonl", results=SMOKE / "results.jsonl", battle_id="3e6a178b0900195e")
    m3 = validate_bundle_dir(out3)
    assert not m3["files"]["battle_log"]["present"] and m3["files"]["decision_trace"]["present"]


def test_frozen_fixture04_replay_only_nullability():
    m = validate_bundle_dir(FIX04_BUNDLE)
    assert m["trace_schema_version"] is None
    assert m["source_hashes"]["decision_trace"] is None
    assert m["source_provenance"]["our_side"] is None


def test_frozen_fixture04_replay_only_resolves_shared_fields_from_result_row():
    """Bundle contract §14 fixture 20 / §11.1.3: with no trace row available, config_hash,
    git_sha, config_id, schedule_hash, and seed_index must resolve from the result row (the
    2nd-priority source once the trace row -- the 1st -- is absent in replay-only mode).

    test_frozen_fixture04_replay_only_nullability (above) proves the §11.1.2 nullability half
    of fixture 20's own §14 text; it does not prove this half -- that the non-null shared
    fields actually come from the result row, not merely that they are present. Extends the
    existing fixture-04 precedent per §1's own fixture-20 recipe ("a pytest extension over the
    existing fixture-04 export rather than a new bundle") instead of authoring a new fixture
    directory -- a fresh fixture-20 bundle in this same replay-only mode would be
    content-identical in shape to the already-committed bundles/fixture-04.
    """
    m = validate_bundle_dir(FIX04_BUNDLE)
    result_row = json.loads((FIX04_SRC / "results.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert m["config_hash"] == result_row["config_hash"]
    assert m["git_sha"] == result_row["git_sha"]
    assert m["source_provenance"]["config_id"] == result_row["config_id"]
    assert m["source_provenance"]["schedule_hash"] == result_row["schedule_hash"]
    assert m["source_provenance"]["seed_index"] == result_row["seed_index"]


def test_frozen_fixture05_trace_only():
    m = validate_bundle_dir(FIX05_BUNDLE)
    assert not m["files"]["battle_log"]["present"]
    assert m["files"]["decision_trace"]["present"]


def test_source_hashes_equal_real_source_digests():
    """Bundle contract §15 gate 23 (positive half): "source_hashes equal the real source
    digests." The audit found the plan's own "likely existing, verify" guess for this gate
    confirmed wrong -- genuinely MISSING. bundle/fixture-01's manifest.source_hashes.
    {battle_log, decision_trace} equal a fresh sha256 computed directly from the actual
    SOURCE files on disk -- not the exported battle.jsonl/decisions.jsonl bytes, which are a
    different digest for a different artifact (proven distinct below, setting up the
    "never compared to files.*.sha256" half).
    """
    import hashlib

    manifest = validate_bundle_dir(FIX01_BUNDLE)
    expected_battle = hashlib.sha256((FIX01 / "battle.log").read_bytes()).hexdigest()
    expected_trace = hashlib.sha256((FIX01 / "decision_trace.jsonl").read_bytes()).hexdigest()
    assert manifest["source_hashes"]["battle_log"] == expected_battle
    assert manifest["source_hashes"]["decision_trace"] == expected_trace
    # Source digests and exported-file digests are for different bytes entirely -- proving
    # they legitimately differ here rules out a test that would pass by accident if the
    # exporter ever collapsed the two concepts.
    assert manifest["source_hashes"]["battle_log"] != manifest["files"]["battle_log"]["sha256"]
    assert manifest["source_hashes"]["decision_trace"] != manifest["files"]["decision_trace"]["sha256"]


def test_source_hashes_never_compared_to_files_sha256_by_the_reader(tmp_path):
    """Bundle contract §15 gate 23 (negative/structural half): "never compared to
    files.*.sha256." Mutating source_hashes to an arbitrary wrong value must not cause
    validate_bundle_dir to refuse -- only files.*.sha256 is ever checked against actual file
    bytes (test_a2_manifest_hash.py::test_frozen_fixture01_hashes_match_manifest already
    proves that half); source_hashes is pure passthrough provenance the reader never
    cross-checks. If a future change ever wired the two together, this test would catch it.
    """
    import json
    import shutil

    from showdownbot_studio_exporter.canonicalize import dumps

    dst = tmp_path / "copy"
    shutil.copytree(FIX01_BUNDLE, dst)
    manifest = json.loads((dst / "manifest.json").read_text(encoding="utf-8"))
    manifest["source_hashes"]["battle_log"] = "0" * 64
    manifest["source_hashes"]["decision_trace"] = "1" * 64
    (dst / "manifest.json").write_bytes(dumps(manifest))

    result = validate_bundle_dir(dst)  # must not raise
    assert result["source_hashes"]["battle_log"] == "0" * 64
    assert result["source_hashes"]["decision_trace"] == "1" * 64


def test_config_manifest_hash_matches_row_config_hash():
    """Bundle contract §15 gate 24 (positive half): "config-manifest.json's config_hash
    equals the row config_hash." Asserted directly against the real source pre-image and
    the real exported manifest, rather than only implicitly (several passing tests happen
    to use fixture-01's own config-manifest without it ever raising).
    """
    import json

    manifest = validate_bundle_dir(FIX01_BUNDLE)
    config_manifest = json.loads((FIX01 / "results.config-manifest.json").read_text(encoding="utf-8"))
    assert config_manifest["config_hash"] == manifest["config_hash"]


def test_config_manifest_hash_mismatch_refuses(tmp_path):
    """Bundle contract §15 gate 24 (refuse half): a mismatch between config-manifest.json's
    config_hash and the row's own config_hash must refuse. The audit found zero tests
    exercised this path even though export_bundle.py's own config_hash_mismatch check
    (export_bundle.py:138-139) is implemented.
    """
    import json

    input_dir = tmp_path / "input"
    input_dir.mkdir()
    mutated_config = input_dir / "results.config-manifest.json"
    original = json.loads((FIX01 / "results.config-manifest.json").read_text(encoding="utf-8"))
    original["config_hash"] = "deadbeefdeadbeef"
    mutated_config.write_text(json.dumps(original), encoding="utf-8")

    with pytest.raises(ExportRefuse) as exc:
        export_bundle(
            out=tmp_path / "out",
            battle_log=FIX01 / "battle.log",
            decision_trace=FIX01 / "decision_trace.jsonl",
            results=FIX01 / "results.jsonl",
            config_manifest=mutated_config,
        )
    assert exc.value.reason == "config_hash_mismatch"


def test_config_hash_never_used_as_a_lookup_key_in_exporter_source():
    """Bundle contract §15 gate 25 / §6: "Nothing in the bundle is derived from
    config_hash... No reverse-lookup table exists in the repository, and none may be added
    to Studio. A test asserts no reverse-lookup exists." The audit found this gate had zero
    trace anywhere in the test suite.

    This is a structural claim about the repository, not a runtime behaviour -- there is no
    black-box signal for "was NOT looked up" from the exported bytes alone, so the test is
    structural too: it walks every exporter source module's AST and asserts no Subscript
    expression ever uses a `config_hash`-named variable as its index, which is the only way
    source code could use a config_hash VALUE to look something else up. This is distinct
    from the common, allowed pattern of storing the value under the string key
    "config_hash" (a Constant in the slice position, not a Name) -- e.g.
    `manifest["config_hash"] = ...` in export_bundle.py is fine and does not trip this.
    """
    import ast

    exporter_src = STUDIO_ROOT / "python" / "src" / "showdownbot_studio_exporter"
    offenders = []
    for path in sorted(exporter_src.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Subscript):
                names = {n.id for n in ast.walk(node.slice) if isinstance(n, ast.Name)}
                if "config_hash" in names:
                    offenders.append(f"{path.name}:{node.lineno}")
    assert offenders == [], f"config_hash used as a subscript/lookup key: {offenders}"


def test_source_hashes_are_recomputed_by_a_fresh_export_not_only_recorded(tmp_path):
    """Gate 23's positive half, on the PRODUCER rather than the committed artifact.

    Measured, not assumed: replacing `trace_source_hash = sha256_file(decision_trace)` in
    export_bundle.py with a constant leaves the whole file green. The existing
    `test_source_hashes_equal_real_source_digests` reads bundles/fixture-01 off disk and
    compares its recorded hashes to fresh digests -- a true and useful assertion about the
    committed bundle, but it never re-exports, so an exporter regression stays invisible
    until somebody regenerates the fixture.

    This exports fixture-01 fresh into tmp_path and asserts the manifest the EXPORTER just
    wrote carries the real digests of the inputs it was handed.
    """
    import hashlib

    out = tmp_path / "bundle"
    export_bundle(
        out=out,
        battle_log=FIX01 / "battle.log",
        decision_trace=FIX01 / "decision_trace.jsonl",
        results=FIX01 / "results.jsonl",
        run_manifest=FIX01 / "results.manifest.json",
        config_manifest=FIX01 / "results.config-manifest.json",
    )

    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    source_hashes = manifest["source_hashes"]

    for key, source in (
        ("battle_log", FIX01 / "battle.log"),
        ("decision_trace", FIX01 / "decision_trace.jsonl"),
    ):
        expected = hashlib.sha256(source.read_bytes()).hexdigest()
        assert source_hashes[key] == expected, f"{key} is not the real source digest"
        # The source digest must never coincide with the exported artifact's own digest --
        # they are different bytes, and collapsing the two concepts is the failure mode
        # gate 23's second half exists to rule out.
        exported = out / ("battle.jsonl" if key == "battle_log" else "decisions.jsonl")
        assert source_hashes[key] != hashlib.sha256(exported.read_bytes()).hexdigest()
