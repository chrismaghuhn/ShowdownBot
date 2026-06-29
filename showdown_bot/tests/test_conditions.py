from showdown_bot.engine.conditions import (
    ConditionInstance,
    ConditionState,
    MonConditions,
    step,
)

A = ("p1", "a")
B = ("p2", "a")


def _cs(**kw):
    return ConditionState(**kw)


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


def test_tailwind_expires_after_4_turns():
    cs = _cs(sides={"p1": {"tailwind": ConditionInstance("tailwind", duration=4)}})
    hp = {A: 1.0}
    for _ in range(3):
        step(cs, hp)
    assert "tailwind" in cs.sides["p1"]  # still active during turn 4
    step(cs, hp)
    assert "tailwind" not in cs.sides["p1"]  # gone after 4th decrement


def test_sandstorm_chips_non_immune():
    cs = _cs(field={"sandstorm": ConditionInstance("sandstorm", duration=5)})
    hp = {A: 1.0, B: 1.0}
    events = step(cs, hp, weather_immune={B})
    assert abs(hp[A] - (1.0 - 1 / 16)) < 1e-9
    assert hp[B] == 1.0  # immune
    assert any(e.source == "sandstorm" for e in events)


def test_grassy_terrain_heals_grounded():
    cs = _cs(field={"grassyterrain": ConditionInstance("grassyterrain", duration=5)})
    hp = {A: 0.5}
    step(cs, hp, grounded={A})
    assert abs(hp[A] - (0.5 + 1 / 16)) < 1e-9


def test_leech_seed_transfers_to_seeder():
    cs = _cs(
        mons={B: MonConditions(volatiles={"leechseed": ConditionInstance("leechseed", params={"seeder": A})})}
    )
    hp = {A: 0.5, B: 1.0}
    events = step(cs, hp)
    assert abs(hp[B] - (1.0 - 1 / 8)) < 1e-9
    assert abs(hp[A] - (0.5 + 1 / 8)) < 1e-9
    assert any(e.source == "leechseed" for e in events)
