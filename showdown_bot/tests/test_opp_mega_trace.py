"""I7b-C: opp-mega-evidence sidecar (off by default, NEVER read to make a decision).
Consumes ScoredResponseEvidence directly, raw components only (Rev. 3 finding 4)."""
from __future__ import annotations

import pytest

from showdown_bot.eval.opp_mega_trace import (
    OppMegaTraceContext,
    OppMegaTraceError,
    OppMegaTraceWriter,
    build_opp_mega_trace_row,
    validate_opp_mega_trace_row,
)


def _context():
    return OppMegaTraceContext(
        battle_id="b0", config_id="heuristic", config_hash="cfg", schedule_hash="sched",
        format_id="gen9championsvgc2026regma", git_sha="a" * 40,
    )


def _evidence():
    from showdown_bot.battle.mega_scoring import ScoredResponseEvidence

    return [
        ScoredResponseEvidence(
            candidate_key='{"version":2,"slots":[]}', response_id="aggro->a|mega=none",
            foe_mega_slot=None, branch_index=0, branch_weight=1.0,
            world_index=0, world_weight=1.0, response_weight=0.4, raw_score=0.12,
            required_classes=("0", "none"), retained_classes=("0", "none"),
        ),
        ScoredResponseEvidence(
            candidate_key='{"version":2,"slots":[]}', response_id="aggro->a|mega=0",
            foe_mega_slot=0, branch_index=0, branch_weight=1.0,
            world_index=0, world_weight=1.0, response_weight=0.35, raw_score=0.31,
            required_classes=("0", "none"), retained_classes=("0", "none"),
        ),
    ]


def test_build_row_keeps_candidate_response_branch_link_explicit():
    row = build_opp_mega_trace_row(
        context=_context(), decision_index=1, turn_number=1, evidence=_evidence(),
        max_candidates=5, click_rate=0.35,
    )
    validate_opp_mega_trace_row(row)
    assert row["candidate_keys"][1] == _evidence()[1].candidate_key
    assert row["response_ids"] == ["aggro->a|mega=none", "aggro->a|mega=0"]
    assert row["foe_mega_slots"] == [None, 0]
    assert row["branch_indices"] == [0, 0]
    assert row["branch_weights"] == [1.0, 1.0]
    assert row["world_indices"] == [0, 0]
    assert row["world_weights"] == [1.0, 1.0]
    assert row["response_weights"] == [0.4, 0.35]
    assert row["raw_scores"] == [0.12, 0.31]
    assert row["opp_mega_click_rate"] == 0.35


def test_row_carries_raw_components_and_no_invented_contribution():
    """Rev. 3 finding 4b/4c: aggregate_scores is non-linear under MUST_REACT
    (`mean - lambda*(mean-min)`) and NEUTRAL (`mean - lambda*variance`), so NO
    single per-response product is the correct 'contribution' under both
    operators. The row must therefore expose the raw components separately and
    must never carry a pre-multiplied score_contribution for a consumer to
    mistake for one."""
    row = build_opp_mega_trace_row(
        context=_context(), decision_index=1, turn_number=1, evidence=_evidence(),
        max_candidates=5, click_rate=0.35,
    )
    for banned in ("score_contribution", "score_contributions", "contribution", "weighted_score"):
        assert banned not in row
    # the raw ingredients a consumer needs to multiply for ITS OWN operator
    for needed in ("world_weights", "response_weights", "branch_weights", "raw_scores"):
        assert needed in row


def test_required_retained_and_scored_classes_are_distinct_and_validated():
    row = build_opp_mega_trace_row(
        context=_context(), decision_index=1, turn_number=1, evidence=_evidence(),
        max_candidates=5, click_rate=0.35,
    )
    assert row["required_classes"] == ["0", "none"]
    assert row["retained_classes"] == ["0", "none"]
    assert row["scored_classes"] == ["0", "none"]
    assert set(row["required_classes"]) <= set(row["retained_classes"])


def test_reserved_classes_does_not_exist():
    """Rev. 4 finding 7: a class absent from scored evidence cannot prove the cap
    retained it, so deriving 'reserved' classes from evidence is invalid and the
    field was removed entirely. Guard against it being reintroduced."""
    row = build_opp_mega_trace_row(
        context=_context(), decision_index=1, turn_number=1, evidence=_evidence(),
        max_candidates=5, click_rate=0.35,
    )
    assert "reserved_classes" not in row


def test_validate_rejects_mismatched_parallel_array_lengths():
    row = build_opp_mega_trace_row(
        context=_context(), decision_index=1, turn_number=1, evidence=_evidence(),
        max_candidates=5, click_rate=0.35,
    )
    row["response_ids"] = row["response_ids"][:1]  # corrupt -- now shorter than candidate_keys
    with pytest.raises(OppMegaTraceError):
        validate_opp_mega_trace_row(row)


def test_writer_writes_one_line_per_decision(tmp_path):
    path = tmp_path / "opp_mega_trace.jsonl"
    writer = OppMegaTraceWriter(str(path))
    row = build_opp_mega_trace_row(
        context=_context(), decision_index=0, turn_number=1, evidence=_evidence(),
        max_candidates=5, click_rate=0.35,
    )
    writer.write(row)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1


def test_written_line_is_deterministic_and_canonical(tmp_path):
    """The sidecar is provenance: the same decision must serialise byte-identically
    on every run and on every platform, or it cannot be frozen as evidence. Key
    order must come from sort_keys, not dict insertion order."""
    import json

    row = build_opp_mega_trace_row(
        context=_context(), decision_index=0, turn_number=1, evidence=_evidence(),
        max_candidates=5, click_rate=0.35,
    )
    a, b = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    OppMegaTraceWriter(str(a)).write(row)
    # same row content, different dict insertion order
    OppMegaTraceWriter(str(b)).write({k: row[k] for k in reversed(list(row))})
    assert a.read_bytes() == b.read_bytes()

    line = a.read_text(encoding="utf-8").splitlines()[0]
    assert list(json.loads(line)) == sorted(json.loads(line))  # keys sorted
    assert ", " not in line and '": ' not in line  # compact separators, no padding


def test_row_never_includes_result_or_winner_fields():
    """Hard constraint: the sidecar is decision-time evidence only -- it must
    never carry a game outcome/winner field that could turn it into an
    accidental Strength artifact."""
    row = build_opp_mega_trace_row(
        context=_context(), decision_index=1, turn_number=1, evidence=_evidence(),
        max_candidates=5, click_rate=0.35,
    )
    assert "winner" not in row
    assert "result" not in row
    assert "game_outcome" not in row


def test_empty_evidence_produces_a_valid_empty_row():
    """No evidence means no coverage claim. The writer stays valid but must
    not invent a retained or required class."""
    row = build_opp_mega_trace_row(
        context=_context(), decision_index=2, turn_number=3, evidence=[],
        max_candidates=5, click_rate=0.35,
    )
    validate_opp_mega_trace_row(row)
    assert row["candidate_keys"] == []
    assert row["required_classes"] == []
    assert row["retained_classes"] == []
    assert row["scored_classes"] == []


def test_validate_rejects_required_class_missing_from_retained_classes():
    row = build_opp_mega_trace_row(
        context=_context(), decision_index=1, turn_number=1, evidence=_evidence(),
        max_candidates=5, click_rate=0.35,
    )
    row["retained_classes"] = ["none"]
    with pytest.raises(OppMegaTraceError):
        validate_opp_mega_trace_row(row)


def test_build_rejects_evidence_disagreeing_on_coverage():
    """required/retained come from ONE scoring call's own pre/post-cap response
    set, so every evidence row in a decision must agree on them. Disagreement
    means the caller mixed decisions -- fail closed rather than silently pick one."""
    from showdown_bot.battle.mega_scoring import ScoredResponseEvidence

    ev = _evidence()
    ev.append(ScoredResponseEvidence(
        candidate_key='{"version":2,"slots":[]}', response_id="protect|mega=none",
        foe_mega_slot=None, branch_index=0, branch_weight=1.0,
        world_index=0, world_weight=1.0, response_weight=0.25, raw_score=0.05,
        required_classes=("none",), retained_classes=("none",),  # <-- disagrees
    ))
    with pytest.raises(OppMegaTraceError):
        build_opp_mega_trace_row(
            context=_context(), decision_index=1, turn_number=1, evidence=ev,
            max_candidates=5, click_rate=0.35,
        )


# --- I7b-C Rev. 9 finding 4: LF-only, cross-platform byte determinism --------
# The sidecar is provenance: the same decision must serialise to the same BYTES
# on every platform. open(..., "a", encoding="utf-8") uses the platform default
# newline translation, so on Windows every "\n" this module writes becomes
# "\r\n" on disk -- a Windows-written line and a Linux-written line for the
# identical decision then differ byte-for-byte, and any digest over the file
# disagrees across the two. sort_keys alone does not fix that.


def test_written_bytes_are_lf_only_and_never_carry_cr(tmp_path):
    """Read the file as BYTES, not text: text mode with universal newlines
    silently translates "\\r\\n" back to "\\n" on read, so a text-mode assertion
    would pass on exactly the platform that has the bug."""
    out = tmp_path / "t.jsonl"
    writer = OppMegaTraceWriter(str(out))
    row = build_opp_mega_trace_row(
        context=_context(), decision_index=0, turn_number=3,
        evidence=_evidence(), max_candidates=5, click_rate=0.35,
    )
    writer.write(row)
    writer.write(row)

    raw = out.read_bytes()
    assert b"\r" not in raw, "sidecar bytes must be LF-only on every platform"
    assert raw.endswith(b"\n")
    assert raw.count(b"\n") == 2  # one terminator per row, no CRLF inflation


def test_written_bytes_are_identical_regardless_of_insertion_order(tmp_path):
    """Byte determinism over the ROW's own key order, checked on bytes."""
    a = tmp_path / "a.jsonl"
    b = tmp_path / "b.jsonl"
    row = build_opp_mega_trace_row(
        context=_context(), decision_index=0, turn_number=3,
        evidence=_evidence(), max_candidates=5, click_rate=0.35,
    )
    reversed_row = dict(reversed(list(row.items())))
    assert list(reversed_row) != list(row)  # genuinely different insertion order

    OppMegaTraceWriter(str(a)).write(row)
    OppMegaTraceWriter(str(b)).write(reversed_row)
    assert a.read_bytes() == b.read_bytes()
    assert b"\r" not in a.read_bytes()
