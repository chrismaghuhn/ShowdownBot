"""I7a-C P1.3: own-Mega smoke evidence gate.

``derive_mega_evidence`` scans a battle's decision-trace rows (already validated v3 rows,
see eval/decision_capture.py) for a FULL own-Mega path: a regular-turn decision that
actually chose the Mega overlay (``chosen_mega_slot`` set + the sent ``/choose`` string
containing "mega"), followed by at least one later non-team-preview decision whose
``state_summary`` proves the bot's own slot rebuilt into its post-Mega species.

Returns ``None`` (INCONCLUSIVE) when no such path is observed -- callers MUST NOT treat
``None`` as PASS. Raises ``MegaEvidenceError`` when a row's own fields are internally
contradictory (a real bug, distinct from mere absence of evidence).
"""
from __future__ import annotations

import pytest

from showdown_bot.eval.mega_evidence import MegaEvidenceError, derive_mega_evidence


def _row(*, decision_index, decision_phase="regular_turn", chosen_mega_slot=None,
         actual_choose_string="move 1", species_a="Charizard", battle_id="b0",
         turn_number=1, chosen_candidate_key=None):
    return {
        "battle_id": battle_id,
        "decision_index": decision_index,
        "turn_number": turn_number,
        "decision_phase": decision_phase,
        "chosen_mega_slot": chosen_mega_slot,
        "actual_choose_string": actual_choose_string,
        "chosen_candidate_key": chosen_candidate_key,
        "state_summary": {
            "sides": {"p1": {"a": {"species": species_a}, "b": {"species": "Aerodactyl"}}},
        },
    }


def test_no_mega_click_in_any_row_is_inconclusive():
    rows = [_row(decision_index=0), _row(decision_index=1)]
    assert derive_mega_evidence(rows, our_side="p1") is None


def test_mega_click_with_no_later_decision_is_inconclusive():
    rows = [
        _row(decision_index=0, chosen_mega_slot=0, actual_choose_string="move 1 mega",
             chosen_candidate_key="k0"),
    ]
    assert derive_mega_evidence(rows, our_side="p1") is None


def test_full_mega_path_returns_evidence():
    rows = [
        _row(decision_index=0, species_a="Charizard"),
        _row(decision_index=1, chosen_mega_slot=0, actual_choose_string="move 1 mega",
             chosen_candidate_key="k1", species_a="Charizard", turn_number=3),
        _row(decision_index=2, species_a="Charizard-Mega-Y", turn_number=4),
    ]

    evidence = derive_mega_evidence(rows, our_side="p1")

    assert evidence is not None
    assert evidence.battle_id == "b0"
    assert evidence.mega_decision_index == 1
    assert evidence.turn_number == 3
    assert evidence.mega_slot == 0
    assert evidence.chosen_candidate_key == "k1"
    assert evidence.post_mega_decision_index == 2
    assert evidence.post_mega_species == "Charizard-Mega-Y"


def test_later_team_preview_row_does_not_count_as_the_post_mega_decision():
    rows = [
        _row(decision_index=0, chosen_mega_slot=0, actual_choose_string="move 1 mega",
             chosen_candidate_key="k1", species_a="Charizard"),
        _row(decision_index=1, decision_phase="team_preview", species_a="Charizard-Mega-Y"),
    ]
    assert derive_mega_evidence(rows, our_side="p1") is None


def test_chosen_mega_slot_without_choose_string_containing_mega_is_a_hard_error():
    rows = [
        _row(decision_index=0, chosen_mega_slot=0, actual_choose_string="move 1",
             chosen_candidate_key="k1"),
        _row(decision_index=1, species_a="Charizard-Mega-Y"),
    ]
    with pytest.raises(MegaEvidenceError, match="mega"):
        derive_mega_evidence(rows, our_side="p1")


def test_post_mega_row_with_unchanged_species_is_a_hard_error():
    rows = [
        _row(decision_index=0, chosen_mega_slot=0, actual_choose_string="move 1 mega",
             chosen_candidate_key="k1", species_a="Charizard"),
        _row(decision_index=1, species_a="Charizard"),  # never actually rebuilt to Mega form
    ]
    with pytest.raises(MegaEvidenceError, match="species"):
        derive_mega_evidence(rows, our_side="p1")


def test_mega_click_on_team_preview_row_is_a_hard_error():
    rows = [
        _row(decision_index=0, decision_phase="team_preview", chosen_mega_slot=0,
             actual_choose_string="team 1234 mega", chosen_candidate_key="k1"),
        _row(decision_index=1, species_a="Charizard-Mega-Y"),
    ]
    with pytest.raises(MegaEvidenceError, match="team_preview"):
        derive_mega_evidence(rows, our_side="p1")


def test_picks_the_earliest_mega_click_when_multiple_present():
    rows = [
        _row(decision_index=0, chosen_mega_slot=0, actual_choose_string="move 1 mega",
             chosen_candidate_key="k1", species_a="Charizard", turn_number=2),
        _row(decision_index=1, species_a="Charizard-Mega-Y", turn_number=3),
        _row(decision_index=2, chosen_mega_slot=0, actual_choose_string="move 2 mega",
             chosen_candidate_key="k2", species_a="Charizard-Mega-Y", turn_number=4),
    ]
    evidence = derive_mega_evidence(rows, our_side="p1")
    assert evidence.mega_decision_index == 0
