"""C3 arm-by-arm proof: every §4 arm is CONSTRUCTIBLE and runs end-to-end through the real
scoring path, producing rows that pass both validator tiers.

This is what unblocks the six arms C2 recorded as unconstructible (P-1..P-5). The proof is a
test, not a run: reps are tiny and passed explicitly (no default), and everything writes into
tmp_path. It freezes no evidence, measures no latency, and starts no battle.

Production topology, not the split-backend fixtures (P-5)
--------------------------------------------------------
``ProfileSession`` shares ONE calc backend across DamageOracle, SpeedOracle and SpeciesDex --
exactly what ``client/gauntlet.py`` does for a live decision, and the fix P-5 named: the old
tests/conftest.py mega fixtures build a SEPARATE SubprocessCalcBackend for speed, so "cold"
and "warm" there mean something production never does. The session implements the harness's
seam (counters/cache_sizes/prepare/score) over the REAL build_own_mega_contexts /
score_evaluated_variants, so the arm the harness drives is the arm production would run.

Boards built AFTER the final state (P-1..P-4)
---------------------------------------------
Every board sets its state -- foe species/item, Trick Room -- BEFORE contexts are built, and
eligibility is resolved by the REAL foe_mega_eligibility(), never a hand-built dict. A
post-hoc kw['state'] swap is exactly what the pre-bound contexts forbid.
"""
from __future__ import annotations

import json

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
from showdown_bot.eval.decision_profile import (
    fixture_input_hash,
    group_a_fixture_dto,
    profile_manifest_hash,
    validate_decision_profile_dataset,
    validate_decision_profile_row,
)
from showdown_bot.eval.profile_arms import PROFILE_ARMS, arm_specs
from showdown_bot.eval.profile_harness import run_arm
from showdown_bot.eval.profile_manifest import build_profile_manifest
from showdown_bot.eval import config_env

FORMAT = "gen9championsvgc2026regma"

_JOLLY = SpreadPreset(nature="Jolly", evs={"atk": 32, "spe": 32, "hp": 2})
_IMPISH = SpreadPreset(nature="Impish", evs={"hp": 32, "def": 32, "spd": 2})
_SPREADS = SpeciesSpreads(offense=_JOLLY, defense=_IMPISH)
_BOLD = SpreadPreset(nature="Bold", evs={"hp": 32, "def": 32})
_MEGANIUM_SET = SpeciesSpreads(offense=_BOLD, defense=_BOLD)


# --------------------------------------------------------------------------
# Boards: (req, state) built coherently, foe resolved by the REAL eligibility.
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


# fixture NAME -> (builder, human note). The names match profile_arms.py's fixture ids.
_BOARDS = {
    "mega_decision_fixture": _board_no_foe,
    "mega_decision_tie_fixture": _board_tie,
    "mega_decision_foe_slotb_fixture": _board_foe_slotb,
    "mega_decision_no_own_mega_fixture": _board_no_own_mega,
    "mega_decision_dual_unequal_fixture": _board_dual_unequal,
    "mega_decision_dual_unequal_tr_fixture": _board_dual_unequal_tr,
}


_OUR_SPREADS = {"aerodactyl": _SPREADS, "whimsicott": _SPREADS,
                "incineroar": _SPREADS, "meganium": _SPREADS}
_CALC_PROFILE = calc_profile_from_config(load_format_config(FORMAT))


def _fixture_dto(name: str) -> dict:
    """The COMPLETE §2.7 group-A input set for a board -- request, full state (both sides AND
    the field), action order, book, spreads, opp_sets, calc_profile, sides. Handed raw to
    encode() via group_a_fixture_dto, so a change to any move, spread or item flips the hash.
    Same board -> same hash (arms sharing a board agree on n_candidates); different board ->
    different hash. This replaces a reduced descriptor that omitted moves and spreads and could
    have collided two genuinely different boards."""
    req, st, opp = _BOARDS[name]()
    return group_a_fixture_dto(
        req=req, state=st, my_actions=enumerate_my_actions(req),
        book=SpreadBook(default=_SPREADS), our_spreads=_OUR_SPREADS, opp_sets=opp,
        calc_profile=_CALC_PROFILE, our_side="p1", opp_side="p2",
    )


_FIXTURE_HASHES = {name: fixture_input_hash(_fixture_dto(name)) for name in _BOARDS}


# --------------------------------------------------------------------------
# The session: production topology, one backend shared across the three oracles.
# --------------------------------------------------------------------------

class ProfileSession:
    def __init__(self, board_name: str):
        req, state, opp_sets = _BOARDS[board_name]()
        self.req = req
        self.state = state
        self.opp_sets = opp_sets
        self.book = SpreadBook(default=_SPREADS)
        self.our_spreads = {"aerodactyl": _SPREADS, "whimsicott": _SPREADS,
                            "incineroar": _SPREADS, "meganium": _SPREADS}
        self.calc = CalcClient()                     # respects SHOWDOWN_CALC_BACKEND (env boundary)
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


def _manifest():
    specs = arm_specs(_FIXTURE_HASHES, reps=1)
    return build_profile_manifest(agent="heuristic", format_id=FORMAT, arms=specs)


def _arm_by_design(design_arm: str):
    return next(a for a in PROFILE_ARMS if a.design_arm == design_arm)


def _run_one_arm(arm, manifest, *, reps):
    """Run one arm through the harness with its own fresh sessions, closing them after."""
    mhash = profile_manifest_hash(manifest)
    entry = next(e for e in manifest["arms"] if e["arm_id"] == arm.arm_id)
    built: list[ProfileSession] = []

    def factory():
        s = ProfileSession(arm.fixture)
        built.append(s)
        return s

    try:
        rows = run_arm(
            arm, factory, agent="heuristic", format_id=FORMAT, config_id="c3-proof",
            git_sha=manifest["git_sha"], config_hash=entry["effective_config_hash"],
            profile_manifest_hash=mhash, reps=reps,
            behavior_env=entry["behavior_env"],   # from the manifest arm, mandatory
        )
    finally:
        for s in built:
            s.close()
    return rows


# The six arms C2 recorded as unconstructible -- the C3 deliverable.
_C3_ARMS = ["5", "7", "8", "10", "13b", "14"]


@pytest.mark.parametrize("design_arm", _C3_ARMS)
def test_each_c3_arm_is_constructible_and_its_rows_validate(design_arm):
    """Each formerly-blocked arm builds a coherent board, runs the REAL scoring path through
    the harness, and every row it emits passes the per-row validator."""
    manifest = _manifest()
    arm = _arm_by_design(design_arm)
    rows = _run_one_arm(arm, manifest, reps=1)
    assert rows, f"arm {arm.arm_id} produced no rows"
    for row in rows:
        validate_decision_profile_row(row, manifest=manifest)   # raises on any violation
    r = rows[0]
    assert r["source"] == "microprofile"
    assert r["timer_scope"] == arm.timer_scope
    assert r["outcome"] == "ok", f"arm {arm.arm_id} crashed: {r}"


def test_foe_mega_arms_actually_reach_the_foe_mega_path():
    """The point of arms 5/7/8/10 is a foe-Mega hypothesis that really composes. Prove the
    branches are non-empty -- otherwise the arm would be measuring the no-mega path under a
    foe-mega label."""
    manifest = _manifest()
    for design_arm in ["5", "7", "8", "10"]:
        arm = _arm_by_design(design_arm)
        rows = _run_one_arm(arm, manifest, reps=1)
        assert rows[0]["foe_mega_active"], f"arm {arm.arm_id} did not reach the foe-Mega path"
        assert rows[0]["n_mega_twins"] > 0


def test_arm_12_reaches_the_depth2_frontier():
    """§4 arm 12 is depth-2 with the foe-Mega frontier actually reached (TOPM>=4). Its rows
    must report depth2_frontier > 0 -- the count that was provably wrong when the shape was
    hard-coded 0. The arm's env (SEARCH_DEPTH=2, TOPM=4) flows through run_arm's boundary into
    the real scoring path, and the at-origin sink counts the refinements."""
    manifest = _manifest()
    rows = _run_one_arm(_arm_by_design("12"), manifest, reps=1)
    assert rows[0]["depth2_frontier"] > 0, rows[0]


def test_persistent_cold_and_warm_differ_in_backend_class():
    """13b (cold) and 14 (warm) at the wide scope must land on opposite sides of the backend
    contrast: cold spawns inside the window (clean_cold), warm is already alive (clean_warm).
    This is the P-5 payoff -- a shared backend measured at contexts_and_score."""
    manifest = _manifest()
    cold = _run_one_arm(_arm_by_design("13b"), manifest, reps=1)
    warm = _run_one_arm(_arm_by_design("14"), manifest, reps=1)
    assert cold[0]["backend_class"] == "clean_cold", cold[0]
    assert warm[0]["backend_class"] == "clean_warm", warm[0]


def test_the_whole_matrix_writes_a_dataset_that_passes_the_dataset_validator(tmp_path):
    """End to end, into tmp only: every runnable arm -> harness rows -> the dataset tier.

    This is the strongest single check: the dataset validator re-runs the per-row validator
    on every row AND enforces the cross-row identities (per-arm backend/cache lifecycle,
    fixture -> constant n_candidates). tmp_path, deliberately: this slice freezes no evidence.
    """
    manifest = _manifest()
    out = tmp_path / "profile.jsonl"
    with open(out, "a", encoding="utf-8", newline="") as fh:
        for arm in PROFILE_ARMS:
            rows = _run_one_arm(arm, manifest, reps=2)
            for row in rows:
                fh.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")

    report = validate_decision_profile_dataset(str(out), manifest)
    assert report["arms"], "no arms in the report"
    assert report["rows"] == 2 * len(PROFILE_ARMS)
    # cold arms are clean_cold or oneshot; the one warm arm contributes clean_warm.
    assert report["backend_class_counts"].get("clean_warm", 0) >= 1
