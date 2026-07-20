"""Task 4: the closed-schema coverage manifest -- ordered matchups (hero_team/opp_team/opp_policy/
target_cell) plus frozen per-team content hashes. Unknown or missing keys are rejected; the four
target cells are all present and every team's content hash is frozen.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from showdown_bot.eval.coverage_schedule import (
    COVERAGE_CELLS,
    COVERAGE_MANIFEST_PATH,
    CoverageManifestError,
    load_coverage_manifest,
)

_REPO = Path(__file__).resolve().parents[2]


def _base() -> dict:
    return json.loads((_REPO / COVERAGE_MANIFEST_PATH).read_text("utf-8"))


def _write(tmp_path, obj) -> str:
    p = tmp_path / "manifest.json"
    p.write_text(json.dumps(obj), encoding="utf-8")
    return str(p)


def test_the_manifest_has_a_closed_schema(tmp_path):
    load_coverage_manifest()  # the real committed manifest loads
    base = _base()
    # an unknown top-level key is rejected
    with pytest.raises(CoverageManifestError):
        load_coverage_manifest(_write(tmp_path, {**base, "surprise": 1}))
    # a missing required key is rejected
    for key in ("matchups", "team_content_hashes"):
        stripped = {k: v for k, v in base.items() if k != key}
        with pytest.raises(CoverageManifestError):
            load_coverage_manifest(_write(tmp_path, stripped))
    # an unknown per-matchup key is rejected
    mutated = json.loads(json.dumps(base))
    mutated["matchups"][0]["extra"] = 1
    with pytest.raises(CoverageManifestError):
        load_coverage_manifest(_write(tmp_path, mutated))


def test_the_coverage_manifest_freezes_its_team_content_hashes():
    manifest = load_coverage_manifest()
    teams = {m.opp_team for m in manifest.matchups} | {m.hero_team for m in manifest.matchups}
    for team in teams:
        assert team in manifest.team_content_hashes
        h = manifest.team_content_hashes[team]
        assert isinstance(h, str) and h
    assert {m.target_cell for m in manifest.matchups} == set(COVERAGE_CELLS)
