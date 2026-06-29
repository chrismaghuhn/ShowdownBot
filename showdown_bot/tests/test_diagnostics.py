from showdown_bot.battle.diagnostics import (
    format_battle_events,
    format_decision,
    format_outcome,
    format_rollout_trace,
    turn_report,
)
from showdown_bot.battle.resolve import PreventedAction, TurnOutcome
from showdown_bot.battle.rollout import RolloutResult, TurnTrace
from showdown_bot.engine.log_parser import parse_log


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


def test_format_battle_events_readable():
    log = "\n".join(
        [
            "|turn|1",
            "|move|p1a: Incineroar|Fake Out|p2a: Flutter Mane",
            "|-damage|p2a: Flutter Mane|70/100",
            "|-status|p1a: Incineroar|brn|[from] item: Flame Orb",
            "|faint|p2a: Flutter Mane",
        ]
    )
    text = format_battle_events(parse_log(log))
    assert "Turn 1" in text
    assert "Fake Out" in text
    assert "Flutter Mane" in text
    assert "70/100" in text
    assert "brn" in text
    assert "fainted" in text


def test_format_decision_shows_choice_mode_alternatives():
    text = format_decision(
        chosen="(Fake Out->p2a, Protect)",
        scored=[
            ("(Fake Out->p2a, Protect)", 8.5),
            ("(Moonblast->p2a, Protect)", 7.2),
            ("(Moonblast->p2a, Tailwind)", 6.9),
        ],
        mode="neutral",
    )
    assert "neutral" in text
    assert "Fake Out->p2a" in text
    assert "+8.5" in text
    assert "Moonblast" in text  # an alternative is listed


def test_turn_report_combines_sections():
    rep = turn_report(
        battle_text="Turn 3\n  Incineroar used Fake Out",
        decision_text="decision [mode=neutral]: chose X +8.50",
        rollout_text="rollout (2 turns) value +0.31",
    )
    assert "Fake Out" in rep
    assert "decision" in rep
    assert "rollout" in rep
    # sections are labeled
    assert "battle" in rep.lower()
