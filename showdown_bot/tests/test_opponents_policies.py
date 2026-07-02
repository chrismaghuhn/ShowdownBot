"""T3c eval-only policies: greedy_protect + simple_heuristic (deterministic, request-only)."""
from __future__ import annotations

import json
from pathlib import Path

from showdown_bot.engine.moves import get_move_meta
from showdown_bot.engine.state import BattleState, PokemonState
from showdown_bot.eval.opponents.policies import (
    greedy_protect_choice,
    simple_heuristic_choice,
    target_types_for_action,
)
from showdown_bot.models.actions import SlotAction
from showdown_bot.models.request import BattleRequest

_FIX = Path(__file__).parent / "fixtures" / "request_doubles_moves.json"


def _req():
    # Incineroar (slot0): FakeOut(1) / FlareBlitz(2,120bp) / Protect(3) / KnockOff(4,65bp).
    return BattleRequest.model_validate(json.loads(_FIX.read_text()))


def _slot0(out: str) -> str:
    return out[len("/choose "):].split("|")[0].split(", ")[0]


def test_greedy_protect_healthy_attacks_not_protect():
    # T3e Task 2: with no state, HP is treated full -> attack the highest-power move
    # (Flare Blitz, move 2), NOT the degenerate always-Protect (move 3).
    assert _slot0(greedy_protect_choice(_req())).startswith("move 2")


def test_greedy_protect_deterministic():
    assert greedy_protect_choice(_req()) == greedy_protect_choice(_req())


def test_simple_heuristic_picks_highest_base_power():
    assert _slot0(simple_heuristic_choice(_req())).startswith("move 2")  # Flare Blitz (120)


def test_simple_heuristic_deterministic():
    assert simple_heuristic_choice(_req()) == simple_heuristic_choice(_req())


def test_choices_are_legal_choose_strings():
    for out in (greedy_protect_choice(_req()), simple_heuristic_choice(_req())):
        assert out.startswith("/choose ") and out.endswith("|2")  # fixture rqid = 2


# --- T3e Task 1: type-aware simple_heuristic ------------------------------------------

def _move(name, mid, target="normal"):
    return {"move": name, "id": mid, "pp": 16, "maxpp": 16, "target": target, "disabled": False}


def _single_slot_req(moves, *, side_id="p1", rqid=7):
    """A one-active-slot request (slot1 -> pass); side.pokemon empty is fine for these policies."""
    return BattleRequest.model_validate({
        "active": [{"moves": moves}],
        "side": {"id": side_id, "name": "P", "pokemon": []},
        "rqid": rqid,
    })


def _foe_state(*, a_types=None, b_types=None, opp_side="p2"):
    st = BattleState()
    if a_types is not None:
        st.sides[opp_side]["a"] = PokemonState(species="A", types=list(a_types))
    if b_types is not None:
        st.sides[opp_side]["b"] = PokemonState(species="B", types=list(b_types))
    return st


def test_type_aware_low_bp_super_effective_beats_high_bp_resisted():
    req = _single_slot_req([
        _move("Flare Blitz", "flareblitz"),  # idx1: Fire 120
        _move("Rock Tomb", "rocktomb"),      # idx2: Rock 60
    ])
    state = _foe_state(a_types=["Fire", "Flying"], b_types=["Fire", "Flying"])
    # Rock 60 * 4.0 = 240 beats Fire 120 * 0.5 = 60 -> Rock Tomb wins despite lower base power.
    assert _slot0(simple_heuristic_choice(req, state=state, our_side="p1")).startswith("move 2")


def test_falls_back_to_base_power_when_state_none():
    req = _single_slot_req([_move("Flare Blitz", "flareblitz"), _move("Rock Tomb", "rocktomb")])
    out = simple_heuristic_choice(req, state=None, our_side="p1")
    assert _slot0(out).startswith("move 1")          # highest base power (120)
    assert out.startswith("/choose ") and out.endswith("|7")   # still a legal choose


def test_unknown_foe_types_falls_back_to_base_power():
    req = _single_slot_req([_move("Flare Blitz", "flareblitz"), _move("Rock Tomb", "rocktomb")])
    state = _foe_state(a_types=[], b_types=[])        # foes present but types unknown -> neutral
    assert _slot0(simple_heuristic_choice(req, state=state, our_side="p1")).startswith("move 1")


def test_immune_target_avoided_when_positive_option_exists():
    req = _single_slot_req([
        _move("High Horsepower", "highhorsepower"),  # idx1: Ground 95 (immune vs Flying -> 0)
        _move("Body Slam", "bodyslam"),              # idx2: Normal 85 (neutral -> 85)
    ])
    state = _foe_state(a_types=["Flying"], b_types=["Flying"])
    # Base power alone would pick the 95-BP Ground move; type-aware must avoid the immune 0.
    assert _slot0(simple_heuristic_choice(req, state=state, our_side="p1")).startswith("move 2")


def test_spread_uses_max_effectiveness_over_foes():
    req = _single_slot_req([
        _move("Earth Power", "earthpower"),                        # idx1: Ground 90 single-target
        _move("Heat Wave", "heatwave", target="allAdjacentFoes"),  # idx2: Fire 95 spread
    ])
    # foe a Water (Fire 0.5), foe b Grass (Fire 2.0) -> spread max = 2.0 -> 95*2 = 190,
    # which beats Earth Power's best single-target (90 vs Water). Proves MAX over both foes,
    # including foe b (target-1 slot alone would give only 0.5).
    state = _foe_state(a_types=["Water"], b_types=["Grass"])
    assert _slot0(simple_heuristic_choice(req, state=state, our_side="p1")).startswith("move 2")


def test_target_types_for_action_single_and_spread():
    state = _foe_state(a_types=["Water"], b_types=["Grass"])
    hh = get_move_meta("highhorsepower")   # single-target
    hw = get_move_meta("heatwave")         # spread
    a1 = SlotAction(kind="move", move_index=1, target=1)
    a2 = SlotAction(kind="move", move_index=1, target=2)
    spread = SlotAction(kind="move", move_index=2, target=None)
    assert target_types_for_action(hh, a1, state, "p1") == [("Water",)]       # target 1 -> opp "a"
    assert target_types_for_action(hh, a2, state, "p1") == [("Grass",)]       # target 2 -> opp "b"
    assert target_types_for_action(hw, spread, state, "p1") == [("Water",), ("Grass",)]  # both foes
    assert target_types_for_action(hh, a1, None, "p1") == []                  # no state
    assert target_types_for_action(hh, a1, state, None) == []                 # no side


def test_missing_move_metadata_is_safe_and_legal():
    req = _single_slot_req([_move("Nonexistent Move XYZ", "nonexistentmovexyz")])
    state = _foe_state(a_types=["Water"], b_types=["Grass"])
    out = simple_heuristic_choice(req, state=state, our_side="p1")
    assert out.startswith("/choose ") and out.endswith("|7")   # never crashes, stays legal
    assert _slot0(out).startswith("move 1")


def test_type_aware_deterministic():
    req = _single_slot_req([_move("Flare Blitz", "flareblitz"), _move("Rock Tomb", "rocktomb")])
    state = _foe_state(a_types=["Fire", "Flying"], b_types=["Fire", "Flying"])
    a = simple_heuristic_choice(req, state=state, our_side="p1")
    b = simple_heuristic_choice(req, state=state, our_side="p1")
    assert a == b


# --- T3e Task 2: situational greedy_protect (HP-gated + no-double-protect) -------------

def _protect_move():
    return _move("Protect", "protect", target="self")


def _atk_protect():
    """One damaging move (idx1 Flare Blitz) + Protect (idx2)."""
    return [_move("Flare Blitz", "flareblitz"), _protect_move()]


def _two_slot_req(moves0, moves1, *, side_id="p1", rqid=7):
    return BattleRequest.model_validate({
        "active": [{"moves": moves0}, {"moves": moves1}],
        "side": {"id": side_id, "name": "P", "pokemon": []},
        "rqid": rqid,
    })


def _our_state(*, a_hp=1.0, b_hp=1.0, our_side="p1"):
    st = BattleState()
    st.sides[our_side]["a"] = PokemonState(species="A", max_hp=100, hp=round(a_hp * 100))
    st.sides[our_side]["b"] = PokemonState(species="B", max_hp=100, hp=round(b_hp * 100))
    return st


def _both(out):
    body = out[len("/choose "):].split("|")[0]
    s0, s1 = body.split(", ")
    return s0, s1


def _is_protect_cmd(slot_cmd: str) -> bool:
    return slot_cmd.startswith("move 2")   # Protect is move index 2 in _atk_protect


def test_greedy_both_healthy_both_attack():
    req = _two_slot_req(_atk_protect(), _atk_protect())
    s0, s1 = _both(greedy_protect_choice(req, state=_our_state(a_hp=1.0, b_hp=1.0), our_side="p1"))
    assert s0.startswith("move 1") and s1.startswith("move 1")   # both attack, neither Protects


def test_greedy_low_hp_protects_healthy_partner_attacks():
    req = _two_slot_req(_atk_protect(), _atk_protect())
    s0, s1 = _both(greedy_protect_choice(req, state=_our_state(a_hp=0.3, b_hp=1.0), our_side="p1"))
    assert _is_protect_cmd(s0)          # low-HP slot0 Protects
    assert s1.startswith("move 1")      # healthy slot1 attacks


def test_greedy_both_low_at_most_one_protect_deterministic():
    req = _two_slot_req(_atk_protect(), _atk_protect())
    st = _our_state(a_hp=0.3, b_hp=0.3)
    out = greedy_protect_choice(req, state=st, our_side="p1")
    s0, s1 = _both(out)
    assert sum(_is_protect_cmd(s) for s in (s0, s1)) == 1        # no-double-protect: exactly one
    assert out == greedy_protect_choice(req, state=st, our_side="p1")   # deterministic


def test_greedy_state_none_attacks_and_legal():
    req = _two_slot_req(_atk_protect(), _atk_protect())
    out = greedy_protect_choice(req, state=None, our_side="p1")
    s0, s1 = _both(out)
    assert s0.startswith("move 1") and s1.startswith("move 1")   # full HP -> attack
    assert out.startswith("/choose ") and out.endswith("|7")


def test_greedy_legal_fallback_when_no_pairs():
    req = BattleRequest.model_validate({"active": [], "side": {"id": "p1", "pokemon": []}, "rqid": 5})
    assert greedy_protect_choice(req) == "/choose default|5"


def test_greedy_two_calls_equal_with_state():
    req = _two_slot_req(_atk_protect(), _atk_protect())
    st = _our_state(a_hp=0.3, b_hp=1.0)
    assert greedy_protect_choice(req, state=st, our_side="p1") == \
        greedy_protect_choice(req, state=st, our_side="p1")
