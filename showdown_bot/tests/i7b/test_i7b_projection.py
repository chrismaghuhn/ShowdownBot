"""I7b-B: mega_activation_order_key, WeightedMegaProjection, compose_mega_projection_branches."""
from __future__ import annotations

import pytest

from showdown_bot.engine.mega_form import mega_form_for
from showdown_bot.engine.mega_projection import (
    WeightedMegaProjection,
    compose_mega_projection_branches,
    copy_battle_state,
    project_mega,
)
from showdown_bot.engine.speed import mega_activation_order_key
from showdown_bot.engine.state import BattleState, FieldState, PokemonState


def test_no_trick_room_higher_speed_sorts_first():
    field = FieldState()
    keyed = sorted([("slow", 80), ("fast", 150)], key=lambda t: mega_activation_order_key(t[1], field))
    assert keyed[0][0] == "fast"


def test_trick_room_lower_speed_sorts_first():
    field = FieldState(trick_room=True)
    keyed = sorted([("slow", 80), ("fast", 150)], key=lambda t: mega_activation_order_key(t[1], field))
    assert keyed[0][0] == "slow"


def test_matches_sort_actions_sign_convention():
    """mega_activation_order_key must use the IDENTICAL sign convention as
    resolve.sort_actions -- not an independently-invented one."""
    from showdown_bot.battle.resolve import sort_actions, PlannedAction
    from showdown_bot.engine.moves import get_move_meta

    field = FieldState(trick_room=True)
    a = PlannedAction(side="p1", slot="a", kind="move", speed=150, move=get_move_meta("Tackle"))
    b = PlannedAction(side="p2", slot="a", kind="move", speed=80, move=get_move_meta("Tackle"))
    resolver_order = [act.slot + act.side for act in sort_actions([a, b], field)]
    key_order = sorted([("a" + "p1", 150), ("a" + "p2", 80)], key=lambda t: mega_activation_order_key(t[1], field))
    assert [x[0] for x in key_order] == resolver_order


# --- Task 2: side-aware project_mega contract -------------------------------


def _dual_capable_state() -> BattleState:
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Aerodactyl", item="aerodactylite", item_known=True, hp=100, max_hp=100)
    st.sides["p1"]["b"] = PokemonState(species="Sneasler", hp=100, max_hp=100)
    st.sides["p2"]["a"] = PokemonState(species="Meganium", item="meganiumite", item_known=True, hp=100, max_hp=100)
    st.sides["p2"]["b"] = PokemonState(species="Incineroar", hp=100, max_hp=100)
    return st


def test_project_mega_for_foe_side_uses_opp_set_lookup_not_our_spreads(i7b_projection_env, opp_sets_meganium):
    """A foe-side project_mega call must resolve its spread via lookup_opp_set
    (the curated opp_sets/likely_sets source), never lookup_our_spreads."""
    state = _dual_capable_state()
    form = mega_form_for("Meganium", "Meganiumite")

    result = project_mega(
        state, "p2", "a", form, species_meta=i7b_projection_env["species_meta"],
        speed_oracle=i7b_projection_env["speed_oracle"], calc_profile=i7b_projection_env["calc_profile"],
        is_ours=False, opp_sets=opp_sets_meganium, book=None,
    )
    assert result.projected_state.sides["p2"]["a"].species == "Meganium-Mega"
    assert result.effective_speed > 0


def test_project_mega_for_foe_side_without_any_opp_set_or_book_fails_closed(i7b_projection_env):
    """No spread source at all for the foe -- must raise MissingMegaSpreadError,
    the same fail-closed contract the own-side path already has, never silently
    default to some own-side spread."""
    from showdown_bot.engine.speed import MissingMegaSpreadError

    state = _dual_capable_state()
    form = mega_form_for("Meganium", "Meganiumite")
    with pytest.raises(MissingMegaSpreadError):
        project_mega(
            state, "p2", "a", form, species_meta=i7b_projection_env["species_meta"],
            speed_oracle=i7b_projection_env["speed_oracle"], calc_profile=i7b_projection_env["calc_profile"],
            is_ours=False, opp_sets=None, book=None,
        )


def test_project_mega_for_foe_side_accepts_book_without_opp_sets(i7b_projection_env):
    """The real SpeedOracle contract checks the SpreadBook first and only then
    falls back to opp_sets. project_mega must not reject this valid book-only
    path before SpeedOracle gets a chance to resolve it."""
    from showdown_bot.engine.belief.hypotheses import SpeciesSpreads, SpreadBook, SpreadPreset

    state = _dual_capable_state()
    form = mega_form_for("Meganium", "Meganiumite")
    preset = SpreadPreset(nature="Bold", evs={"hp": 32, "def": 32}, items=["Meganiumite"])
    spreads = SpeciesSpreads(offense=preset, defense=preset)
    book = SpreadBook(default=spreads, species={"meganium": spreads})

    result = project_mega(
        state, "p2", "a", form, species_meta=i7b_projection_env["species_meta"],
        speed_oracle=i7b_projection_env["speed_oracle"], calc_profile=i7b_projection_env["calc_profile"],
        is_ours=False, opp_sets=None, book=book,
    )
    assert result.projected_state.sides["p2"]["a"].species == "Meganium-Mega"
    assert result.effective_speed > 0


def test_project_mega_own_side_default_is_byte_identical_to_before(i7b_projection_env, i7b_aerodactyl_spreads):
    """Regression: every existing I7a call site omits is_ours/opp_sets/book --
    the own-side default behavior (lookup_our_spreads, is_ours=True) must be
    completely unchanged."""
    state = _dual_capable_state()
    form = mega_form_for("Aerodactyl", "Aerodactylite")
    result = project_mega(
        state, "p1", "a", form, species_meta=i7b_projection_env["species_meta"],
        speed_oracle=i7b_projection_env["speed_oracle"], calc_profile=i7b_projection_env["calc_profile"],
        spread_lookup=i7b_aerodactyl_spreads,
    )
    assert result.projected_state.sides["p1"]["a"].species == "Aerodactyl-Mega"


# --- Task 3: WeightedMegaProjection / compose_mega_projection_branches -------


def _dual_mega_state() -> BattleState:
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Aerodactyl", item="aerodactylite", item_known=True, hp=100, max_hp=100)
    st.sides["p1"]["b"] = PokemonState(species="Sneasler", hp=100, max_hp=100)
    st.sides["p2"]["a"] = PokemonState(species="Meganium", item="meganiumite", item_known=True, hp=100, max_hp=100)
    st.sides["p2"]["b"] = PokemonState(species="Incineroar", hp=100, max_hp=100)
    return st


def test_unequal_pre_mega_speed_yields_one_full_weight_branch(i7b_projection_env, i7b_aerodactyl_spreads, opp_sets_meganium):
    # Aerodactyl (~200 pre-mega speed) unambiguously outspeeds Meganium (100) here.
    state = _dual_mega_state()
    activations = [
        ("p1", "a", mega_form_for("Aerodactyl", "Aerodactylite")),
        ("p2", "a", mega_form_for("Meganium", "Meganiumite")),
    ]
    branches = compose_mega_projection_branches(
        state, activations, our_side="p1", speed_oracle=i7b_projection_env["speed_oracle"],
        our_spreads=i7b_aerodactyl_spreads, opp_sets=opp_sets_meganium, book=None,
        species_meta=i7b_projection_env["species_meta"], calc_profile=i7b_projection_env["calc_profile"],
    )
    assert len(branches) == 1
    assert all(isinstance(b, WeightedMegaProjection) for b in branches)
    assert branches[0].weight == 1.0
    assert branches[0].activation_order[0] == ("p1", "a")  # Aerodactyl (faster) activates first


def test_equal_pre_mega_speed_yields_two_half_weight_branches(
    i7b_projection_env, i7b_aerodactyl_spreads, opp_sets_meganium, monkeypatch,
):
    """Force equal pre-mega speed via a direct monkeypatch on speed_for_species
    (real fixture, patched return value -- not a fake stand-in class)."""
    state = _dual_mega_state()
    activations = [
        ("p1", "a", mega_form_for("Aerodactyl", "Aerodactylite")),
        ("p2", "a", mega_form_for("Meganium", "Meganiumite")),
    ]
    monkeypatch.setattr(
        i7b_projection_env["speed_oracle"], "speed_for_species", lambda **kwargs: 150,
    )
    branches = compose_mega_projection_branches(
        state, activations, our_side="p1", speed_oracle=i7b_projection_env["speed_oracle"],
        our_spreads=i7b_aerodactyl_spreads, opp_sets=opp_sets_meganium, book=None,
        species_meta=i7b_projection_env["species_meta"], calc_profile=i7b_projection_env["calc_profile"],
    )
    assert len(branches) == 2
    assert {b.weight for b in branches} == {0.5}
    orders = {b.activation_order for b in branches}
    assert orders == {
        (("p1", "a"), ("p2", "a")),
        (("p2", "a"), ("p1", "a")),
    }  # both permutations present, no third/duplicate order


def test_compose_never_mutates_input_state(i7b_projection_env, i7b_aerodactyl_spreads, opp_sets_meganium):
    state = _dual_mega_state()
    before = copy_battle_state(state)
    activations = [
        ("p1", "a", mega_form_for("Aerodactyl", "Aerodactylite")),
        ("p2", "a", mega_form_for("Meganium", "Meganiumite")),
    ]
    compose_mega_projection_branches(
        state, activations, our_side="p1", speed_oracle=i7b_projection_env["speed_oracle"],
        our_spreads=i7b_aerodactyl_spreads, opp_sets=opp_sets_meganium, book=None,
        species_meta=i7b_projection_env["species_meta"], calc_profile=i7b_projection_env["calc_profile"],
    )
    assert state == before


def test_weather_ordering_follows_the_LAST_processed_activator_not_the_first(
    i7b_projection_env, i7b_froslass_spreads, i7b_opp_sets_tyranitar,
):
    """Froslass-Mega (Snow Warning) vs Tyranitar-Mega (Sand Stream), T26 §1,
    CORRECTED per verified pinned Showdown mechanics (audit §Rev.2): the queue
    processes the FASTER pre-mega activator's megaEvo action first (sim/battle.ts
    comparePriority), which fires its weather ability's onStart first
    (sim/pokemon.ts setAbility -> singleEvent('Start', ...) on Mega Evolution,
    confirmed by reading the pinned f8ac140 source) -- then the SLOWER
    activator's megaEvo processes second and its OWN weather ability's onStart
    unconditionally OVERWRITES the field (data/abilities.ts's onStart calls
    field.setWeather(...) unconditionally, no "first setter wins" guard). The
    SLOWER (later-processed) activator's weather is therefore what remains
    active -- NOT the faster one's. This implements the binding Rev. 10 correction
    and matches Rev. 9's own tie-case prose ("last weather-setting ability wins within that
    branch") -- one consistent rule governs both the unequal and tied cases."""
    state = BattleState()
    state.sides["p1"]["a"] = PokemonState(species="Froslass", item="froslassite", item_known=True, hp=100, max_hp=100)
    state.sides["p1"]["b"] = PokemonState(species="Sneasler", hp=100, max_hp=100)
    state.sides["p2"]["a"] = PokemonState(species="Tyranitar", item="tyranitarite", item_known=True, hp=100, max_hp=100)
    state.sides["p2"]["b"] = PokemonState(species="Incineroar", hp=100, max_hp=100)
    activations = [
        ("p1", "a", mega_form_for("Froslass", "Froslassite")),
        ("p2", "a", mega_form_for("Tyranitar", "Tyranitarite")),
    ]
    branches = compose_mega_projection_branches(
        state, activations, our_side="p1", speed_oracle=i7b_projection_env["speed_oracle"],
        our_spreads=i7b_froslass_spreads, opp_sets=i7b_opp_sets_tyranitar, book=None,
        species_meta=i7b_projection_env["species_meta"], calc_profile=i7b_projection_env["calc_profile"],
    )
    assert len(branches) == 1
    last_side, last_slot = branches[0].activation_order[-1]
    expected_weather = "snowscape" if (last_side, last_slot) == ("p1", "a") else "sandstorm"
    assert branches[0].projected_state.field.weather == expected_weather
    # Sanity: this is genuinely the SLOWER activator, not accidentally the faster one.
    assert branches[0].activation_order[-1] != branches[0].activation_order[0]


def test_trick_room_reverses_activation_order_vs_no_tr(i7b_projection_env, i7b_froslass_spreads, i7b_opp_sets_tyranitar, monkeypatch):
    """T26 §2: same speeds, Trick Room on -- activation order reversed vs the
    no-TR unequal-speed case above."""
    state = BattleState()
    state.field.trick_room = True
    state.sides["p1"]["a"] = PokemonState(species="Froslass", item="froslassite", item_known=True, hp=100, max_hp=100)
    state.sides["p1"]["b"] = PokemonState(species="Sneasler", hp=100, max_hp=100)
    state.sides["p2"]["a"] = PokemonState(species="Tyranitar", item="tyranitarite", item_known=True, hp=100, max_hp=100)
    state.sides["p2"]["b"] = PokemonState(species="Incineroar", hp=100, max_hp=100)
    activations = [
        ("p1", "a", mega_form_for("Froslass", "Froslassite")),
        ("p2", "a", mega_form_for("Tyranitar", "Tyranitarite")),
    ]
    tr_branches = compose_mega_projection_branches(
        state, activations, our_side="p1", speed_oracle=i7b_projection_env["speed_oracle"],
        our_spreads=i7b_froslass_spreads, opp_sets=i7b_opp_sets_tyranitar, book=None,
        species_meta=i7b_projection_env["species_meta"], calc_profile=i7b_projection_env["calc_profile"],
    )
    state.field.trick_room = False
    no_tr_branches = compose_mega_projection_branches(
        state, activations, our_side="p1", speed_oracle=i7b_projection_env["speed_oracle"],
        our_spreads=i7b_froslass_spreads, opp_sets=i7b_opp_sets_tyranitar, book=None,
        species_meta=i7b_projection_env["species_meta"], calc_profile=i7b_projection_env["calc_profile"],
    )
    assert len(tr_branches) == 1 and len(no_tr_branches) == 1
    assert tr_branches[0].activation_order != no_tr_branches[0].activation_order
    assert tr_branches[0].activation_order == tuple(reversed(no_tr_branches[0].activation_order))


def test_project_mega_rejects_species_form_mismatch_and_does_not_mutate(i7b_projection_env, opp_sets_meganium):
    """[REV.5 correction 2] project_mega must fail closed when the slot's mon is
    not the form's base species. Rev. 4 had no such check: it wrote
    `mon.species = form_meta.form_species_name` unconditionally, so an
    Aerodactyl-Mega form projected onto an Incineroar silently "succeeded" --
    which is exactly what Rev. 4's own Task 4 tests were accidentally relying on.
    The input state must also come back unmutated."""
    from copy import deepcopy

    from showdown_bot.engine.mega_projection import MegaProjectionSpeciesMismatchError

    state = BattleState()
    state.sides["p2"]["a"] = PokemonState(
        species="Incineroar", base_species_id="incineroar", hp=100, max_hp=100,
    )
    before = deepcopy(state)
    form = mega_form_for("Aerodactyl", "Aerodactylite")  # base_species_id="aerodactyl"

    with pytest.raises(MegaProjectionSpeciesMismatchError):
        project_mega(
            state, "p2", "a", form, species_meta=i7b_projection_env["species_meta"],
            speed_oracle=i7b_projection_env["speed_oracle"],
            calc_profile=i7b_projection_env["calc_profile"],
            is_ours=False, opp_sets=opp_sets_meganium, book=None,
        )
    assert state == before  # fail-closed must not leave a half-projected board


def test_project_mega_accepts_already_mega_species_via_base_species_id(i7b_projection_env, i7b_aerodactyl_spreads):
    """[REV.5 correction 2] The coherence check matches on normalized
    base_species_id OR normalized species -- so a valid sub-form mapping (a mon
    whose `species` already reads "Aerodactyl-Mega" but whose `base_species_id`
    is still "aerodactyl") is NOT rejected. Pins the `or` half of the rule; a
    species-only check would break this (to_id("Aerodactyl-Mega") is
    "aerodactylmega", which does NOT equal the form's "aerodactyl")."""
    state = BattleState()
    state.sides["p1"]["a"] = PokemonState(
        species="Aerodactyl-Mega", base_species_id="aerodactyl",
        item="Aerodactylite", hp=100, max_hp=100,
    )
    form = mega_form_for("Aerodactyl", "Aerodactylite")
    result = project_mega(
        state, "p1", "a", form, species_meta=i7b_projection_env["species_meta"],
        speed_oracle=i7b_projection_env["speed_oracle"],
        calc_profile=i7b_projection_env["calc_profile"],
        spread_lookup=i7b_aerodactyl_spreads,
    )
    assert result.projected_state.sides["p1"]["a"].species == "Aerodactyl-Mega"
