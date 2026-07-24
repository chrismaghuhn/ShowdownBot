from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from conftest import STUDIO_ROOT

from showdownbot_studio_exporter.errors import ExportRefuse
from showdownbot_studio_exporter.export_decisions import export_decisions_jsonl, load_trace_rows


FIX01_TRACE = STUDIO_ROOT / "fixtures" / "viewer-v0" / "sources" / "fixture-01" / "decision_trace.jsonl"


def test_v3_export_produces_three_phases():
    rows = load_trace_rows(FIX01_TRACE)
    blob, warnings, version = export_decisions_jsonl(rows)
    assert version == "decision-trace-v3"
    phases = set()
    has_chosen = False
    for line in blob.decode("utf-8").splitlines():
        row = json.loads(line)
        phases.add(row["decision_phase"])
        if row.get("chosen_candidate_key"):
            has_chosen = True
    assert phases == {"team_preview", "forced_replacement", "regular_turn"}
    assert has_chosen


def test_v3_aggregation_null_with_warning():
    rows = load_trace_rows(FIX01_TRACE)
    blob, warnings, _ = export_decisions_jsonl(rows)
    row = json.loads(blob.decode("utf-8").splitlines()[0])
    assert row["aggregation"]["mode"] is None
    assert row["warning_count"] >= 1


def test_v3_empty_candidates_team_preview_ok():
    rows = load_trace_rows(FIX01_TRACE)
    blob, _, _ = export_decisions_jsonl(rows)
    row0 = json.loads(blob.decode("utf-8").splitlines()[0])
    assert row0["candidates"] == []
    assert row0["chosen_candidate_key"] is None


def test_chosen_candidate_key_resolves_to_exactly_one_matching_candidate_with_agreeing_rank():
    """Bundle contract §15 gates 10 and 11 on the real committed v3 fixture: every row with
    a non-null chosen_candidate_key resolves to EXACTLY one candidate (gate 10), and
    chosen_rank equals that resolved candidate's own rank (gate 11). The audit found both
    gates over-claimed as "existing" -- coverage was only implicit (load_trace_rows would
    raise on broken real data; nothing compared the resolved values directly). This asserts
    the resolution and the rank agreement explicitly.
    """
    rows = load_trace_rows(FIX01_TRACE)
    blob, _, _ = export_decisions_jsonl(rows)
    exported = [json.loads(ln) for ln in blob.decode("utf-8").splitlines()]
    checked = 0
    for row in exported:
        if row["chosen_candidate_key"] is None:
            continue
        matches = [c for c in row["candidates"] if c["candidate_key"] == row["chosen_candidate_key"]]
        assert len(matches) == 1, row["decision_index"]
        assert row["chosen_rank"] == matches[0]["rank"], row["decision_index"]
        checked += 1
    assert checked >= 2  # fixture-01 rows 1 and 2 both carry a resolved chosen candidate


def test_resolved_chosen_candidate_agrees_with_normalized_action():
    """Bundle contract §15 gate 12 (positive half): the resolved chosen candidate's slot
    kinds -- and, for move slots, move_index/target -- agree with normalized_action's own
    slots, on real fixture-01 data. The refuse half (disagreement -> chosen_integrity) is
    already proven by test_fixture14_chosen_candidate_desync_refuses
    (test_f1_fixture_catalogue.py); this is the positive half the audit found missing --
    nothing before this asserted agreement directly on passing data, only that loading it
    didn't raise.
    """
    rows = load_trace_rows(FIX01_TRACE)
    blob, _, _ = export_decisions_jsonl(rows)
    exported = [json.loads(ln) for ln in blob.decode("utf-8").splitlines()]
    checked = 0
    for row in exported:
        if row["chosen_candidate_key"] is None:
            continue
        matched = next(c for c in row["candidates"] if c["candidate_key"] == row["chosen_candidate_key"])
        key_slots = json.loads(matched["candidate_key"])["slots"]
        norm = row["normalized_action"]
        assert norm["kind"] == "joint", row["decision_index"]
        norm_slots = norm["slots"]
        assert len(key_slots) == len(norm_slots) == 2
        for key_slot, norm_slot in zip(key_slots, norm_slots, strict=True):
            assert key_slot["kind"] == norm_slot["kind"], row["decision_index"]
            if norm_slot["kind"] == "move":
                assert key_slot["move_index"] == norm_slot["move_index"], row["decision_index"]
                assert key_slot["target"] == norm_slot.get("target"), row["decision_index"]
            elif norm_slot["kind"] == "switch":
                normalized_ident = "".join(ch for ch in key_slot["target_ident"].lower() if ch.isalnum())
                assert normalized_ident == norm_slot["switch_target"], row["decision_index"]
        checked += 1
    assert checked >= 2  # fixture-01 rows 1 (switch) and 2 (move) both exercise this


def test_chosen_candidate_key_unresolvable_refuses(tmp_path):
    """Bundle contract §15 gate 10 (refuse half): a chosen_candidate_key that matches no
    traced candidate must refuse. The audit found nothing anywhere exercised this path.
    No committed fixture holds this exact malformation (fixture-14 mutates a DIFFERENT
    field -- the chosen candidate's move_index, producing a resolvable-but-disagreeing key,
    gate 12's subject -- not an unresolvable one), so this constructs a tmp_path trace file:
    row 2's chosen_candidate_key becomes a syntactically valid, canonical
    candidate-key-v2 string that simply isn't any of row 2's own traced candidate_key
    values.
    """
    lines = FIX01_TRACE.read_text(encoding="utf-8").splitlines()
    rows = [json.loads(ln) for ln in lines if ln.strip()]
    unresolvable_key = json.dumps(
        {
            "version": 2,
            "slots": [
                {
                    "kind": "switch",
                    "move_index": None,
                    "target": None,
                    "target_ident": "p1: Nobody",
                    "terastallize": False,
                    "mega_evolve": False,
                },
                {
                    "kind": "pass",
                    "move_index": None,
                    "target": None,
                    "target_ident": None,
                    "terastallize": False,
                    "mega_evolve": False,
                },
            ],
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    rows[2] = dict(rows[2], chosen_candidate_key=unresolvable_key)
    mutated = tmp_path / "decision_trace.jsonl"
    mutated.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    with pytest.raises(ExportRefuse) as exc:
        load_trace_rows(mutated)
    assert exc.value.reason == "chosen_integrity"
    assert "must reference a traced candidate" in exc.value.message


def test_chosen_rank_mismatch_refuses(tmp_path):
    """Bundle contract §15 gate 11 (refuse half): chosen_rank disagreeing with the resolved
    candidate's own rank must refuse. The audit found nothing anywhere exercised this path.
    Row 2's chosen_candidate_key still resolves (unlike the gate-10 test above), but
    chosen_rank is wrong.
    """
    lines = FIX01_TRACE.read_text(encoding="utf-8").splitlines()
    rows = [json.loads(ln) for ln in lines if ln.strip()]
    rows[2] = dict(rows[2], chosen_rank=99)
    mutated = tmp_path / "decision_trace.jsonl"
    mutated.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    with pytest.raises(ExportRefuse) as exc:
        load_trace_rows(mutated)
    assert exc.value.reason == "chosen_integrity"
    assert "chosen_rank must match rank" in exc.value.message


def test_duplicate_candidate_key_within_row_refuses():
    """Bundle contract §15 gate 13 (second half): "duplicate candidate keys refuse."
    godot/tests/bundle/test_bundle_validator.gd::test_fixture09_duplicate_decision_index_refuses
    already proves gate 13's *duplicate decision identity* half (fixture-09); this proves
    the other half the audit found genuinely untested anywhere -- two candidates in the SAME
    decision row sharing one candidate_key string.

    Exercises export_decisions_jsonl directly rather than the full load_trace_rows pipeline:
    showdown_bot's own validate_trace_row (called from load_trace_rows) already enforces
    row-level candidate_key uniqueness upstream and would refuse first with a
    non-exporter-owned reason, making the exporter's OWN duplicate_candidate_key guard
    otherwise unreachable through the real pipeline. Rows are loaded for real (so they start
    valid) and then mutated in memory before being handed to export_decisions_jsonl
    directly, the same construction style test_a4_decisions_v1_refuse.py already uses for
    decision-trace-v1 rows.
    """
    rows = load_trace_rows(FIX01_TRACE)
    mutated = [dict(r) for r in rows]
    row2 = dict(mutated[2])
    dup_key = row2["candidates"][0]["candidate_key"]
    cand0 = dict(row2["candidates"][0])
    cand1 = dict(row2["candidates"][1], candidate_key=dup_key)
    row2["candidates"] = [cand0, cand1]
    mutated[2] = row2
    with pytest.raises(ExportRefuse) as exc:
        export_decisions_jsonl(mutated)
    assert exc.value.reason == "duplicate_candidate_key"
