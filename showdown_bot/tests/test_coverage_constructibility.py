"""Task 4: schedule-linked offline constructibility proofs. Each coverage cell has a node-free
proof board (COVERAGE_PROOF_BOARDS) that, scored through the REAL scoring path, forces that cell on
the resulting MegaShapeCounts -- so every manifest target_cell is provably reachable offline.

Review finding (F1): the proof boards above are DISCONNECTED synthetic fixtures -- they prove the
SCORING path can produce a cell's shape, but say nothing about whether the actual schedule TEAM
ever reaches that shape through the REAL deterministic team-preview picker. cov_foe_slot0 and
cov_foe_slot1 originally failed exactly this: pick_team_preview_default never brought (slot1) or
never led (slot0) the team's own Mega holder, so those two manifest matchups could never construct
their target_cell in a real battle no matter how the scoring path behaves. The tests below close
that gap: they parse the REAL packed team files the schedule actually uses and drive them through
the REAL preview picker, asserting the Mega holder is both brought AND leads in the intended slot.
"""
from __future__ import annotations

from pathlib import Path

import showdown_bot.eval.profile_fixtures as pf
from showdown_bot.battle.evaluate import EvalWeights
from showdown_bot.battle.mega_scoring import MegaShapeCounts, score_evaluated_variants
from showdown_bot.battle.opponent import foe_mega_eligibility
from showdown_bot.battle.team_preview import pick_team_preview_default
from showdown_bot.engine.belief.game_mode import GameMode
from showdown_bot.engine.species_meta import species_meta_table
from showdown_bot.engine.state import to_id
from showdown_bot.eval.coverage_schedule import COVERAGE_CELLS, COVERAGE_PROOF_BOARDS, load_coverage_manifest
from showdown_bot.models.request import BattleRequest, PokemonSlot, SideInfo
from showdown_bot.team.pack import load_packed_team

_REPO = Path(__file__).resolve().parents[2]


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


# --------------------------------------------------------------------------
# Real-team proofs (review finding F1): does the ACTUAL schedule team, run through the ACTUAL
# deterministic preview picker, actually bring + lead its Mega holder into the intended slot?
# --------------------------------------------------------------------------

def _parse_packed_roster(packed: str) -> list[tuple[str, list[str]]]:
    """Minimal packed-format reader (test-local, mirrors Teams.pack's field layout in
    sim/teams.ts): (species, move_ids) per mon, in team-sheet order. Field 0 is name, field 1 is
    species (empty when it equals name -- Showdown's own packing convention), field 4 is the
    comma-separated move list."""
    roster = []
    for mon in packed.strip("\n").split("]"):
        fields = mon.split("|")
        name, species_field, moves_field = fields[0], fields[1], fields[4]
        species = species_field or name
        roster.append((species, [to_id(m) for m in moves_field.split(",")]))
    return roster


def _real_preview_leads(team_path: str) -> list[str]:
    """The species (to_id) that the REAL pick_team_preview_default leads with, in slot order
    ([0]='a', [1]='b'), driven off the REAL packed team file the schedule actually references."""
    packed = load_packed_team(str(_REPO / "showdown_bot" / team_path))
    roster = _parse_packed_roster(packed)
    pokemon = [PokemonSlot(ident=f"p2: {species}", details=f"{species}, L50", condition="100/100",
                           active=False, moves=moves) for species, moves in roster]
    req = BattleRequest(team_preview=True, side=SideInfo(id="p2", pokemon=pokemon), rqid=1)
    chosen = pick_team_preview_default(req)   # 1-indexed team-sheet positions
    return [to_id(roster[pos - 1][0]) for pos in chosen[:2]]


def test_cov_foe_slot0s_real_team_leads_its_mega_holder_in_slot_a():
    leads = _real_preview_leads("teams/panel_champions_coverage_v0/cov_foe_slot0.txt")
    assert leads[0] == "meganium", (
        f"cov_foe_slot0's target_cell=slot0 requires its Mega holder (Meganium) to lead in slot "
        f"a (chosen[0]); the real preview picker leads with {leads!r}"
    )


def test_cov_foe_slot1s_real_team_leads_its_mega_holder_in_slot_b():
    leads = _real_preview_leads("teams/panel_champions_coverage_v0/cov_foe_slot1.txt")
    assert leads[1] == "delphox", (
        f"cov_foe_slot1's target_cell=slot1 requires its Mega holder (Delphox) to lead in slot b "
        f"(chosen[1]); the real preview picker leads with {leads!r}"
    )


def test_cov_foe_boths_real_team_leads_both_mega_holders():
    leads = _real_preview_leads("teams/panel_champions_coverage_v0/cov_foe_both.txt")
    assert set(leads) == {"aerodactyl", "meganium"}, (
        f"cov_foe_both's target_cell=both_foe_slots requires BOTH Mega holders (Aerodactyl, "
        f"Meganium) to lead -- order-independent, since the cell only needs both slots occupied, "
        f"not a specific letter; the real preview picker leads with {leads!r}"
    )
