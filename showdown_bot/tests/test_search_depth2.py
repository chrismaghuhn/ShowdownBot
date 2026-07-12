import copy
from showdown_bot.engine.state import BattleState, PokemonState
from showdown_bot.battle.search import approx_turn2_state


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
