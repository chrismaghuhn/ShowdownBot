from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from showdown_bot.eval.room_raw_replay import (
    RequestKind,
    extract_decisions_from_log,
)

REAL_LOG = (
    Path(__file__).resolve().parents[3]
    / "data" / "eval" / "t4" / "room_raw_divergent" / "prefix-idx09-regi-380.log.gz"
)


def _write_log(tmp_path: Path, lines: list[str], *, gzip_it: bool = False) -> Path:
    text = "\n".join(lines)
    if gzip_it:
        path = tmp_path / "synthetic.log.gz"
        with gzip.open(path, "wt", encoding="utf-8") as fh:
            fh.write(text)
    else:
        path = tmp_path / "synthetic.log"
        path.write_text(text, encoding="utf-8")
    return path


@pytest.mark.skipif(not REAL_LOG.exists(), reason="real corpus log not present in this checkout")
def test_real_log_first_decision_is_team_preview():
    decisions = extract_decisions_from_log(REAL_LOG)
    assert decisions, "expected at least one decision point in the real log"
    first = decisions[0]
    assert first.kind == RequestKind.TEAM_PREVIEW
    assert first.state is None  # matches gauntlet.py's _state_for: team-preview -> no state
    assert first.request.team_preview is True


@pytest.mark.skipif(not REAL_LOG.exists(), reason="real corpus log not present in this checkout")
def test_real_log_hero_side_matches_player_frame():
    decisions = extract_decisions_from_log(REAL_LOG)
    sides = {d.side for d in decisions}
    assert sides == {"p1"}, f"expected every decision to be p1's own requests, got {sides}"


def test_causality_excludes_frames_after_the_request(tmp_path):
    # A minimal synthetic log: turn 1 move request, then turn 2's board-mutating lines,
    # then a turn 2 move request. Extracting turn 1's decision must NOT see turn 2's HP change.
    lines = [
        ">battle-gen9vgc2025regi-1",
        '|request|{"active":[{"moves":[{"move":"Tackle","id":"tackle","target":"normal"}]}],'
        '"side":{"name":"Hero","id":"p1","pokemon":[]},"rqid":1}',
        "|turn|1",
        "|-damage|p2a: Wobbuffet|50/100",
        '|request|{"active":[{"moves":[{"move":"Tackle","id":"tackle","target":"normal"}]}],'
        '"side":{"name":"Hero","id":"p1","pokemon":[]},"rqid":2}',
        "|turn|2",
    ]
    path = _write_log(tmp_path, lines)
    decisions = extract_decisions_from_log(path)
    assert len(decisions) == 2
    first_prefix = decisions[0].log_prefix_hash
    second_prefix = decisions[1].log_prefix_hash
    assert first_prefix != second_prefix
    # The damage line must only be visible to the SECOND decision's prefix, not the first's.
    assert "-damage" not in "\n".join(lines[:2])  # sanity: line 3 (index 2) carries it
    # first decision's own prefix text must end at/before the first |request| line (index 1)
    assert decisions[0]._debug_prefix_line_count <= 2  # noqa: SLF001 (test-only introspection)


def test_reconnect_duplicate_request_kept_once(tmp_path):
    req_line = (
        '|request|{"active":[{"moves":[{"move":"Tackle","id":"tackle","target":"normal"}]}],'
        '"side":{"name":"Hero","id":"p1","pokemon":[]},"rqid":7}'
    )
    lines = [
        ">battle-gen9vgc2025regi-2",
        req_line,
        "|turn|1",
        req_line,  # reconnect resend: identical rqid, identical payload
    ]
    path = _write_log(tmp_path, lines)
    decisions = extract_decisions_from_log(path)
    assert len(decisions) == 1


def test_force_switch_request_classified_separately(tmp_path):
    lines = [
        ">battle-gen9vgc2025regi-3",
        '|request|{"active":[{"moves":[{"move":"Tackle","id":"tackle","target":"normal"}]}],'
        '"side":{"name":"Hero","id":"p1","pokemon":[]},"rqid":1}',
        "|turn|1",
        "|faint|p1a: Wobbuffet",
        '|request|{"forceSwitch":[true],'
        '"side":{"name":"Hero","id":"p1","pokemon":[]},"rqid":2}',
    ]
    path = _write_log(tmp_path, lines)
    decisions = extract_decisions_from_log(path)
    assert [d.kind for d in decisions] == [RequestKind.MOVE, RequestKind.FORCE_SWITCH]


def test_causality_boundary_wrong_by_one_line_is_detectable(tmp_path):
    """A fixture specifically constructed so that reading ONE frame too many produces an
    OBSERVABLY different, wrong state -- not a state that happens to look the same either way.
    A KO strictly AFTER the first request must not be visible when building that request's state."""
    lines = [
        ">battle-gen9vgc2025regi-9",
        '|request|{"active":[{"moves":[{"move":"Tackle","id":"tackle","target":"normal"}]}],'
        '"side":{"name":"Hero","id":"p1","pokemon":['
        '{"ident":"p2a: Wobbuffet","details":"Wobbuffet","condition":"100/100","active":false}]},"rqid":1}',
        "|turn|1",
        "|faint|p2a: Wobbuffet",  # this KO must be invisible to decision 0's state
        '|request|{"active":[{"moves":[{"move":"Tackle","id":"tackle","target":"normal"}]}],'
        '"side":{"name":"Hero","id":"p1","pokemon":['
        '{"ident":"p2a: Wobbuffet","details":"Wobbuffet","condition":"0 fnt","active":false}]},"rqid":2}',
    ]
    path = _write_log(tmp_path, lines)
    decisions = extract_decisions_from_log(path)
    assert len(decisions) == 2
    # decision 0's prefix text must end at-or-before line index 1 (the first |request| line);
    # the |faint| line is at index 3, strictly after -- asserting the line count catches an
    # off-by-one boundary bug that a same-looking-either-way fixture would miss.
    assert decisions[0]._debug_prefix_line_count == 2  # noqa: SLF001 (test-only introspection)
    assert decisions[1]._debug_prefix_line_count == 5  # noqa: SLF001 (test-only introspection)
    # The line count is only a proxy for what actually matters: the built BattleState itself.
    # Assert on the real state objects directly -- p2 never gets a |switch| line in this
    # fixture, so decision 0 (built from a prefix that ends before the |faint| line) must see
    # an untouched, empty p2 side, while decision 1 (built from a prefix that includes the
    # |faint| line) must see p2's slot "a" synthesized and marked fainted.
    assert decisions[0].state is not None
    assert decisions[0].state.sides["p2"] == {}
    assert decisions[1].state is not None
    assert decisions[1].state.sides["p2"]["a"].fainted is True


def test_hermetic_fixtures_do_not_require_the_real_log(monkeypatch, tmp_path):
    """Sanity check that Task 1/2/3's synthetic-fixture tests collectively exercise every
    §6 requirement (causality, reconnect dedup, force-switch classification, dedup) without
    depending on the real on-disk corpus -- so this module's core correctness is provable even
    in a checkout that doesn't have data/eval/ committed.

    Proof, not just an import check: point this module's REAL_LOG constant (the same constant
    the @pytest.mark.skipif guards above key off of) at a path that provably does not exist,
    then directly re-invoke every hermetic (non-real-log) test function defined in this file
    under that condition. None of those functions reference REAL_LOG in their bodies -- if they
    all still pass with no real corpus reachable, that demonstrates their correctness claims
    hold independent of data/eval/, which is the actual thing this test is supposed to prove.
    """
    import sys

    this_module = sys.modules[__name__]
    fake_real_log = tmp_path / "no-such-corpus" / "unreachable.log.gz"
    monkeypatch.setattr(this_module, "REAL_LOG", fake_real_log)
    assert not this_module.REAL_LOG.exists()

    hermetic_tests = [
        test_causality_excludes_frames_after_the_request,
        test_reconnect_duplicate_request_kept_once,
        test_force_switch_request_classified_separately,
        test_gzip_and_plain_logs_produce_identical_decisions,
        test_causality_boundary_wrong_by_one_line_is_detectable,
    ]
    for i, test_fn in enumerate(hermetic_tests):
        sub_dir = tmp_path / f"hermetic-{i}-{test_fn.__name__}"
        sub_dir.mkdir()
        test_fn(sub_dir)  # raises AssertionError (failing this test) if the claim doesn't hold


def test_gzip_and_plain_logs_produce_identical_decisions(tmp_path):
    lines = [
        ">battle-gen9vgc2025regi-4",
        '|request|{"active":[{"moves":[{"move":"Tackle","id":"tackle","target":"normal"}]}],'
        '"side":{"name":"Hero","id":"p1","pokemon":[]},"rqid":1}',
        "|turn|1",
    ]
    plain = _write_log(tmp_path, lines, gzip_it=False)
    gz = _write_log(tmp_path, lines, gzip_it=True)
    d_plain = extract_decisions_from_log(plain)
    d_gz = extract_decisions_from_log(gz)
    assert [d.request_hash for d in d_plain] == [d.request_hash for d in d_gz]
