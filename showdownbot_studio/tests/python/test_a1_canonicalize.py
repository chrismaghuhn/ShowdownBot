from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

STUDIO_ROOT = Path(__file__).resolve().parents[2]
VECTORS = STUDIO_ROOT / "tests" / "python" / "jcs_vectors"
PINNED = {
    "tests/python/jcs_vectors/input/arrays.json": (
        "e503b6d71d1afa595b1c74b1016445c944cd89f90418066b23de1aeda7d17563"
    ),
    "tests/python/jcs_vectors/output/arrays.json": (
        "099601b171cafed97c333f8878d68e7f8c8f795412adb34b2fdcf0e7c7beac42"
    ),
    "tests/python/jcs_vectors/outhex/arrays.txt": (
        "e306733ca0c4da9595ebde73ec072c295f0f9ef0ea4aafc4d267d4a04988ce51"
    ),
    "tests/python/jcs_vectors/input/french.json": (
        "03676a951cd8753ac62589f72eb2105cc782c33425418cfe1d517c111f6e5d5a"
    ),
    "tests/python/jcs_vectors/output/french.json": (
        "d99d0ebdcb0033cb858cfa830ae46bc0fb3309413b271f1da828c89901a27ed5"
    ),
    "tests/python/jcs_vectors/outhex/french.txt": (
        "f9b3bfd02f4edb3d0a490703153d836db5ef0a2090a9d3357f8c3797e12d4043"
    ),
    "tests/python/jcs_vectors/input/structures.json": (
        "d66893805be1784116af50af3110d08766c70a6b4aad93374723f72346e7aaa6"
    ),
    "tests/python/jcs_vectors/output/structures.json": (
        "605f65004ec2db7692522a0852c22f1c989e036d547e88963d1a3143cf3195d5"
    ),
    "tests/python/jcs_vectors/outhex/structures.txt": (
        "063ee2bc6fa3f93b2a131841315f5c6bf0ea7488cc128ed50725cabf5592627b"
    ),
    "tests/python/jcs_vectors/input/unicode.json": (
        "4621864e014d4a805a563f55b9ea20aba4a2d2dc09c7394f625496998c00702c"
    ),
    "tests/python/jcs_vectors/output/unicode.json": (
        "0d99aad92a125196ff887876643fd3206786a84ddce2cee52ba4ad256d2381d3"
    ),
    "tests/python/jcs_vectors/outhex/unicode.txt": (
        "0471fea1ee0464e435a52510d2c187b216961a5e7e2665402ea9cb1cd04109ca"
    ),
    "tests/python/jcs_vectors/input/values.json": (
        "c4a041b503d6bc236036ef44db4dac499272f60fc22c40dc3b7a54870ba6f1c3"
    ),
    "tests/python/jcs_vectors/output/values.json": (
        "2d5e01a318d0f0879ab568c4be289c8b1f64ef8921a53c6277d5e069978baacb"
    ),
    "tests/python/jcs_vectors/outhex/values.txt": (
        "b8b802e82c7bead71a7841e27fce6458854eb72ffd0eaa51474dacdfbdf3ab64"
    ),
    "tests/python/jcs_vectors/input/weird.json": (
        "a3a905266bd4a49a969274ea69baa14ee0c4af0ead926d6fa2b7612b4af75387"
    ),
    "tests/python/jcs_vectors/output/weird.json": (
        "6af595a9aa80110b964b4de3f82a05fa6ae7423005019bacfa2620dddc4e94d1"
    ),
    "tests/python/jcs_vectors/outhex/weird.txt": (
        "1061953c7129537722f9abd9de321c787120489d09f34ba58065bd77ba9a84b6"
    ),
}


def test_jcs_vectors_sha256sums():
    sums_path = VECTORS / "SHA256SUMS"
    if not sums_path.is_file():
        raise FileNotFoundError(sums_path)
    lines = [ln.strip() for ln in sums_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 18
    missing: list[str] = []
    for rel, want in PINNED.items():
        path = STUDIO_ROOT / rel
        if not path.is_file():
            missing.append(rel)
            continue
        got = hashlib.sha256(path.read_bytes()).hexdigest()
        assert got == want, f"{rel}: {got} != {want}"
    if missing:
        raise AssertionError(f"missing vector paths: {missing}")
    parsed = {}
    for line in lines:
        digest, rel = line.split(None, 1)
        parsed[rel] = digest
    assert parsed == PINNED


def _assert_vector(name: str) -> None:
    from showdownbot_studio_exporter.canonicalize import dumps

    inp = json.loads((VECTORS / "input" / f"{name}.json").read_text(encoding="utf-8"))
    expected = (VECTORS / "output" / f"{name}.json").read_bytes()
    # Upstream output files are UTF-8 text without trailing newline in some cases;
    # compare against exact file bytes after normalizing only if dumps returns bytes.
    got = dumps(inp)
    assert got == expected, f"{name}: dumps mismatch"
    hex_raw = (VECTORS / "outhex" / f"{name}.txt").read_text(encoding="utf-8")
    hex_expected = "".join(hex_raw.split()).lower()
    assert got.hex() == hex_expected


def test_jcs_vector_arrays():
    _assert_vector("arrays")


def test_jcs_vector_french():
    _assert_vector("french")


def test_jcs_vector_structures():
    _assert_vector("structures")


def test_jcs_vector_unicode():
    _assert_vector("unicode")


def test_jcs_vector_values():
    _assert_vector("values")


def test_jcs_vector_weird():
    _assert_vector("weird")


def test_refuse_nan():
    from showdownbot_studio_exporter.canonicalize import CanonicalizeError, dumps

    with pytest.raises(CanonicalizeError):
        dumps({"x": float("nan")})


def test_refuse_infinity():
    from showdownbot_studio_exporter.canonicalize import CanonicalizeError, dumps

    with pytest.raises(CanonicalizeError):
        dumps({"x": float("inf")})
