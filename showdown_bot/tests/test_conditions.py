from showdown_bot.engine.conditions import (
    ConditionInstance,
    ConditionState,
    MonConditions,
    step,
)

A = ("p1", "a")
B = ("p2", "a")


def test_burn_residual_chips_one_sixteenth():
    cs = ConditionState(mons={A: MonConditions(status="brn")})
    hp = {A: 1.0}
    events = step(cs, hp)
    assert abs(hp[A] - (1.0 - 1 / 16)) < 1e-9
    assert any(e.key == A and e.source == "brn" for e in events)


def test_poison_residual_chips_one_eighth():
    cs = ConditionState(mons={A: MonConditions(status="psn")})
    hp = {A: 1.0}
    step(cs, hp)
    assert abs(hp[A] - (1.0 - 1 / 8)) < 1e-9


def test_residual_clamps_at_zero():
    cs = ConditionState(mons={A: MonConditions(status="brn")})
    hp = {A: 0.02}
    step(cs, hp)
    assert hp[A] == 0.0


def test_toxic_escalates_each_turn():
    cs = ConditionState(mons={A: MonConditions(status="tox", status_counter=1)})
    hp = {A: 1.0}
    step(cs, hp)  # stage 1 -> -1/16
    assert abs(hp[A] - (1.0 - 1 / 16)) < 1e-9
    assert cs.mons[A].status_counter == 2
    step(cs, hp)  # stage 2 -> -2/16
    assert abs(hp[A] - (1.0 - 1 / 16 - 2 / 16)) < 1e-9
    assert cs.mons[A].status_counter == 3
