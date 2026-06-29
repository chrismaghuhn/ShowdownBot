from showdown_bot.engine.conditions import (
    ConditionInstance,
    ConditionState,
    MonConditions,
    action_act_probability,
    atk_multiplier,
    screen_modifier,
    speed_multiplier,
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


def test_speed_multiplier_tailwind_and_paralysis():
    tw = _cs(sides={"p1": {"tailwind": ConditionInstance("tailwind", 4)}})
    assert speed_multiplier(tw, A) == 2.0
    par = _cs(mons={A: MonConditions(status="par")})
    assert speed_multiplier(par, A) == 0.5
    assert speed_multiplier(_cs(), A) == 1.0


def test_atk_multiplier_burn():
    burned = _cs(mons={A: MonConditions(status="brn")})
    assert atk_multiplier(burned, A) == 0.5
    assert atk_multiplier(_cs(), A) == 1.0


def test_action_act_probability():
    assert action_act_probability(_cs(mons={A: MonConditions(status="par")}), A) == 0.75
    assert action_act_probability(_cs(mons={A: MonConditions(status="slp")}), A) == 0.0
    conf = _cs(mons={A: MonConditions(volatiles={"confusion": ConditionInstance("confusion", 2)})})
    assert abs(action_act_probability(conf, A) - 2 / 3) < 1e-9
    assert action_act_probability(_cs(), A) == 1.0


def _two_burned_sandstorm():
    return _cs(
        mons={A: MonConditions(status="brn"), B: MonConditions(status="brn")},
        field={"sandstorm": ConditionInstance("sandstorm", duration=5)},
    )


def test_step_is_deterministic():
    """No RNG: identical input -> identical events and hp (rollout requirement)."""
    cs1, cs2 = _two_burned_sandstorm(), _two_burned_sandstorm()
    hp1, hp2 = {A: 1.0, B: 1.0}, {A: 1.0, B: 1.0}
    ev1 = [(e.key, e.source, round(e.delta, 9)) for e in step(cs1, hp1)]
    ev2 = [(e.key, e.source, round(e.delta, 9)) for e in step(cs2, hp2)]
    assert ev1 == ev2
    assert hp1 == hp2


def test_screen_modifier_doubles():
    refl = _cs(sides={"p2": {"reflect": ConditionInstance("reflect", 5)}})
    assert abs(screen_modifier(refl, "p2", "physical") - 2 / 3) < 1e-9
    assert screen_modifier(refl, "p2", "special") == 1.0  # reflect = physical only
    ls = _cs(sides={"p2": {"lightscreen": ConditionInstance("lightscreen", 5)}})
    assert abs(screen_modifier(ls, "p2", "special") - 2 / 3) < 1e-9
    veil = _cs(sides={"p2": {"auroraveil": ConditionInstance("auroraveil", 5)}})
    assert abs(screen_modifier(veil, "p2", "physical") - 2 / 3) < 1e-9
    assert abs(screen_modifier(veil, "p2", "special") - 2 / 3) < 1e-9
    assert screen_modifier(_cs(), "p2", "physical") == 1.0
    # singles halves instead of two-thirds
    assert screen_modifier(refl, "p2", "physical", game_type="singles") == 0.5


def test_step_order_field_before_status():
    """Spec §7.3: weather (field) residual is applied before status residual."""
    cs = _cs(
        mons={A: MonConditions(status="brn")},
        field={"sandstorm": ConditionInstance("sandstorm", duration=5)},
    )
    events = step(cs, {A: 1.0})
    sources = [e.source for e in events if e.key == A]
    assert sources.index("sandstorm") < sources.index("brn")
