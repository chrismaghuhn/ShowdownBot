import json
from pathlib import Path

import copy
from showdown_bot.engine.state import BattleState, PokemonState
from showdown_bot.battle.search import approx_turn2_state

FIXTURES = Path(__file__).parent / "fixtures"


def _state():
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Incineroar", hp=150, max_hp=150)
    st.sides["p2"]["a"] = PokemonState(species="Flutter Mane", hp=131, max_hp=131)
    st.field.trick_room = True
    st.turn = 3
    return st


def test_transition_subtracts_damage_marks_faint_advances_turn():
    st = _state()
    # opponent deals 200 to our Incineroar(150) -> faint; we deal 50 to Flutter Mane(131)
    nxt = approx_turn2_state(st, our_side="p1",
        applied_damage={("p1", "a"): 200, ("p2", "a"): 50})
    assert nxt is not st and nxt.side("p1")["a"] is not st.side("p1")["a"]  # deep copy
    assert nxt.side("p1")["a"].hp == 0 and nxt.side("p1")["a"].fainted is True
    assert nxt.side("p2")["a"].hp == 81 and nxt.side("p2")["a"].fainted is False
    assert nxt.turn == 4                      # turn advanced
    assert nxt.field.trick_room is True       # field persists (no counters in FieldState)
    assert st.side("p1")["a"].hp == 150        # original untouched


def test_transition_clamps_hp_nonnegative():
    st = _state()
    nxt = approx_turn2_state(st, our_side="p1", applied_damage={("p2", "a"): 9999})
    assert nxt.side("p2")["a"].hp == 0 and nxt.side("p2")["a"].fainted is True


def test_depth2_value_is_turn2_aggregate(monkeypatch):
    from showdown_bot.battle import search
    # fake turn-2 world: one opp response, evaluate_line returns fixed values,
    # aggregate returns the max over my turn-2 actions.
    monkeypatch.setattr(search, "predict_responses", lambda *a, **k: [
        type("R", (), {"actions": [], "weight": 1.0})()])
    my_turn2 = {"A": [1.0], "B": [3.0]}     # B is better at turn 2
    monkeypatch.setattr(search, "_score_turn2_plans",
                        lambda *a, **k: [("A", my_turn2["A"]), ("B", my_turn2["B"])])
    monkeypatch.setattr(search, "aggregate_scores", lambda scores, *a, **k: max(scores))
    monkeypatch.setattr(search, "pick_best",
                        lambda items, *a, **k: max(items, key=lambda it: max(it[1])))
    v = search.depth2_value(_state(), our_side="p1", applied_damage={},
                            mode="NEUTRAL", risk_lambda=0.5, top_m=2,
                            book=None, oracle=None, predict_kwargs={}, model_kwargs={},
                            eval_kwargs={})
    assert v == 3.0     # my best turn-2 action's value


def test_depth2_value_real_path_smoke():
    """Non-mocked integration smoke (beyond the plan's DI test): the real
    ``_score_turn2_plans`` body -- the role-reversed ``predict_responses``
    adaptation used because no live ``BattleRequest`` exists for a
    hypothetical turn-2 state -- runs end-to-end against a real ``SpreadBook``
    and a fake oracle (no Node/network dependency) and returns a finite
    float. De-risks the one seam Task 3's given DI test fully mocks out."""
    from showdown_bot.battle.search import depth2_value
    from showdown_bot.engine.belief.game_mode import GameMode
    from showdown_bot.engine.belief.hypotheses import load_spread_book
    from showdown_bot.engine.calc.models import DamageResult
    from showdown_bot.engine.format_config import load_format_config

    class _FakeOracle:
        def request(self, req):
            return (req.attacker.species, req.move, req.defender.species)

        def get(self, key):
            return DamageResult(min_damage=45, max_damage=70, max_hp=150)

        def damage(self, req):
            return DamageResult(min_damage=45, max_damage=70, max_hp=150)

        def flush(self):
            pass

    cfg = load_format_config("gen9vgc2025regi")
    book = load_spread_book(cfg.meta_path("default_spreads"))

    v = depth2_value(
        _state(), our_side="p1", applied_damage={("p2", "a"): 40},
        mode=GameMode.NEUTRAL, risk_lambda=0.5, top_m=2,
        book=book, oracle=_FakeOracle(),
    )
    assert isinstance(v, float)


# ---------------------------------------------------------------------------
# Task 4: wiring depth2_value into _choose_best's single-world path
# ---------------------------------------------------------------------------
# Fakes mirror test_decision_trace.py's fixture (no live server / Node needed).

class _FakeCalc:
    """Returns non-KO damage (keeps game mode NEUTRAL)."""

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


def _d2_kwargs():
    return dict(
        state=_d2_state(),
        book=_d2_book(),
        our_side="p1",
        calc=_FakeCalc(),
        oracle=_FakeOracleD2(),
        speed_oracle=_FakeSpeed(),
        dex=_FakeDex(),
    )


def test_off_parity_search_depth_unset_matches_pre_wrap_baseline(monkeypatch):
    """With SHOWDOWN_SEARCH_DEPTH unset, _choose_best takes the verbatim 1-ply
    branch. These exact values were captured from the fixture BEFORE the
    depth-2 wrap was wired in (main/79cdc39), so any drift here means the OFF
    path is no longer byte-identical."""
    for var in ("SHOWDOWN_SEARCH_DEPTH", "SHOWDOWN_SEARCH_TOPN", "SHOWDOWN_SEARCH_TOPM",
                "SHOWDOWN_WORLD_SAMPLES"):
        monkeypatch.delenv(var, raising=False)
    from showdown_bot.battle.decision import heuristic_choose_for_request
    from showdown_bot.battle.decision_trace import DecisionTrace

    req = _d2_req()
    tr = DecisionTrace()
    choice = heuristic_choose_for_request(req, trace=tr, **_d2_kwargs())

    assert choice == "/choose move 3, move 3|2"
    assert tr.chosen_candidate_id == "(Protect, Protect)"
    assert tr.game_mode == "NEUTRAL"
    assert len(tr.candidates) == 6
    assert tr.candidates[0].score_vector == [5.4, 5.4, 3.6, 1.8, 3.6]
    assert tr.candidates[0].aggregate_score == 3.0528
    assert tr.opponent_response_weights == []


def test_applied_damage_from_outcome_bridge():
    from showdown_bot.battle.decision import _applied_damage_from_outcome
    from showdown_bot.battle.resolve import TurnOutcome

    st = BattleState()
    st.sides["p2"]["a"] = PokemonState(species="Flutter Mane", hp=75, max_hp=150)

    dmg_outcome = TurnOutcome(hp_delta={("p2", "a"): -0.5})
    assert _applied_damage_from_outcome(dmg_outcome, st) == {("p2", "a"): 75.0}

    heal_outcome = TurnOutcome(hp_delta={("p2", "a"): 0.1})
    assert _applied_damage_from_outcome(heal_outcome, st) == {}


def test_depth2_fires_frontier_bound_and_leaves_unselected_untouched(monkeypatch):
    """SHOWDOWN_SEARCH_DEPTH=2 (default N=2, M1=2): depth2_value is called
    exactly N*M1 times, the decision is legal, and a non-selected candidate's
    score vector is byte-unchanged from its 1-ply value."""
    from showdown_bot.battle import decision
    from showdown_bot.battle.actions import JointAction

    for var in ("SHOWDOWN_SEARCH_TOPN", "SHOWDOWN_SEARCH_TOPM", "SHOWDOWN_WORLD_SAMPLES"):
        monkeypatch.delenv(var, raising=False)

    req = _d2_req()

    # --- baseline: depth=1, capture every candidate's 1-ply score vector ---
    monkeypatch.delenv("SHOWDOWN_SEARCH_DEPTH", raising=False)
    baseline_items: dict[JointAction, list] = {}
    real_pick_best = decision.pick_best

    def _capture_baseline(items, *a, **k):
        baseline_items.update(dict(items))
        return real_pick_best(items, *a, **k)

    monkeypatch.setattr(decision, "pick_best", _capture_baseline)
    decision.heuristic_choose_for_request(req, **_d2_kwargs())
    monkeypatch.setattr(decision, "pick_best", real_pick_best)

    # --- depth=2 run: spy on depth2_value + capture the final items vectors ---
    monkeypatch.setenv("SHOWDOWN_SEARCH_DEPTH", "2")
    calls = []

    def _spy_depth2_value(*args, **kwargs):
        calls.append((args, kwargs))
        return -777.0

    monkeypatch.setattr(decision, "depth2_value", _spy_depth2_value)

    d2_items: dict[JointAction, list] = {}

    def _capture_d2(items, *a, **k):
        d2_items.update(dict(items))
        return real_pick_best(items, *a, **k)

    monkeypatch.setattr(decision, "pick_best", _capture_d2)

    choice_ja = decision._choose_best_ja(req, **_d2_kwargs())

    # Legal choice: matches one of the enumerated joint actions.
    from showdown_bot.battle.actions import enumerate_my_actions
    legal = enumerate_my_actions(req, moved_since_switch=[False, False])
    assert choice_ja in legal

    # Frontier bound: exactly N(=2) x M1(=2) depth2_value calls.
    assert len(calls) == 4

    # Exactly 2 candidates carry the -777.0 sentinel (the top-N selected ones),
    # each with exactly 2 sentinel slots.
    selected = {ja: vec for ja, vec in d2_items.items() if -777.0 in vec}
    assert len(selected) == 2
    for vec in selected.values():
        assert vec.count(-777.0) == 2

    # A non-selected candidate's vector is byte-unchanged from its 1-ply value.
    unselected_ja = next(ja for ja in d2_items if ja not in selected)
    assert d2_items[unselected_ja] == baseline_items[unselected_ja]
