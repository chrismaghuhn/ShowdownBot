"""group_a_fixture_dto binds the WHOLE §2.7 group-A input (C3-fix).

fixture_input_hash is only sound if identical hash => identical scoring inputs => identical
n_candidates (the dataset fixture-identity check rests on exactly that). A reduced descriptor
that enumerated a board slice (species/item per slot) omitted moves, spreads and most of the
request, so two genuinely different boards could collide. These tests pin the property the
descriptor lacked: any material change to the inputs flips the hash, and only an identical
input repeats it -- because the builder hands the raw objects to encode(), which is exhaustive.
"""
from __future__ import annotations

from showdown_bot.battle.actions import enumerate_my_actions
from showdown_bot.engine.belief.hypotheses import SpeciesSpreads, SpreadBook, SpreadPreset
from showdown_bot.engine.calc_profile import calc_profile_from_config
from showdown_bot.engine.format_config import load_format_config
from showdown_bot.engine.state import BattleState, PokemonState, to_id
from showdown_bot.models.request import BattleRequest
from showdown_bot.eval.decision_profile import fixture_input_hash, group_a_fixture_dto

FORMAT = "gen9championsvgc2026regma"
_J = SpreadPreset(nature="Jolly", evs={"atk": 32, "spe": 32, "hp": 2})
_S = SpeciesSpreads(offense=_J, defense=_J)
_PROFILE = calc_profile_from_config(load_format_config(FORMAT))


def _slots(ns):
    return [{"move": n, "id": to_id(n), "pp": 8, "maxpp": 8, "target": "normal", "disabled": False} for n in ns]


def _req(move="Rock Slide"):
    return BattleRequest.model_validate({
        "active": [{"moves": _slots([move]), "canMegaEvo": True},
                   {"moves": _slots(["Moonblast"]), "canMegaEvo": False}],
        "side": {"name": "P1", "id": "p1", "pokemon": [
            {"ident": "p1: Aerodactyl", "details": "Aerodactyl, L50", "condition": "100/100",
             "active": True, "stats": {"atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100},
             "moves": [to_id(move)], "baseTypes": ["Rock", "Flying"], "item": "Aerodactylite"},
            {"ident": "p1: Whimsicott", "details": "Whimsicott, L50", "condition": "100/100",
             "active": True, "stats": {"atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100},
             "moves": ["moonblast"], "baseTypes": ["Grass", "Fairy"]}]}, "rqid": 1})


def _state(*, foe_item="Aerodactylite", trick_room=False):
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Aerodactyl", base_species_id="aerodactyl",
                                       item="Aerodactylite", types=["Rock", "Flying"], hp=100, max_hp=100)
    st.sides["p2"]["a"] = PokemonState(species="Aerodactyl", base_species_id="aerodactyl",
                                       item=foe_item, item_known=True, types=["Rock", "Flying"], hp=100, max_hp=100)
    st.field.trick_room = trick_room
    return st


def _hash(*, req=None, state=None, our_spreads=None, opp_sets=None):
    req = req if req is not None else _req()
    state = state if state is not None else _state()
    dto = group_a_fixture_dto(
        req=req, state=state, my_actions=enumerate_my_actions(req),
        book=SpreadBook(default=_S), our_spreads=our_spreads or {"aerodactyl": _S},
        opp_sets=opp_sets, calc_profile=_PROFILE, our_side="p1", opp_side="p2",
    )
    return fixture_input_hash(dto)


def test_identical_inputs_repeat_the_hash():
    assert _hash() == _hash()


def test_a_changed_move_flips_the_hash():
    assert _hash(req=_req("Earthquake")) != _hash()


def test_a_changed_spread_ev_flips_the_hash():
    fat = SpeciesSpreads(offense=SpreadPreset(nature="Jolly", evs={"atk": 100, "spe": 32, "hp": 2}),
                         defense=_J)
    assert _hash(our_spreads={"aerodactyl": fat}) != _hash()


def test_a_changed_item_flips_the_hash():
    # foe holds a different (non-Mega) item -> a genuinely different board.
    assert _hash(state=_state(foe_item="Leftovers")) != _hash()


def test_trick_room_flips_the_hash():
    assert _hash(state=_state(trick_room=True)) != _hash()


def test_opp_sets_flip_the_hash():
    preset = SpeciesSpreads(offense=SpreadPreset(nature="Bold", evs={"hp": 32}), defense=_J)
    assert _hash(opp_sets={"aerodactyl": preset}) != _hash()
