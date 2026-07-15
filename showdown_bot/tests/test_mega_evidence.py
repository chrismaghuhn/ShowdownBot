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

from showdown_bot.eval.mega_evidence import (
    MegaEvidenceError,
    bind_protocol_mega_pair,
    derive_mega_evidence,
)


def _row(*, decision_index, decision_phase="regular_turn", chosen_mega_slot=None,
         actual_choose_string="move 1", species_a="Charizard", battle_id="b0",
         turn_number=1, chosen_candidate_key=None, item_a=None, item_a_known=False):
    return {
        "battle_id": battle_id,
        "decision_index": decision_index,
        "turn_number": turn_number,
        "decision_phase": decision_phase,
        "chosen_mega_slot": chosen_mega_slot,
        "actual_choose_string": actual_choose_string,
        "chosen_candidate_key": chosen_candidate_key,
        "state_summary": {
            "sides": {
                "p1": {
                    "a": {"species": species_a, "item": item_a, "item_known": item_a_known},
                    "b": {"species": "Aerodactyl", "item": None, "item_known": False},
                },
            },
        },
    }


def test_no_mega_click_in_any_row_is_inconclusive():
    rows = [_row(decision_index=0), _row(decision_index=1)]
    assert derive_mega_evidence(rows, our_side="p1") is None


def test_mega_click_with_no_later_decision_is_inconclusive():
    rows = [
        _row(decision_index=0, chosen_mega_slot=0, actual_choose_string="move 1 mega",
             chosen_candidate_key="k0", species_a="Charizard",
             item_a="Charizardite Y", item_a_known=True),
    ]
    assert derive_mega_evidence(rows, our_side="p1") is None


def test_full_mega_path_returns_evidence():
    rows = [
        _row(decision_index=0, species_a="Charizard"),
        _row(decision_index=1, chosen_mega_slot=0, actual_choose_string="move 1 mega",
             chosen_candidate_key="k1", species_a="Charizard", turn_number=3,
             item_a="Charizardite Y", item_a_known=True),
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
             chosen_candidate_key="k1", species_a="Charizard",
             item_a="Charizardite Y", item_a_known=True),
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


def test_post_mega_row_with_unchanged_species_is_inconclusive():
    """Codex re-review (semantics): a legitimate later switch/faint before the Mega form
    is ever observed again is INCONCLUSIVE (no evidence found), not a hard internal
    error -- it doesn't prove anything is broken, just that this battle's trace never
    shows the rebuilt state."""
    rows = [
        _row(decision_index=0, chosen_mega_slot=0, actual_choose_string="move 1 mega",
             chosen_candidate_key="k1", species_a="Charizard",
             item_a="Charizardite Y", item_a_known=True),
        _row(decision_index=1, species_a="Charizard"),  # never actually rebuilt to Mega form
    ]
    assert derive_mega_evidence(rows, our_side="p1") is None


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
             chosen_candidate_key="k1", species_a="Charizard", turn_number=2,
             item_a="Charizardite Y", item_a_known=True),
        _row(decision_index=1, species_a="Charizard-Mega-Y", turn_number=3,
             item_a="Charizardite Y", item_a_known=True),
        _row(decision_index=2, chosen_mega_slot=0, actual_choose_string="move 2 mega",
             chosen_candidate_key="k2", species_a="Charizard-Mega-Y", turn_number=4,
             item_a="Charizardite Y", item_a_known=True),
    ]
    evidence = derive_mega_evidence(rows, our_side="p1")
    assert evidence.mega_decision_index == 0


# --- Codex re-review finding: a later SWITCH must not be accepted as a Mega rebuild ------

def test_switch_to_a_different_unrelated_species_after_mega_click_is_inconclusive():
    """P1.3 correction (Codex re-review, 2026-07-15): the prior implementation accepted
    ANY species change in the slot as proof of a Mega rebuild. A Charizard Mega click
    followed by a switch to Incineroar in the same slot must NOT be accepted as evidence
    -- the post-click species must match the form mega_form_for(pre_species, stone)
    actually derives. A second re-review pass then clarified the semantics: a switch is
    legitimate normal play, so the correct outcome is INCONCLUSIVE (None), not a hard
    MegaEvidenceError -- see test_post_mega_row_with_unchanged_species_is_inconclusive."""
    rows = [
        _row(decision_index=0, chosen_mega_slot=0, actual_choose_string="move 1 mega",
             chosen_candidate_key="k1", species_a="Charizard",
             item_a="Charizardite Y", item_a_known=True),
        _row(decision_index=1, species_a="Incineroar"),  # switched, not Mega-rebuilt
    ]
    assert derive_mega_evidence(rows, our_side="p1") is None


def test_later_row_after_an_intervening_switch_still_counts_as_evidence():
    """The search for the expected Mega form must not stop at the FIRST later row -- if
    an intervening decision shows an unrelated species (a switch) but a SUBSEQUENT
    decision shows the mon back in its exact expected Mega form, that later row is valid
    evidence of a rebuilt Mega state."""
    rows = [
        _row(decision_index=0, chosen_mega_slot=0, actual_choose_string="move 1 mega",
             chosen_candidate_key="k1", species_a="Charizard", turn_number=2,
             item_a="Charizardite Y", item_a_known=True),
        _row(decision_index=1, species_a="Incineroar", turn_number=3),  # switched out
        _row(decision_index=2, species_a="Charizard-Mega-Y", turn_number=4),  # switched back in
    ]
    evidence = derive_mega_evidence(rows, our_side="p1")
    assert evidence is not None
    assert evidence.post_mega_decision_index == 2
    assert evidence.post_mega_species == "Charizard-Mega-Y"


def test_mega_click_with_unknown_item_is_a_hard_error():
    """Cannot verify the claimed Mega form without knowing the pre-click stone item --
    fail closed rather than silently trusting an unverifiable species diff."""
    rows = [
        _row(decision_index=0, chosen_mega_slot=0, actual_choose_string="move 1 mega",
             chosen_candidate_key="k1", species_a="Charizard",
             item_a=None, item_a_known=False),
        _row(decision_index=1, species_a="Charizard-Mega-Y"),
    ]
    with pytest.raises(MegaEvidenceError, match="item"):
        derive_mega_evidence(rows, our_side="p1")


# --- Codex re-review finding: bind trace-derived evidence to the real protocol pair ------

import hashlib

_RAW_LOG_WITH_MEGA = """\
|switch|p1a: Charizard|Charizard, L50|100/100
|switch|p2a: Incineroar|Incineroar, L50|100/100
|turn|1
|detailschange|p1a: Charizard|Charizard-Mega-Y, L50
|-mega|p1a: Charizard|Charizard|Charizardite Y
|move|p1a: Charizard|Flamethrower|p2a: Incineroar
"""

_RAW_LOG_REVERSED_ORDER = """\
|switch|p1a: Charizard|Charizard, L50|100/100
|-mega|p1a: Charizard|Charizard|Charizardite Y
|detailschange|p1a: Charizard|Charizard-Mega-Y, L50
"""

_RAW_LOG_AMBIGUOUS_PAIR = """\
|switch|p1a: Charizard|Charizard, L50|100/100
|detailschange|p1a: Charizard|Charizard-Mega-Y, L50
|-mega|p1a: Charizard|Charizard|Charizardite Y
|detailschange|p1a: Charizard|Charizard-Mega-Y, L50
|-mega|p1a: Charizard|Charizard|Charizardite Y
"""


def _log_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_bind_protocol_mega_pair_finds_matching_detailschange_and_mega_lines():
    binding = bind_protocol_mega_pair(
        _RAW_LOG_WITH_MEGA,
        actor_ident="p1a: Charizard",
        mega_species_details="Charizard-Mega-Y, L50",
        base_species="Charizard",
        stone_display="Charizardite Y",
        expected_normalized_log_sha256=_log_hash(_RAW_LOG_WITH_MEGA),
    )

    assert binding.detailschange_line_sha256 == hashlib.sha256(
        "|detailschange|p1a: Charizard|Charizard-Mega-Y, L50".encode("utf-8")
    ).hexdigest()
    assert binding.mega_line_sha256 == hashlib.sha256(
        "|-mega|p1a: Charizard|Charizard|Charizardite Y".encode("utf-8")
    ).hexdigest()
    assert binding.normalized_log_sha256 == _log_hash(_RAW_LOG_WITH_MEGA)


def test_bind_protocol_mega_pair_fails_closed_when_no_mega_line_present():
    log_without_mega = "|switch|p1a: Charizard|Charizard, L50|100/100\n|turn|1\n"
    with pytest.raises(MegaEvidenceError, match="no matching"):
        bind_protocol_mega_pair(
            log_without_mega,
            actor_ident="p1a: Charizard",
            mega_species_details="Charizard-Mega-Y, L50",
            base_species="Charizard",
            stone_display="Charizardite Y",
            expected_normalized_log_sha256=_log_hash(log_without_mega),
        )


def test_bind_protocol_mega_pair_fails_closed_on_wrong_stone():
    with pytest.raises(MegaEvidenceError, match="no matching"):
        bind_protocol_mega_pair(
            _RAW_LOG_WITH_MEGA,
            actor_ident="p1a: Charizard",
            mega_species_details="Charizard-Mega-Y, L50",
            base_species="Charizard",
            stone_display="Charizardite X",  # wrong stone -- doesn't match the logged pair
            expected_normalized_log_sha256=_log_hash(_RAW_LOG_WITH_MEGA),
        )


def test_bind_protocol_mega_pair_fails_closed_on_reversed_line_order():
    """Codex re-review: -mega must not be accepted if it precedes its detailschange."""
    with pytest.raises(MegaEvidenceError, match="order"):
        bind_protocol_mega_pair(
            _RAW_LOG_REVERSED_ORDER,
            actor_ident="p1a: Charizard",
            mega_species_details="Charizard-Mega-Y, L50",
            base_species="Charizard",
            stone_display="Charizardite Y",
            expected_normalized_log_sha256=_log_hash(_RAW_LOG_REVERSED_ORDER),
        )


def test_bind_protocol_mega_pair_fails_closed_on_ambiguous_pairing():
    """Codex re-review: more than one matching detailschange/-mega line is ambiguous,
    not a pairable single event -- must reject, not silently pick one."""
    with pytest.raises(MegaEvidenceError, match="ambiguous"):
        bind_protocol_mega_pair(
            _RAW_LOG_AMBIGUOUS_PAIR,
            actor_ident="p1a: Charizard",
            mega_species_details="Charizard-Mega-Y, L50",
            base_species="Charizard",
            stone_display="Charizardite Y",
            expected_normalized_log_sha256=_log_hash(_RAW_LOG_AMBIGUOUS_PAIR),
        )


def test_bind_protocol_mega_pair_fails_closed_on_log_hash_mismatch():
    """Codex re-review: the caller must pass the expected canonical log hash (from the
    battle's result row's normalized_room_log_sha256) and the function must refuse to
    bind evidence to a log that doesn't match it."""
    with pytest.raises(MegaEvidenceError, match="hash mismatch"):
        bind_protocol_mega_pair(
            _RAW_LOG_WITH_MEGA,
            actor_ident="p1a: Charizard",
            mega_species_details="Charizard-Mega-Y, L50",
            base_species="Charizard",
            stone_display="Charizardite Y",
            expected_normalized_log_sha256="0" * 64,  # wrong hash
        )


# ---------------------------------------------------------------------------
# I7a-C capture-boundary fix integration: a realistic pre-click Aerodactyl row
# produced from the ENRICHED prepare_capture (not a hand-rolled dict) plus a
# later Aerodactyl-Mega row must let derive_mega_evidence return evidence.
# This is the exact live-smoke failure mode the fix addresses: before the fix,
# prepare_capture's state_summary showed item=None/item_known=False for the
# hero's own Aerodactyl even though the request carried "aerodactylite" and
# the live decision correctly chose Mega -- derive_mega_evidence raised
# MegaEvidenceError instead of returning evidence.
# ---------------------------------------------------------------------------


def _capture_row(*, decision_index, chosen_mega_slot, actual_choose_string,
                  chosen_candidate_key, species_b, item):
    from showdown_bot.eval.decision_capture import prepare_capture
    from showdown_bot.engine.state import BattleState, PokemonState
    from showdown_bot.models.request import BattleRequest

    poke = {
        "ident": "p1: Aerodactyl", "details": f"{species_b}, L50", "condition": "100/100",
        "active": True, "stats": {"atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100},
        "moves": ["rockslide"], "baseTypes": ["Rock", "Flying"],
    }
    if item is not None:
        poke["item"] = item
    request = BattleRequest.model_validate({
        "active": [
            {"moves": [{"move": "Sneasler move", "id": "closecombat", "pp": 8, "maxpp": 8,
                        "target": "normal", "disabled": False}], "canMegaEvo": False},
            {"moves": [{"move": "Rock Slide", "id": "rockslide", "pp": 8, "maxpp": 8,
                        "target": "normal", "disabled": False}], "canMegaEvo": True},
        ],
        "side": {"name": "Player1", "id": "p1", "pokemon": [
            {"ident": "p1: Sneasler", "details": "Sneasler, L50", "condition": "100/100",
             "active": True, "stats": {"atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100},
             "moves": ["closecombat"], "baseTypes": ["Fighting", "Poison"]},
            poke,
        ]},
        "rqid": decision_index + 1,
    })
    state = BattleState()
    state.sides["p1"]["a"] = PokemonState(species="Sneasler", hp=100, max_hp=100)
    state.sides["p1"]["b"] = PokemonState(species=species_b, hp=100, max_hp=100)
    state.sides["p2"]["a"] = PokemonState(species="Incineroar", hp=100, max_hp=100)

    prepared = prepare_capture(state, request)
    return {
        "battle_id": "b0",
        "decision_index": decision_index,
        "turn_number": decision_index + 1,
        "decision_phase": "regular_turn",
        "chosen_mega_slot": chosen_mega_slot,
        "actual_choose_string": actual_choose_string,
        "chosen_candidate_key": chosen_candidate_key,
        "state_summary": prepared.state_summary,
        "our_side": "p1",
    }


def test_derive_mega_evidence_succeeds_on_enriched_pre_click_capture_row():
    pre_click = _capture_row(
        decision_index=0, chosen_mega_slot=1,
        actual_choose_string="/choose move 1 2, move 4 2 mega|1",
        chosen_candidate_key="k1", species_b="Aerodactyl", item="aerodactylite",
    )
    post_click = _capture_row(
        decision_index=1, chosen_mega_slot=None, actual_choose_string="/choose move 1 2, move 4|2",
        chosen_candidate_key=None, species_b="Aerodactyl-Mega", item="aerodactylite",
    )

    evidence = derive_mega_evidence([pre_click, post_click], our_side="p1")

    assert evidence is not None
    assert evidence.mega_decision_index == 0
    assert evidence.post_mega_decision_index == 1
    assert evidence.post_mega_species == "Aerodactyl-Mega"


def test_derive_mega_evidence_still_fails_closed_without_the_capture_fix():
    """Regression pin: WITHOUT item enrichment (item=None), the pre-click row cannot
    verify the claimed Mega form at all -- this is the exact failure the capture-boundary
    fix eliminates for a real live capture, and it must remain a hard, fail-closed error
    (not silently accepted) for a genuinely unenriched capture."""
    pre_click = _capture_row(
        decision_index=0, chosen_mega_slot=1,
        actual_choose_string="/choose move 1 2, move 4 2 mega|1",
        chosen_candidate_key="k1", species_b="Aerodactyl", item=None,
    )
    post_click = _capture_row(
        decision_index=1, chosen_mega_slot=None, actual_choose_string="/choose move 1 2, move 4|2",
        chosen_candidate_key=None, species_b="Aerodactyl-Mega", item=None,
    )

    with pytest.raises(MegaEvidenceError, match="item"):
        derive_mega_evidence([pre_click, post_click], our_side="p1")
