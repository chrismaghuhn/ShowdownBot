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

def test_depth2_accuracy_forwarded_mega(mega_decision_fixture, monkeypatch):
    """With SHOWDOWN_ACCURACY_MODE=1, SHOWDOWN_SEARCH_DEPTH=2, and a Mega-capable
    board, depth2_value_for_mega_context receives the resolved accuracy values
    in eval_kwargs (spec §10.1 test 3).

    Patches the already-imported reference in mega_scoring, not search_module."""
    from showdown_bot.battle import mega_scoring as mega_scoring_module

    d2_calls: list[dict] = []
    real_d2 = mega_scoring_module.depth2_value_for_mega_context

    def _spy(*args, **kwargs):
        ek = kwargs.get("eval_kwargs") or {}
        d2_calls.append({
            "accuracy_mode": ek.get("accuracy_mode", "MISSING"),
            "accuracy_branch_cap": ek.get("accuracy_branch_cap", "MISSING"),
        })
        return real_d2(*args, **kwargs)

    monkeypatch.setattr(mega_scoring_module, "depth2_value_for_mega_context", _spy)
    monkeypatch.setenv("SHOWDOWN_SEARCH_DEPTH", "2")
    monkeypatch.setenv("SHOWDOWN_ACCURACY_MODE", "1")
    monkeypatch.delenv("SHOWDOWN_ACCURACY_BRANCH_CAP", raising=False)

    req, kw = mega_decision_fixture
    # Filter to only kwargs _choose_best accepts (fixture also provides
    # calc_profile, evaluated_variants, contexts, mode for _choose_best_mega).
    _CB_KEYS = {
        "state", "book", "our_side", "calc", "oracle", "speed_oracle", "dex",
        "priors", "weights", "risk_lambda", "tera_margin", "rollout_horizon",
        "report", "our_spreads", "opp_sets", "trace", "format_config",
        "opp_mega_evidence_sink", "shape_sink", "readiness_sink",
    }
    cb_kw = {k: v for k, v in kw.items() if k in _CB_KEYS}
    _choose_best(req, **cb_kw)

    assert d2_calls, "mega path must invoke depth-2 at least once for this board"

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


# ---- §10.3: Telemetry wiring ----

def test_readiness_sink_populated_depth2(monkeypatch):
    """With profiling conceptually on and SHOWDOWN_SEARCH_DEPTH=2, the
    readiness sink is populated with correct search/accuracy settings
    and non-zero Turn-1 accuracy counts (spec §10.3 tests 1-3)."""
    from showdown_bot.eval.depth2_readiness import Depth2ReadinessCounts

    monkeypatch.setenv("SHOWDOWN_SEARCH_DEPTH", "2")
    monkeypatch.setenv("SHOWDOWN_ACCURACY_MODE", "1")
    monkeypatch.delenv("SHOWDOWN_ACCURACY_BRANCH_CAP", raising=False)
    monkeypatch.delenv("SHOWDOWN_WORLD_SAMPLES", raising=False)

    sink = Depth2ReadinessCounts()
    _choose_best(_d2_req(), readiness_sink=sink, **_d2_kwargs())

    assert sink.search_depth == 2
    assert sink.search_topn_requested == 2
    assert sink.search_topm_requested == 2
    assert sink.accuracy_mode is True
    assert sink.accuracy_branch_cap == 6
    assert sink.turn1_accuracy_leaf_count > 0
    assert sink.depth2_candidates_selected > 0
    assert sink.depth2_response_slots_eligible > 0


def test_shape_sink_depth2_frontier_nonmega(monkeypatch):
    """The non-Mega depth-2 path must increment shape_sink.depth2_frontier
    for each (candidate, response_slot) evaluation, matching the Mega path's
    behavior (Blocker 1 fix)."""
    from showdown_bot.battle.mega_scoring import MegaShapeCounts

    monkeypatch.setenv("SHOWDOWN_SEARCH_DEPTH", "2")
    monkeypatch.setenv("SHOWDOWN_ACCURACY_MODE", "1")
    monkeypatch.delenv("SHOWDOWN_ACCURACY_BRANCH_CAP", raising=False)
    monkeypatch.delenv("SHOWDOWN_WORLD_SAMPLES", raising=False)

    shape = MegaShapeCounts()
    _choose_best(_d2_req(), shape_sink=shape, **_d2_kwargs())

    top_n = 2
    top_m = 2
    assert shape.depth2_frontier == top_n * top_m, (
        f"expected depth2_frontier={top_n * top_m} but got {shape.depth2_frontier} — "
        "non-Mega depth-2 must increment shape_sink.depth2_frontier"
    )


def test_readiness_sink_none_does_not_crash(monkeypatch):
    """With readiness_sink=None (profiling off), the decision runs
    identically with no allocation or crash (spec §10.3 test 4)."""
    monkeypatch.setenv("SHOWDOWN_SEARCH_DEPTH", "2")
    monkeypatch.setenv("SHOWDOWN_ACCURACY_MODE", "1")

    choice, _ = _choose_best(_d2_req(), readiness_sink=None, **_d2_kwargs())
    assert choice is not None


def test_readiness_sink_depth1_zeros(monkeypatch):
    """With SHOWDOWN_SEARCH_DEPTH=1, Turn-2 and depth2 counters are all zero."""
    from showdown_bot.eval.depth2_readiness import Depth2ReadinessCounts

    monkeypatch.delenv("SHOWDOWN_SEARCH_DEPTH", raising=False)
    monkeypatch.setenv("SHOWDOWN_ACCURACY_MODE", "1")

    sink = Depth2ReadinessCounts()
    _choose_best(_d2_req(), readiness_sink=sink, **_d2_kwargs())

    assert sink.search_depth == 1
    assert sink.depth2_candidates_selected == 0
    assert sink.depth2_response_slots_eligible == 0
    assert sink.turn2_accuracy_leaf_count == 0
    assert sink.turn2_accuracy_cap_hits == 0
    assert sink.turn1_accuracy_leaf_count > 0  # Turn-1 still counted


def test_trace_recomputation_does_not_alter_counts(monkeypatch):
    """Passing trace= and report= to _choose_best triggers _breakdowns_for
    recomputation inside the trace path. That recomputation must NOT increment
    the readiness sink's counters (spec §10.3 test 2).

    Runs two decisions with the same board: one with trace/report (which triggers
    recomputation), one without. The sink counts must be identical."""
    from showdown_bot.eval.depth2_readiness import Depth2ReadinessCounts

    monkeypatch.setenv("SHOWDOWN_SEARCH_DEPTH", "2")
    monkeypatch.setenv("SHOWDOWN_ACCURACY_MODE", "1")
    monkeypatch.delenv("SHOWDOWN_ACCURACY_BRANCH_CAP", raising=False)
    monkeypatch.delenv("SHOWDOWN_WORLD_SAMPLES", raising=False)

    sink_no_trace = Depth2ReadinessCounts()
    _choose_best(_d2_req(), readiness_sink=sink_no_trace, **_d2_kwargs())

    sink_with_trace = Depth2ReadinessCounts()
    _choose_best(
        _d2_req(), readiness_sink=sink_with_trace,
        report=[], trace=DecisionTrace(), **_d2_kwargs(),
    )

    assert sink_no_trace.turn1_accuracy_leaf_count == sink_with_trace.turn1_accuracy_leaf_count
    assert sink_no_trace.turn1_accuracy_cap_hits == sink_with_trace.turn1_accuracy_cap_hits
    assert sink_no_trace.turn2_accuracy_leaf_count == sink_with_trace.turn2_accuracy_leaf_count
    assert sink_no_trace.turn2_accuracy_cap_hits == sink_with_trace.turn2_accuracy_cap_hits


# ---- Origin counterproof: search resolvers once per decision ----

def test_search_resolvers_called_once_per_decision(monkeypatch):
    """_search_depth, _search_topn, _search_topm each called exactly once per
    scored decision (mirrors the accuracy resolver test)."""
    from showdown_bot.battle import decision as decision_module

    depth_calls, topn_calls, topm_calls = [], [], []
    real_depth = decision_module._search_depth
    real_topn = decision_module._search_topn
    real_topm = decision_module._search_topm

    def _spy_depth():
        r = real_depth(); depth_calls.append(r); return r

    def _spy_topn():
        r = real_topn(); topn_calls.append(r); return r

    def _spy_topm():
        r = real_topm(); topm_calls.append(r); return r

    monkeypatch.setattr(decision_module, "_search_depth", _spy_depth)
    monkeypatch.setattr(decision_module, "_search_topn", _spy_topn)
    monkeypatch.setattr(decision_module, "_search_topm", _spy_topm)
    monkeypatch.setenv("SHOWDOWN_SEARCH_DEPTH", "2")
    monkeypatch.setenv("SHOWDOWN_SEARCH_TOPN", "3")
    monkeypatch.setenv("SHOWDOWN_SEARCH_TOPM", "2")

    _choose_best(_d2_req(), **_d2_kwargs())

    assert len(depth_calls) == 1, f"_search_depth called {len(depth_calls)} times"
    assert len(topn_calls) == 1, f"_search_topn called {len(topn_calls)} times"
    assert len(topm_calls) == 1, f"_search_topm called {len(topm_calls)} times"


# ---- Origin counterproof: K-world → n_worlds > 1, zero depth-2 ----

def test_kworld_nonmega_n_worlds_and_no_depth2(monkeypatch):
    """With real K-world sampling active (opp_sets diverge from book, triggering
    build_world_dist's 2-point distribution), shape_sink.n_worlds > 1 and all
    depth-2 counters are zero (K-world suppresses depth-2)."""
    from showdown_bot.battle.mega_scoring import MegaShapeCounts
    from showdown_bot.battle.opponent import SpeciesDex
    from showdown_bot.battle.oracle import DamageOracle
    from showdown_bot.engine.belief.hypotheses import SpeciesSpreads, SpreadPreset
    from showdown_bot.engine.calc.client import CalcClient
    from showdown_bot.engine.calc_profile import build_speed_oracle, calc_profile_from_config
    from showdown_bot.engine.format_config import load_format_config
    from showdown_bot.eval.depth2_readiness import Depth2ReadinessCounts

    monkeypatch.setenv("SHOWDOWN_WORLD_SAMPLES", "3")
    monkeypatch.setenv("SHOWDOWN_SEARCH_DEPTH", "2")
    monkeypatch.delenv("SHOWDOWN_ACCURACY_MODE", raising=False)

    calc = CalcClient()
    oracle = DamageOracle(calc)
    cfg = load_format_config("gen9vgc2025regi")
    profile = calc_profile_from_config(cfg)
    speed = build_speed_oracle(calc.backend, profile)
    dex = SpeciesDex(calc.backend)
    book = _d2_book()

    custom_spread = SpeciesSpreads(
        offense=SpreadPreset(nature="Adamant", evs={"atk": 64}),
        defense=SpreadPreset(nature="Relaxed", evs={"def": 64}),
    )
    opp_sets = {"fluttermane": custom_spread}

    shape = MegaShapeCounts()
    readiness = Depth2ReadinessCounts()
    _choose_best(
        _d2_req(), state=_d2_state(), book=book, our_side="p1",
        calc=calc, oracle=oracle, speed_oracle=speed, dex=dex,
        opp_sets=opp_sets, shape_sink=shape, readiness_sink=readiness,
    )

    assert shape.n_worlds > 1, f"expected n_worlds > 1, got {shape.n_worlds}"
    assert shape.depth2_frontier == 0, "K-world must suppress depth-2"
    assert readiness.depth2_candidates_selected == 0
    assert readiness.depth2_response_slots_eligible == 0


# ---- Origin counterproof: eligible slots pre-cap, non-Mega ----

def test_eligible_slots_precap_nonmega(monkeypatch):
    """With SHOWDOWN_SEARCH_TOPM=1 and depth 2, depth2_response_slots_eligible
    counts ALL response slots (pre-cap), not just the top-M refined ones.
    eligible > frontier proves the count is pre-cap."""
    from showdown_bot.battle.mega_scoring import MegaShapeCounts
    from showdown_bot.eval.depth2_readiness import Depth2ReadinessCounts

    monkeypatch.setenv("SHOWDOWN_SEARCH_DEPTH", "2")
    monkeypatch.setenv("SHOWDOWN_SEARCH_TOPM", "1")
    monkeypatch.delenv("SHOWDOWN_WORLD_SAMPLES", raising=False)
    monkeypatch.delenv("SHOWDOWN_ACCURACY_MODE", raising=False)

    shape = MegaShapeCounts()
    readiness = Depth2ReadinessCounts()
    _choose_best(_d2_req(), shape_sink=shape, readiness_sink=readiness, **_d2_kwargs())

    assert readiness.depth2_response_slots_eligible > 0
    assert shape.depth2_frontier > 0
    assert readiness.depth2_response_slots_eligible > shape.depth2_frontier, (
        f"eligible ({readiness.depth2_response_slots_eligible}) should exceed "
        f"frontier ({shape.depth2_frontier}) when top-M < n_resps (pre-cap count)"
    )


# ---- Origin counterproof: eligible slots pre-cap, Mega ----

def test_eligible_slots_precap_mega(mega_decision_fixture, monkeypatch):
    """Same pre-cap proof for the Mega path: depth2_response_slots_eligible
    counts all response slots per top-N candidate, not just top-M."""
    from showdown_bot.battle.mega_scoring import MegaShapeCounts
    from showdown_bot.eval.depth2_readiness import Depth2ReadinessCounts

    monkeypatch.setenv("SHOWDOWN_SEARCH_DEPTH", "2")
    monkeypatch.setenv("SHOWDOWN_SEARCH_TOPM", "1")
    monkeypatch.delenv("SHOWDOWN_WORLD_SAMPLES", raising=False)
    monkeypatch.delenv("SHOWDOWN_ACCURACY_MODE", raising=False)

    req, kw = mega_decision_fixture
    _CB_KEYS = {
        "state", "book", "our_side", "calc", "oracle", "speed_oracle", "dex",
        "priors", "weights", "risk_lambda", "tera_margin", "rollout_horizon",
        "report", "our_spreads", "opp_sets", "trace", "format_config",
        "opp_mega_evidence_sink", "shape_sink", "readiness_sink",
    }

    shape = MegaShapeCounts()
    readiness = Depth2ReadinessCounts()
    cb_kw = {k: v for k, v in kw.items() if k in _CB_KEYS}
    cb_kw["shape_sink"] = shape
    cb_kw["readiness_sink"] = readiness

    _choose_best(req, **cb_kw)

    assert readiness.depth2_response_slots_eligible > 0
    assert shape.depth2_frontier > 0
    assert readiness.depth2_response_slots_eligible > shape.depth2_frontier, (
        f"eligible ({readiness.depth2_response_slots_eligible}) should exceed "
        f"frontier ({shape.depth2_frontier}) when top-M < n_resps (pre-cap count)"
    )
