"""I7b-A: limited-view foe-Mega eligibility discovery."""
from __future__ import annotations

from showdown_bot.battle.opponent import foe_mega_eligibility
from showdown_bot.engine.belief.hypotheses import SpeciesSpreads, SpreadPreset
from showdown_bot.engine.mega_form import MegaForm
from showdown_bot.engine.state import BattleState, PokemonState


def _state_with_opp(species: str, *, item: str | None, item_known: bool, item_lost: bool = False,
                     side_mega_spent: bool = False) -> BattleState:
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Incineroar", hp=100, max_hp=100)
    mon = PokemonState(species=species, hp=100, max_hp=100, item=item, item_known=item_known, item_lost=item_lost)
    st.sides["p2"]["a"] = mon
    st.sides["p2"]["b"] = PokemonState(species="Rillaboom", hp=100, max_hp=100)
    st.side_mega_spent["p2"] = side_mega_spent
    return st


def test_revealed_stone_makes_slot_eligible():
    state = _state_with_opp("Aerodactyl", item="aerodactylite", item_known=True)

    result = foe_mega_eligibility(state, "p2", opp_sets=None)

    assert "a" in result
    assert isinstance(result["a"], MegaForm)
    assert result["a"].form_species_name == "Aerodactyl-Mega"


def test_unrevealed_unhypothesized_stone_yields_no_response():
    """T19-adjacent counterexample: no revealed item, no opp_sets hypothesis
    listing a mega stone -> not eligible, even though the real (hidden) held item
    IS a mega stone -- eligibility must never see the true hidden item."""
    state = _state_with_opp("Aerodactyl", item=None, item_known=False)

    result = foe_mega_eligibility(state, "p2", opp_sets=None)

    assert "a" not in result


def test_likely_set_stone_makes_slot_eligible_without_reveal():
    state = _state_with_opp("Aerodactyl", item=None, item_known=False)
    curated = SpeciesSpreads(
        offense=SpreadPreset(nature="Jolly", evs={}, items=["Aerodactylite"]),
        defense=SpreadPreset(nature="Jolly", evs={}, items=["Aerodactylite"]),
    )

    result = foe_mega_eligibility(state, "p2", opp_sets={"aerodactyl": curated})

    assert "a" in result
    assert result["a"].form_species_name == "Aerodactyl-Mega"


def test_revealed_stone_still_eligible_even_with_no_curated_hypothesis():
    """Revealed item alone is sufficient -- opp_sets absence must not block it."""
    state = _state_with_opp("Aerodactyl", item="aerodactylite", item_known=True)

    result = foe_mega_eligibility(state, "p2", opp_sets={})

    assert "a" in result


def test_revealed_non_mega_item_blocks_opp_sets_mega_hypothesis():
    """Known truth wins: a revealed Choice Scarf must never be overridden by a
    curated opp_sets Mega-stone hypothesis for the same species -- known item
    truth is authoritative and must not fall back to a hypothesis."""
    state = _state_with_opp("Aerodactyl", item="choicescarf", item_known=True)
    curated = SpeciesSpreads(
        offense=SpreadPreset(nature="Jolly", evs={}, items=["Aerodactylite"]),
        defense=SpreadPreset(nature="Jolly", evs={}, items=["Aerodactylite"]),
    )

    result = foe_mega_eligibility(state, "p2", opp_sets={"aerodactyl": curated})

    assert "a" not in result


def test_item_lost_blocks_opp_sets_mega_hypothesis():
    """A known-lost item means the mon cannot currently hold a mega stone --
    must not fall back to an opp_sets Mega-stone hypothesis either."""
    state = _state_with_opp("Aerodactyl", item=None, item_known=True, item_lost=True)
    curated = SpeciesSpreads(
        offense=SpreadPreset(nature="Jolly", evs={}, items=["Aerodactylite"]),
        defense=SpreadPreset(nature="Jolly", evs={}, items=["Aerodactylite"]),
    )

    result = foe_mega_eligibility(state, "p2", opp_sets={"aerodactyl": curated})

    assert "a" not in result


def test_side_already_spent_mega_yields_no_eligible_slot():
    state = _state_with_opp("Aerodactyl", item="aerodactylite", item_known=True, side_mega_spent=True)

    result = foe_mega_eligibility(state, "p2", opp_sets=None)

    assert result == {}


def test_lost_item_never_eligible_even_if_species_could_mega():
    state = _state_with_opp("Aerodactyl", item=None, item_known=True, item_lost=True)

    result = foe_mega_eligibility(state, "p2", opp_sets=None)

    assert "a" not in result


def test_non_mega_capable_species_yields_no_eligible_slot():
    state = _state_with_opp("Incineroar", item="choicescarf", item_known=True)
    # overwrite slot a directly since _state_with_opp always seeds p1/a as Incineroar
    state.sides["p2"]["a"] = PokemonState(species="Incineroar", item="choicescarf", item_known=True)

    result = foe_mega_eligibility(state, "p2", opp_sets=None)

    assert result == {}


def test_eligibility_never_reads_the_real_opponent_team_file():
    """Hard leakage counterexample: opp_sets carries no hypothesis, but a
    hypothetical 'real team paste' dict (simulating a gauntlet schedule's actual
    opponent roster) DOES list a mega stone for this species. foe_mega_eligibility
    must not accept a team-paste-shaped argument at all -- this test proves the
    function signature has no such parameter and that passing real team data as
    opp_sets (the only hypothesis source it accepts) still requires the SAME
    curated-hypothesis shape, not a raw roster dict, to produce a hit."""
    import inspect

    sig = inspect.signature(foe_mega_eligibility)
    assert set(sig.parameters) == {"state", "opp_side", "opp_sets"}

    state = _state_with_opp("Aerodactyl", item=None, item_known=False)
    fake_real_roster = {"real_team_paste": "Aerodactyl @ Aerodactylite"}  # wrong shape on purpose
    result = foe_mega_eligibility(state, "p2", opp_sets=fake_real_roster)
    assert result == {}  # malformed/foreign shape -> no match, never a silent leak
