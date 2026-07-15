from __future__ import annotations

import copy

import pytest

from showdown_bot.battle.actions import enumerate_my_actions
from showdown_bot.battle.mega_scoring import build_own_mega_contexts
from showdown_bot.battle.oracle import DamageOracle
from showdown_bot.engine.belief.hypotheses import SpreadBook
from showdown_bot.engine.calc.client import SubprocessCalcBackend
from showdown_bot.engine.calc.models import CalcMon
from showdown_bot.engine.species_meta import species_meta_table
from showdown_bot.engine.state import BattleState, PokemonState, to_id
from showdown_bot.models.request import BattleRequest

# ---------------------------------------------------------------------------
# I7a-B Task 2: MegaEvaluationContext + post-Mega plan speed
# ---------------------------------------------------------------------------


def _build_req(
    *, a_species: str, a_item: str, a_moves: list[str], a_can_mega: bool,
    b_species: str, b_moves: list[str],
) -> BattleRequest:
    return BattleRequest.model_validate({
        "active": [
            {
                "moves": [
                    {
                        "move": name, "id": to_id(name), "pp": 8, "maxpp": 8,
                        "target": "normal", "disabled": False,
                    }
                    for name in a_moves
                ],
                "canMegaEvo": a_can_mega,
            },
            {
                "moves": [
                    {
                        "move": name, "id": to_id(name), "pp": 8, "maxpp": 8,
                        "target": "normal", "disabled": False,
                    }
                    for name in b_moves
                ],
                "canMegaEvo": False,
            },
        ],
        "side": {
            "name": "Player1",
            "id": "p1",
            "pokemon": [
                {
                    "ident": f"p1: {a_species}",
                    "details": f"{a_species}, L50",
                    "condition": "100/100",
                    "active": True,
                    "stats": {"atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100},
                    "moves": [to_id(n) for n in a_moves],
                    "baseTypes": ["Normal"],
                    "item": a_item,
                },
                {
                    "ident": f"p1: {b_species}",
                    "details": f"{b_species}, L50",
                    "condition": "100/100",
                    "active": True,
                    "stats": {"atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100},
                    "moves": [to_id(n) for n in b_moves],
                    "baseTypes": ["Normal"],
                },
            ],
        },
        "rqid": 1,
    })


def _build_state(a_species: str, a_item: str, b_species: str, foe_species: str) -> BattleState:
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(
        species=a_species, base_species_id=to_id(a_species), item=a_item,
        types=["Normal"], hp=100, max_hp=100,
    )
    st.sides["p1"]["b"] = PokemonState(
        species=b_species, base_species_id=to_id(b_species),
        types=["Normal"], hp=100, max_hp=100,
    )
    st.sides["p2"]["a"] = PokemonState(
        species=foe_species, base_species_id=to_id(foe_species),
        types=["Normal"], hp=100, max_hp=100,
    )
    return st


@pytest.fixture
def speed_oracle(calc_profile):
    from showdown_bot.engine.speed import SpeedOracle

    return SpeedOracle(stats_backend=SubprocessCalcBackend(), profile=calc_profile)


def _build_aerodactyl_contexts(speed_oracle, aerodactyl_spreads, calc_profile):
    req = _build_req(
        a_species="Aerodactyl", a_item="Aerodactylite", a_moves=["Rock Slide"],
        a_can_mega=True, b_species="Whimsicott", b_moves=["Moonblast"],
    )
    state = _build_state("Aerodactyl", "Aerodactylite", "Whimsicott", "Incineroar")
    spreads = {"aerodactyl": aerodactyl_spreads, "whimsicott": aerodactyl_spreads}
    book = SpreadBook(default=aerodactyl_spreads)
    oracle = DamageOracle()
    my_actions = enumerate_my_actions(req)
    contexts = build_own_mega_contexts(
        req, state, our_side="p1", opp_side="p2", book=book, oracle=oracle,
        speed_oracle=speed_oracle, species_meta=species_meta_table(),
        our_spreads=spreads, opp_sets=None, calc_profile=calc_profile,
        my_actions=my_actions,
    )
    return req, state, contexts


def test_build_own_mega_contexts_returns_none_and_mega_slot_branches(
    speed_oracle, aerodactyl_spreads, calc_profile,
):
    req, state, contexts = _build_aerodactyl_contexts(speed_oracle, aerodactyl_spreads, calc_profile)

    slots = {c.own_mega_slot for c in contexts}
    assert slots == {None, 0}
    for c in contexts:
        assert c.foe_mega_slot is None
        assert c.branch_weight == 1.0
        assert c.activation_order is None
        assert c.projected_state is not state
        assert c.plans  # at least one candidate joint action was planned

    mega_ctx = next(c for c in contexts if c.own_mega_slot == 0)
    assert mega_ctx.projected_state.sides["p1"]["a"].species == "Aerodactyl-Mega"

    none_ctx = next(c for c in contexts if c.own_mega_slot is None)
    assert none_ctx.projected_state.sides["p1"]["a"].species == "Aerodactyl"


def test_mega_context_damage_model_hyps_use_projected_species_and_ability(
    speed_oracle, aerodactyl_spreads, calc_profile,
):
    _req, _state, contexts = _build_aerodactyl_contexts(speed_oracle, aerodactyl_spreads, calc_profile)

    mega_ctx = next(c for c in contexts if c.own_mega_slot == 0)
    hyp = mega_ctx.damage_model.hyps[("p1", "a")]
    assert hyp.species == "Aerodactyl-Mega"
    assert hyp.ability == "Tough Claws"

    none_ctx = next(c for c in contexts if c.own_mega_slot is None)
    hyp0 = none_ctx.damage_model.hyps[("p1", "a")]
    assert hyp0.species == "Aerodactyl"


def test_build_own_mega_contexts_does_not_mutate_live_state_or_request(
    speed_oracle, aerodactyl_spreads, calc_profile,
):
    req = _build_req(
        a_species="Aerodactyl", a_item="Aerodactylite", a_moves=["Rock Slide"],
        a_can_mega=True, b_species="Whimsicott", b_moves=["Moonblast"],
    )
    state = _build_state("Aerodactyl", "Aerodactylite", "Whimsicott", "Incineroar")
    spreads = {"aerodactyl": aerodactyl_spreads, "whimsicott": aerodactyl_spreads}
    book = SpreadBook(default=aerodactyl_spreads)
    oracle = DamageOracle()
    my_actions = enumerate_my_actions(req)

    before_sides = copy.deepcopy(state.sides)
    before_field = copy.deepcopy(state.field)
    before_mega_spent = copy.deepcopy(state.side_mega_spent)
    before_req = req.model_copy(deep=True)

    contexts = build_own_mega_contexts(
        req, state, our_side="p1", opp_side="p2", book=book, oracle=oracle,
        speed_oracle=speed_oracle, species_meta=species_meta_table(),
        our_spreads=spreads, opp_sets=None, calc_profile=calc_profile,
        my_actions=my_actions,
    )

    assert state.sides == before_sides
    assert state.field == before_field
    assert state.side_mega_spent == before_mega_spent
    assert req == before_req
    for ctx in contexts:
        assert ctx.projected_state is not state
        assert ctx.projected_state.sides is not state.sides


def test_mega_context_plan_speed_overrides_to_projected_222(
    speed_oracle, aerodactyl_spreads, calc_profile,
):
    # Ground truth: BASE (non-Mega) Aerodactyl's request speed at the same
    # spread used for the projected Mega form (already pinned at 222 by
    # test_i7a_foundation.test_aerodactyl_gen0_speed_222).
    mega_calc_mon = CalcMon(
        species="Aerodactyl", level=50, nature="Jolly",
        evs={"atk": 32, "spe": 32, "hp": 2}, ivs={"spe": 31},
    )
    backend = SubprocessCalcBackend()
    base_stats = backend.stats_batch([mega_calc_mon], gen=0)
    assert base_stats[0]["spe"] == 200

    req = _build_req(
        a_species="Aerodactyl", a_item="Aerodactylite", a_moves=["Rock Slide"],
        a_can_mega=True, b_species="Whimsicott", b_moves=["Moonblast"],
    )
    state = _build_state("Aerodactyl", "Aerodactylite", "Whimsicott", "Incineroar")
    spreads = {"aerodactyl": aerodactyl_spreads, "whimsicott": aerodactyl_spreads}
    book = SpreadBook(default=aerodactyl_spreads)
    oracle = DamageOracle()
    my_actions = enumerate_my_actions(req)

    before_state = copy.deepcopy(state)
    before_req_stats = copy.deepcopy(req.side.pokemon[0].stats)

    contexts = build_own_mega_contexts(
        req, state, our_side="p1", opp_side="p2", book=book, oracle=oracle,
        speed_oracle=speed_oracle, species_meta=species_meta_table(),
        our_spreads=spreads, opp_sets=None, calc_profile=calc_profile,
        my_actions=my_actions,
    )

    mega_ctx = next(c for c in contexts if c.own_mega_slot == 0)
    plan = next(iter(mega_ctx.plans.values()))
    slot_a_plan = next(p for p in plan if p.slot == "a")
    assert slot_a_plan.speed == 222

    assert state.sides == before_state.sides
    assert req.side.pokemon[0].stats == before_req_stats


def test_mega_sol_fire_boosted_water_weakened_partner_and_foe_unchanged(
    speed_oracle, aerodactyl_spreads, calc_profile,
):
    """T28: projected Mega Sol boosts Meganium-Mega's own Fire move and weakens
    its own Water move vs. a neutral (ability-blanked) baseline. Partner and
    foe moves are untouched (Mega Sol never sets global weather -- it's a
    per-attacker check in the calc, not a field effect)."""
    from showdown_bot.battle.resolve import PlannedAction
    from showdown_bot.battle.evaluate import DamageModel
    from showdown_bot.engine.moves import get_move_meta

    req = _build_req(
        a_species="Meganium", a_item="Meganiumite", a_moves=["Overheat", "Hydro Pump"],
        a_can_mega=True, b_species="Whimsicott", b_moves=["Moonblast"],
    )
    state = _build_state("Meganium", "Meganiumite", "Whimsicott", "Incineroar")
    spreads = {
        "meganium": aerodactyl_spreads, "whimsicott": aerodactyl_spreads,
        "incineroar": aerodactyl_spreads,
    }
    book = SpreadBook(default=aerodactyl_spreads)
    oracle = DamageOracle()
    my_actions = enumerate_my_actions(req)

    contexts = build_own_mega_contexts(
        req, state, our_side="p1", opp_side="p2", book=book, oracle=oracle,
        speed_oracle=speed_oracle, species_meta=species_meta_table(),
        our_spreads=spreads, opp_sets=None, calc_profile=calc_profile,
        my_actions=my_actions,
    )
    mega_context = next(c for c in contexts if c.own_mega_slot == 0)
    assert mega_context.projected_state.field.weather is None

    mega_model = mega_context.damage_model

    neutral_state = copy.deepcopy(mega_context.projected_state)
    # An empty-string ability is falsy on the calc side and falls back to the
    # species' declared default ability (which for Meganium-Mega IS "Mega
    # Sol") -- use a real, different ability so the payload actually diverges.
    neutral_state.sides["p1"]["a"].ability = "Overgrow"
    neutral_model = DamageModel(
        neutral_state, "p1", "p2", book=book, oracle=oracle,
        field=neutral_state.field, our_spreads=spreads, opp_sets=None,
        calc_profile=calc_profile,
    )

    our_fire_action = PlannedAction(
        "p1", "a", "move", speed=222, move=get_move_meta("Overheat"),
        target=("p2", "a"), is_ours=True, is_mega=True,
    )
    our_water_action = PlannedAction(
        "p1", "a", "move", speed=222, move=get_move_meta("Hydro Pump"),
        target=("p2", "a"), is_ours=True, is_mega=True,
    )
    partner_action = PlannedAction(
        "p1", "b", "move", speed=100, move=get_move_meta("Moonblast"),
        target=("p2", "a"), is_ours=True,
    )
    foe_action = PlannedAction(
        "p2", "a", "move", speed=100, move=get_move_meta("Knock Off"),
        target=("p1", "a"), is_ours=False,
    )

    foe_target = mega_context.projected_state.sides["p2"]["a"]
    our_target = mega_context.projected_state.sides["p1"]["a"]

    action_groups = [
        [our_fire_action, our_water_action, partner_action],
        [foe_action],
    ]
    mega_model.enqueue(action_groups)
    neutral_model.enqueue(action_groups)
    oracle.flush()

    fire_mega = mega_model.damage_fn(our_fire_action, foe_target)
    fire_neutral = neutral_model.damage_fn(our_fire_action, foe_target)
    water_mega = mega_model.damage_fn(our_water_action, foe_target)
    water_neutral = neutral_model.damage_fn(our_water_action, foe_target)

    assert fire_mega > fire_neutral
    assert water_mega < water_neutral
    assert mega_model.damage_fn(partner_action, foe_target) == neutral_model.damage_fn(
        partner_action, foe_target
    )
    assert mega_model.damage_fn(foe_action, our_target) == neutral_model.damage_fn(
        foe_action, our_target
    )
    assert mega_context.projected_state.field.weather is None
