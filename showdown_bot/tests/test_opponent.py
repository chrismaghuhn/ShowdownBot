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


def test_best_damaging_move_prefers_super_effective_over_higher_bp():
    """Stage A: pick by damage proxy (BP x STAB x type effectiveness), not raw BP.
    Earthquake (100 BP, Ground) does 0 to Dragon/Flying; Dazzling Gleam (80 BP,
    Fairy) hits for 2x -> it must win despite lower base power."""
    attacker = PokemonState(species="MysteryMon")
    attacker.move_names = {"Dazzling Gleam", "Earthquake"}
    target = PokemonState(species="Dragonite")
    target.types = ["Dragon", "Flying"]
    best = best_damaging_move(attacker, dex=None, target_mon=target)
    assert best.name == "Dazzling Gleam"


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


def test_item_for_speed_precedence():
    from showdown_bot.battle.opponent import _item_for_speed
    from showdown_bot.engine.state import PokemonState
    assert _item_for_speed(PokemonState(species="Landorus-Therian"), ["Choice Scarf"]) == "Choice Scarf"  # unknown -> curated
    revealed = PokemonState(species="Landorus-Therian", item="Sitrus Berry", item_known=True)
    assert _item_for_speed(revealed, ["Choice Scarf"]) == "Sitrus Berry"                                   # revealed wins
    lost = PokemonState(species="Landorus-Therian", item=None, item_known=True, item_lost=True)
    assert _item_for_speed(lost, ["Choice Scarf"]) is None                                                 # known-lost -> None


class _SpeFake:
    def stats_batch(self, specs):
        return [{"spe": 100} for _ in specs]

    def types_batch(self, species):
        return [["Normal"] for _ in species]


def test_opponent_speed_curated_vs_fallback(monkeypatch):
    from showdown_bot.battle.opponent import _opponent_speed
    from showdown_bot.engine.speed import SpeedOracle
    from showdown_bot.engine.state import PokemonState, FieldState
    from showdown_bot.engine.belief.hypotheses import (
        SpeciesSpreads, SpreadPreset, load_spread_book,
    )
    from showdown_bot.engine.format_config import load_format_config

    oracle = SpeedOracle(stats_backend=_SpeFake())
    book = load_spread_book(load_format_config("gen9vgc2026regi").meta_path("default_spreads"))
    p = SpreadPreset(nature="Careful", evs={"hp": 252}, items=["Sitrus Berry"])  # non-scarf, no spe
    opp_sets = {"incineroar": SpeciesSpreads(offense=p, defense=p)}
    field = FieldState()
    inc = PokemonState(species="Incineroar")        # curated
    tor = PokemonState(species="Tornadus")          # un-curated

    monkeypatch.setenv("SHOWDOWN_OPP_SPEED", "1")
    curated = _opponent_speed(inc, field, "p2", speed_oracle=oracle, book=book, opp_sets=opp_sets)
    fallback = _opponent_speed(tor, field, "p2", speed_oracle=oracle, book=book, opp_sets=opp_sets)
    monkeypatch.setenv("SHOWDOWN_OPP_SPEED", "0")
    knob_off = _opponent_speed(inc, field, "p2", speed_oracle=oracle, book=book, opp_sets=opp_sets)

    assert curated == 100      # likely, non-scarf
    assert fallback == 150     # un-curated -> opponent_range.max (base 100, scarf assumed -> x1.5)
    assert knob_off == 150     # knob off -> always max
