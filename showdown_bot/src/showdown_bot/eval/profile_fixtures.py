"""Source-owned I8 microprofile fixtures: the coherent boards and the production-topology
session the arm matrix is measured on (I8-C, measurement-only).

Why this lives in source, not tests
------------------------------------
The C3 proof built these boards and ``ProfileSession`` INSIDE
``tests/test_profile_arms_end_to_end.py``. That was correct for proving the six blocked arms
constructible, but a runner cannot import a test: production code reaching into ``tests/`` is
exactly the coupling the harness's session seam was designed to avoid. So the reusable pieces
-- the boards, the fixture DTOs/hashes, and the session -- are promoted here, ONCE, and both
the runner and the end-to-end test consume this single implementation. There is no second copy.

This module measures nothing and starts nothing. Building a board and hashing its inputs is
node-free; only :meth:`ProfileSession.prepare` / :meth:`ProfileSession.score` touch the calc
bridge, and only when a caller (the harness) drives them.

Production topology, not the split-backend fixtures (P-5)
--------------------------------------------------------
``ProfileSession`` shares ONE calc backend across ``DamageOracle``, ``SpeedOracle`` and
``SpeciesDex`` -- exactly what ``client/gauntlet.py`` does for a live decision. The old
``tests/conftest.py`` mega fixtures build a SEPARATE backend for speed, so "cold" and "warm"
there mean something a live decision never does. The session implements the harness seam
(``counters``/``cache_sizes``/``prepare``/``score``) over the REAL ``build_own_mega_contexts`` /
``score_evaluated_variants``, so the arm the harness drives is the arm production would run.

Boards built AFTER the final state (P-1..P-4)
---------------------------------------------
Every board sets its state -- foe species/item, Trick Room -- BEFORE contexts are built, and
foe eligibility is resolved by the REAL ``foe_mega_eligibility()``, never a hand-built dict.
"""
from __future__ import annotations

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
from showdown_bot.eval.decision_profile import fixture_input_hash, group_a_fixture_dto

FORMAT = "gen9championsvgc2026regma"

_JOLLY = SpreadPreset(nature="Jolly", evs={"atk": 32, "spe": 32, "hp": 2})
_IMPISH = SpreadPreset(nature="Impish", evs={"hp": 32, "def": 32, "spd": 2})
_SPREADS = SpeciesSpreads(offense=_JOLLY, defense=_IMPISH)
_BOLD = SpreadPreset(nature="Bold", evs={"hp": 32, "def": 32})
_MEGANIUM_SET = SpeciesSpreads(offense=_BOLD, defense=_BOLD)

# Shared, read-only priors used both to build the fixture DTO (hashing) and to drive scoring.
OUR_SPREADS = {"aerodactyl": _SPREADS, "whimsicott": _SPREADS,
               "incineroar": _SPREADS, "meganium": _SPREADS}
SPREAD_BOOK = SpreadBook(default=_SPREADS)
CALC_PROFILE = calc_profile_from_config(load_format_config(FORMAT))


# --------------------------------------------------------------------------
# Boards: (req, state, opp_sets) built coherently, foe resolved by the REAL eligibility.
# --------------------------------------------------------------------------

def _move_slots(names):
    return [{"move": n, "id": to_id(n), "pp": 8, "maxpp": 8, "target": "normal",
             "disabled": False} for n in names]


def _req(*, own_can_mega: bool, own_item: str | None):
    from showdown_bot.models.request import BattleRequest

    mon_a = {
        "ident": "p1: Aerodactyl", "details": "Aerodactyl, L50", "condition": "100/100",
        "active": True, "stats": {"atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100},
        "moves": ["rockslide"], "baseTypes": ["Rock", "Flying"],
    }
    if own_item:
        mon_a["item"] = own_item
    return BattleRequest.model_validate({
        "active": [{"moves": _move_slots(["Rock Slide"]), "canMegaEvo": own_can_mega},
                   {"moves": _move_slots(["Moonblast"]), "canMegaEvo": False}],
        "side": {"name": "P1", "id": "p1", "pokemon": [
            mon_a,
            {"ident": "p1: Whimsicott", "details": "Whimsicott, L50", "condition": "100/100",
             "active": True, "stats": {"atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100},
             "moves": ["moonblast"], "baseTypes": ["Grass", "Fairy"]},
        ]}, "rqid": 1,
    })


def _own_side(st, *, own_item):
    st.sides["p1"]["a"] = PokemonState(species="Aerodactyl", base_species_id="aerodactyl",
                                       item=own_item, types=["Rock", "Flying"], hp=100, max_hp=100)
    st.sides["p1"]["b"] = PokemonState(species="Whimsicott", base_species_id="whimsicott",
                                       types=["Grass", "Fairy"], hp=100, max_hp=100)


def _incineroar():
    return PokemonState(species="Incineroar", base_species_id="incineroar",
                        types=["Fire", "Dark"], hp=100, max_hp=100)


def _aerodactyl_holder():
    return PokemonState(species="Aerodactyl", base_species_id="aerodactyl",
                        item="Aerodactylite", item_known=True, types=["Rock", "Flying"],
                        hp=100, max_hp=100)


def _meganium_holder():
    return PokemonState(species="Meganium", base_species_id="meganium",
                        item="Meganiumite", item_known=True, types=["Grass"], hp=100, max_hp=100)


def _board_no_foe():
    st = BattleState(); _own_side(st, own_item="Aerodactylite")
    st.sides["p2"]["a"] = _incineroar()
    return _req(own_can_mega=True, own_item="Aerodactylite"), st, None


def _board_tie():
    st = BattleState(); _own_side(st, own_item="Aerodactylite")
    st.sides["p2"]["a"] = _aerodactyl_holder()
    return _req(own_can_mega=True, own_item="Aerodactylite"), st, None


def _board_foe_slotb():
    st = BattleState(); _own_side(st, own_item="Aerodactylite")
    st.sides["p2"]["a"] = _incineroar()
    st.sides["p2"]["b"] = _aerodactyl_holder()
    return _req(own_can_mega=True, own_item="Aerodactylite"), st, None


def _board_no_own_mega():
    # Coherent on BOTH signals: no own stone AND canMegaEvo False.
    st = BattleState(); _own_side(st, own_item=None)
    st.sides["p2"]["a"] = _aerodactyl_holder()
    return _req(own_can_mega=False, own_item=None), st, None


def _board_dual_unequal():
    st = BattleState(); _own_side(st, own_item="Aerodactylite")
    st.sides["p2"]["a"] = _meganium_holder()
    return _req(own_can_mega=True, own_item="Aerodactylite"), st, {"meganium": _MEGANIUM_SET}


def _board_dual_unequal_tr():
    req, st, opp = _board_dual_unequal()
    st.field.trick_room = True     # on the FINAL state, before contexts are built
    return req, st, opp


def _board_both_foe_slots():
    # Task 2: TWO foe-Mega holders, one per slot (Meganium@Meganiumite in slot a=0, Aerodactyl@
    # Aerodactylite in slot b=1) with the own Mega present, so the bot scores a foe-Mega branch for
    # BOTH slots -> foe_mega_slots == (0, 1). (Item Clause = 1 permits two DIFFERENT stones.)
    st = BattleState(); _own_side(st, own_item="Aerodactylite")
    st.sides["p2"]["a"] = _meganium_holder()
    st.sides["p2"]["b"] = _aerodactyl_holder()
    return _req(own_can_mega=True, own_item="Aerodactylite"), st, {"meganium": _MEGANIUM_SET}


# fixture NAME -> builder. The names match profile_arms.py's fixture ids (plus the Task 2 coverage
# both_foe_slots board, which is a coverage proof fixture, not an arm).
BOARDS = {
    "mega_decision_fixture": _board_no_foe,
    "mega_decision_tie_fixture": _board_tie,
    "mega_decision_foe_slotb_fixture": _board_foe_slotb,
    "mega_decision_no_own_mega_fixture": _board_no_own_mega,
    "mega_decision_dual_unequal_fixture": _board_dual_unequal,
    "mega_decision_dual_unequal_tr_fixture": _board_dual_unequal_tr,
    "mega_decision_both_foe_slots_fixture": _board_both_foe_slots,
}


def board(name: str):
    """Build a fixture board: ``(req, state, opp_sets)``. KeyError on an unknown name."""
    return BOARDS[name]()


def fixture_dto(name: str) -> dict:
    """The COMPLETE §2.7 group-A input set for a board -- request, full state (both sides AND
    the field), action order, book, spreads, opp_sets, calc_profile, sides. Handed raw to
    ``encode()`` via ``group_a_fixture_dto``, so a change to any move, spread or item flips the
    hash. Same board -> same hash (arms sharing a board agree on n_candidates); different board
    -> different hash."""
    req, st, opp = board(name)
    return group_a_fixture_dto(
        req=req, state=st, my_actions=enumerate_my_actions(req),
        book=SPREAD_BOOK, our_spreads=OUR_SPREADS, opp_sets=opp,
        calc_profile=CALC_PROFILE, our_side="p1", opp_side="p2",
    )


# Fixture NAME -> fixture_input_hash, via the ONE canonical recipe. Computed once at import;
# node-free (no scoring). arm_specs() consumes this to pin each arm's fixture identity.
FIXTURE_HASHES = {name: fixture_input_hash(fixture_dto(name)) for name in BOARDS}


# --------------------------------------------------------------------------
# The session: production topology, one backend shared across the three oracles.
# --------------------------------------------------------------------------

class ProfileSession:
    """The harness seam over the REAL scoring path, on ONE shared calc backend.

    ``CalcClient()`` reads ``SHOWDOWN_CALC_BACKEND`` at construction, so a session must be
    built INSIDE ``run_arm``'s environment boundary -- which is exactly where the harness's
    ``session_factory`` calls it.
    """

    def __init__(self, board_name: str):
        req, state, opp_sets = board(board_name)
        self.req = req
        self.state = state
        self.opp_sets = opp_sets
        self.book = SpreadBook(default=_SPREADS)      # fresh per session; value == SPREAD_BOOK
        self.our_spreads = dict(OUR_SPREADS)
        self.calc = CalcClient()                      # respects SHOWDOWN_CALC_BACKEND (env boundary)
        self.oracle = DamageOracle(self.calc)
        self.calc_profile = calc_profile_from_config(load_format_config(FORMAT))
        self.speed = build_speed_oracle(self.calc.backend, self.calc_profile)
        self.dex = SpeciesDex(self.calc.backend)
        self._contexts = None
        self._variants = None

    def counters(self):
        b = self.calc.backend
        return {
            "damage_batch_calls": self.oracle.batch_calls,
            "planned_damage_batches": self.oracle.planned_damage_batches,
            "implicit_damage_batches": self.oracle.implicit_damage_batches,
            "stats_batch_calls": b.stats_batch_calls,
            "types_batch_calls": b.types_batch_calls,
            "mixed_batch_calls": b.mixed_batch_calls,
            "transport_attempts": b.transport_attempts,
            "spawn_count": b.spawn_count,
            "requests_total": self.oracle.requests_total,
            "requests_unique": self.oracle.requests_unique,
            "cache_hits": self.oracle.cache_hits,
        }

    def cache_sizes(self):
        return {"damage": len(self.oracle._cache),
                "speed": len(self.speed._spe_cache),
                "dex": len(self.dex._cache)}

    def prepare(self):
        # Context construction only. Rebuilt every call (contexts_and_variants per_rep).
        self._contexts, self._variants = build_own_mega_contexts(
            self.req, self.state, our_side="p1", opp_side="p2", book=self.book,
            oracle=self.oracle, speed_oracle=self.speed, species_meta=species_meta_table(),
            our_spreads=self.our_spreads, opp_sets=self.opp_sets,
            calc_profile=self.calc_profile, my_actions=enumerate_my_actions(self.req),
        )

    def score(self):
        elig = foe_mega_eligibility(self.state, "p2", opp_sets=self.opp_sets)  # the REAL one
        shape = MegaShapeCounts()      # the ONLY source of the row's work-set (counted at origin)
        score_evaluated_variants(
            self._variants, self._contexts, req=self.req, state=self.state, book=self.book,
            our_side="p1", opp_side="p2", calc=self.calc, oracle=self.oracle,
            speed_oracle=self.speed, dex=self.dex, priors=None, weights=EvalWeights(),
            mode=GameMode.NEUTRAL, risk_lambda=0.5, rollout_horizon=0,
            our_spreads=self.our_spreads, opp_sets=self.opp_sets,
            calc_profile=self.calc_profile, accuracy_mode=False, accuracy_branch_cap=6,
            endgame=False, fast_board=False, foe_mega_eligibility=elig,
            species_meta=species_meta_table(), shape_sink=shape,
        )
        return {
            "n_candidates": shape.n_candidates,
            "n_responses": shape.n_responses,
            "n_mega_twins": shape.n_mega_twins,
            "n_branches": shape.n_branches,
            "n_worlds": shape.n_worlds,
            "depth2_frontier": shape.depth2_frontier,
            # derived from the at-origin count, so n_mega_twins > 0 <=> foe_mega_active holds.
            "foe_mega_active": shape.n_mega_twins > 0,
        }

    def close(self):
        try:
            self.calc.close()
        except Exception:  # noqa: BLE001 - teardown best-effort
            pass


def make_session(board_name: str) -> ProfileSession:
    """The session factory the runner hands to ``run_arm`` (one call per lifecycle unit)."""
    return ProfileSession(board_name)
