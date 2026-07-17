"""Production telemetry addendum: MegaShapeCounts, counted AT ORIGIN in
score_evaluated_variants (I8, C3-fix).

Two properties matter and are both proven here:

  * ``shape_sink=None`` is byte-identical to the legacy path -- the counts are pure telemetry
    and must never touch a score. Proven by scoring two independently-built copies of the SAME
    board, one with a sink and one without, and asserting identical aggregate scores.
  * every count is the REAL work-set, taken where the work happens -- V, scored responses, the
    foe-Mega subset, composed branches, worlds, and (the one that was provably wrong when
    estimated) depth-2 refinements: 0 at depth 1, > 0 at depth 2.
"""
from __future__ import annotations

import pytest

from showdown_bot.battle.actions import enumerate_my_actions
from showdown_bot.battle.evaluate import EvalWeights
from showdown_bot.battle.mega_scoring import (
    MegaShapeCounts,
    build_own_mega_contexts,
    score_evaluated_variants,
)
from showdown_bot.battle.opponent import SpeciesDex, foe_mega_eligibility
from showdown_bot.battle.oracle import DamageOracle
from showdown_bot.engine.belief.game_mode import GameMode
from showdown_bot.engine.belief.hypotheses import SpeciesSpreads, SpreadBook, SpreadPreset
from showdown_bot.engine.calc.client import CalcClient
from showdown_bot.engine.calc_profile import build_speed_oracle, calc_profile_from_config
from showdown_bot.engine.format_config import load_format_config
from showdown_bot.engine.species_meta import species_meta_table
from showdown_bot.engine.state import BattleState, PokemonState, to_id
from showdown_bot.models.request import BattleRequest

FORMAT = "gen9championsvgc2026regma"
_JOLLY = SpreadPreset(nature="Jolly", evs={"atk": 32, "spe": 32, "hp": 2})
_IMPISH = SpreadPreset(nature="Impish", evs={"hp": 32, "def": 32, "spd": 2})
_SPREADS = SpeciesSpreads(offense=_JOLLY, defense=_IMPISH)


def _tie_board():
    """A fresh, self-contained copy of the tie board (own Aerodactyl+stone vs foe
    Aerodactyl+stone, 200/200). Fresh backend each call, so two copies score independently."""
    def _slots(names):
        return [{"move": n, "id": to_id(n), "pp": 8, "maxpp": 8, "target": "normal",
                 "disabled": False} for n in names]

    req = BattleRequest.model_validate({
        "active": [{"moves": _slots(["Rock Slide"]), "canMegaEvo": True},
                   {"moves": _slots(["Moonblast"]), "canMegaEvo": False}],
        "side": {"name": "P1", "id": "p1", "pokemon": [
            {"ident": "p1: Aerodactyl", "details": "Aerodactyl, L50", "condition": "100/100",
             "active": True, "stats": {"atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100},
             "moves": ["rockslide"], "baseTypes": ["Rock", "Flying"], "item": "Aerodactylite"},
            {"ident": "p1: Whimsicott", "details": "Whimsicott, L50", "condition": "100/100",
             "active": True, "stats": {"atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100},
             "moves": ["moonblast"], "baseTypes": ["Grass", "Fairy"]},
        ]}, "rqid": 1,
    })
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Aerodactyl", base_species_id="aerodactyl",
                                       item="Aerodactylite", types=["Rock", "Flying"], hp=100, max_hp=100)
    st.sides["p1"]["b"] = PokemonState(species="Whimsicott", base_species_id="whimsicott",
                                       types=["Grass", "Fairy"], hp=100, max_hp=100)
    st.sides["p2"]["a"] = PokemonState(species="Aerodactyl", base_species_id="aerodactyl",
                                       item="Aerodactylite", item_known=True,
                                       types=["Rock", "Flying"], hp=100, max_hp=100)

    calc = CalcClient()
    oracle = DamageOracle(calc)
    profile = calc_profile_from_config(load_format_config(FORMAT))
    speed = build_speed_oracle(calc.backend, profile)
    dex = SpeciesDex(calc.backend)
    our_spreads = {"aerodactyl": _SPREADS, "whimsicott": _SPREADS}
    contexts, variants = build_own_mega_contexts(
        req, st, our_side="p1", opp_side="p2", book=SpreadBook(default=_SPREADS), oracle=oracle,
        speed_oracle=speed, species_meta=species_meta_table(), our_spreads=our_spreads,
        opp_sets=None, calc_profile=profile, my_actions=enumerate_my_actions(req),
    )
    return dict(req=req, state=st, contexts=contexts, variants=variants, calc=calc,
                oracle=oracle, speed=speed, dex=dex, profile=profile,
                book=SpreadBook(default=_SPREADS), our_spreads=our_spreads)


def _score(b, *, shape_sink=None):
    elig = foe_mega_eligibility(b["state"], "p2", opp_sets=None)
    return score_evaluated_variants(
        b["variants"], b["contexts"], req=b["req"], state=b["state"], book=b["book"],
        our_side="p1", opp_side="p2", calc=b["calc"], oracle=b["oracle"],
        speed_oracle=b["speed"], dex=b["dex"], priors=None, weights=EvalWeights(),
        mode=GameMode.NEUTRAL, risk_lambda=0.5, rollout_horizon=0, our_spreads=b["our_spreads"],
        opp_sets=None, calc_profile=b["profile"], accuracy_mode=False, accuracy_branch_cap=6,
        endgame=False, fast_board=False, foe_mega_eligibility=elig,
        species_meta=species_meta_table(), shape_sink=shape_sink,
    )


def test_shape_sink_none_is_byte_identical_to_a_scored_run():
    """The sink is telemetry: passing one must not change a single score. Two independent
    copies of the same board, one scored with a sink and one without, aggregate identically."""
    with_sink = _tie_board()
    without = _tie_board()
    shape = MegaShapeCounts()
    recs_a = _score(with_sink, shape_sink=shape)
    recs_b = _score(without, shape_sink=None)
    assert [r.aggregate_score for r in recs_a] == [r.aggregate_score for r in recs_b]
    assert shape.n_candidates == len(recs_a) > 0


def test_counts_are_the_real_work_set_not_an_estimate():
    b = _tie_board()
    shape = MegaShapeCounts()
    recs = _score(b, shape_sink=shape)
    # V is exactly the number of scored records.
    assert shape.n_candidates == len(recs)
    # single most-likely world (SHOWDOWN_WORLD_SAMPLES unset).
    assert shape.n_worlds == 1
    # this board reaches the foe-Mega path, so branches were composed and twins were scored.
    assert shape.n_branches >= 1
    assert shape.n_mega_twins >= 1
    # every scored line counts once; the foe-Mega lines are a subset of all scored lines.
    assert shape.n_responses >= shape.n_mega_twins
    # depth 1 by default: nothing refined.
    assert shape.depth2_frontier == 0


def test_depth2_frontier_is_positive_at_depth_2(monkeypatch):
    """The count that was provably wrong when hard-coded 0: at depth 2 with the frontier
    actually reached (TOPM>=4, §4 arm 12), the depth-2 wrap refines real (record, index)
    slots, so depth2_frontier > 0."""
    monkeypatch.setenv("SHOWDOWN_SEARCH_DEPTH", "2")
    monkeypatch.setenv("SHOWDOWN_SEARCH_TOPM", "4")
    monkeypatch.setenv("SHOWDOWN_SEARCH_TOPN", "10")
    b = _tie_board()
    shape = MegaShapeCounts()
    _score(b, shape_sink=shape)
    assert shape.depth2_frontier > 0


def test_depth2_frontier_stays_zero_at_depth_1(monkeypatch):
    monkeypatch.setenv("SHOWDOWN_SEARCH_DEPTH", "1")
    b = _tie_board()
    shape = MegaShapeCounts()
    _score(b, shape_sink=shape)
    assert shape.depth2_frontier == 0
