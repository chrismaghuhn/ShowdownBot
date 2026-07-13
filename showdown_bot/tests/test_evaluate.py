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
from showdown_bot.engine.moves import MoveMeta, get_move_meta
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


def test_fast_board_protect_penalty_wasted_protect_scores_lower():
    """[2026-07-11] A wasted Protect (blocks nothing) on a fast board (both sides
    Tailwind) is scored strictly lower with fast_board_protect set than with the
    weight left at 0.0 -- additive to the existing protect_stall penalty."""
    out = TurnOutcome(flags={"protect:p1a"})
    w_off = EvalWeights()  # fast_board_protect defaults to 0.0
    w_on = EvalWeights(fast_board_protect=-2.0)
    s_off = score_outcome(out, "p1", w_off, fast_board=True)
    s_on = score_outcome(out, "p1", w_on, fast_board=True)
    assert s_on < s_off
    assert abs(s_on - (w_on.protect_stall + w_on.fast_board_protect)) < 1e-9


def test_fast_board_protect_penalty_recorded_in_breakdown():
    out = TurnOutcome(flags={"protect:p1a"})
    w = EvalWeights(fast_board_protect=-2.0)
    from showdown_bot.battle.evaluate import score_outcome_with_breakdown

    _, bd = score_outcome_with_breakdown(out, "p1", w, fast_board=True)
    assert bd.fast_board_protect_penalty == w.fast_board_protect


def test_fast_board_protect_not_applied_when_protect_blocks_a_hit():
    """A Protect that BLOCKS a hit on a fast board is NOT extra-penalized -- only
    wasted Protects (blocked nothing) take the fast_board_protect hit."""
    out = TurnOutcome(
        flags={"protect:p1a"},
        protected_hits=[ProtectedHit(("p2", "a"), ("p1", "a"), "flareblitz")],
    )
    w = EvalWeights(fast_board_protect=-2.0)
    s = score_outcome(out, "p1", w, fast_board=True)
    assert abs(s - w.protect_block) < 1e-9  # unchanged from the non-fast-board case
    from showdown_bot.battle.evaluate import score_outcome_with_breakdown

    _, bd = score_outcome_with_breakdown(out, "p1", w, fast_board=True)
    assert bd.fast_board_protect_penalty == 0.0


def test_fast_board_protect_unchanged_when_not_fast_board():
    """Single-Tailwind / no-Tailwind boards (fast_board=False) are unchanged
    regardless of the weight."""
    out = TurnOutcome(flags={"protect:p1a"})
    w = EvalWeights(fast_board_protect=-2.0)
    s_fast_off = score_outcome(out, "p1", w, fast_board=False)
    s_default = score_outcome(out, "p1", w)  # fast_board defaults False
    assert s_fast_off == s_default
    assert abs(s_fast_off - w.protect_stall) < 1e-9  # no fast_board_protect applied


def test_fast_board_protect_byte_identical_when_weight_zero():
    """Env-unset default: fast_board_protect == 0.0 -> adding it changes nothing,
    so fast_board=True and fast_board=False score identically."""
    out = TurnOutcome(flags={"protect:p1a"})
    w = EvalWeights()  # fast_board_protect default 0.0
    s_true = score_outcome(out, "p1", w, fast_board=True)
    s_false = score_outcome(out, "p1", w, fast_board=False)
    assert s_true == s_false


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
    cfg = load_format_config("gen9vgc2025regi")
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
    cfg = load_format_config("gen9vgc2025regi")
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


def test_evaluate_line_threads_fast_board_to_score():
    """evaluate_line threads fast_board through to score_outcome, like endgame."""
    st = _model_state()
    protect = PlannedAction("p1", "a", "protect", speed=100, is_ours=True)
    w = EvalWeights(fast_board_protect=-2.0)

    def dmg(action, target):
        return 0.0

    score_fast, out = evaluate_line(st, [protect], [], dmg, our_side="p1", weights=w, fast_board=True)
    score_slow, _ = evaluate_line(st, [protect], [], dmg, our_side="p1", weights=w, fast_board=False)
    assert "protect:p1a" in out.flags
    assert score_fast < score_slow  # extra penalty only when fast_board=True


def test_evaluate_line_fast_board_default_false_byte_identical():
    """fast_board defaults False everywhere -> omitting it is identical to False."""
    st = _model_state()
    protect = PlannedAction("p1", "a", "protect", speed=100, is_ours=True)
    w = EvalWeights(fast_board_protect=-2.0)

    def dmg(action, target):
        return 0.0

    score_default, _ = evaluate_line(st, [protect], [], dmg, our_side="p1", weights=w)
    score_explicit_false, _ = evaluate_line(
        st, [protect], [], dmg, our_side="p1", weights=w, fast_board=False
    )
    assert score_default == score_explicit_false


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


from showdown_bot.engine.belief.hypotheses import SpeciesSpreads, SpreadPreset


def _opp_state():
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Incineroar", hp=100, max_hp=100)
    st.sides["p2"]["a"] = PokemonState(species="Incineroar", hp=100, max_hp=100)
    return st


def _likely_incin():
    p = SpreadPreset(nature="Careful", evs={"hp": 252, "atk": 4, "spd": 252}, items=["Sitrus Berry"])
    return {"incineroar": SpeciesSpreads(offense=p, defense=p)}


def test_opp_sets_overrides_opponent_hypothesis():
    st = _opp_state()
    cfg = load_format_config("gen9vgc2025regi")
    book = load_spread_book(cfg.meta_path("default_spreads"))
    real = DamageModel(st, "p1", "p2", book=book, opp_sets=_likely_incin())
    d = real.hyps[("p2", "a")].as_defender()
    assert d.nature == "Careful"
    assert d.evs == {"hp": 252, "atk": 4, "spd": 252}   # the likely set, not the book preset


def test_opp_sets_none_is_unchanged():
    st = _opp_state()
    cfg = load_format_config("gen9vgc2025regi")
    book = load_spread_book(cfg.meta_path("default_spreads"))
    a = DamageModel(st, "p1", "p2", book=book)
    b = DamageModel(st, "p1", "p2", book=book, opp_sets=None)
    assert a.hyps[("p2", "a")].as_defender().nature == b.hyps[("p2", "a")].as_defender().nature


def test_revealed_item_beats_likely_item():
    st = _opp_state()
    st.sides["p2"]["a"].item = "Assault Vest"
    st.sides["p2"]["a"].item_known = True
    cfg = load_format_config("gen9vgc2025regi")
    book = load_spread_book(cfg.meta_path("default_spreads"))
    model = DamageModel(st, "p1", "p2", book=book, opp_sets=_likely_incin())
    assert model.hyps[("p2", "a")].as_defender().item == "Assault Vest"


def test_uncurated_opponent_stays_worstcase():
    st = _opp_state()
    st.sides["p2"]["a"] = PokemonState(species="Rillaboom", hp=100, max_hp=100)
    cfg = load_format_config("gen9vgc2025regi")
    book = load_spread_book(cfg.meta_path("default_spreads"))
    base = DamageModel(st, "p1", "p2", book=book)
    real = DamageModel(st, "p1", "p2", book=book, opp_sets=_likely_incin())
    assert real.hyps[("p2", "a")].as_defender().nature == base.hyps[("p2", "a")].as_defender().nature


# --- accuracy_mode / accuracy_branch_cap (accuracy-slice Task 5) -----------------------

def _doubles_state_for_eval():
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Incineroar", hp=100, max_hp=100)
    st.sides["p2"]["a"] = PokemonState(species="Flutter Mane", hp=100, max_hp=100)
    return st


def test_evaluate_line_accuracy_mode_off_is_byte_identical_to_default():
    st = _doubles_state_for_eval()
    moon = get_move_meta("Moonblast")  # accuracy 100, still deterministic here
    mine = PlannedAction("p1", "a", "move", speed=100, move=moon, target=("p2", "a"), is_ours=True)

    def dmg(action, target):
        return 0.4

    s_default, out_default = evaluate_line(st, [mine], [], dmg, our_side="p1")
    s_explicit_off, out_explicit_off = evaluate_line(
        st, [mine], [], dmg, our_side="p1", accuracy_mode=False,
    )
    assert s_default == s_explicit_off
    assert out_default.hp_delta == out_explicit_off.hp_delta


def test_evaluate_line_accuracy_mode_on_weights_hit_and_miss():
    st = _doubles_state_for_eval()
    risky = MoveMeta(id="risky", name="Risky", accuracy=70, base_power=100,
                      category="physical", target="normal")
    mine = PlannedAction("p1", "a", "move", speed=100, move=risky, target=("p2", "a"), is_ours=True)

    def dmg(action, target):
        return 0.5

    w = EvalWeights()
    s_on, _out_on = evaluate_line(st, [mine], [], dmg, our_side="p1", accuracy_mode=True, weights=w)

    # hand-computed: hit branch (p=0.7) deals 0.5 dmg dealt; miss branch (p=0.3) deals 0 dmg.
    hit_score = w.dmg_dealt * 0.5
    miss_score = 0.0
    expected = 0.7 * hit_score + 0.3 * miss_score
    assert abs(s_on - expected) < 1e-9


def test_evaluate_line_tight_accuracy_branch_cap_increments_telemetry():
    st = _doubles_state_for_eval()
    st.sides["p1"]["b"] = PokemonState(species="Rillaboom", hp=100, max_hp=100)
    st.sides["p2"]["b"] = PokemonState(species="Amoonguss", hp=100, max_hp=100)
    u1 = MoveMeta(id="u1", name="U1", accuracy=50, base_power=100, category="physical", target="normal")
    u2 = MoveMeta(id="u2", name="U2", accuracy=50, base_power=100, category="physical", target="normal")
    a1 = PlannedAction("p1", "a", "move", speed=150, move=u1, target=("p2", "a"), is_ours=True)
    a2 = PlannedAction("p1", "b", "move", speed=140, move=u2, target=("p2", "b"), is_ours=True)

    def dmg(action, target):
        return 0.1

    _s, out_capped = evaluate_line(
        st, [a1, a2], [], dmg, our_side="p1", accuracy_mode=True, accuracy_branch_cap=1,
    )
    assert out_capped.accuracy_branch_cap_hits >= 1


# --- AccuracyDiagnostics / accuracy_diagnostics (accuracy-slice Task 6) ----------------

from showdown_bot.battle.evaluate import AccuracyDiagnostics, accuracy_diagnostics
from showdown_bot.battle.resolve import ForkRecord, TurnOutcome


def _diag_state_full_hp():
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Attacker", hp=100, max_hp=100)
    st.sides["p2"]["a"] = PokemonState(species="Target", hp=100, max_hp=100)
    return st


def test_accuracy_diagnostics_ko_and_survival_probability():
    target = ("p2", "a")
    st = _diag_state_full_hp()
    leaves = [
        (0.7, TurnOutcome(opp_kos=1, hp_delta={target: -1.0})),
        (0.3, TurnOutcome(opp_kos=0, hp_delta={target: 0.0})),
    ]
    diag = accuracy_diagnostics(leaves, targets=[target], state=st, actions=[], field=None)
    assert isinstance(diag, AccuracyDiagnostics)
    assert abs(diag.ko_probability[target] - 0.7) < 1e-9
    assert abs(diag.survival_probability[target] - 0.3) < 1e-9


def test_accuracy_diagnostics_single_leaf_is_certain():
    target = ("p2", "a")
    st = _diag_state_full_hp()
    leaves = [(1.0, TurnOutcome(opp_kos=1, hp_delta={target: -1.0}))]
    diag = accuracy_diagnostics(leaves, targets=[target], state=st, actions=[], field=None)
    assert diag.ko_probability[target] == 1.0
    assert diag.survival_probability[target] == 0.0


def test_accuracy_diagnostics_ko_probability_uses_starting_hp_not_flat_minus_one():
    """Regression test: a target at 30% starting HP is KO'd by hp_delta=-0.3, not -1.0. A
    naive `hp_delta <= -1.0` check silently reports 0% KO probability for this real, already-
    happened KO -- this is the exact bug an earlier draft had."""
    target = ("p2", "a")
    st = BattleState()
    st.sides["p2"]["a"] = PokemonState(species="Weak", hp=30, max_hp=100)  # 30% HP
    leaves = [(1.0, TurnOutcome(opp_kos=1, hp_delta={target: -0.3}))]
    diag = accuracy_diagnostics(leaves, targets=[target], state=st, actions=[], field=None)
    assert diag.ko_probability[target] == 1.0
    assert diag.survival_probability[target] == 0.0


def test_accuracy_diagnostics_ko_probability_not_triggered_by_partial_damage():
    # Same starting HP as above, but damage this time leaves the target alive (10% HP left).
    target = ("p2", "a")
    st = BattleState()
    st.sides["p2"]["a"] = PokemonState(species="Weak", hp=30, max_hp=100)  # 30% HP
    leaves = [(1.0, TurnOutcome(hp_delta={target: -0.2}))]  # 30% -> 10%, survives
    diag = accuracy_diagnostics(leaves, targets=[target], state=st, actions=[], field=None)
    assert diag.ko_probability[target] == 0.0
    assert diag.survival_probability[target] == 1.0


def test_accuracy_diagnostics_accuracy_required_and_miss_punish_value():
    from showdown_bot.battle.evaluate import EvalWeights
    from showdown_bot.battle.resolve import AttemptedHit, PlannedAction
    from showdown_bot.engine.moves import MoveMeta

    st = _diag_state_full_hp()
    risky = MoveMeta(id="risky", name="Risky", accuracy=70, base_power=100,
                      category="physical", target="normal")
    action = PlannedAction("p1", "a", "move", speed=100, move=risky, target=("p2", "a"), is_ours=True)
    pair = (("p1", "a"), ("p2", "a"))
    w = EvalWeights()

    hit_out = TurnOutcome(hp_delta={("p2", "a"): -0.5}, attempted_hits=[AttemptedHit(*pair, "risky")])
    miss_out = TurnOutcome(hp_delta={("p2", "a"): 0.0}, attempted_hits=[AttemptedHit(*pair, "risky")])
    leaves = [(0.7, hit_out), (0.3, miss_out)]
    fork_records: list[ForkRecord] = [(pair, [(0.3, miss_out)])]

    diag = accuracy_diagnostics(
        leaves, targets=[("p2", "a")], state=st, actions=[action], field=FieldState(),
        fork_records=fork_records, weights=w, our_side="p1",
    )
    assert abs(diag.accuracy_required[pair] - 0.70) < 1e-9
    # miss_punish_value = score(miss subtree) - score(leaves[0]) = (0 - w.dmg_dealt*0.5) < 0
    expected = 0.0 - (w.dmg_dealt * 0.5)
    assert abs(diag.miss_punish_value[pair] - expected) < 1e-9


def test_accuracy_diagnostics_duplicate_targets_do_not_double_count():
    """Regression test: a duplicate slot in `targets` (e.g. two of our attackers targeting the
    same weakened opposing slot -- an ordinary Doubles pattern) must not double-count that
    leaf's weight into ko_probability."""
    target = ("p2", "a")
    st = _diag_state_full_hp()
    leaves = [
        (0.7, TurnOutcome(hp_delta={target: -1.0})),
        (0.3, TurnOutcome(hp_delta={target: 0.0})),
    ]
    diag = accuracy_diagnostics(leaves, targets=[target, target], state=st, actions=[], field=None)
    assert abs(diag.ko_probability[target] - 0.7) < 1e-9
    assert abs(diag.survival_probability[target] - 0.3) < 1e-9


def test_accuracy_diagnostics_empty_leaves_raises_value_error():
    import pytest

    with pytest.raises(ValueError):
        accuracy_diagnostics([], targets=[("p2", "a")], state=_diag_state_full_hp(), actions=[], field=None)


# --- LineEvaluation / _evaluate_line_details refactor (accuracy-slice Task 5) ----------

import dataclasses

from showdown_bot.battle.evaluate import (
    AccuracyEventDetail,
    LineEvaluation,
    TieOrderEvaluation,
    _accuracy_events_from_leaves,
    _evaluate_line_details,
)
from showdown_bot.battle.resolve import resolve_turn_branches


def test_evaluate_line_wraps_evaluate_line_details_off_path():
    """off-path: byte-identical to today's evaluate_line -- construct with accuracy_mode=False
    and assert the wrapper's (score, outcome) equals _evaluate_line_details'."""
    st = _model_state()

    def dmg(action, target):
        return 0.0  # never invoked -- there are no actions on this line

    score, outcome = evaluate_line(st, [], [], dmg, our_side="p1", accuracy_mode=False)
    detail = _evaluate_line_details(st, [], [], dmg, our_side="p1", accuracy_mode=False)
    assert (score, outcome) == (detail.score, detail.representative_outcome)
    assert detail.leaves is None
    assert detail.fork_records is None
    assert detail.fallback_leaves == 0
    assert detail.accuracy_events == []


def _scripted_accuracy_state():
    """A single uncertain-accuracy move -- enough to exercise accuracy_mode branching without
    any KO/tie interaction, for a pure determinism check."""
    st = _doubles_state_for_eval()
    risky = MoveMeta(id="risky2", name="Risky2", accuracy=70, base_power=100,
                      category="physical", target="normal")
    mine = PlannedAction("p1", "a", "move", speed=100, move=risky, target=("p2", "a"), is_ours=True)

    def dmg(action, target):
        return 0.5

    return st, [mine], [], dmg


def test_evaluate_line_details_repeat_call_identical():
    state, my_actions, opp_actions, damage_fn = _scripted_accuracy_state()
    kwargs = dict(
        state=state, my_actions=my_actions, opp_actions=opp_actions, damage_fn=damage_fn,
        our_side="p1", accuracy_mode=True, accuracy_branch_cap=8,
    )
    d1 = _evaluate_line_details(**kwargs)
    d2 = _evaluate_line_details(**kwargs)
    assert d1.score == d2.score
    assert d1.fallback_leaves == d2.fallback_leaves
    assert [dataclasses.astuple(e) for e in d1.accuracy_events] == \
           [dataclasses.astuple(e) for e in d2.accuracy_events]
    assert [dataclasses.astuple(t) for t in d1.tie_order_details] == \
           [dataclasses.astuple(t) for t in d2.tie_order_details]


def _ko_dependent_accuracy_state():
    """A miss-branch-only accuracy event: p1a's hit on p2a resolves as a hit by default in
    leaves[0], KO-ing p2a before p2a's own uncertain move ever fires. Only in the sibling
    miss-branch (p1a's hit forced to miss) does p2a survive to attempt its own move -- an event
    absent from leaves[0].attempted_hits but present elsewhere in the full leaf union."""
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Incineroar", hp=100, max_hp=100)
    st.sides["p1"]["b"] = PokemonState(species="Rillaboom", hp=100, max_hp=100)
    st.sides["p2"]["a"] = PokemonState(species="Flutter Mane", hp=100, max_hp=100)
    strike1 = MoveMeta(id="strike1", name="Strike1", accuracy=70, base_power=100,
                        category="physical", target="normal")
    strike2 = MoveMeta(id="strike2", name="Strike2", accuracy=70, base_power=100,
                        category="physical", target="normal")
    p1a = PlannedAction("p1", "a", "move", speed=150, move=strike1, target=("p2", "a"), is_ours=True)
    p2a = PlannedAction("p2", "a", "move", speed=100, move=strike2, target=("p1", "b"), is_ours=False)

    def dmg(action, target):
        return 1.0 if action.move.id == "strike1" else 0.3

    return st, [p1a, p2a], dmg


def test_accuracy_events_use_full_leaf_union_not_leaves_zero_only():
    """Regression test for the round-3 discovery bug: an event only attempted in a miss-branch
    must still appear in accuracy_events, even though it's absent from leaves[0]'s attempted_hits.
    Mirrors the merged slice's Task 4 KO-dependent regression test shape."""
    state, actions, damage_fn = _ko_dependent_accuracy_state()
    leaves, fallback_leaves, fork_records = resolve_turn_branches(
        state, actions, damage_fn, our_side="p1", branch_cap=8,
    )
    # Sanity: the scripted fixture must actually exercise the bug shape (an attempted_hit
    # absent from leaves[0] but present in some other leaf).
    leaves0_pairs = {(ah.attacker, ah.target, ah.move_id) for ah in leaves[0][1].attempted_hits}
    all_pairs = {
        (ah.attacker, ah.target, ah.move_id)
        for _w, out in leaves for ah in out.attempted_hits
    }
    assert all_pairs - leaves0_pairs, "fixture doesn't exercise a miss-branch-only event"

    events = _accuracy_events_from_leaves(actions, state, leaves, state.field, tie_order="ours_last")
    found_pairs = {(e.attacker, e.target, e.move_id) for e in events}
    missing_from_leaves0 = all_pairs - leaves0_pairs
    assert missing_from_leaves0 <= found_pairs, (
        "an event only reachable via a miss-branch was dropped -- leaves[0]-only bug reintroduced"
    )


def _tie_scripted_state():
    """A genuine speed tie between p1a (an uncertain-accuracy move at an unrelated target) and
    p2a (a guaranteed-hit KO move aimed straight at p1a). Under ours_first, p1a acts before p2a
    can KO it, so p1a's own uncertain-accuracy event fires; under ours_last, p2a acts first and
    KOs p1a before it ever gets a turn, so that event never appears at all.

    p1b/move_y is a THIRD action, outside the tied pair (distinct speed, unaffected by which of
    p1a/p2a goes first), whose own uncertain-accuracy move fires identically under both
    orderings -- this is the shared event the dedup fix needs: it must appear exactly ONCE in
    the tie-merged accuracy_events, not once per evaluated ordering."""
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Incineroar", hp=100, max_hp=100)
    st.sides["p1"]["b"] = PokemonState(species="Grimmsnarl", hp=100, max_hp=100)
    st.sides["p2"]["a"] = PokemonState(species="Flutter Mane", hp=100, max_hp=100)
    st.sides["p2"]["b"] = PokemonState(species="Amoonguss", hp=100, max_hp=100)
    move_x = MoveMeta(id="movex", name="MoveX", accuracy=70, base_power=80,
                       category="physical", target="normal")
    ko_strike = MoveMeta(id="ko_strike", name="KOStrike", base_power=120,
                          category="physical", target="normal")
    move_y = MoveMeta(id="movey", name="MoveY", accuracy=60, base_power=90,
                       category="physical", target="normal")
    p1a = PlannedAction("p1", "a", "move", speed=100, move=move_x, target=("p2", "b"), is_ours=True)
    p1b = PlannedAction("p1", "b", "move", speed=200, move=move_y, target=("p2", "a"), is_ours=True)
    p2a = PlannedAction("p2", "a", "move", speed=100, move=ko_strike, target=("p1", "a"), is_ours=False)

    def dmg(action, target):
        return 1.0 if action.move.id == "ko_strike" else 0.5

    return st, [p1a, p1b], [p2a], dmg


def test_tie_averaging_preserves_asymmetric_cap_hit_and_event():
    """Round-4 fix regression: a genuine tie where ours_first's KO-before-act ordering makes an
    attacker act (attempting an accuracy event) before ours_last's ordering removes that same
    action via an earlier KO. The merged result must retain it even though ours_last alone
    wouldn't have it -- checked as real set containment, not just a cardinality count."""
    state, my_actions, opp_actions, damage_fn = _tie_scripted_state()
    detail = _evaluate_line_details(
        state, my_actions, opp_actions, damage_fn,
        our_side="p1", accuracy_mode=True, accuracy_branch_cap=8,
    )
    ours_last_only = _evaluate_line_details(
        state, my_actions, opp_actions, damage_fn,
        our_side="p1", accuracy_mode=True, accuracy_branch_cap=8,
        _force_tie_break="ours_last",
    )
    ours_first_only = _evaluate_line_details(
        state, my_actions, opp_actions, damage_fn,
        our_side="p1", accuracy_mode=True, accuracy_branch_cap=8,
        _force_tie_break="ours_first",
    )

    def keys(events):
        return {(e.attacker, e.target, e.move_id) for e in events}

    merged_keys = keys(detail.accuracy_events)
    ours_last_keys = keys(ours_last_only.accuracy_events)
    ours_first_keys = keys(ours_first_only.accuracy_events)

    assert ours_last_keys <= merged_keys, (
        "every event ours_last alone discovers must survive the merge"
    )
    assert (("p1", "a"), ("p2", "b"), "movex") in merged_keys, (
        "the ours_first-only event (p1a's move, never attempted under ours_last) must survive the merge"
    )
    assert (("p1", "a"), ("p2", "b"), "movex") not in ours_last_keys, (
        "fixture sanity: this event must genuinely be absent from ours_last alone"
    )
    # ours_first alone already discovers everything ours_last does for this fixture (p1b's
    # move_y fires under both orderings, p1a's move_x only under ours_first) -- so the merge
    # should add nothing beyond ours_first_keys here; this is what makes the dedup assertion
    # below meaningful rather than vacuous.
    assert merged_keys == ours_first_keys

    assert detail.representative_outcome == ours_last_only.representative_outcome, (
        "representative_outcome must stay on the unchanged ours_last-only convention"
    )
    tie_orders = {t.tie_order for t in detail.tie_order_details}
    assert tie_orders == {"ours_first", "ours_last"}


def test_tie_averaging_dedups_shared_event_across_orderings():
    """Round-5 fix regression: p1b's move_y is uncertain and fires identically under BOTH
    ours_first and ours_last (it's outside the tied pair, so tie-break doesn't affect whether it
    executes). A naive concatenation of d_first.accuracy_events + d_last.accuracy_events would
    list it twice -- once per evaluated ordering -- silently breaking the
    len(accuracy_events) == distinct-event-count contract downstream callers (Task 6's
    AccuracyResponseDetail.accuracy_event_count) rely on."""
    state, my_actions, opp_actions, damage_fn = _tie_scripted_state()
    detail = _evaluate_line_details(
        state, my_actions, opp_actions, damage_fn,
        our_side="p1", accuracy_mode=True, accuracy_branch_cap=8,
    )
    ours_first_only = _evaluate_line_details(
        state, my_actions, opp_actions, damage_fn,
        our_side="p1", accuracy_mode=True, accuracy_branch_cap=8,
        _force_tie_break="ours_first",
    )
    ours_last_only = _evaluate_line_details(
        state, my_actions, opp_actions, damage_fn,
        our_side="p1", accuracy_mode=True, accuracy_branch_cap=8,
        _force_tie_break="ours_last",
    )
    shared_key = (("p1", "b"), ("p2", "a"), "movey")
    # Sanity: the fixture must actually exercise a genuinely shared event under both orderings,
    # otherwise this test would pass vacuously.
    assert shared_key in {(e.attacker, e.target, e.move_id) for e in ours_first_only.accuracy_events}
    assert shared_key in {(e.attacker, e.target, e.move_id) for e in ours_last_only.accuracy_events}

    keys_list = [(e.attacker, e.target, e.move_id) for e in detail.accuracy_events]
    assert keys_list.count(shared_key) == 1, (
        "a genuinely tie-order-independent uncertain event must appear exactly once in the "
        "merged accuracy_events, not once per evaluated tie ordering"
    )
    assert len(keys_list) == len(set(keys_list)), (
        "no duplicate (attacker, target, move_id) keys anywhere in the merged accuracy_events"
    )
    # len(accuracy_events) must equal the distinct-event count exactly -- this is the contract
    # Task 6's AccuracyResponseDetail.accuracy_event_count relies on.
    assert len(detail.accuracy_events) == len(set(keys_list))


def _capped_accuracy_state():
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Incineroar", hp=100, max_hp=100)
    st.sides["p1"]["b"] = PokemonState(species="Rillaboom", hp=100, max_hp=100)
    st.sides["p2"]["a"] = PokemonState(species="Flutter Mane", hp=100, max_hp=100)
    st.sides["p2"]["b"] = PokemonState(species="Amoonguss", hp=100, max_hp=100)
    u1 = MoveMeta(id="u1", name="U1", accuracy=50, base_power=100, category="physical", target="normal")
    u2 = MoveMeta(id="u2", name="U2", accuracy=50, base_power=100, category="physical", target="normal")
    a1 = PlannedAction("p1", "a", "move", speed=150, move=u1, target=("p2", "a"), is_ours=True)
    a2 = PlannedAction("p1", "b", "move", speed=140, move=u2, target=("p2", "b"), is_ours=True)

    def dmg(action, target):
        return 0.1

    return st, [a1, a2], [], dmg


def test_events_complete_reflects_branch_cap():
    state, my_actions, opp_actions, damage_fn = _capped_accuracy_state()
    detail_capped = _evaluate_line_details(
        state, my_actions, opp_actions, damage_fn,
        our_side="p1", accuracy_mode=True, accuracy_branch_cap=1,  # force an early cap
    )
    assert detail_capped.fallback_leaves >= 1
    assert any(t.events_complete is False for t in detail_capped.tie_order_details)

    detail_uncapped = _evaluate_line_details(
        state, my_actions, opp_actions, damage_fn,
        our_side="p1", accuracy_mode=True, accuracy_branch_cap=64,
    )
    assert detail_uncapped.fallback_leaves == 0
    assert all(t.events_complete for t in detail_uncapped.tie_order_details)
