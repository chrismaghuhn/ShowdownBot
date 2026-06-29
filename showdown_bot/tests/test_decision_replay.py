from __future__ import annotations

import json
import re
from pathlib import Path

from showdown_bot.battle.decision import (
    choose_with_fallback,
    heuristic_choose_for_request,
)
from showdown_bot.engine.belief.hypotheses import load_spread_book
from showdown_bot.engine.calc.models import DamageResult
from showdown_bot.engine.format_config import load_format_config
from showdown_bot.engine.speed import SpeedRange
from showdown_bot.engine.state import BattleState, PokemonState
from showdown_bot.models.request import BattleRequest

FIXTURES = Path(__file__).parent / "fixtures"
CHOOSE_RE = re.compile(r"^/choose .+, .+\|\d+$")


def _book():
    cfg = load_format_config("gen9vgc2026regi")
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


class FakeCalc:
    """damage_batch for classify_game_mode; never a guaranteed KO -> NEUTRAL."""

    backend = None

    def damage_batch(self, requests):
        return [DamageResult(min_damage=20, max_damage=35, max_hp=150) for _ in requests]


class FakeOracle:
    def __init__(self):
        self.batch_calls = 0

    def request(self, req):
        return (req.attacker.species, req.move, req.defender.species)

    def get(self, key):
        return DamageResult(min_damage=45, max_damage=70, max_hp=150)

    def damage(self, req):
        return DamageResult(min_damage=45, max_damage=70, max_hp=150)

    def flush(self):
        self.batch_calls += 1


class FakeSpeed:
    def our_speed(self, base, mon, field, side):
        return base or 100

    def opponent_range(self, mon, field, side, *, book):
        return SpeedRange(min=80, likely=110, max=150)


class FakeDex:
    def types(self, species):
        return {"Flutter Mane": ["Ghost", "Fairy"], "Tornadus": ["Flying"]}.get(
            species, ["Normal"]
        )


def test_heuristic_returns_legal_choose_offline():
    out = heuristic_choose_for_request(
        _req(),
        state=_state(),
        book=_book(),
        our_side="p1",
        calc=FakeCalc(),
        oracle=FakeOracle(),
        speed_oracle=FakeSpeed(),
        dex=FakeDex(),
    )
    assert CHOOSE_RE.match(out), out
    assert out.endswith("|2")


def test_heuristic_is_deterministic():
    kw = dict(
        state=_state(), book=_book(), our_side="p1",
        calc=FakeCalc(), oracle=FakeOracle(), speed_oracle=FakeSpeed(), dex=FakeDex(),
    )
    a = heuristic_choose_for_request(_req(), **kw)
    b = heuristic_choose_for_request(_req(), **kw)
    assert a == b


def test_does_not_spam_protect_when_doomed():
    """Regression: when both actives already Protected last turn (consecutive=1)
    a second Protect fails, so the heuristic must pick a real action instead of
    spamming Protect into a KO."""
    st = _state()
    st.sides["p1"]["a"].consecutive_protect = 1
    st.sides["p1"]["a"].moved_since_switch = True
    st.sides["p1"]["b"].consecutive_protect = 1
    st.sides["p1"]["b"].moved_since_switch = True

    class HardHitOracle:
        def request(self, req):
            return (req.attacker.species, req.move, req.defender.species)

        def get(self, key):
            return DamageResult(min_damage=60, max_damage=90, max_hp=150)

        def damage(self, req):
            return DamageResult(min_damage=60, max_damage=90, max_hp=150)

        def flush(self):
            pass

    out = heuristic_choose_for_request(
        _req(), state=st, book=_book(), our_side="p1",
        calc=FakeCalc(), oracle=HardHitOracle(), speed_oracle=FakeSpeed(), dex=FakeDex(),
    )
    # Both slots choosing Protect would be "move 3, move 3" (Protect is index 3).
    assert "move 3, move 3" not in out, out


def test_fallback_to_random_without_state():
    out = choose_with_fallback(_req())  # no state/book -> random legal pair
    assert out.startswith("/choose ")
    assert out.endswith("|2")


def test_fallback_chain_survives_broken_calc():
    class BrokenCalc:
        backend = None

        def damage_batch(self, requests):
            raise RuntimeError("calc down")

    out = choose_with_fallback(
        _req(),
        state=_state(),
        book=_book(),
        our_side="p1",
        calc=BrokenCalc(),
        oracle=FakeOracle(),
        speed_oracle=FakeSpeed(),
        dex=FakeDex(),
        hard_timeout=4.0,
    )
    # heuristic crashes -> chain still produces a legal choice
    assert out.startswith("/choose ")
