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
"""

# ruff: noqa: S101 -- pytest assertion rewriting needs bare `assert`, matches every
# sibling file under tests/python/.
from __future__ import annotations

import pytest

from conftest import STUDIO_ROOT

from showdownbot_studio_exporter.errors import ExportRefuse
from showdownbot_studio_exporter.export_battle import read_battle_log
from showdownbot_studio_exporter.export_decisions import load_trace_rows
from showdownbot_studio_exporter.join import join_request_protocol_indices

FIX11 = STUDIO_ROOT / "fixtures" / "viewer-v0" / "sources" / "fixture-11" / "decision_trace.jsonl"
FIX14 = STUDIO_ROOT / "fixtures" / "viewer-v0" / "sources" / "fixture-14" / "decision_trace.jsonl"
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
