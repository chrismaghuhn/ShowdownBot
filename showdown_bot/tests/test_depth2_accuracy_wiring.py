"""Accuracy × Depth-2 consistency tests (spec §10.1, §10.2).

Proves the once-resolved accuracy configuration reaches every Turn-2 evaluation
call through both the non-Mega and Mega Depth-2 paths.
"""
from __future__ import annotations

import json
from pathlib import Path

from showdown_bot.battle import evaluate as evaluate_module
from showdown_bot.battle.decision import _choose_best
from showdown_bot.engine.state import BattleState, PokemonState

FIXTURES = Path(__file__).parent / "fixtures"


def _install_eval_recorder(monkeypatch):
    """Wrap ``_evaluate_line_details`` to record accuracy kwargs on every call.
    Same pattern as test_accuracy_mode_wiring.py."""
    calls: list[dict] = []
    real = evaluate_module._evaluate_line_details

    def _wrapped(*args, **kwargs):
        calls.append({
            "accuracy_mode": kwargs.get("accuracy_mode", False),
            "accuracy_branch_cap": kwargs.get("accuracy_branch_cap", 4),
        })
        return real(*args, **kwargs)

    monkeypatch.setattr(evaluate_module, "_evaluate_line_details", _wrapped)
    return calls


# --- Fixtures (reuse test_search_depth2.py's board) ---

def _d2_req():
    from showdown_bot.models.request import BattleRequest
    data = json.loads((FIXTURES / "request_doubles_moves.json").read_text())
    return BattleRequest.model_validate(data)


def _d2_state():
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


class _FakeCalc:
    backend = None
    def damage_batch(self, requests):
        from showdown_bot.engine.calc.models import DamageResult
        return [DamageResult(min_damage=20, max_damage=35, max_hp=150) for _ in requests]


class _FakeOracleD2:
    def request(self, req):
        return (req.attacker.species, req.move, req.defender.species)
    def get(self, key):
        from showdown_bot.engine.calc.models import DamageResult
        return DamageResult(min_damage=45, max_damage=70, max_hp=150)
    def damage(self, req):
        from showdown_bot.engine.calc.models import DamageResult
        return DamageResult(min_damage=45, max_damage=70, max_hp=150)
    def flush(self):
        pass


class _FakeSpeed:
    def our_speed(self, base, mon, field, side):
        return base or 100
    def opponent_range(self, mon, field, side, *, book):
        from showdown_bot.engine.speed import SpeedRange
        return SpeedRange(min=80, likely=110, max=150)


class _FakeDex:
    def types(self, species):
        return {"Flutter Mane": ["Ghost", "Fairy"], "Tornadus": ["Flying"]}.get(
            species, ["Normal"]
        )


def _d2_book():
    from showdown_bot.engine.belief.hypotheses import load_spread_book
    from showdown_bot.engine.format_config import load_format_config
    cfg = load_format_config("gen9vgc2025regi")
    return load_spread_book(cfg.meta_path("default_spreads"))


def _d2_kwargs():
    return dict(
        state=_d2_state(), book=_d2_book(), our_side="p1",
        calc=_FakeCalc(), oracle=_FakeOracleD2(),
        speed_oracle=_FakeSpeed(), dex=_FakeDex(),
    )


# ---- §10.1 Test 1: accuracy resolvers called exactly once per decision ----

def test_accuracy_resolvers_called_once_per_decision(monkeypatch):
    """Patch _accuracy_mode and _accuracy_branch_cap with call-count spies;
    one scored decision calls each exactly once (spec §10.1 test 1)."""
    from showdown_bot.battle import decision as decision_module

    mode_calls = []
    cap_calls = []
    real_mode = decision_module._accuracy_mode
    real_cap = decision_module._accuracy_branch_cap

    def _spy_mode():
        result = real_mode()
        mode_calls.append(result)
        return result

    def _spy_cap():
        result = real_cap()
        cap_calls.append(result)
        return result

    monkeypatch.setattr(decision_module, "_accuracy_mode", _spy_mode)
    monkeypatch.setattr(decision_module, "_accuracy_branch_cap", _spy_cap)
    monkeypatch.setenv("SHOWDOWN_SEARCH_DEPTH", "2")
    monkeypatch.setenv("SHOWDOWN_ACCURACY_MODE", "1")
    monkeypatch.delenv("SHOWDOWN_ACCURACY_BRANCH_CAP", raising=False)

    _choose_best(_d2_req(), **_d2_kwargs())

    assert len(mode_calls) == 1, f"_accuracy_mode called {len(mode_calls)} times"
    assert len(cap_calls) == 1, f"_accuracy_branch_cap called {len(cap_calls)} times"


# ---- §10.1 Test 2: non-Mega Depth-2 forwarding ----

def test_depth2_accuracy_forwarded_nonmega(monkeypatch):
    """With SHOWDOWN_ACCURACY_MODE=1 and SHOWDOWN_SEARCH_DEPTH=2, every
    evaluate_line call (including Turn-2 via depth2_value) receives
    accuracy_mode=True and accuracy_branch_cap=6.

    THIS TEST SHOULD FAIL before the fix: Turn-2 calls currently receive
    accuracy_mode=False (the evaluate_line default)."""
    calls = _install_eval_recorder(monkeypatch)
    monkeypatch.setenv("SHOWDOWN_SEARCH_DEPTH", "2")
    monkeypatch.setenv("SHOWDOWN_ACCURACY_MODE", "1")
    monkeypatch.delenv("SHOWDOWN_ACCURACY_BRANCH_CAP", raising=False)
    monkeypatch.delenv("SHOWDOWN_WORLD_SAMPLES", raising=False)

    _choose_best(_d2_req(), **_d2_kwargs())

    assert len(calls) >= 5, (
        f"expected Turn-1 calls + Turn-2 calls, got {len(calls)}"
    )
    assert all(c["accuracy_mode"] is True for c in calls), (
        f"not all calls got accuracy_mode=True: {calls}"
    )
    assert all(c["accuracy_branch_cap"] == 6 for c in calls), (
        f"not all calls got accuracy_branch_cap=6: {calls}"
    )
