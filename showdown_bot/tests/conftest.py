"""Shared pytest fixtures for the showdown_bot test suite."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from showdown_bot.engine.belief.hypotheses import load_spread_book
from showdown_bot.engine.calc.models import DamageResult
from showdown_bot.engine.format_config import load_format_config
from showdown_bot.engine.speed import SpeedRange
from showdown_bot.engine.state import BattleState, PokemonState
from showdown_bot.models.request import BattleRequest

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Fakes — mirrors of test_decision_replay.py fakes (no live server needed)
# ---------------------------------------------------------------------------


class _FakeCalc:
    """Returns non-KO damage (keeps game mode NEUTRAL)."""

    backend = None

    def damage_batch(self, requests):
        return [DamageResult(min_damage=20, max_damage=35, max_hp=150) for _ in requests]


class _FakeOracle:
    def request(self, req):
        return (req.attacker.species, req.move, req.defender.species)

    def get(self, key):
        return DamageResult(min_damage=45, max_damage=70, max_hp=150)

    def damage(self, req):
        return DamageResult(min_damage=45, max_damage=70, max_hp=150)

    def flush(self):
        pass


class _FakeSpeed:
    def our_speed(self, base, mon, field, side):
        return base or 100

    def opponent_range(self, mon, field, side, *, book):
        return SpeedRange(min=80, likely=110, max=150)


class _FakeDex:
    def types(self, species):
        return {"Flutter Mane": ["Ghost", "Fairy"], "Tornadus": ["Flying"]}.get(
            species, ["Normal"]
        )


def _book():
    cfg = load_format_config("gen9vgc2025regi")
    return load_spread_book(cfg.meta_path("default_spreads"))


def _req():
    data = json.loads((FIXTURES / "request_doubles_moves.json").read_text())
    return BattleRequest.model_validate(data)


def _state():
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Incineroar", hp=150, max_hp=150)
    st.sides["p1"]["b"] = PokemonState(species="Rillaboom", hp=155, max_hp=155)
    fm = PokemonState(species="Flutter Mane", hp=131, max_hp=131)
    fm.move_names = {"Moonblast", "Shadow Ball"}
    tor = PokemonState(species="Tornadus", hp=140, max_hp=140)
    tor.move_names = {"Tailwind", "Bleakwind Storm"}
    st.sides["p2"]["a"] = fm
    st.sides["p2"]["b"] = tor
    return st


@pytest.fixture
def decision_fixture():
    req = _req()
    kw = dict(
        state=_state(),
        book=_book(),
        our_side="p1",
        calc=_FakeCalc(),
        oracle=_FakeOracle(),
        speed_oracle=_FakeSpeed(),
        dex=_FakeDex(),
    )
    return req, kw


# ---------------------------------------------------------------------------
# I7a-B Task 5: a REAL Mega-capable board (Aerodactyl holding Aerodactylite),
# scoped here (not just tests/i7a/conftest.py) so export/rollout consumer
# tests can exercise a genuine format_config.mega=True decision -- including
# a mega_evolve=True JointAction -- without duplicating the board-building
# helpers per test file. Mirrors tests/i7a/test_i7a_decision.py's Aerodactyl
# fixture pattern (real SpeedOracle/SubprocessCalcBackend -- Mega
# projectability asserts speed_oracle.profile == calc_profile and calls
# speed_oracle.speed_for_species, which a hand-rolled fake would have to
# reimplement exactly).
# ---------------------------------------------------------------------------

def _mega_req():
    from showdown_bot.engine.state import to_id

    def _move_slots(names):
        return [
            {
                "move": name, "id": to_id(name), "pp": 8, "maxpp": 8,
                "target": "normal", "disabled": False,
            }
            for name in names
        ]

    a_moves = ["Rock Slide"]
    b_moves = ["Moonblast"]
    return BattleRequest.model_validate({
        "active": [
            {"moves": _move_slots(a_moves), "canMegaEvo": True},
            {"moves": _move_slots(b_moves), "canMegaEvo": False},
        ],
        "side": {
            "name": "Player1",
            "id": "p1",
            "pokemon": [
                {
                    "ident": "p1: Aerodactyl",
                    "details": "Aerodactyl, L50",
                    "condition": "100/100",
                    "active": True,
                    "stats": {"atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100},
                    "moves": [to_id(n) for n in a_moves],
                    "baseTypes": ["Rock", "Flying"],
                    "item": "Aerodactylite",
                },
                {
                    "ident": "p1: Whimsicott",
                    "details": "Whimsicott, L50",
                    "condition": "100/100",
                    "active": True,
                    "stats": {"atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100},
                    "moves": [to_id(n) for n in b_moves],
                    "baseTypes": ["Grass", "Fairy"],
                },
            ],
        },
        "rqid": 1,
    })


def _mega_state(foe_a: "PokemonState | None" = None):
    """Default (foe_a=None) is byte-identical to the pre-Rev.5 board: p2.a Incineroar."""
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(
        species="Aerodactyl", base_species_id="aerodactyl", item="Aerodactylite",
        types=["Rock", "Flying"], hp=100, max_hp=100,
    )
    st.sides["p1"]["b"] = PokemonState(
        species="Whimsicott", base_species_id="whimsicott",
        types=["Grass", "Fairy"], hp=100, max_hp=100,
    )
    st.sides["p2"]["a"] = foe_a if foe_a is not None else PokemonState(
        species="Incineroar", base_species_id="incineroar",
        types=["Fire", "Dark"], hp=100, max_hp=100,
    )
    return st


def _build_mega_decision_kw(state):
    """Test-only builder. contexts/evaluated_variants are built FROM ``state``, so a
    caller-supplied board is coherent from the start -- never a post-hoc
    kw["state"] swap after contexts already exist (which would leave every context's
    projected_state/plans/damage_model bound to the OTHER board)."""
    from showdown_bot.battle.actions import enumerate_my_actions
    from showdown_bot.battle.evaluate import EvalWeights
    from showdown_bot.battle.mega_scoring import build_own_mega_contexts
    from showdown_bot.battle.oracle import DamageOracle
    from showdown_bot.engine.belief.game_mode import GameMode
    from showdown_bot.engine.belief.hypotheses import SpeciesSpreads, SpreadBook, SpreadPreset
    from showdown_bot.engine.calc.client import SubprocessCalcBackend
    from showdown_bot.engine.calc_profile import calc_profile_from_config
    from showdown_bot.engine.format_config import load_format_config
    from showdown_bot.engine.speed import SpeedOracle
    from showdown_bot.engine.species_meta import species_meta_table

    cfg = load_format_config("gen9championsvgc2026regma")
    calc_profile = calc_profile_from_config(cfg)
    speed_oracle = SpeedOracle(stats_backend=SubprocessCalcBackend(), profile=calc_profile)
    spreads = SpeciesSpreads(
        offense=SpreadPreset(nature="Jolly", evs={"atk": 32, "spe": 32, "hp": 2}),
        defense=SpreadPreset(nature="Impish", evs={"hp": 32, "def": 32, "spd": 2}),
    )
    book = SpreadBook(default=spreads)
    req = _mega_req()
    oracle = DamageOracle()
    our_spreads = {"aerodactyl": spreads, "whimsicott": spreads, "incineroar": spreads}
    contexts, evaluated_variants = build_own_mega_contexts(
        req, state, our_side="p1", opp_side="p2", book=book, oracle=oracle,
        speed_oracle=speed_oracle, species_meta=species_meta_table(),
        our_spreads=our_spreads, opp_sets=None, calc_profile=calc_profile,
        my_actions=enumerate_my_actions(req),
    )
    kw = dict(
        state=state, book=book, our_side="p1", oracle=oracle, speed_oracle=speed_oracle,
        format_config=cfg, calc_profile=calc_profile,
        evaluated_variants=evaluated_variants, contexts=contexts, calc=oracle.client,
        dex=None, weights=EvalWeights(), mode=GameMode.NEUTRAL,
        our_spreads=our_spreads, opp_sets=None,
    )
    return req, kw


@pytest.fixture
def mega_decision_fixture():
    """Unchanged default board (p2.a Incineroar). NOT usable for foe-Mega scoring:
    its foe is not a Mega holder, so the real foe_mega_eligibility() returns {}."""
    return _build_mega_decision_kw(_mega_state())


@pytest.fixture
def mega_decision_tie_fixture():
    """[REV.5 correction 1] p2.a is a REAL Aerodactyl holding Aerodactylite with
    item_known=True, so the real foe_mega_eligibility() yields a coherent
    Aerodactyl-Mega hypothesis AND both pre-mega speeds tie -- the two branches at
    weight 0.5 that Task 4's weighting test requires.

    Verified against the real SpeedOracle + real SubprocessCalcBackend, not assumed:
      p1.a Aerodactyl (our_spreads, is_ours=True)  -> 200
      p2.a Aerodactyl (book.default, is_ours=False) -> 200   => tie, 2 branches @ 0.5
    (Rev. 4 used the Incineroar board here: 200 vs 123, one branch @ 1.0, so its own
    `assert tied_groups` could never pass -- see the plan's Rev. 5 section.)"""
    foe = PokemonState(
        species="Aerodactyl", base_species_id="aerodactyl", item="Aerodactylite",
        item_known=True, types=["Rock", "Flying"], hp=100, max_hp=100,
    )
    return _build_mega_decision_kw(_mega_state(foe_a=foe))


@pytest.fixture
def mega_decision_unsupported_ability_fixture():
    """[REV.5 correction 3] p2.a is a REAL Scovillain holding Scovillainite, so
    Task 2's species/form coherence check PASSES and the FAIL_CLOSED_ABILITIES gate
    ('Spicy Spray' -- verified against species_meta as the dex's only fail-closed
    mega ability) is what actually fires.

    The foe genuinely IS the form's base species: Rev. 4 injected a Scovillain-Mega
    form onto a non-Scovillain foe, which post-Task-2 raises
    MegaProjectionSpeciesMismatchError BEFORE the ability gate is ever reached --
    Task 4 deliberately does not catch that error, so such a test would crash instead
    of proving exclusion, and would not exercise the ability gate at all.

    No speed tie is needed or asserted here: this fixture is about exclusion, not
    branch weighting (that is mega_decision_tie_fixture's job)."""
    foe = PokemonState(
        species="Scovillain", base_species_id="scovillain", item="Scovillainite",
        item_known=True, types=["Grass", "Fire"], hp=100, max_hp=100,
    )
    return _build_mega_decision_kw(_mega_state(foe_a=foe))
