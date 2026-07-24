"""Plan F fixture catalogue -- exporter-side proofs for fixtures 11, 14, 19 (bundle contract §14).

Fixture 9 (duplicate decision identity) and fixture 21 (provenance disagreement) are Plan F's
own §14 rows too, but are proved elsewhere: 9 is a Godot-validator-side fixture
(godot/tests/bundle/test_bundle_validator.gd, since the recipe is "same shape as
godot/tests/fixtures/unit/refuse-duplicate-decision-index"), and 21's refuse behaviour is
already covered by three existing tests (test_a6_provenance_modes.py::test_provenance_disagreement_refuses,
test_a6_provenance_modes.py::test_trace_rows_disagreeing_config_hash_refuses,
test_a7_cli.py::test_cli_refuse_provenance_disagreement) -- Plan F only authors fixture 21's
catalogue directory (fixtures/viewer-v0/sources/fixture-21/), it does not duplicate the gate
test (Rev. 5 gate-coverage audit, §3: gate 33 already COVERED).

Fixture 18 (`|request|` skip rules) is this batch's own §14 row too, but its gate (§15 gate 35)
is already directly proved by test_a5_battle_join.py::test_request_skip_rules (Rev. 5
gate-coverage audit: "materially stronger than 'new' implies"). Plan F only authors fixture 18's
catalogue directory (fixtures/viewer-v0/sources/fixture-18/, fixtures/viewer-v0/bundles/fixture-18/),
it does not duplicate the gate test.

Fixture 13 (legacy trace-v1) is this batch's own §14 row too. Its gate (§15 gate 37) is already
proved by test_a4_decisions_v1_refuse.py, but only against an ephemeral row constructed inline in
a tmp_path, never against a committed catalogue fixture. This file adds fixture-13's own
catalogue directory (fixtures/viewer-v0/sources/fixture-13/) and re-proves both halves of gate 37
against it -- "extend[ing] to the fixture catalogue, not a new mechanism" per §1's own recipe --
without committing a bundles/fixture-13/: the replay-only fallback bundle this fixture's own
room log would produce is byte-identical in shape to the already-committed bundles/fixture-04
(fixture-01's battle_log + results, no trace), so a second committed copy would be pure
duplication (see the task report's fixture-13 disposition).
"""

# ruff: noqa: S101 -- pytest assertion rewriting needs bare `assert`, matches every
# sibling file under tests/python/.
from __future__ import annotations

import json

import pytest

from conftest import STUDIO_ROOT

from showdownbot_studio_exporter.errors import ExportRefuse
from showdownbot_studio_exporter.export_battle import export_battle_jsonl, read_battle_log
from showdownbot_studio_exporter.export_bundle import export_bundle
from showdownbot_studio_exporter.export_decisions import export_decisions_jsonl, load_trace_rows
from showdownbot_studio_exporter.join import join_request_protocol_indices
from showdownbot_studio_exporter.validate_bundle import validate_bundle_dir

FIX01_LOG = STUDIO_ROOT / "fixtures" / "viewer-v0" / "sources" / "fixture-01" / "battle.log"
FIX01_RESULTS = STUDIO_ROOT / "fixtures" / "viewer-v0" / "sources" / "fixture-01" / "results.jsonl"
FIX02 = STUDIO_ROOT / "fixtures" / "viewer-v0" / "sources" / "fixture-02" / "decision_trace.jsonl"
FIX11 = STUDIO_ROOT / "fixtures" / "viewer-v0" / "sources" / "fixture-11" / "decision_trace.jsonl"
FIX13 = STUDIO_ROOT / "fixtures" / "viewer-v0" / "sources" / "fixture-13" / "decision_trace.jsonl"
FIX14 = STUDIO_ROOT / "fixtures" / "viewer-v0" / "sources" / "fixture-14" / "decision_trace.jsonl"
FIX16_TRACE = STUDIO_ROOT / "fixtures" / "viewer-v0" / "sources" / "fixture-16" / "decision_trace.jsonl"
FIX17_LOG = STUDIO_ROOT / "fixtures" / "viewer-v0" / "sources" / "fixture-17" / "battle.log"
FIX19 = STUDIO_ROOT / "fixtures" / "viewer-v0" / "sources" / "fixture-19"


def test_fixture11_non_finite_value_fails_export():
    """Bundle contract §15 gate 8: "A non-finite input fails export (fixture 11)."

    Finding (see task report): §1's own recipe column additionally claims the reason would be
    ExportRefuse("non_finite_value", ...) -- export_decisions.py's own non_finite_value checks
    (lines checking decision_latency_ms / candidate aggregate_score). Empirically, both fields
    are validated for finiteness earlier, inside showdown_bot.eval.decision_capture.validate_trace_row
    (called from load_trace_rows before export_decisions_jsonl is ever reached), so the reason
    actually produced through the real load_trace_rows -> export_bundle pipeline is
    "trace_validation", not "non_finite_value". export_decisions.py's own non_finite_value
    branches are therefore dead code on this pipeline. Gate 8's own binding text ("fails
    export") does not name a reason string, so this is satisfied either way; asserting the
    real reason here rather than the plan's paraphrase.
    """
    with pytest.raises(ExportRefuse) as exc:
        load_trace_rows(FIX11)
    assert exc.value.reason == "trace_validation"
    assert exc.value.message == "decision_latency_ms must be finite"


def test_fixture14_chosen_candidate_desync_refuses():
    """Bundle contract §14 fixture 14 / §15 gate 12: chosen_* disagreeing with normalized_action.

    fixture-14's decision_trace.jsonl row 2 has its chosen (and matching candidate) key's
    move_index changed from 1 to 2, while normalized_action is left untouched (still move_index
    1) -- the resolved candidate now disagrees with normalized_action's own recorded slot.
    """
    with pytest.raises(ExportRefuse) as exc:
        load_trace_rows(FIX14)
    assert exc.value.reason == "chosen_integrity"
    assert exc.value.message == "chosen_candidate_key move_index mismatch vs normalized_action"


def test_fixture13_legacy_trace_v1_refuses_and_replay_only_fallback(tmp_path):
    """Bundle contract §14 fixture 13 / §15 gate 37: a legacy trace-v1 source's trace export is
    rejected with a precise reason, and a replay-only bundle is still produced when a room log
    exists.

    fixture-13/decision_trace.jsonl is fixture-01's own three rows with every row's
    trace_schema_version changed to "decision-trace-v1" and chosen_candidate_key removed (no
    validated candidate_key -- §14's own wording), mirroring
    test_a4_decisions_v1_refuse.py's mutation exactly but as a committed, hash-pinned catalogue
    fixture rather than an ephemeral tmp_path row.
    """
    with pytest.raises(ExportRefuse) as exc:
        load_trace_rows(FIX13)
    assert exc.value.reason == "unsupported_trace_v1"

    # Passing the v1 trace alongside a room log still refuses the whole export -- trace export
    # is rejected outright, never silently downgraded.
    with pytest.raises(ExportRefuse) as exc:
        export_bundle(out=tmp_path / "trace-attempt", battle_log=FIX01_LOG, decision_trace=FIX13, results=FIX01_RESULTS)
    assert exc.value.reason == "unsupported_trace_v1"

    # The same room log, without the v1 trace, still exports as a replay-only bundle.
    replay_only = tmp_path / "replay-only"
    export_bundle(out=replay_only, battle_log=FIX01_LOG, results=FIX01_RESULTS)
    manifest = validate_bundle_dir(replay_only)
    assert manifest["files"]["battle_log"]["present"]
    assert not manifest["files"]["decision_trace"]["present"]


def test_fixture19_unjoinable_decision_not_dropped():
    """Bundle contract §14 fixture 19: a trace row's request_hash matches no raw request.

    Not a refuse case (§14's own "must prove" text): join_request_protocol_indices must not
    raise, the mutated decision's request_protocol_index must be null, and every decision
    (including the unjoinable one) must still be present -- never dropped.
    """
    log = read_battle_log(FIX19 / "battle.log")
    rows = load_trace_rows(FIX19 / "decision_trace.jsonl")
    joined = join_request_protocol_indices(rows, log)
    assert len(joined) == len(rows)  # nothing dropped
    unjoined = [idx for idx, protocol_index in joined.items() if protocol_index is None]
    assert unjoined == [2]
    assert all(protocol_index is not None for idx, protocol_index in joined.items() if idx != 2)


def test_fixture02_close_decision_margin_small_correct_no_threshold():
    """Bundle contract §14 fixture 2 / §15 (unnumbered completion row): top1_top2_margin small
    and correct; no threshold implied; margin null when fewer than two candidates.

    fixture-02/decision_trace.jsonl is fixture-01's own three rows with row 2's second candidate
    ("pass", rank 1) aggregate_score changed 0.5 -> 3.487, so the top two candidates (3.5, 3.487)
    are 0.013 apart -- small and, unlike fixture-01's original 3.0 gap, not a round number, so a
    passing assertion here cannot be explained by the exporter applying some implicit cutoff.
    Row 0 (team_preview, 0 candidates) and row 1 (forced_replacement, exactly 1 candidate) both
    exercise "fewer than two candidates" -- two different counts below the threshold, not just
    the zero case.
    """
    rows = load_trace_rows(FIX02)
    decisions_bytes, _, _ = export_decisions_jsonl(rows)
    by_index = {
        row["decision_index"]: row for row in (json.loads(ln) for ln in decisions_bytes.decode("utf-8").splitlines())
    }
    assert len(by_index[0]["candidates"]) == 0
    assert by_index[0]["top1_top2_margin"] is None
    assert len(by_index[1]["candidates"]) == 1
    assert by_index[1]["top1_top2_margin"] is None
    assert len(by_index[2]["candidates"]) == 2
    assert by_index[2]["top1_top2_margin"] == pytest.approx(0.013)


def test_fixture17_protocol_index_gaps_land_exactly_on_filtered_lines():
    """Bundle contract §14 fixture 17 / §15 gate 34: protocol_index is sparse, strictly
    increasing, and the gaps land exactly on the filtered lines (§11.3.1) -- asserted against the
    real index values and the real filtered-line positions, not merely that the sequence
    increases (a test that only checked monotonicity would pass on a completely wrong mapping).

    fixture-17/battle.log has 11 lines: |player| (0), |j| (1), |t:| (2), |request| (3, 7, 10),
    and |c| chat (5) are all filtered; |turn| (4, 8), |switch| (6), and |move| (9) are real
    parsed events and the only lines that produce a battle.jsonl row.
    """
    lines = read_battle_log(FIX17_LOG)
    battle_bytes = export_battle_jsonl(lines)
    rows = [json.loads(ln) for ln in battle_bytes.decode("utf-8").splitlines()]
    indices = [row["protocol_index"] for row in rows]
    assert indices == [4, 6, 8, 9]
    assert indices == sorted(indices)
    assert len(set(indices)) == len(indices)  # strictly increasing, not merely non-decreasing
    gap_positions = sorted(set(range(len(lines))) - set(indices))
    assert gap_positions == [0, 1, 2, 3, 5, 7, 10]


def test_fixture16_104_candidate_row_export_not_truncated():
    """Cross-cutting rule 7 (index §5) / Choice Point 3 (§0.11, CLOSED: L1): the 104-candidate
    bounded-render fixture. See the task report -- this is already satisfied by the real
    committed row in fixtures/viewer-v0/sources/fixture-16 (a byte-identical copy of
    data/eval/champions-panel-v0/smoke-i7a-mega/decision_trace.jsonl, confirmed by sha256), which
    fixture-16's own bundle already carries into bundles/fixture-16/decisions.jsonl and which
    godot/tests/decision/test_candidate_table_view.gd::test_table_bounded_104_candidates already
    proves the UI *renders* bounded to exactly 104 controls. That test does not touch the
    exporter; this test proves the complementary half -- export_decisions_jsonl does not truncate
    the real 104-candidate row before it ever reaches the UI (bundle contract §2.5's
    TOP_K_TRACE_CANDIDATES only bounds the non-Mega producer branch, not this exporter).
    """
    rows = load_trace_rows(FIX16_TRACE)
    decisions_bytes, _, _ = export_decisions_jsonl(rows)
    decisions = [json.loads(ln) for ln in decisions_bytes.decode("utf-8").splitlines()]
    counts = [len(d["candidates"]) for d in decisions]
    assert 104 in counts
    hundred_four = next(d for d in decisions if len(d["candidates"]) == 104)
    assert len(hundred_four["candidates"]) == 104
