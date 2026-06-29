from __future__ import annotations

from showdown_bot.battle.evaluate import (
    DamageModel,
    EvalWeights,
    build_field_payload,
    evaluate_line,
    score_outcome,
)
from showdown_bot.battle.resolve import (
    PlannedAction,
    PreventedAction,
    ProtectedHit,
    TurnOutcome,
)
from showdown_bot.engine.belief.hypotheses import load_spread_book
from showdown_bot.engine.calc.models import DamageResult
from showdown_bot.engine.format_config import load_format_config
from showdown_bot.engine.moves import get_move_meta
from showdown_bot.engine.state import BattleState, FieldState, PokemonState


def test_score_rewards_my_ko_penalizes_my_faint():
    w = EvalWeights()
    ko = TurnOutcome(my_kos=1)
    faint = TurnOutcome(my_faints=1)
    assert score_outcome(ko, "p1", w) == w.ko
    assert score_outcome(faint, "p1", w) == w.faint


def test_score_damage_signs():
    w = EvalWeights()
    out = TurnOutcome(hp_delta={("p2", "a"): -0.5, ("p1", "a"): -0.25})
    s = score_outcome(out, "p1", w)
    expected = w.dmg_dealt * 0.5 - w.dmg_taken * 0.25
    assert abs(s - expected) < 1e-9


def test_score_tempo_and_protect():
    w = EvalWeights()
    out = TurnOutcome(
        prevented_actions=[PreventedAction("p2", "a", "fainted_before_acting")],
        protected_hits=[ProtectedHit(("p2", "a"), ("p1", "a"), "moonblast")],
    )
    s = score_outcome(out, "p1", w)
    assert abs(s - (w.tempo_prevent + w.protect_block)) < 1e-9


def test_score_speed_control_only_for_us():
    w = EvalWeights()
    ours = TurnOutcome(flags={"status:tailwind:p1a"})
    theirs = TurnOutcome(flags={"status:tailwind:p2a"})
    assert score_outcome(ours, "p1", w) == w.speed_control
    assert score_outcome(theirs, "p1", w) == 0.0


def test_protect_stall_penalty_no_block_and_endgame():
    """Protecting with our last mon that blocks nothing is pure wasted tempo +
    just defers the loss (the observed 1v1 protect-spam failure mode)."""
    w = EvalWeights()
    out = TurnOutcome(flags={"protect:p1a"})
    s = score_outcome(out, "p1", w, endgame=True)
    assert abs(s - (w.protect_stall + w.endgame_protect)) < 1e-9


def test_protect_blocking_a_hit_midgame_not_penalized():
    """Protect with a concrete purpose (it actually blocked an incoming hit),
    mid-game, keeps its block reward and is NOT stalled."""
    w = EvalWeights()
    out = TurnOutcome(
        flags={"protect:p1a"},
        protected_hits=[ProtectedHit(("p2", "a"), ("p1", "a"), "flareblitz")],
    )
    s = score_outcome(out, "p1", w, endgame=False)
    assert abs(s - w.protect_block) < 1e-9


def test_partner_abandon_penalty():
    """Protecting our own mon while a teammate faints the same turn is bad action
    economy (Turn 8: Incineroar protects, Flutter Mane dies)."""
    w = EvalWeights()
    out = TurnOutcome(my_faints=1, flags={"protect:p1a"})
    s = score_outcome(out, "p1", w, endgame=False)
    assert abs(s - (w.faint + w.protect_stall + w.partner_abandon)) < 1e-9


def test_build_field_payload():
    fp = build_field_payload(FieldState(weather="SunnyDay", terrain="Grassy Terrain"))
    assert fp["gameType"] == "Doubles"
    assert fp["weather"] == "Sun"
    assert fp["terrain"] == "Grassy"


class FakeOracle:
    """Returns scripted damage by move name; counts batches."""

    def __init__(self, by_move):
        self.by_move = by_move
        self._pending = {}
        self.batch_calls = 0

    def request(self, req):
        return req.move

    def get(self, key):
        self.batch_calls += 1
        return self.by_move[key]

    def damage(self, req):
        return self.by_move[req.move]

    def flush(self):
        pass


def _model_state():
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Incineroar", hp=100, max_hp=100)
    st.sides["p2"]["a"] = PokemonState(species="Flutter Mane", hp=100, max_hp=100)
    return st


def test_damage_model_damage_fn_uses_min_for_us_max_vs_us():
    st = _model_state()
    cfg = load_format_config("gen9vgc2026regi")
    book = load_spread_book(cfg.meta_path("default_spreads"))
    fake = FakeOracle(
        {
            "Moonblast": DamageResult(min_damage=40, max_damage=60, max_hp=100),
        }
    )
    model = DamageModel(st, "p1", "p2", book=book, oracle=fake)
    moon = get_move_meta("Moonblast")
    ours = PlannedAction("p1", "a", "move", move=moon, target=("p2", "a"), is_ours=True)
    theirs = PlannedAction("p2", "a", "move", move=moon, target=("p1", "a"), is_ours=False)
    assert abs(model.damage_fn(ours, None) - 0.40) < 1e-9  # min roll for our attack
    assert abs(model.damage_fn(theirs, None) - 0.60) < 1e-9  # max roll incoming


def test_damage_model_helpers():
    st = _model_state()
    cfg = load_format_config("gen9vgc2026regi")
    book = load_spread_book(cfg.meta_path("default_spreads"))
    fake = FakeOracle({"Moonblast": DamageResult(min_damage=120, max_damage=140, max_hp=100)})
    model = DamageModel(st, "p1", "p2", book=book, oracle=fake)
    assert model.secures_ko(("p1", "a"), ("p2", "a"), "Moonblast") is True
    assert model.has_ko_chance(("p1", "a"), ("p2", "a"), "Moonblast") is True
    assert model.survives_for_sure(("p1", "a"), ("p2", "a"), "Moonblast") is False


def test_evaluate_line_integration_with_fake_dmg():
    st = _model_state()
    moon = get_move_meta("Moonblast")
    mine = PlannedAction("p1", "a", "move", speed=100, move=moon, target=("p2", "a"), is_ours=True)
    theirs = PlannedAction("p2", "a", "move", speed=120, move=moon, target=("p1", "a"), is_ours=False)

    def dmg(action, target):
        return 1.0 if action.is_ours else 0.2

    score, out = evaluate_line(st, [mine], [theirs], dmg, our_side="p1")
    assert out.my_kos == 1
    assert score > 0


def test_evaluate_line_rollout_additive_at_horizon_zero():
    """Invariant I-7: Rollout(H=0) == no rollout."""
    st = _model_state()
    moon = get_move_meta("Moonblast")
    mine = PlannedAction("p1", "a", "move", speed=100, move=moon, target=("p2", "a"), is_ours=True)

    def dmg(action, target):
        return 0.3 if action.is_ours else 0.0

    base = evaluate_line(st, [mine], [], dmg, our_side="p1")[0]
    h0 = evaluate_line(st, [mine], [], dmg, our_side="p1", rollout_horizon=0)[0]
    assert h0 == base


def test_evaluate_line_rollout_values_status_chip():
    st = _model_state()
    st.sides["p2"]["a"].status = "brn"  # burned opponent chips over the horizon
    moon = get_move_meta("Moonblast")
    mine = PlannedAction("p1", "a", "move", speed=100, move=moon, target=("p2", "a"), is_ours=True)

    def dmg(action, target):
        return 0.1 if action.is_ours else 0.0  # opp survives turn 0, then chips

    h0 = evaluate_line(st, [mine], [], dmg, our_side="p1", rollout_horizon=0)[0]
    h2 = evaluate_line(st, [mine], [], dmg, our_side="p1", rollout_horizon=2)[0]
    assert h2 > h0


def _mirror_state():
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Incineroar", hp=100, max_hp=100)
    st.sides["p2"]["a"] = PokemonState(species="Incineroar", hp=100, max_hp=100)
    return st


def _move(side, ours):
    return PlannedAction(side, "a", "move", speed=100, move=get_move_meta("Flare Blitz"),
                         target=("p2" if ours else "p1", "a"), is_ours=ours)


def test_tie_ev_averages_two_orderings():
    st = _mirror_state()

    def damage_fn(action, target_mon):
        return 0.5

    ours = [_move("p1", True)]
    opp = [_move("p2", False)]
    score, _ = evaluate_line(st, ours, opp, damage_fn, our_side="p1")
    score_last, _ = evaluate_line(st, ours, opp, damage_fn, our_side="p1", _force_tie_break="ours_last")
    score_first, _ = evaluate_line(st, ours, opp, damage_fn, our_side="p1", _force_tie_break="ours_first")
    assert abs(score - 0.5 * (score_first + score_last)) < 1e-9


def test_no_tie_is_bit_identical():
    st = _mirror_state()

    def damage_fn(action, target_mon):
        return 0.4

    ours = [PlannedAction("p1", "a", "move", speed=130, move=get_move_meta("Flare Blitz"),
                          target=("p2", "a"), is_ours=True)]   # faster -> no tie
    opp = [PlannedAction("p2", "a", "move", speed=80, move=get_move_meta("Flare Blitz"),
                         target=("p1", "a"), is_ours=False)]
    score_ev, _ = evaluate_line(st, ours, opp, damage_fn, our_side="p1")
    score_plain, _ = evaluate_line(st, ours, opp, damage_fn, our_side="p1", _force_tie_break="ours_last")
    assert score_ev == score_plain  # no tie -> single pass, unchanged


def test_tie_ev_makes_no_new_oracle_calls():
    st = _mirror_state()
    calls = {"n": 0}

    def damage_fn(action, target_mon):
        calls["n"] += 1
        return 0.5  # 50% per hit -> no KO -> no action cancellation, so calls are stable

    ours = [_move("p1", True)]
    opp = [_move("p2", False)]
    evaluate_line(st, ours, opp, damage_fn, our_side="p1")            # tie-EV: two passes
    two_pass = calls["n"]
    calls["n"] = 0
    evaluate_line(st, ours, opp, damage_fn, our_side="p1", _force_tie_break="ours_last")  # one pass
    one_pass = calls["n"]
    assert two_pass == 2 * one_pass  # second pass adds exactly one pass of (cacheable) lookups, nothing extra
