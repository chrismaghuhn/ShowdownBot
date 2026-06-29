from __future__ import annotations

from showdown_bot.battle.opponent import (
    best_damaging_move,
    predict_responses,
    revealed_support,
)
from showdown_bot.engine.state import BattleState, PokemonState


class FakeDex:
    def __init__(self, mapping):
        self.mapping = mapping

    def types(self, species):
        return self.mapping.get(species, ["Normal"])


def _state():
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Incineroar", hp=100, max_hp=100)
    st.sides["p1"]["b"] = PokemonState(species="Rillaboom", hp=100, max_hp=100)
    opp = PokemonState(species="Flutter Mane", hp=100, max_hp=100)
    opp.move_names = {"Moonblast", "Shadow Ball", "Protect"}
    opp2 = PokemonState(species="Tornadus", hp=100, max_hp=100)
    opp2.move_names = {"Tailwind", "Bleakwind Storm"}
    st.sides["p2"]["a"] = opp
    st.sides["p2"]["b"] = opp2
    return st


def test_best_damaging_picks_highest_bp_revealed():
    mon = PokemonState(species="Flutter Mane")
    mon.move_names = {"Moonblast", "Shadow Ball"}  # 95 vs 80
    meta = best_damaging_move(mon, dex=None)
    assert meta.id == "moonblast"


def test_best_damaging_stab_fallback_when_unrevealed():
    mon = PokemonState(species="Mystery")
    meta = best_damaging_move(mon, dex=FakeDex({"Mystery": ["Fairy"]}))
    assert meta.id == "moonblast"  # STAB_MOVE[Fairy]


def test_revealed_support_detected():
    mon = PokemonState(species="Tornadus")
    mon.move_names = {"Tailwind", "Bleakwind Storm"}
    assert revealed_support(mon).id == "tailwind"


def test_predict_responses_has_aggro_and_support():
    st = _state()
    resps = predict_responses(st, our_side="p1", opp_side="p2", dex=None)
    labels = {r.label for r in resps}
    assert any(lbl.startswith("aggro") for lbl in labels)
    assert any(lbl.startswith("support:tailwind") for lbl in labels)
    # protect read candidate present
    assert any("protect" in lbl for lbl in labels)
    # every response is a list of opponent PlannedActions
    for r in resps:
        for a in r.actions:
            assert a.side == "p2"
            assert not a.is_ours


def test_predict_responses_targets_our_alive_slots():
    st = _state()
    resps = predict_responses(st, our_side="p1", opp_side="p2", dex=None)
    aggro = next(r for r in resps if r.label == "aggro->a")
    targets = {a.target for a in aggro.actions if a.kind == "move"}
    assert ("p1", "a") in targets


def test_consecutive_protect_lowers_protect_weight():
    from showdown_bot.engine.belief.protect_priors import ProtectPriors

    priors = ProtectPriors(
        default=0.5, threatened_bump=0.0, consecutive_penalty=0.4, species={}
    )
    st = _state()
    base = predict_responses(st, "p1", "p2", dex=None, priors=priors)
    base_protect = next(r for r in base if "protect" in r.label).weight

    # opp slot a has just spammed Protect twice -> a third should be discounted
    st.sides["p2"]["a"].consecutive_protect = 2
    after = predict_responses(st, "p1", "p2", dex=None, priors=priors)
    after_protect = next(r for r in after if "protect" in r.label).weight

    assert after_protect < base_protect
