from __future__ import annotations

from showdown_bot.eval.accuracy_gate_a import FIELD_VARIANTS, GateAResult, run_gate_a


def test_run_gate_a_produces_one_result_per_board_x_field_combo():
    result = run_gate_a(board_names=["primary"], field_variants=["neutral", "sun"])
    assert isinstance(result, GateAResult)
    assert len(result.rows) == 2
    for row in result.rows:
        assert row.board == "primary"
        assert row.field_variant in ("neutral", "sun")
        assert isinstance(row.off_chosen_action, str) and row.off_chosen_action
        assert isinstance(row.on_chosen_action, str) and row.on_chosen_action
        assert row.exception is None


def test_run_gate_a_default_sweeps_all_7_field_variants_and_both_boards():
    result = run_gate_a()
    assert len(FIELD_VARIANTS) == 7
    assert {r.board for r in result.rows} == {"primary", "single_target"}
    assert {r.field_variant for r in result.rows} == set(FIELD_VARIANTS)
    assert len(result.rows) == 2 * 7
    assert result.exception_count == 0
