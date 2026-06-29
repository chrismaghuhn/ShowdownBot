from showdown_bot.battle.diagnostics import format_outcome, format_rollout_trace
from showdown_bot.battle.resolve import PreventedAction, TurnOutcome
from showdown_bot.battle.rollout import RolloutResult, TurnTrace


def test_format_rollout_trace_is_readable():
    res = RolloutResult(
        value=0.31,
        final_hp={("p1", "a"): 0.94, ("p2", "a"): 0.0},
        trace=[
            TurnTrace(turn=1, order=[("p2", "a"), ("p1", "a")], kos=[("p2", "a")],
                      hp={"p1a": 1.0, "p2a": 0.0}, score=1.2),
            TurnTrace(turn=2, order=[("p1", "a")], kos=[],
                      hp={"p1a": 0.94, "p2a": 0.0}, score=0.3),
        ],
    )
    text = format_rollout_trace(res)
    assert "+0.31" in text          # horizon value
    assert "T+1" in text and "T+2" in text
    assert "p2a" in text            # the KO appears
    assert "score" in text.lower()


def test_format_rollout_trace_empty_horizon():
    text = format_rollout_trace(RolloutResult(value=0.0, final_hp={}, trace=[]))
    assert "0 turns" in text or "no rollout" in text.lower()


def test_format_outcome_summarizes_kos_damage_tempo():
    out = TurnOutcome(
        my_kos=1,
        my_faints=0,
        hp_delta={("p2", "a"): -0.4, ("p1", "a"): -0.1},
        prevented_actions=[PreventedAction("p2", "a", "fainted_before_acting")],
        flags={"status:tailwind:p1a"},
    )
    text = format_outcome(out, "p1")
    assert "KO" in text
    assert "p2a" in text          # damaged / KO'd opponent
    assert "tailwind" in text.lower()


def test_format_outcome_no_effect():
    assert "no effect" in format_outcome(TurnOutcome(), "p1").lower()
