"""Task 4: schedule-linked offline constructibility proofs. Each coverage cell has a node-free
proof board (COVERAGE_PROOF_BOARDS) that, scored through the REAL scoring path, forces that cell on
the resulting MegaShapeCounts -- so every manifest target_cell is provably reachable offline.
"""
from __future__ import annotations

import showdown_bot.eval.profile_fixtures as pf
from showdown_bot.battle.evaluate import EvalWeights
from showdown_bot.battle.mega_scoring import MegaShapeCounts, score_evaluated_variants
from showdown_bot.battle.opponent import foe_mega_eligibility
from showdown_bot.engine.belief.game_mode import GameMode
from showdown_bot.engine.species_meta import species_meta_table
from showdown_bot.eval.coverage_schedule import COVERAGE_CELLS, COVERAGE_PROOF_BOARDS, load_coverage_manifest


def _shape_for(board_name: str) -> MegaShapeCounts:
    s = pf.make_session(board_name)
    try:
        s.prepare()
        shape = MegaShapeCounts()
        elig = foe_mega_eligibility(s.state, "p2", opp_sets=s.opp_sets)
        score_evaluated_variants(
            s._variants, s._contexts, req=s.req, state=s.state, book=s.book, our_side="p1",
            opp_side="p2", calc=s.calc, oracle=s.oracle, speed_oracle=s.speed, dex=s.dex,
            priors=None, weights=EvalWeights(), mode=GameMode.NEUTRAL, risk_lambda=0.5,
            rollout_horizon=0, our_spreads=s.our_spreads, opp_sets=s.opp_sets,
            calc_profile=s.calc_profile, accuracy_mode=False, accuracy_branch_cap=6, endgame=False,
            fast_board=False, foe_mega_eligibility=elig, species_meta=species_meta_table(),
            shape_sink=shape,
        )
        return shape
    finally:
        s.close()


def test_slot0_matchup_is_constructible():
    assert 0 in _shape_for(COVERAGE_PROOF_BOARDS["slot0"]).foe_mega_slots


def test_slot1_matchup_is_constructible():
    assert 1 in _shape_for(COVERAGE_PROOF_BOARDS["slot1"]).foe_mega_slots


def test_both_foe_slots_matchup_is_constructible():
    assert tuple(_shape_for(COVERAGE_PROOF_BOARDS["both_foe_slots"]).foe_mega_slots) == (0, 1)


def test_order_tie_matchup_is_constructible():
    shape = _shape_for(COVERAGE_PROOF_BOARDS["order_tie"])
    # order_tie is set ONLY when both mutually-reversed 0.5 orderings of the tie were scored.
    assert shape.foe_mega_order_tie is True
    assert tuple(shape.foe_mega_slots) != ()


def test_every_manifest_matchup_has_a_target_cell_and_a_proof():
    manifest = load_coverage_manifest()
    target_cells = {m.target_cell for m in manifest.matchups}
    assert target_cells == set(COVERAGE_CELLS)
    for m in manifest.matchups:
        assert m.target_cell in COVERAGE_PROOF_BOARDS
