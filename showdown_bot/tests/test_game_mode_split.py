"""Lever A, commit 1: the two-phase (enqueue -> shared flush -> resolve) game-mode classifier.

These pin the NEW oracle-backed split against the SAME behavior as the direct
``compute_game_mode`` / ``classify_game_mode``, and prove the base ``threatened > 0``
short-circuit issues no outgoing request. The existing test_game_mode.py /
test_classify_game_mode.py remain the characterization guard for the public wrappers.
"""
from __future__ import annotations

from showdown_bot.battle.oracle import DamageOracle
from showdown_bot.engine.belief import game_mode as gm
from showdown_bot.engine.belief.hypotheses import load_spread_book
from showdown_bot.engine.calc.client import CalcClient
from showdown_bot.engine.calc.models import DamageResult
from showdown_bot.engine.format_config import load_format_config
from showdown_bot.engine.state import BattleState, PokemonState


class RecordingBackend:
    """Scripted backend keyed on (move, defender_species) -> (min_dmg, max_hp).
    Records every defender species it is asked about, so a test can prove which
    calcs were (and were not) issued."""

    def __init__(self, script):
        self.script = script
        self.seen_defenders: list[str] = []

    def calc_batch(self, requests):
        out = []
        for req in requests:
            self.seen_defenders.append(req.defender.species)
            min_dmg, max_hp = self.script.get((req.move, req.defender.species), (0, 999))
            out.append(DamageResult(rolls=[min_dmg, min_dmg], min_damage=min_dmg,
                                    max_damage=min_dmg, max_hp=max_hp, id=req.id))
        return out


def _book():
    cfg = load_format_config("gen9vgc2025regi")
    return load_spread_book(cfg.meta_path("default_spreads"))


def _state() -> BattleState:
    state = BattleState()
    state.sides["p1"]["a"] = PokemonState(species="Incineroar", hp=200, max_hp=200,
                                          move_names={"Flare Blitz"})
    state.sides["p2"]["a"] = PokemonState(species="Flutter Mane", hp=130, max_hp=130,
                                          move_names={"Moonblast"})
    return state


def _resolve_base(state, backend, book):
    """enqueue -> single shared flush -> resolve, the way the decision path will."""
    oracle = DamageOracle(client=CalcClient(backend=backend))
    handle = gm.enqueue_base_game_mode(state, our_side="p1", oracle=oracle, book=book)
    oracle.flush()  # the ONE shared flush (incoming folds here)
    return gm.resolve_base_game_mode(handle, oracle=oracle)


def test_two_phase_resolve_matches_must_react():
    book = _book()
    backend = RecordingBackend({("Moonblast", "Incineroar"): (260, 202),  # opp OHKOs us
                                ("Flare Blitz", "Flutter Mane"): (300, 131)})
    assert _resolve_base(_state(), backend, book) == gm.GameMode.MUST_REACT


def test_two_phase_resolve_matches_ahead():
    book = _book()
    backend = RecordingBackend({("Moonblast", "Incineroar"): (10, 202),  # opp cannot OHKO us
                                ("Flare Blitz", "Flutter Mane"): (300, 131)})  # we OHKO opp
    assert _resolve_base(_state(), backend, book) == gm.GameMode.AHEAD


def test_two_phase_resolve_matches_neutral():
    book = _book()
    backend = RecordingBackend({("Moonblast", "Incineroar"): (10, 202),  # neither side OHKOs
                                ("Flare Blitz", "Flutter Mane"): (10, 131)})
    assert _resolve_base(_state(), backend, book) == gm.GameMode.NEUTRAL


def test_base_must_react_short_circuit_issues_no_outgoing():
    """On base MUST_REACT (threatened>0) resolve must NOT build/send an outgoing
    request (us attacking the opponent) -- only incoming (opp attacking us)."""
    book = _book()
    backend = RecordingBackend({("Moonblast", "Incineroar"): (260, 202)})  # opp OHKOs us
    mode = _resolve_base(_state(), backend, book)
    assert mode == gm.GameMode.MUST_REACT
    # Every calc must have been an INCOMING check (defender = one of OUR mons).
    assert backend.seen_defenders  # something was asked
    assert set(backend.seen_defenders) == {"Incineroar"}
    assert "Flutter Mane" not in backend.seen_defenders  # no outgoing calc


def test_resolve_classification_extended_down_mons_forces_must_react():
    """Base NEUTRAL, but we are down a mon (mon_diff < 0) -> extended MUST_REACT."""
    book = _book()
    state = _state()
    # add a fainted mon on our side so _faints(p1) > _faints(p2)
    state.sides["p1"]["b"] = PokemonState(species="Rillaboom", hp=0, max_hp=200,
                                          move_names={"Grassy Glide"}, fainted=True)
    backend = RecordingBackend({("Moonblast", "Incineroar"): (10, 202),  # neither OHKOs -> base NEUTRAL
                                ("Flare Blitz", "Flutter Mane"): (10, 131)})
    oracle = DamageOracle(client=CalcClient(backend=backend))
    handle = gm.enqueue_classification(state, our_side="p1", oracle=oracle, book=book)
    oracle.flush()
    mode = gm.resolve_classification(handle, oracle=oracle, state=state, our_side="p1")
    assert mode == gm.GameMode.MUST_REACT


def test_wrappers_bind_injected_calc():
    """The public wrappers must route through the injected calc backend, never a
    freshly-constructed default CalcClient (which would drop a pinned/spy/stub)."""
    book = _book()
    backend = RecordingBackend({("Moonblast", "Incineroar"): (260, 202)})
    gm.compute_game_mode(_state(), our_side="p1", calc=CalcClient(backend=backend), book=book)
    assert backend.seen_defenders  # the injected backend actually received the requests


def test_degenerate_empty_side_resolves_neutral_without_any_calc():
    """No living opponent -> enqueue returns a degenerate handle and resolve short-circuits to NEUTRAL,
    mirroring compute_game_mode's ``not our_mons or not opp_mons`` guard, WITHOUT enqueuing or flushing
    any damage request. Guards the new split against issuing a stray calc on a degenerate board."""
    book = _book()
    state = BattleState()
    state.sides["p1"]["a"] = PokemonState(species="Incineroar", hp=200, max_hp=200,
                                          move_names={"Flare Blitz"})
    # p2 has no mons at all -> the opponent side is empty
    backend = RecordingBackend({})
    oracle = DamageOracle(client=CalcClient(backend=backend))
    handle = gm.enqueue_base_game_mode(state, our_side="p1", oracle=oracle, book=book)
    assert handle.degenerate is True
    oracle.flush()  # nothing was enqueued -> a no-op
    assert gm.resolve_base_game_mode(handle, oracle=oracle) == gm.GameMode.NEUTRAL
    assert backend.seen_defenders == []  # degenerate short-circuit issued NO damage calc
