"""The promoted, source-owned I8 microprofile fixtures (measurement-only).

These prove the fixtures/session logic that used to live in
``tests/test_profile_arms_end_to_end.py`` now has ONE home in
``showdown_bot.eval.profile_fixtures`` -- a source module the runner can import -- and that
the promotion changed nothing: the fixture hashes are byte-identical to the values the C3
proof observed, they still come from the shared canonical ``fixture_input_hash`` /
``group_a_fixture_dto`` path, every arm still resolves, and the session still shares ONE calc
backend across the three oracles (the P-5 production topology).

Nothing here scores or spawns a server: building boards and hashing inputs is node-free. The
one session-construction test does not call ``prepare``/``score``.
"""
from __future__ import annotations

import pytest

from showdown_bot.eval import profile_fixtures as pf
from showdown_bot.eval.decision_profile import fixture_input_hash, group_a_fixture_dto
from showdown_bot.eval.profile_arms import PROFILE_ARMS

# The hashes the C3 end-to-end proof produced, before promotion. A change to any board input
# (move, spread, item, nature, field) would move these; pinning them makes the promotion a
# provable no-op rather than a trust-me refactor.
_GOLDEN = {
    "mega_decision_fixture": "c8c3b460429173e1",
    "mega_decision_tie_fixture": "f5b78e23651079fe",
    "mega_decision_foe_slotb_fixture": "750b0fa3b9cc6d95",
    "mega_decision_no_own_mega_fixture": "8c6523c2e124aff3",
    "mega_decision_dual_unequal_fixture": "e2737e76dbddff05",
    "mega_decision_dual_unequal_tr_fixture": "aee3b1b127e75a37",
}

_GROUP_A_KEYS = {
    "our_side", "opp_side", "request", "state", "action_order", "book", "our_spreads",
    "opp_sets", "calc_profile",
}


def test_the_six_boards_are_registered():
    assert set(pf.BOARDS) == set(_GOLDEN)


def test_fixture_hashes_are_byte_identical_to_the_c3_proof():
    """Promotion must not move a single hash: same boards, same canonical encoding."""
    assert pf.FIXTURE_HASHES == _GOLDEN


def test_fixture_hashes_come_from_the_shared_canonical_path():
    """Each stored hash is exactly ``fixture_input_hash(group_a_fixture_dto(...))`` recomputed
    from the module's own board, so the hashes are produced by the ONE canonical recipe and
    never hand-written."""
    for name in pf.BOARDS:
        dto = pf.fixture_dto(name)
        assert set(dto) == _GROUP_A_KEYS, name          # it IS the group-A DTO
        assert pf.FIXTURE_HASHES[name] == fixture_input_hash(dto), name


def test_the_dto_matches_an_independently_built_group_a_dto():
    """Belt-and-suspenders: the module's DTO equals one built here directly through
    ``group_a_fixture_dto`` from the module's raw board -- so ``fixture_dto`` is a thin wrapper
    over the shared builder, not a second descriptor."""
    from showdown_bot.battle.actions import enumerate_my_actions

    name = "mega_decision_tie_fixture"
    req, state, opp = pf.board(name)
    direct = group_a_fixture_dto(
        req=req, state=state, my_actions=enumerate_my_actions(req),
        book=pf.SPREAD_BOOK, our_spreads=pf.OUR_SPREADS, opp_sets=opp,
        calc_profile=pf.CALC_PROFILE, our_side="p1", opp_side="p2",
    )
    assert fixture_input_hash(direct) == pf.FIXTURE_HASHES[name]


def test_every_arm_fixture_resolves_exactly_once():
    """All 15 arms name a fixture the registry can build -- none is silently unresolved."""
    for arm in PROFILE_ARMS:
        assert arm.fixture in pf.BOARDS, arm.arm_id
    # every arm resolves; boards may be shared, but no arm points at a missing one
    assert {a.fixture for a in PROFILE_ARMS} <= set(pf.BOARDS)


def test_make_session_yields_the_harness_seam():
    """A session exposes exactly the harness seam and a close(). No scoring here."""
    s = pf.make_session("mega_decision_tie_fixture")
    try:
        for method in ("counters", "cache_sizes", "prepare", "score", "close"):
            assert callable(getattr(s, method)), method
    finally:
        s.close()


def test_session_shares_one_backend_across_all_three_oracles():
    """Production topology (P-5): DamageOracle, SpeedOracle and SpeciesDex all route to the
    ONE ``calc.backend`` -- not the split backends the old conftest fixtures used, where
    'cold'/'warm' meant something a live decision never does."""
    s = pf.make_session("mega_decision_tie_fixture")
    try:
        backend = s.calc.backend
        assert s.oracle.client is s.calc
        assert s.speed.backend is backend
        assert s.dex.backend is backend
    finally:
        s.close()


def test_unknown_board_fails_closed():
    with pytest.raises(KeyError):
        pf.board("no_such_board")
