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
