from __future__ import annotations

import json
import re
from pathlib import Path

from showdown_bot.battle.baselines import max_damage_choice
from showdown_bot.engine.belief.hypotheses import load_spread_book
from showdown_bot.engine.calc.models import DamageResult
from showdown_bot.engine.format_config import load_format_config
from showdown_bot.engine.state import BattleState, PokemonState
from showdown_bot.models.request import BattleRequest

FIXTURES = Path(__file__).parent / "fixtures"
CHOOSE_RE = re.compile(r"^/choose .+, .+\|\d+$")


def _book():
    cfg = load_format_config("gen9vgc2025regi")
    return load_spread_book(cfg.meta_path("default_spreads"))


def _req():
    return BattleRequest.model_validate(
        json.loads((FIXTURES / "request_doubles_moves.json").read_text())
    )


def _state():
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Incineroar", hp=150, max_hp=150)
    st.sides["p1"]["b"] = PokemonState(species="Rillaboom", hp=155, max_hp=155)
    st.sides["p2"]["a"] = PokemonState(species="Flutter Mane", hp=131, max_hp=131)
    st.sides["p2"]["b"] = PokemonState(species="Tornadus", hp=140, max_hp=140)
    return st


class FakeOracle:
    def __init__(self, frac):
        self.frac = frac

    def _res(self):
        return DamageResult(min_damage=int(self.frac * 100), max_damage=int(self.frac * 100), max_hp=100)

    def request(self, req):
        return id(req)

    def get(self, key):
        return self._res()

    def damage(self, req):
        return self._res()

    def flush(self):
        pass


def test_max_damage_returns_legal_choose():
    out = max_damage_choice(
        _req(), state=_state(), book=_book(), our_side="p1",
        oracle=FakeOracle(0.3), speed_oracle=None,
    )
    assert CHOOSE_RE.match(out), out


def test_max_damage_never_teras():
    out = max_damage_choice(
        _req(), state=_state(), book=_book(), our_side="p1",
        oracle=FakeOracle(0.3), speed_oracle=None,
    )
    assert "terastallize" not in out


def test_max_damage_prefers_attacks_over_passive():
    # With positive damage on every move, the chosen pair should be two moves
    # (max damage), not a switch/protect line.
    out = max_damage_choice(
        _req(), state=_state(), book=_book(), our_side="p1",
        oracle=FakeOracle(0.5), speed_oracle=None,
    )
    body = out[len("/choose "):].split("|")[0]
    left, right = body.split(", ")
    assert left.startswith("move")
    assert right.startswith("move")


# --- T3c: eval-deterministic fallback (live default unchanged) ---

def test_equal_damage_tie_is_deterministic():
    # FakeOracle(const) makes EVERY move deal equal damage -> a genuine tie across
    # many joint actions. The pick must be deterministic (enumeration-order tie-break).
    kw = dict(state=_state(), book=_book(), our_side="p1", oracle=FakeOracle(0.3), speed_oracle=None)
    a = max_damage_choice(_req(), **kw)
    b = max_damage_choice(_req(), **kw)
    assert a == b


def test_default_fallback_routes_through_pick_random_pair(monkeypatch):
    # fallback=None (live default) must still route the no-actions path through
    # pick_random_pair -> live behavior byte-for-byte preserved.
    from showdown_bot.battle.legal_actions import enumerate_slot_pairs
    monkeypatch.setattr("showdown_bot.battle.baselines.enumerate_my_actions", lambda req: [])
    seen = {}

    def fake_prp(req):
        seen["called"] = True
        return enumerate_slot_pairs(req)[0]

    monkeypatch.setattr("showdown_bot.battle.baselines.pick_random_pair", fake_prp)
    out = max_damage_choice(_req(), state=_state(), book=_book(), our_side="p1",
                            oracle=FakeOracle(0.3), speed_oracle=None)  # fallback default (None)
    assert seen.get("called") and out.startswith("/choose")


def test_injected_fallback_is_used_on_empty_actions(monkeypatch):
    monkeypatch.setattr("showdown_bot.battle.baselines.enumerate_my_actions", lambda req: [])
    req = _req()
    out = max_damage_choice(req, state=_state(), book=_book(), our_side="p1",
                            oracle=FakeOracle(0.3), speed_oracle=None,
                            fallback=lambda r: f"/choose default|{r.rqid}")
    assert out == f"/choose default|{req.rqid}"
