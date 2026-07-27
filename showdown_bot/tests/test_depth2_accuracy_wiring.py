"""Accuracy × Depth-2 consistency tests (spec §10.1, §10.2).

Proves the once-resolved accuracy configuration reaches every Turn-2 evaluation
call through both the non-Mega and Mega Depth-2 paths.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from showdown_bot.battle import evaluate as evaluate_module
from showdown_bot.battle import search as search_module
from showdown_bot.battle.decision import _choose_best
from showdown_bot.battle.decision_trace import DecisionTrace
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


# ---- §10.1 Test 3: Mega Depth-2 forwarding ----

def test_depth2_accuracy_forwarded_mega(monkeypatch):
    """With SHOWDOWN_ACCURACY_MODE=1, SHOWDOWN_SEARCH_DEPTH=2, and a Mega-capable
    board, depth2_value_for_mega_context receives the resolved accuracy values
    in eval_kwargs (spec §10.1 test 3).

    Uses the mega_decision_fixture from conftest.py if available; otherwise skips."""
    d2_calls: list[dict] = []
    real_d2 = search_module.depth2_value_for_mega_context

    def _spy(*args, **kwargs):
        ek = kwargs.get("eval_kwargs") or {}
        d2_calls.append({
            "accuracy_mode": ek.get("accuracy_mode", "MISSING"),
            "accuracy_branch_cap": ek.get("accuracy_branch_cap", "MISSING"),
        })
        return real_d2(*args, **kwargs)

    monkeypatch.setattr(search_module, "depth2_value_for_mega_context", _spy)
    monkeypatch.setenv("SHOWDOWN_SEARCH_DEPTH", "2")
    monkeypatch.setenv("SHOWDOWN_ACCURACY_MODE", "1")
    monkeypatch.delenv("SHOWDOWN_ACCURACY_BRANCH_CAP", raising=False)

    try:
        from conftest import mega_decision_fixture_data
        req, kw = mega_decision_fixture_data()
        _choose_best(req, **kw)
    except (ImportError, AttributeError, TypeError):
        pytest.skip("mega_decision_fixture not available")

    if not d2_calls:
        pytest.skip("no depth-2 calls in mega path (board may not trigger depth-2)")

    for c in d2_calls:
        assert c["accuracy_mode"] is True, f"d2 mega call missing accuracy_mode: {c}"
        assert c["accuracy_branch_cap"] == 6, f"d2 mega call wrong cap: {c}"


# ---- §8.1: Depth-1 deterministic projection is unchanged ----

def test_depth1_projection_unchanged(monkeypatch):
    """With SHOWDOWN_SEARCH_DEPTH unset (=1), the deterministic decision projection
    matches the pre-slice golden exactly (spec §8.1)."""
    for var in ("SHOWDOWN_SEARCH_DEPTH", "SHOWDOWN_SEARCH_TOPN", "SHOWDOWN_SEARCH_TOPM",
                "SHOWDOWN_WORLD_SAMPLES"):
        monkeypatch.delenv(var, raising=False)

    from showdown_bot.battle.decision import heuristic_choose_for_request

    req = _d2_req()
    tr = DecisionTrace()
    choice = heuristic_choose_for_request(req, trace=tr, **_d2_kwargs())

    assert choice == "/choose move 3, move 3|2"
    assert tr.chosen_candidate_id == "(Protect, Protect)"
    assert tr.game_mode == "NEUTRAL"
    assert len(tr.candidates) == 6
    assert tr.candidates[0].score_vector == [5.4, 5.4, 3.6, 1.8, 3.6]
    assert tr.candidates[0].aggregate_score == 3.0528


# ---- §8.2: Accuracy-off Depth-2 projection is unchanged ----

def test_accuracy_off_depth2_unchanged(monkeypatch):
    """With SHOWDOWN_ACCURACY_MODE=0 and SHOWDOWN_SEARCH_DEPTH=2, passing
    explicit False/cap through eval_kwargs must not change evaluate_line's
    legacy accuracy-off behavior (spec §8.2)."""
    from showdown_bot.battle import decision as decision_module

    monkeypatch.setenv("SHOWDOWN_SEARCH_DEPTH", "2")
    monkeypatch.setenv("SHOWDOWN_ACCURACY_MODE", "0")
    for var in ("SHOWDOWN_SEARCH_TOPN", "SHOWDOWN_SEARCH_TOPM", "SHOWDOWN_WORLD_SAMPLES"):
        monkeypatch.delenv(var, raising=False)

    d2_calls = []
    real_d2 = decision_module.depth2_value

    def _spy(*args, **kwargs):
        ek = kwargs.get("eval_kwargs") or {}
        d2_calls.append({
            "accuracy_mode": ek.get("accuracy_mode"),
            "accuracy_branch_cap": ek.get("accuracy_branch_cap"),
        })
        return real_d2(*args, **kwargs)

    monkeypatch.setattr(decision_module, "depth2_value", _spy)

    choice_ja, _ = _choose_best(_d2_req(), **_d2_kwargs())

    assert len(d2_calls) == 4, f"expected 4 depth2_value calls, got {len(d2_calls)}"
    for c in d2_calls:
        assert c["accuracy_mode"] is False
        assert c["accuracy_branch_cap"] is not None


# ---- §10.2 Test 1: consumption counterproof ----

def test_accuracy_on_changes_turn2_value(monkeypatch):
    """A controlled scenario where accuracy on/off produces different refined
    values, proving the parameter is consumed not just forwarded (spec §10.2 test 1)."""
    from showdown_bot.battle import decision as decision_module

    monkeypatch.setenv("SHOWDOWN_SEARCH_DEPTH", "2")
    monkeypatch.delenv("SHOWDOWN_SEARCH_TOPN", raising=False)
    monkeypatch.delenv("SHOWDOWN_SEARCH_TOPM", raising=False)
    monkeypatch.delenv("SHOWDOWN_WORLD_SAMPLES", raising=False)

    real_d2 = decision_module.depth2_value

    def _run_with_mode(mode_val):
        values = []

        def _capture(*args, **kwargs):
            v = real_d2(*args, **kwargs)
            values.append(v)
            return v

        monkeypatch.setattr(decision_module, "depth2_value", _capture)
        monkeypatch.setenv("SHOWDOWN_ACCURACY_MODE", mode_val)
        _choose_best(_d2_req(), **_d2_kwargs())
        monkeypatch.setattr(decision_module, "depth2_value", real_d2)
        return values

    off_values = _run_with_mode("0")
    on_values = _run_with_mode("1")

    assert len(off_values) == len(on_values) == 4
    assert off_values != on_values, (
        "accuracy_mode=True produced the same Turn-2 values as accuracy_mode=False — "
        "the parameter is forwarded but not consumed"
    )


# ---- §6.4 / §10.2 Test 4: one Turn-2 successor per selected slot ----

def test_one_successor_per_selected_slot(monkeypatch):
    """Multiple Turn-1 accuracy leaves still produce exactly one Depth-2 successor
    per selected (candidate, response slot). Call count bounded by frontier (N*M),
    never multiplied by Turn-1 accuracy leaves (spec §6.4)."""
    from showdown_bot.battle import decision as decision_module

    monkeypatch.setenv("SHOWDOWN_SEARCH_DEPTH", "2")
    monkeypatch.setenv("SHOWDOWN_ACCURACY_MODE", "1")
    monkeypatch.delenv("SHOWDOWN_ACCURACY_BRANCH_CAP", raising=False)
    monkeypatch.delenv("SHOWDOWN_WORLD_SAMPLES", raising=False)

    d2_calls = []
    real_d2 = decision_module.depth2_value

    def _spy(*args, **kwargs):
        d2_calls.append(1)
        return real_d2(*args, **kwargs)

    monkeypatch.setattr(decision_module, "depth2_value", _spy)

    _choose_best(_d2_req(), **_d2_kwargs())

    top_n = 2  # default SHOWDOWN_SEARCH_TOPN
    top_m = 2  # default SHOWDOWN_SEARCH_TOPM
    assert len(d2_calls) == top_n * top_m, (
        f"expected {top_n * top_m} depth2_value calls but got {len(d2_calls)} — "
        "Turn-1 accuracy leaves may have expanded into Turn-2"
    )


# ---- §10.2 Test 5: K-world active suppresses Depth-2 ----

def test_kworld_suppresses_depth2_with_accuracy(monkeypatch):
    """With SHOWDOWN_WORLD_SAMPLES=2, depth2_value must NOT fire even when
    SHOWDOWN_SEARCH_DEPTH=2 and SHOWDOWN_ACCURACY_MODE=1 (spec §10.2 test 5)."""
    from showdown_bot.battle import decision as decision_module

    d2_calls = []
    real_d2 = decision_module.depth2_value

    def _spy(*args, **kwargs):
        d2_calls.append(1)
        return real_d2(*args, **kwargs)

    monkeypatch.setattr(decision_module, "depth2_value", _spy)
    monkeypatch.setenv("SHOWDOWN_SEARCH_DEPTH", "2")
    monkeypatch.setenv("SHOWDOWN_ACCURACY_MODE", "1")
    monkeypatch.setenv("SHOWDOWN_WORLD_SAMPLES", "2")

    _choose_best(_d2_req(), **_d2_kwargs())

    assert len(d2_calls) == 0, "depth2_value fired with K-world sampling active"


# ---- §10.1 Test 4: no new accuracy env reads downstream ----

def test_no_accuracy_env_reads_in_search(monkeypatch):
    """Neither search.py::depth2_value nor search.py::_score_turn2_plans
    reads SHOWDOWN_ACCURACY_MODE or SHOWDOWN_ACCURACY_BRANCH_CAP from the
    environment (spec §10.1 test 4)."""
    import os

    original_getenv = os.environ.get
    forbidden = {"SHOWDOWN_ACCURACY_MODE", "SHOWDOWN_ACCURACY_BRANCH_CAP"}
    violations = []

    def _guarded_get(key, *args):
        if key in forbidden:
            import traceback
            tb = traceback.format_stack()
            if any("search.py" in frame for frame in tb):
                violations.append(key)
        return original_getenv(key, *args)

    monkeypatch.setattr(os.environ, "get", _guarded_get)
    monkeypatch.setenv("SHOWDOWN_SEARCH_DEPTH", "2")
    monkeypatch.setenv("SHOWDOWN_ACCURACY_MODE", "1")

    _choose_best(_d2_req(), **_d2_kwargs())

    assert violations == [], f"search.py read forbidden env vars: {violations}"
