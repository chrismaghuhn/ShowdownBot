from showdown_bot.team.spreads import our_spreads_from_packed

# A trimmed packed team (Incineroar = bulky support, Flutter Mane = frail
# offensive -- the mon the crude "everything bulky" proxy wrongly tanked).
PACKED = (
    "Incineroar||sitrusberry|intimidate|fakeout,flareblitz,knockoff,protect"
    "|Adamant|252,4,,,252,||||50|"
    "]Flutter Mane||choicespecs|protosynthesis|moonblast,shadowball,dazzlinggleam,protect"
    "|Timid|,,,252,4,252||,0,,,,||50|"
    "]Landorus-Therian||choicescarf|intimidate|earthpower,sludgebomb,uturn,protect"
    "|Modest|,,,252,4,252||||50|"
)


def test_our_spreads_from_packed_real_values():
    sp = our_spreads_from_packed(PACKED)
    inc = sp["Incineroar"]
    # both presets are the single real spread -> used regardless of offense/defense mode
    assert inc.offense == inc.defense
    assert inc.defense.nature == "Adamant"
    assert inc.defense.evs == {"hp": 252, "atk": 4, "spd": 252}
    assert inc.defense.items == ["sitrusberry"]


def test_frail_mon_not_bulked():
    sp = our_spreads_from_packed(PACKED)
    fm = sp["Flutter Mane"]
    assert fm.defense.nature == "Timid"
    assert fm.defense.evs == {"spa": 252, "spd": 4, "spe": 252}  # no HP/def -> genuinely frail


def test_forme_species_names_preserved():
    sp = our_spreads_from_packed(PACKED)
    assert "Landorus-Therian" in sp


from showdown_bot.team.spreads import apply_own_team_knowledge, our_spreads_from_packed
from showdown_bot.engine.state import BattleState, PokemonState
from showdown_bot.models.request import BattleRequest


def _state_with(species, **kw):
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species=species, hp=100, max_hp=100, **kw)
    return st


def _req(item, *, species="Landorus-Therian", drop_item=False):
    poke = {"ident": f"p1: {species}", "details": f"{species}, L50, M", "condition": "179/179",
            "active": True, "stats": {"spe": 100}, "moves": ["earthpower"], "baseTypes": ["Ground"]}
    if not drop_item:
        poke["item"] = item
    return BattleRequest.model_validate({"rqid": 1, "side": {"name": "P1", "id": "p1", "pokemon": [poke]}})


def test_request_item_nonempty_sets_known():
    st = _state_with("Landorus-Therian")
    apply_own_team_knowledge(st, _req("choicescarf"), None)
    mon = st.sides["p1"]["a"]
    assert mon.item == "choicescarf" and mon.item_known and not mon.item_lost


def test_request_item_empty_marks_lost():
    st = _state_with("Landorus-Therian")
    apply_own_team_knowledge(st, _req(""), None)
    mon = st.sides["p1"]["a"]
    assert mon.item is None and mon.item_known and mon.item_lost


def test_fallback_sets_only_when_unknown_and_not_lost():
    sp = our_spreads_from_packed("Incineroar||sitrusberry|intimidate|fakeout|Adamant|252,,,,,||||50|")
    st = _state_with("Incineroar")
    apply_own_team_knowledge(st, _req(None, species="Incineroar", drop_item=True), sp)
    assert st.sides["p1"]["a"].item == "sitrusberry"


def test_fallback_never_resurrects_lost_item():
    sp = our_spreads_from_packed("Incineroar||sitrusberry|intimidate|fakeout|Adamant|252,,,,,||||50|")
    st = _state_with("Incineroar", item=None, item_known=True, item_lost=True)
    apply_own_team_knowledge(st, _req(None, species="Incineroar", drop_item=True), sp)
    assert st.sides["p1"]["a"].item is None  # NOT restored to sitrusberry
